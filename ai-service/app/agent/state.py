"""
LangGraph Agent 状态定义

AgentState 继承 MessagesState，额外携带本次工作流中间产物，
供各节点读写、前端 SSE 消费。
"""
from typing import Annotated, Optional
from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Poetry RAG Agent 全局状态."""

    # ── Planner 输出 ────────────────────────────────────────────
    intent: str = "CHAT"
    # 分类值: CHAT | POETRY_QA | POETRY_SEARCH | VISUALIZE | CLARIFY

    subject: str = ""
    # 用户消息的核心主题词（由 Planner 提取）

    plan: dict = {}
    # Planner 返回的完整 JSON 输出

    # ── RAG 检索结果 ────────────────────────────────────────────
    retrieved_poems: Annotated[list[dict], "ChromaDB 召回的诗词列表"] = []

    # ── 提示词增强结果 ──────────────────────────────────────────
    enhanced_prompt: Optional[str] = None

    # ── 图像生成结果 ────────────────────────────────────────────
    image_url: Optional[str] = None

    # ── 当前会话 ID（从 HTTP 请求注入，用于记忆隔离）──────────────
    session_id: str = "default"
