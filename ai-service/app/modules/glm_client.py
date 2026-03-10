import json
import os
from typing import AsyncGenerator

import httpx

from app.config.model_config import get_llm_config


class GlmClient:
    """
    文本 LLM 客户端（raw httpx，OpenAI Chat Completions 兼容）。

    提供商、端点、模型名、API Key 均从 model_config 读取，
    支持 GLM / 豆包 / Ollama 等任意 OpenAI 兼容服务。

    Spec: specs/001-model-api-config/spec.md §3.3
    """

    def __init__(self) -> None:
        cfg = get_llm_config()
        self.api_key  = cfg.api_key
        self.base_url = cfg.base_url
        self.model    = cfg.model
        self.timeout  = cfg.timeout

    def is_enabled(self) -> bool:
        return bool(self.api_key)

    def complete(self, user_prompt: str, system_prompt: str = "你是一个擅长中文诗意场景描述的提示词助手。") -> str:
        if not self.is_enabled():
            raise RuntimeError("模型 API Key 未配置，请设置 LLM_API_KEY 环境变量")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "stream": False,
            "temperature": 0.6,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("模型返回为空")
        message = choices[0].get("message") or {}
        # 部分推理模型正文在 reasoning_content，普通模型在 content
        content = message.get("content") or message.get("reasoning_content") or ""
        if not content:
            raise RuntimeError("模型返回内容为空（content 和 reasoning_content 均为空）")
        return content.strip()

    async def stream_thinking(
        self,
        user_prompt: str,
        system_prompt: str = "你是一个擅长中文诗意场景描述的提示词助手。",
    ) -> AsyncGenerator[str, None]:
        """异步流式生成，每次 yield 一个文本片段。
        对于推理模型，优先 yield reasoning_content delta；
        普通模型 yield content delta。
        """
        if not self.is_enabled():
            raise RuntimeError("模型 API Key 未配置，请设置 LLM_API_KEY 环境变量")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "stream": True,
            "temperature": 0.6,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for raw_line in response.aiter_lines():
                    raw_line = raw_line.strip()
                    if not raw_line or not raw_line.startswith("data:"):
                        continue
                    data_str = raw_line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    # GLM-5 推理片段优先
                    chunk = delta.get("reasoning_content") or delta.get("content") or ""
                    if chunk:
                        yield chunk
