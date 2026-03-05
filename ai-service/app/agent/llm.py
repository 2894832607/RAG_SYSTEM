"""
GLM LLM 封装（通过 langchain-openai 兼容层接入）

智谱 AI 的 GLM 系列完全兼容 OpenAI Chat Completions API，
因此可以直接用 ChatOpenAI 指定 base_url 来驱动。
"""
import os
from functools import lru_cache

from langchain_openai import ChatOpenAI


@lru_cache(maxsize=1)
def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """
    返回全局单例 GLM LLM。

    环境变量：
        GLM_API_KEY   - 必须（智谱 AI 开放平台 API Key）
        GLM_BASE_URL  - 可选，默认 https://open.bigmodel.cn/api/paas/v4
        GLM_MODEL     - 可选，默认 glm-4-flash
    """
    api_key = os.getenv("GLM_API_KEY", "").strip()
    base_url = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
    model = os.getenv("GLM_MODEL", "glm-4-flash")

    if not api_key:
        # 未配置 API Key 时返回 None，各节点自行降级处理
        return None  # type: ignore

    timeout = float(os.getenv("GLM_TIMEOUT", "90"))

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        streaming=True,       # 全局开启流式，SSE 端点需要
        timeout=timeout,
        max_retries=2,
    )
