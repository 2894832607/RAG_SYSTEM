"""
视频分镜生成模块（超级提示词文生视频模式）

Spec: specs/features/unified-agent/plan.md §3

LLM 根据诗词 RAG 结果生成一个覆盖场景、人物、分镜、动作、画风、转场的超级提示词，
直接送入 Seedance/Vidu/Zhipu 进行文生视频，无需先生图。

包含：
  - SeedanceClient           — 字节 Seedance 异步任务轮询客户端
  - ViduClient               — 智谱 GLM Vidu2 异步任务轮询客户端
  - ZhipuVideoClientWrapper  — 智谱 CogVideoX SDK 包装器
  - VideoStoryboardGenerator — 编排器（超级提示词 → 文生视频）
"""
from __future__ import annotations

import json
import logging
import time
from typing import Callable, List, Optional

import requests

from app.agent.prompt_loader import load_prompt
from app.config.model_config import get_video_config
from app.modules.zhipu_client import ZhipuVideoClient

logger = logging.getLogger(__name__)


# ── SeedanceClient ─────────────────────────────────────────────────────────────


class SeedanceClient:
    """
    字节 Seedance 视频生成客户端（异步任务轮询）。

    使用 Doubao ARK 端点：
      POST /contents/generations/tasks  — 创建任务，返回 task_id
      GET  /contents/generations/tasks/{id} — 轮询状态，succeeded 后返回 video_url
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "seedance-1-lite",
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.poll_interval = poll_interval

    @classmethod
    def from_config(cls) -> "SeedanceClient":
        """从环境变量构建客户端（工厂方法）。"""
        cfg = get_video_config()
        return cls(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model=cfg.model,
            timeout=cfg.timeout,
            poll_interval=cfg.poll_interval,
        )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _create_task(self, prompt: str, image_url: Optional[str] = None) -> str:
        """
        创建 Seedance 视频生成任务。

        Args:
            prompt: 视频内容描述
            image_url: 参考图片（通常为最后一帧，引导视频风格延续）

        Returns:
            task_id 字符串
        """
        content: list = [{"type": "text", "text": prompt}]
        if image_url:
            content.append({"type": "image_url", "image_url": {"url": image_url}})

        resp = requests.post(
            f"{self.base_url}/contents/generations/tasks",
            json={"model": self.model, "content": content},
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("id") or data.get("task_id")
        if not task_id:
            raise RuntimeError(f"Seedance 创建任务返回结构异常：{data}")
        logger.info("[Seedance] 任务已创建 task_id=%s", task_id)
        return str(task_id)

    def _poll_until_done(self, task_id: str) -> str:
        """
        轮询任务状态直到完成。

        Returns:
            video_url 字符串

        Raises:
            TimeoutError: 超过 self.timeout 秒仍未完成
            RuntimeError: 任务失败
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        deadline = time.monotonic() + self.timeout

        while time.monotonic() < deadline:
            resp = requests.get(
                f"{self.base_url}/contents/generations/tasks/{task_id}",
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "")

            if status == "succeeded":
                # 兼容三种响应结构：
                # 1. content 是数组：content[0].video.url
                # 2. content 是对象：content.video_url
                # 3. 顶层字段：data.video_url 或 data.url
                content = data.get("content")
                video_url = ""
                
                if isinstance(content, list) and len(content) > 0:
                    # 结构 1: content 是数组
                    first_item = content[0]
                    if isinstance(first_item, dict):
                        video_url = first_item.get("video", {}).get("url", "")
                elif isinstance(content, dict):
                    # 结构 2: content 是对象
                    video_url = content.get("video_url", "")
                
                # 备用：顶层字段
                if not video_url:
                    video_url = data.get("video_url") or data.get("url", "")
                
                if not video_url:
                    raise RuntimeError(f"Seedance 任务成功但未找到 video_url：{data}")
                logger.info("[Seedance] 视频生成成功 task_id=%s url=%s", task_id, video_url[:60])
                return video_url

            if status == "failed":
                err = data.get("error", {})
                msg = err.get("message") if isinstance(err, dict) else str(err)
                raise RuntimeError(f"Seedance 任务失败 task_id={task_id}：{msg}")

            logger.debug("[Seedance] 轮询 task_id=%s status=%s", task_id, status)
            time.sleep(self.poll_interval)

        raise TimeoutError(
            f"Seedance 视频生成超时（{self.timeout}s）task_id={task_id}"
        )

    def generate(self, prompt: str, image_url: Optional[str] = None) -> str:
        """
        完整流程：创建任务 → 轮询 → 返回 video_url。

        Args:
            prompt: 视频描述
            image_url: 参考最后一帧图片 URL（可选，推荐传入以保持风格延续）

        Returns:
            video_url 字符串
        """
        if not self.api_key:
            raise RuntimeError("VIDEO_API_KEY 未配置，无法调用 Seedance 视频生成 API")
        task_id = self._create_task(prompt, image_url)
        return self._poll_until_done(task_id)


