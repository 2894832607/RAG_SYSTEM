"""
诗词分镜生成器

流程：
  1. RAG 召回 → 白话译文知识块
  2. 一次 GLM 调用（03_storyboard.md）→ 完整分镜方案 JSON（含每张图提示词）
  3. 逐张调用 CogView-4，顺序生成，每张完成立即推送 SSE 事件
  4. 429 限速自动等待重试，两张图之间有间隔防限速

Spec: specs/features/poetry-visualization.spec.md
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import AsyncGenerator, List, Optional

from app.agent.prompt_loader import load_prompt
from app.modules.generation import CogViewClient
from app.modules.glm_client import GlmClient

logger = logging.getLogger(__name__)

# ── 限速 / 重试参数 ───────────────────────────────────────────────
_MAX_RETRIES = 3          # 每张图最大重试次数
_RETRY_DELAY_429 = 5.0    # 遇到 429 限速时等待秒数（上限 5 秒）
_RETRY_DELAY_ERR = 3.0    # 其他错误重试等待（上限 5 秒）
_BETWEEN_SHOTS_DELAY = 4.0  # 两张图之间的间隔（避免 429）

# ── 数据结构 ──────────────────────────────────────────────────────

@dataclass
class Shot:
    """单个分镜的完整描述，包含预生成好的图像提示词。"""
    shot_id: int
    shot_name: str
    shot_type: str          # establishing | medium | close_up | atmospheric
    poem_lines: List[str]
    translation_excerpt: str
    camera_angle: str
    emotion: str
    positive_prompt: str
    negative_prompt: str


@dataclass
class StoryboardPlan:
    """整部诗的分镜方案：全局风格 + 有序分镜列表。"""
    poem_title: str
    author: str
    dynasty: str
    global_style: str       # 所有分镜共享的画风描述
    shots: List[Shot] = field(default_factory=list)


# ── 主类 ────────────────────────────────────────────────────────

class StoryboardGenerator:
    """
    诗词分镜生成器。

    用法（async generator）：
        async for event in generator.generate(poem, knowledge_blocks):
            # event 是 dict，type 字段区分事件类型
            send_sse(event)
    """

    def __init__(self) -> None:
        self.glm = GlmClient()
        self.cogview = CogViewClient()

    def is_enabled(self) -> bool:
        return self.glm.is_enabled()

    def plan(self, poem: str, knowledge_blocks: List[str]) -> StoryboardPlan:
        """
        调用 GLM，一次性生成完整分镜方案（含每张图的 CogView-4 提示词）。
        """
        knowledge_text = "\n\n".join(knowledge_blocks).strip() or poem
        user_prompt = load_prompt(
            "chains/visualize/03_storyboard",
            poem=poem,
            knowledge=knowledge_text,
        )
        raw = self.glm.complete(user_prompt).strip()
        logger.debug("GLM 分镜规划原始输出（前 500 字）：%s", raw[:500])
        return _parse_plan(raw)

    async def generate(
        self,
        poem: str,
        knowledge_blocks: List[str],
    ) -> AsyncGenerator[dict, None]:
        """
        主入口：规划 → 逐张生成 → 推送进度事件。

        SSE 事件 type 字段说明：
          progress  — 进度消息（stage: planning / generating / retry）
          plan      — 分镜方案确定
          shot_done — 单张图生成完成
          shot_error — 单张图最终失败（继续下一张）
          done      — 全部完成
        """
        # ── Step 1：规划分镜 ──────────────────────────────────────
        yield _ev("progress", stage="planning",
                   message="正在分析诗词结构，规划分镜方案……", current=0, total=0)

        try:
            plan = await asyncio.get_event_loop().run_in_executor(
                None, self.plan, poem, knowledge_blocks
            )
        except Exception as exc:
            logger.exception("分镜规划失败")
            yield _ev("shot_error", shot_id=None,
                       message=f"分镜规划失败：{exc}")
            yield _ev("done", total_shots=0)
            return

        total = len(plan.shots)
        # 推送计划（前端可据此渲染占位框，让用户看到将要生成几张）
        yield {
            "type": "plan",
            "poem_title": plan.poem_title,
            "author": plan.author,
            "dynasty": plan.dynasty,
            "global_style": plan.global_style,
            "total_shots": total,
            "shots": [
                {
                    "shot_id": s.shot_id,
                    "shot_name": s.shot_name,
                    "shot_type": s.shot_type,
                    "poem_lines": s.poem_lines,
                    "camera_angle": s.camera_angle,
                    "emotion": s.emotion,
                }
                for s in plan.shots
            ],
        }

        # ── Step 2：逐张生成图像 ──────────────────────────────────
        for idx, shot in enumerate(plan.shots):
            current = idx + 1

            yield _ev("progress",
                       stage="generating",
                       shot_id=shot.shot_id,
                       shot_name=shot.shot_name,
                       message=f"正在生成第 {current}/{total} 张「{shot.shot_name}」……",
                       current=current,
                       total=total)

            # ── 带重试的内联生成（可 yield 重试事件）────────────
            image_url: Optional[str] = None
            last_error: Optional[str] = None

            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    image_url = await asyncio.get_event_loop().run_in_executor(
                        None, self.cogview.generate,
                        shot.positive_prompt, shot.negative_prompt,
                    )
                    break  # 成功，跳出重试循环
                except Exception as exc:
                    last_error = str(exc)
                    is_429 = _is_rate_limit(last_error)
                    wait = _RETRY_DELAY_429 if is_429 else _RETRY_DELAY_ERR

                    if attempt < _MAX_RETRIES:
                        reason = "API 限速（429）" if is_429 else "请求失败"
                        retry_msg = (
                            f"「{shot.shot_name}」{reason}，"
                            f"第 {attempt}/{_MAX_RETRIES - 1} 次重试，"
                            f"等待 {wait:.0f} 秒……"
                        )
                        logger.warning("%s 原因：%s", retry_msg, last_error)
                        yield _ev("progress",
                                   stage="retry",
                                   shot_id=shot.shot_id,
                                   shot_name=shot.shot_name,
                                   message=retry_msg,
                                   attempt=attempt,
                                   wait=wait,
                                   current=current,
                                   total=total)
                        await asyncio.sleep(wait)
                    else:
                        logger.error("「%s」生成最终失败：%s", shot.shot_name, last_error)

            if image_url:
                yield {
                    "type": "shot_done",
                    "shot_id": shot.shot_id,
                    "shot_name": shot.shot_name,
                    "shot_type": shot.shot_type,
                    "poem_lines": shot.poem_lines,
                    "translation_excerpt": shot.translation_excerpt,
                    "camera_angle": shot.camera_angle,
                    "emotion": shot.emotion,
                    "positive_prompt": shot.positive_prompt,
                    "image_url": image_url,
                    "current": current,
                    "total": total,
                }
            else:
                yield _ev("shot_error",
                           shot_id=shot.shot_id,
                           shot_name=shot.shot_name,
                           message=last_error or "未知错误",
                           current=current,
                           total=total)

            # 分镜间隔（最后一张不等待）
            if idx < total - 1:
                yield _ev("progress",
                           stage="waiting",
                           message=f"第 {current}/{total} 张完成，等待 {_BETWEEN_SHOTS_DELAY:.0f} 秒后继续……",
                           current=current,
                           total=total)
                await asyncio.sleep(_BETWEEN_SHOTS_DELAY)

        yield _ev("done", total_shots=total)


# ── 内部工具函数 ─────────────────────────────────────────────────

def _ev(type_: str, **kwargs) -> dict:
    """快捷构建事件 dict。"""
    return {"type": type_, **kwargs}


def _is_rate_limit(error_msg: str) -> bool:
    """判断错误是否为 429 限速。"""
    lower = error_msg.lower()
    return "429" in error_msg or "rate limit" in lower or "too many requests" in lower


def _parse_plan(raw: str) -> StoryboardPlan:
    """
    从 GLM 输出中提取 JSON 并解析为 StoryboardPlan。
    支持：纯 JSON / ```json ... ``` 块 / 混有说明文字的输出。
    """
    data = _extract_json(raw)

    shots: List[Shot] = []
    for s in data.get("shots", []):
        shots.append(Shot(
            shot_id=int(s.get("shot_id", len(shots))),
            shot_name=s.get("shot_name", f"分镜{len(shots)}"),
            shot_type=s.get("shot_type", "medium"),
            poem_lines=s.get("poem_lines", []),
            translation_excerpt=s.get("translation_excerpt", ""),
            camera_angle=s.get("camera_angle", ""),
            emotion=s.get("emotion", ""),
            positive_prompt=s.get("positive_prompt", "高质量, 超精细, 中国传统水墨画"),
            negative_prompt=s.get(
                "negative_prompt",
                "低质量, 模糊, 水印, 文字, 现代建筑, 西方油画, 3D渲染, 动漫卡通",
            ),
        ))

    if not shots:
        raise ValueError("分镜规划结果为空：GLM 未返回任何 shots")

    return StoryboardPlan(
        poem_title=data.get("poem_title", ""),
        author=data.get("author", ""),
        dynasty=data.get("dynasty", ""),
        global_style=data.get("global_style", "中国传统水墨画"),
        shots=shots,
    )


def _extract_json(raw: str) -> dict:
    """
    容错地从字符串中提取第一个有效 JSON 对象。
    优先级：直接解析 > 代码块 > 最外层 { }。
    """
    # 1. 直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 2. 提取 ```json ... ``` 或 ``` ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 3. 找最外层 { ... }（贪婪，取从第一个 { 到最后一个 } 的范围）
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"无法从 GLM 输出中解析合法 JSON。\n"
        f"GLM 输出（前 300 字）：{raw[:300]}"
    )
