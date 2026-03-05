import json
import os
from typing import AsyncGenerator

import httpx


class GlmClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("GLM_API_KEY", "").strip()
        self.base_url = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        self.model = os.getenv("GLM_MODEL", "glm-5")
        self.timeout = float(os.getenv("GLM_TIMEOUT", "30"))

    def is_enabled(self) -> bool:
        return bool(self.api_key)

    def complete(self, user_prompt: str, system_prompt: str = "你是一个擅长中文诗意场景描述的提示词助手。") -> str:
        if not self.is_enabled():
            raise RuntimeError("GLM_API_KEY 未配置")

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
            raise RuntimeError("GLM 返回为空")
        message = choices[0].get("message") or {}
        # GLM-5 等推理模型正文在 reasoning_content，普通模型在 content
        content = message.get("content") or message.get("reasoning_content") or ""
        if not content:
            raise RuntimeError("GLM 返回内容为空（content 和 reasoning_content 均为空）")
        return content.strip()

    async def stream_thinking(
        self,
        user_prompt: str,
        system_prompt: str = "你是一个擅长中文诗意场景描述的提示词助手。",
    ) -> AsyncGenerator[str, None]:
        """异步流式生成 GLM 思考过程，每次 yield 一个文本片段。
        对于 GLM-5 推理模型，优先 yield reasoning_content delta；
        普通模型 yield content delta。
        """
        if not self.is_enabled():
            raise RuntimeError("GLM_API_KEY 未配置")

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