# ── ViduClient ─────────────────────────────────────────────────────────────────


class ViduClient:
    """
    智谱 GLM Vidu2 视频生成客户端（异步任务轮询）。

    端点：
      POST /videos/generations          — 创建任务，body 含 image_url 列表（所有参考帧）
      GET  /videos/generations/{id}     — 轮询状态，task_status=succeed 后提取 video_url
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "vidu2-reference",
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.poll_interval = poll_interval

    @classmethod
    def from_config(cls) -> "ViduClient":
        """从环境变量构建客户端（工厂方法）。"""
        cfg = get_video_config()
        return cls(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model=cfg.model,
            timeout=cfg.timeout,
            poll_interval=cfg.poll_interval,
        )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _create_task(self, prompt: str, image_urls: Optional[List[str]] = None) -> str:
        """
        创建 Vidu 视频生成任务。

        Args:
            prompt: 视频内容描述
            image_urls: 参考帧图片 URL 列表（vidu2-reference 支持多帧）

        Returns:
            task_id 字符串
        """
        body: dict = {
            "model": self.model,
            "prompt": prompt,
            "duration": 10,
            "aspect_ratio": "16:9",
            "movement_amplitude": "auto",
        }
        if image_urls:
            body["image_url"] = image_urls

        resp = requests.post(
            f"{self.base_url}/videos/generations",
            json=body,
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            raise RuntimeError(f"Vidu 创建任务返回结构异常：{data}")
        logger.info("[Vidu] 任务已创建 task_id=%s", task_id)
        return str(task_id)

    def _poll_until_done(self, task_id: str) -> str:
        """
        轮询任务状态直到完成。

        Returns:
            video_url 字符串

        Raises:
            TimeoutError: 超过 self.timeout 秒仍未完成
            RuntimeError: 任务失败
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        deadline = time.monotonic() + self.timeout

        while time.monotonic() < deadline:
            resp = requests.get(
                f"{self.base_url}/videos/generations/{task_id}",
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("task_status", "")

            if status == "succeed":
                # 尝试多种响应结构
                task_result = data.get("task_result") or {}
                videos = task_result.get("videos") or []
                if videos and videos[0].get("url"):
                    video_url = videos[0]["url"]
                else:
                    video_url = data.get("video_url") or data.get("url", "")
                if not video_url:
                    raise RuntimeError(f"Vidu 任务成功但未找到 video_url：{data}")
                logger.info("[Vidu] 视频生成成功 task_id=%s url=%s", task_id, video_url[:60])
                return video_url

            if status == "failed":
                err = data.get("error", {})
                msg = err.get("message") if isinstance(err, dict) else str(err)
                raise RuntimeError(f"Vidu 任务失败 task_id={task_id}：{msg}")

            logger.debug("[Vidu] 轮询 task_id=%s status=%s", task_id, status)
            time.sleep(self.poll_interval)

        raise TimeoutError(
            f"Vidu 视频生成超时（{self.timeout}s）task_id={task_id}"
        )

    def generate(self, prompt: str, image_urls: Optional[List[str]] = None) -> str:
        """
        完整流程：创建任务 → 轮询 → 返回 video_url。

        Args:
            prompt: 视频描述
            image_urls: 所有参考帧 URL 列表（vidu2-reference 利用多帧保持画面一致性）

        Returns:
            video_url 字符串
        """
        if not self.api_key:
            raise RuntimeError("VIDEO_API_KEY 未配置，无法调用 Vidu 视频生成 API")
        task_id = self._create_task(prompt, image_urls)
        return self._poll_until_done(task_id)


class ZhipuVideoClientWrapper:
    """
    智谱 CogVideoX SDK 包装器（使用 zai-sdk）。
    
    包装 ZhipuVideoClient 以适配 VideoStoryboardGenerator 的接口。
    """
    
    def __init__(self) -> None:
        self.client = ZhipuVideoClient()
    
    def generate(self, prompt: str, image_urls: Optional[List[str]] = None) -> str:
        """
        生成视频。
        
        Args:
            prompt: 视频描述
            image_urls: 参考图像 URL 列表（智谱暂不支持）
        
        Returns:
            本地视频路径字符串
        """
        return self.client.generate(
            prompt=prompt,
            quality="quality",
            with_audio=True,
            size="1920x1080",
            fps=30,
        )


class VideoStoryboardGenerator:
    """
    文生视频编排器（超级提示词模式）。

    生成流程：
    1. generate_super_prompt() — LLM 生成包含场景、人物、分镜、动作、画风、转场的超级提示词
    2. generate()              — 超级提示词 → Seedance/Vidu 文生视频 → 返回 video_url

    不再生成中间图像帧，降低 API 费用，缩短等待时间。
    """

    def __init__(
        self,
        llm_client,
        video_client,   # SeedanceClient | ViduClient | None
    ) -> None:
        self._llm = llm_client
        self._vid = video_client

    @classmethod
    def from_defaults(cls) -> "VideoStoryboardGenerator":
        """
        从默认配置创建实例（工厂方法，从环境变量读取所有参数）。

        根据 VIDEO_PROVIDER 选择视频客户端：
          - "vidu"     → ViduClient（GLM Vidu2）
          - "zhipu"    → ZhipuVideoClientWrapper（智谱 CogVideoX SDK）
          - "disabled" → None（跳过视频生成）
          - 其他       → SeedanceClient（默认）
        """
        from app.modules.glm_client import GlmClient
        vcfg = get_video_config()
        if vcfg.provider == "vidu":
            video_client = ViduClient.from_config()
        elif vcfg.provider == "zhipu":
            video_client = ZhipuVideoClientWrapper()
        elif vcfg.provider == "disabled":
            video_client = None
        else:
            video_client = SeedanceClient.from_config()
        return cls(
            llm_client=GlmClient(),
            video_client=video_client,
        )

    def generate_super_prompt(self, poem_info: dict) -> tuple:
        """
        调用 LLM 生成文生视频超级提示词。

        Args:
            poem_info: 包含 title、content、author、translation 的字典

        Returns:
            (video_prompt: str, style_tag: str, shots: list)
        """
        title = poem_info.get("title", "未知")
        content = poem_info.get("content", "")
        author = poem_info.get("author", "")
        translation = poem_info.get("translation") or content

        prompt = load_prompt(
            "chains/visualize/04_video_super_prompt",
            title=title,
            content=content,
            author=author,
            translation=translation,
        )
        raw = self._llm.complete(prompt, system_prompt="你是严格的 JSON 输出器，只输出 JSON。")

        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(raw[start:end])
                return (
                    data.get("video_prompt", ""),
                    data.get("style_tag", "历史纪录片风"),
                    data.get("shots", []),
                )
            except json.JSONDecodeError:
                logger.warning("[VideoGen] 超级提示词 JSON 解析失败，使用兜底提示词")

        fallback = (
            f"A cinematic short video of the ancient Chinese poem '{title}' by {author}. "
            f"Presented as a historical documentary with natural light, restrained camera movement, "
            f"weathered materials, low-saturation cinematic color, and visually grounded details from the poem's translation."
        )
        return fallback, "历史纪录片风", []

    def generate(
        self,
        poem_info: dict,
        callback: Callable[[dict], None],
    ) -> str:
        """
        完整生成流程：超级提示词 → 文生视频 → video_url。

        Args:
            poem_info: 包含 title、content、author、translation 的字典
            callback: SSE 事件推送回调

        Returns:
            video_url 字符串
        """
        # 阶段 1：LLM 生成超级提示词与分镜设计描述
        video_prompt, style_tag, shots = self.generate_super_prompt(poem_info)
        callback({
            "type": "plan",
            "poem_title": poem_info.get("title", ""),
            "style_tag": style_tag,
            "video_prompt": video_prompt,
            "total_shots": len(shots),
            "shots": shots,
        })

        # 阶段 2：文生视频（纯文本 prompt，不传图像）
        if self._vid is None:
            logger.info("[VideoGen] 视频生成已禁用（VIDEO_PROVIDER=disabled）")
            callback({"type": "video_done", "video_url": ""})
            return ""

        video_url = self._vid.generate(video_prompt)
        callback({"type": "video_done", "video_url": video_url})
        return video_url
