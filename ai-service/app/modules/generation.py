"""
图像生成客户端

支持多种图像生成提供商，通过 IMAGE_PROVIDER 环境变量配置：
  - cogview (默认): 调用 CogView-4-250304（/images/generations）
  - disabled: 禁用图像生成，返回占位图 URL（适合本地开发）

Spec: specs/001-model-api-config/spec.md §3.4
"""
import os
import uuid
from pathlib import Path

import httpx

from app.config.model_config import get_image_config


# 本地静态输出目录（ai-service/statics/outputs/）
_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "statics" / "outputs"
_PLACEHOLDER_URL = "/statics/outputs/placeholder.svg"


class CogViewClient:
    """图像生成客户端（OpenAI Images API 兼容）。

    配置通过 model_config.get_image_config() 读取：
      IMAGE_PROVIDER  — cogview（默认）/ disabled
      IMAGE_API_KEY   — 图像 API 密钥（缺省继承 LLM_API_KEY）
      IMAGE_BASE_URL  — 图像 API 端点（缺省继承 LLM_BASE_URL）
      IMAGE_MODEL     — 图像模型名称，默认 cogview-4-250304
      COGVIEW_SIZE    — 图像尺寸，默认 1024x1024
      COGVIEW_TIMEOUT — 超时秒数，默认 120
    """

    def __init__(self) -> None:
        cfg = get_image_config()
        self.api_key   = cfg.api_key
        self.base_url  = cfg.base_url
        self.model     = cfg.model
        self.size      = cfg.size
        self.timeout   = cfg.timeout
        self._disabled = cfg.provider == "disabled"

    def is_enabled(self) -> bool:
        return bool(self.api_key) and not self._disabled

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def generate(self, prompt: str, negative_prompt: str = "") -> str:
        """生成图像，返回可访问的 URL（优先本地路径）。

        IMAGE_PROVIDER=disabled 时直接返回占位图 URL，不调用远端 API。

        步骤：
        1. 调用图像 API，拿到 CDN URL
        2. 下载图片到 statics/outputs/{uuid}.png
        3. 返回本地相对路径 /statics/outputs/{uuid}.png
           若下载失败则 fallback 返回 CDN URL
        """
        if self._disabled:
            return _PLACEHOLDER_URL

        if not self.api_key:
            raise RuntimeError("图像 API Key 未配置，请设置 IMAGE_API_KEY 或 LLM_API_KEY 环境变量")

        cdn_url = self._call_api(prompt, negative_prompt)
        try:
            local_url = self._download(cdn_url)
            return local_url
        except Exception:
            # 下载失败时直接返回 CDN URL，前端仍可展示
            return cdn_url

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _call_api(self, prompt: str, negative_prompt: str = "") -> str:
        """调用 /paas/v4/images/generations，返回 data[0].url。"""
        url = f"{self.base_url}/images/generations"
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "size": self.size,
        }
        if negative_prompt.strip():
            payload["negative_prompt"] = negative_prompt
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout, trust_env=False) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        images = data.get("data") or []
        if not images or not images[0].get("url"):
            raise RuntimeError(f"CogView-4 返回结构异常：{data}")
        return images[0]["url"]

    def _download(self, cdn_url: str) -> str:
        """下载图片到本地，返回 /statics/outputs/{uuid}.png。"""
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        image_name = f"{uuid.uuid4()}.png"
        dest = _OUTPUT_DIR / image_name

        with httpx.Client(timeout=60.0, trust_env=False) as client:
            resp = client.get(cdn_url)
            resp.raise_for_status()
            dest.write_bytes(resp.content)

        return f"/statics/outputs/{image_name}"


# 向后兼容旧名称（pipeline.py 仍使用 DiffusionClient）
DiffusionClient = CogViewClient
