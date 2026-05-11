import asyncio
import json
import logging
from typing import AsyncGenerator

import httpx

from app.config.model_config import get_llm_config

logger = logging.getLogger(__name__)


class GlmClient:
    """
    文本 LLM 客户端（raw httpx，OpenAI Chat Completions 兼容）。

    提供商、端点、模型名、API Key 均从 model_config 读取，
    支持 GLM / 豆包 / Ollama 等任意 OpenAI 兼容服务。

    Spec: specs/001-model-api-config/spec.md §3.3
    """

    def __init__(self) -> None:
        cfg = get_llm_config()
        self.provider = cfg.provider
        self.api_key  = cfg.api_key
        self.base_url = cfg.base_url
        self.model    = cfg.model
        self.timeout  = cfg.timeout

    def is_enabled(self) -> bool:
        return bool(self.api_key) or self.provider == "ollama"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key or 'ollama'}",
            "Content-Type": "application/json",
        }

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

        headers = self._headers()

        with httpx.Client(timeout=None, trust_env=False) as client:
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
        cancel_token: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        """异步流式生成思考内容，兼容多家 OpenAI 兼容实现的推理字段。
        
        Args:
            user_prompt: 用户提示词
            system_prompt: 系统提示词
            cancel_token: 可选的取消信号，当 event 被设置时会中断生成
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
        headers = self._headers()

        async with httpx.AsyncClient(timeout=None, trust_env=False) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for raw_line in response.aiter_lines():
                    # 检查是否被取消
                    if cancel_token is not None and cancel_token.is_set():
                        logger.info("[GlmClient] 请求被用户取消")
                        break
                    
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
                    chunk = self._extract_reasoning_from_delta(delta)
                    if chunk:
                        yield chunk

    def _extract_reasoning_from_delta(self, delta: dict) -> str:
        """
        提取推理文本，兼容 GLM / 豆包等常见字段格式：
        - delta.reasoning_content
        - delta.reasoning / delta.thinking / delta.thinking_content
        - camelCase: reasoningContent / thinkingContent
        - delta.content 为 list[dict] 且 type 为 reasoning/thinking 的片段
        """
        if not isinstance(delta, dict):
            return ""

        direct_keys = (
            "reasoning_content",
            "reasoning",
            "thinking",
            "thinking_content",
            "reasoningContent",
            "thinkingContent",
        )
        for key in direct_keys:
            value = delta.get(key)
            if isinstance(value, str) and value:
                return value

        content = delta.get("content")
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                item_type = (item.get("type") or "").lower()
                if item_type in {"reasoning", "thinking"}:
                    text = item.get("text") or item.get("content") or ""
                    if isinstance(text, str) and text:
                        parts.append(text)
            if parts:
                return "".join(parts)

        return ""
