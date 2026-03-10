"""
agent/graph.py  诗境 Agent — 纯 ReAct 架构

LangGraph create_react_agent：
  - LLM 自主决定何时对话、何时检索、何时生图
  - 无需意图分类节点，不输出 JSON 格式
  - MemorySaver 按 thread_id（session_id）隔离会话记忆
  - 工具调用：search_poetry / visualize_poem

内部节点名（astream_events 过滤用）：
  "agent" — LLM 推理与输出
  "tools" — 工具执行
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from app.agent.llm import get_llm
from app.agent.prompt_loader import load_prompt
from app.agent.tools import search_poetry, visualize_poem

_memory = MemorySaver()
_agent = None  # 全局单例，首次调用 build_agent() 时初始化


def build_agent():
    """构建（或返回已有的）ReAct Agent。"""
    global _agent
    if _agent is not None:
        return _agent

    llm = get_llm()
    if llm is None:
        return None

    system_prompt = load_prompt("system/main_agent")

    _agent = create_react_agent(
        model=llm,
        tools=[search_poetry, visualize_poem],
        prompt=system_prompt,
        checkpointer=_memory,
    )
    return _agent


def get_thread_config(session_id: str) -> dict:
    """生成 LangGraph 线程配置，按 session 隔离记忆。"""
    return {"configurable": {"thread_id": session_id}}
