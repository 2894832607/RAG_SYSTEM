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
        try:
            return _parse_plan(raw)
        except Exception as exc:
            logger.warning("GLM 分镜 JSON 解析失败，切换到本地降级分镜方案: %s", exc)
            return _build_fallback_plan(poem, knowledge_blocks)

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
    cleaned = raw.strip()

    # Qwen / 推理模型可能先输出 <think>...</think>，先剥离再解析。
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE).strip()

    # 1. 直接解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 2. 提取 ```json ... ``` 或 ``` ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 3. 找最外层 { ... }（贪婪，取从第一个 { 到最后一个 } 的范围）
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"无法从 GLM 输出中解析合法 JSON。\n"
        f"GLM 输出（前 300 字）：{cleaned[:300]}"
    )


def _build_fallback_plan(poem: str, knowledge_blocks: List[str]) -> StoryboardPlan:
    """当本地模型无法稳定输出 JSON 时，生成一个可用的基础分镜方案。"""
    title = ""
    author = ""
    dynasty = ""

    if knowledge_blocks:
        first = knowledge_blocks[0].splitlines()[0] if knowledge_blocks[0] else ""
        m = re.match(r"【(.+?)·(.+?)·《(.+?)》】", first)
        if m:
            dynasty, author, title = m.groups()

    poem_lines = [seg.strip() for seg in re.split(r"[，。！？；\n]", poem) if seg.strip()]
    if not poem_lines:
        poem_lines = [poem.strip() or "诗意场景"]

    line_a = poem_lines[0]
    line_b = poem_lines[1] if len(poem_lines) > 1 else poem_lines[0]
    line_c = poem_lines[2] if len(poem_lines) > 2 else line_b
    line_d = poem_lines[-1]

    global_style = "中国传统青绿山水与水墨融合风格，电影级构图，光影克制，古典东方意境"

    shots = [
        Shot(
            shot_id=1,
            shot_name="整体意境",
            shot_type="establishing",
            poem_lines=[line_a, line_b],
            translation_excerpt="以全景建立山水环境、时间气息与整体氛围。",
            camera_angle="wide aerial",
            emotion="幽静开阔",
            positive_prompt=f"{global_style}，全景远眺，{line_a}，{line_b}，群山、松林、清泉、薄雾、秋意，层次分明，电影感构图",
            negative_prompt="低质量, 模糊, 水印, 文字, 现代建筑, 西方油画, 3D渲染, 动漫卡通",
        ),
        Shot(
            shot_id=2,
            shot_name="主体画面",
            shot_type="medium",
            poem_lines=[line_b],
            translation_excerpt="聚焦诗中核心景物，让观者进入主要场景。",
            camera_angle="eye level",
            emotion="清润宁静",
            positive_prompt=f"{global_style}，中景，重点表现{line_b}，松间月色与石上清泉相互映照，雨后空气清冽，细节真实",
            negative_prompt="低质量, 模糊, 水印, 文字, 现代建筑, 西方油画, 3D渲染, 动漫卡通",
        ),
        Shot(
            shot_id=3,
            shot_name="细节特写",
            shot_type="close_up",
            poem_lines=[line_c],
            translation_excerpt="放大诗中细节意象，增强沉浸感。",
            camera_angle="close up",
            emotion="细腻空灵",
            positive_prompt=f"{global_style}，近景特写，突出{line_c}相关细节，月光、水纹、石面、竹影、微风痕迹，质感细腻",
            negative_prompt="低质量, 模糊, 水印, 文字, 现代建筑, 西方油画, 3D渲染, 动漫卡通",
        ),
        Shot(
            shot_id=4,
            shot_name="余韵收束",
            shot_type="atmospheric",
            poem_lines=[line_d],
            translation_excerpt="以氛围镜头收束画面，形成诗意停留感。",
            camera_angle="long shot",
            emotion="悠远留白",
            positive_prompt=f"{global_style}，氛围收束镜头，{line_d}，暮色、留白、远山与水声交织，画面宁静悠长",
            negative_prompt="低质量, 模糊, 水印, 文字, 现代建筑, 西方油画, 3D渲染, 动漫卡通",
        ),
    ]

    return StoryboardPlan(
        poem_title=title,
        author=author,
        dynasty=dynasty,
        global_style=global_style,
        shots=shots,
    )
