"""agent/graph.py  诗境 Agent — 纯 ReAct 架构

LangGraph create_react_agent：
  - LLM 自主决定何时对话、何时检索、何时生图/制作视频
  - 无需意图分类节点，不输出 JSON 格式
  - MemorySaver 按 thread_id（session_id）隔离会话记忆
  - 工具调用：search_poetry / generate_image / generate_video / generate_storyboard
  - Ollama 不支持 tool calling 的模型降级为纯对话模式（无工具）

内部节点名（astream_events 过滤用）：
  "agent" — LLM 推理与输出
  "tools" — 工具执行
"""
from __future__ import annotations

import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from app.agent.llm import get_llm
from app.agent.prompt_loader import load_prompt
from app.agent.tools import search_poetry, generate_image, generate_video, generate_storyboard
from app.config.model_config import get_llm_config

logger = logging.getLogger(__name__)

_memory = MemorySaver()
_agent = None  # 全局单例，首次调用 build_agent() 时初始化


def _ollama_supports_tools() -> bool:
    """向 Ollama /api/show 查询当前模型是否支持 tools。"""
    import httpx
    cfg = get_llm_config()
    # base_url 形如 http://localhost:11434/v1，去掉 /v1
    ollama_base = cfg.base_url.rstrip("/")
    if ollama_base.endswith("/v1"):
        ollama_base = ollama_base[:-3]
    try:
        r = httpx.get(
            f"{ollama_base}/api/show",
            params={"name": cfg.model},
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
        caps = data.get("capabilities") or []
        return "tools" in caps
    except Exception as exc:
        logger.warning("无法查询 Ollama model capabilities: %s", exc)
        return False


def build_agent():
    """构建（或返回已有的）ReAct Agent。"""
    global _agent
    if _agent is not None:
        return _agent

    llm = get_llm()
    if llm is None:
        return None

    system_prompt = load_prompt("system/main_agent")
    cfg = get_llm_config()

    # Ollama 模型：检测是否支持 tool calling
    if cfg.provider == "ollama" and not _ollama_supports_tools():
        logger.warning(
            "Ollama 模型 %s 不支持 tool calling，降级为纯对话模式（无 RAG/生图工具）。"
            "如需工具功能请拉取支持 tools 的模型，例如：ollama pull qwen3:4b",
            cfg.model,
        )
        active_tools = []
    else:
        active_tools = [search_poetry, generate_image, generate_video, generate_storyboard]

    _agent = create_react_agent(
        model=llm,
        tools=active_tools,
        prompt=system_prompt,
        checkpointer=_memory,
    )
    return _agent


def reset_agent() -> None:
    """清空缓存的 ReAct Agent，使其在下次请求时按最新模型配置重建。"""
    global _agent
    _agent = None


def get_thread_config(session_id: str) -> dict:
    """生成 LangGraph 线程配置，按 session 隔离记忆。"""
    return {"configurable": {"thread_id": session_id}}



def reset_agent() -> None:
    """清空缓存的 ReAct Agent，使其在下次请求时按最新模型配置重建。"""
    global _agent
    _agent = None


def get_thread_config(session_id: str) -> dict:
    """生成 LangGraph 线程配置，按 session 隔离记忆。"""
    return {"configurable": {"thread_id": session_id}}
