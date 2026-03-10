"""
LLM 封装（通过 langchain-openai 兼容层接入）

支持任意 OpenAI Chat Completions 兼容的提供商（GLM、豆包、OpenAI、Ollama 等），
通过 app/config/model_config.py 统一读取环境变量配置，无需修改本文件即可切换模型。

Spec: specs/001-model-api-config/spec.md §3.2
"""
import os
from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config.model_config import get_llm_config


def get_llm(temperature: float | None = None) -> ChatOpenAI:
    """
    返回 LLM 实例（ChatOpenAI 兼容层）。

    提供商、端点、模型名、API Key 均从环境变量读取（见 model_config.py）。
    temperature 参数若传入则覆盖配置中的默认值。

    返回 None 当 API Key 未配置且非 Ollama 本地模式。
    """
    cfg = get_llm_config()

    if not cfg.api_key and cfg.provider != "ollama":
        # 未配置 API Key 时返回 None，各节点自行降级处理
        return None  # type: ignore

    effective_temp = temperature if temperature is not None else cfg.temperature

    return ChatOpenAI(
        model=cfg.model,
        api_key=cfg.api_key or "ollama",   # Ollama 要求非空字符串
        base_url=cfg.base_url,
        temperature=effective_temp,
        streaming=True,       # 全局开启流式，SSE 端点需要
        timeout=cfg.timeout,
        max_retries=2,
    )
