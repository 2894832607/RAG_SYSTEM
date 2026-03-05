"""
agent/graph.py  诗境 Agent 主图

架构（三层）：

    START
      
  [planner_node]            意图分类 (GLM JSON输出)
      
  [route_by_intent]
     CHAT           [chat_node]             END
     POETRY_QA      [poetry_qa_node]        END
     POETRY_SEARCH  [poetry_qa_node]        END
     VISUALIZE      [visualize_chain_node]  END
     CLARIFY        [clarify_node]          END

viz_chain 内部：retrieve  enhance  generate  回复
记忆：LangGraph MemorySaver 按 thread_id（session_id）隔离。
"""
from __future__ import annotations

import json
import re
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

from app.agent.llm import get_llm
from app.agent.prompt_loader import load_prompt
from app.agent.state import AgentState
from app.agent.tools import enhance_prompt, generate_image, search_poetry

INTENT_LABELS = ("CHAT", "POETRY_QA", "POETRY_SEARCH", "VISUALIZE", "CLARIFY")


def _last_human_message(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return ""


def _history_summary(state: AgentState, n: int = 3) -> str:
    messages = state["messages"][-(n * 2):]
    lines = []
    for msg in messages:
        role = "用户" if isinstance(msg, HumanMessage) else "AI"
        lines.append(f"{role}: {str(msg.content)[:80]}")
    return "\n".join(lines) if lines else "无"


def _parse_intent(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*?\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {"intent": "CHAT", "confidence": 0.5, "subject": "", "reason": "parse_failed"}


#  节点 

def planner_node(state: AgentState) -> dict:
    """Planner：GLM 分类意图，写入 state['intent'] 和 state['subject']。"""
    llm = get_llm()
    if llm is None:
        return {"intent": "CHAT", "subject": "", "plan": {}}

    prompt_text = load_prompt(
        "planner/intent_router",
        user_message=_last_human_message(state),
        history=_history_summary(state),
    )
    response = llm.invoke([SystemMessage(content=prompt_text)])
    parsed = _parse_intent(str(response.content))

    intent = parsed.get("intent", "CHAT").upper()
    if intent not in INTENT_LABELS:
        intent = "CHAT"

    return {"intent": intent, "subject": parsed.get("subject", ""), "plan": parsed}


def chat_node(state: AgentState) -> dict:
    """通用对话：main_agent + general 提示直接调 LLM。"""
    llm = get_llm()
    if llm is None:
        return {"messages": [AIMessage(content="抱歉，AI 服务暂时不可用。")]}

    system_prompt = (
        load_prompt("system/main_agent") + "\n\n---\n\n" + load_prompt("chat/general")
    )
    response = llm.invoke([SystemMessage(content=system_prompt)] + list(state["messages"]))
    return {"messages": [response]}


def poetry_qa_node(state: AgentState) -> dict:
    """诗词问答：ReAct + search_poetry 工具 + poetry_qa 提示。"""
    llm = get_llm()
    if llm is None:
        return {"messages": [AIMessage(content="抱歉，AI 服务暂时不可用。")]}

    system_prompt = (
        load_prompt("system/main_agent") + "\n\n---\n\n" + load_prompt("chat/poetry_qa")
    )
    react = create_react_agent(model=llm, tools=[search_poetry], prompt=system_prompt)
    result = react.invoke({"messages": state["messages"]})
    new_ai = [m for m in result["messages"] if isinstance(m, AIMessage)]
    return {"messages": new_ai[-1:]} if new_ai else {}


def visualize_chain_node(state: AgentState) -> dict:
    """可视化链路：retrieve  enhance  generate  回复。"""
    from app.modules.generation import DiffusionClient
    from app.modules.prompt import PromptEnhancer
    from app.modules.retriever import Retriever

    subject = state.get("subject", "") or _last_human_message(state)
    try:
        knowledge = Retriever().fetch(subject)
        retrieved_text = knowledge[0] if knowledge else subject
        enhanced_prompt = PromptEnhancer().enrich(subject, knowledge)
        image_url = DiffusionClient().generate(enhanced_prompt)
        reply = (
            f" 意境插画已生成！\n\n"
            f"**意境参考：**\n{retrieved_text[:200]}\n\n"
            f"**提示词：**\n`{enhanced_prompt[:150]}`\n\n"
            f"图像：`{image_url}`"
        )
    except Exception as exc:
        reply = f"生成遇到问题：{exc}\n\n请重新描述您想要的意境，我再试一次。"

    return {"messages": [AIMessage(content=reply)]}


def clarify_node(state: AgentState) -> dict:
    """意图不明：引导用户明确需求。"""
    reply = (
        "您好！我是「诗境」，请问您希望我做什么？\n\n"
        "我可以：\n"
        " 解释或赏析一首古诗词\n"
        " 帮您找到描写某种意境的诗词\n"
        " 将诗句转化为一幅意境插画\n\n"
        "请告诉我您的想法 "
    )
    return {"messages": [AIMessage(content=reply)]}


def route_by_intent(state: AgentState) -> Literal[
    "chat_node", "poetry_qa_node", "visualize_chain_node", "clarify_node"
]:
    intent = state.get("intent", "CHAT")
    if intent in ("POETRY_QA", "POETRY_SEARCH"):
        return "poetry_qa_node"
    if intent == "VISUALIZE":
        return "visualize_chain_node"
    if intent == "CLARIFY":
        return "clarify_node"
    return "chat_node"


#  构建图 

_memory = MemorySaver()


def build_agent():
    """构建并返回带记忆的诗境 Agent 图。"""
    if get_llm() is None:
        return None

    builder = StateGraph(AgentState)
    builder.add_node("planner_node", planner_node)
    builder.add_node("chat_node", chat_node)
    builder.add_node("poetry_qa_node", poetry_qa_node)
    builder.add_node("visualize_chain_node", visualize_chain_node)
    builder.add_node("clarify_node", clarify_node)

    builder.add_edge(START, "planner_node")
    builder.add_conditional_edges(
        "planner_node",
        route_by_intent,
        {
            "chat_node": "chat_node",
            "poetry_qa_node": "poetry_qa_node",
            "visualize_chain_node": "visualize_chain_node",
            "clarify_node": "clarify_node",
        },
    )
    for node in ("chat_node", "poetry_qa_node", "visualize_chain_node", "clarify_node"):
        builder.add_edge(node, END)

    return builder.compile(checkpointer=_memory)


def get_thread_config(session_id: str) -> dict:
    """生成 LangGraph 线程配置，按 session 隔离记忆。"""
    return {"configurable": {"thread_id": session_id}}
