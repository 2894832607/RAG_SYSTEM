import json
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config.model_config import get_image_config, get_llm_config, validate_and_log
from app.modules.glm_client import GlmClient
from app.modules.pipeline import generate_once, run_generation
from app.schemas.requests import CallbackBody, GenerationRequest, SimpleGenerationRequest, SimpleGenerationResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期事件：启动时打印模型配置摘要。"""
    validate_and_log()
    yield


app = FastAPI(
    title="Poetry RAG AI Service",
    version="0.4.0",
    description="Poetry RAG Agent — LangGraph + 可配置 LLM + ChromaDB.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 静态文件服务：生成图像存储目录 ─────────────────────────────
_STATIC_DIR = Path(__file__).resolve().parents[1] / "statics" / "outputs"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/statics/outputs", StaticFiles(directory=str(_STATIC_DIR)), name="outputs")

_mock_callbacks: dict[str, dict] = {}
_mock_store = Path(__file__).resolve().parents[1] / "tmp" / "mock_callbacks.jsonl"
_mock_store.parent.mkdir(parents=True, exist_ok=True)


def _save_mock_callback(record: dict) -> None:
    with _mock_store.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_mock_callback(task_id: str) -> dict | None:
    if not _mock_store.exists():
        return None
    matched: dict | None = None
    with _mock_store.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if item.get("taskId") == task_id:
                matched = item
    return matched


@app.post("/ai/api/v1/generate/async", status_code=202)
async def queue_generation(request: GenerationRequest, background_tasks: BackgroundTasks):
    """Launches the RAG pipeline as a background job matching the async contract."""
    background_tasks.add_task(run_generation, request)
    return {"message": "Task accepted", "taskId": request.taskId}


@app.post("/ai/api/v1/generate/simple", response_model=SimpleGenerationResponse)
async def simple_generation(request: SimpleGenerationRequest):
    """Minimal sync endpoint for local smoke testing without callback."""
    return generate_once(request.sourceText)


@app.post("/ai/api/v1/generate/think-stream")
async def think_stream(request: SimpleGenerationRequest):
    """SSE endpoint: streams GLM-5 reasoning_content token by token.
    Each event: data: {"text": "..."}\n\n
    Final event: data: [DONE]\n\n
    """
    glm = GlmClient()

    async def event_generator():
        try:
            async for chunk in glm.stream_thinking(request.sourceText):
                payload = json.dumps({"text": chunk}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except Exception as exc:
            err = json.dumps({"error": str(exc)}, ensure_ascii=False)
            yield f"data: {err}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/ai/health")
async def health():
    """health check — 返回当前配置的模型信息（不含 API Key）。见 HealthResponse schema。"""
    llm = get_llm_config()
    img = get_image_config()
    return {
        "status": "ok",
        "service": "poetry rag ai",
        "models": {
            "llm": {
                "provider": llm.provider,
                "model":    llm.model,
                "base_url": llm.base_url,
                "enabled":  bool(llm.api_key) or llm.provider == "ollama",
            },
            "image": {
                "provider": img.provider,
                "model":    img.model,
                "enabled":  img.provider != "disabled" and bool(img.api_key),
            },
        },
    }


# ══════════════════════════════════════════════════════════════════
#  分镜生成  —  SSE 逐张推送，含进度 & 重试状态
# ══════════════════════════════════════════════════════════════════

@app.post("/ai/api/v1/generate/storyboard")
async def storyboard_stream(request: SimpleGenerationRequest):
    """
    诗词分镜生成 SSE 接口。

    接收一句诗词（或诗题），自动：
    1. RAG 检索完整原诗 + 译文
    2. GLM 规划分镜方案（1 张全景基调 + 3-5 张叙事分镜）
    3. 逐张调用 CogView-4，生成图像后立即推送

    SSE 事件格式（每条 data: {JSON}）：
      {"type": "progress",   "stage": "planning|generating|waiting", "message": "...", "current": N, "total": N}
      {"type": "plan",       "poem_title": "...", "global_style": "...", "total_shots": N, "shots": [...]}
      {"type": "shot_done",  "shot_id": N, "shot_name": "...", "shot_type": "...",
                             "poem_lines": [...], "translation_excerpt": "...",
                             "camera_angle": "...", "emotion": "...",
                             "positive_prompt": "...", "image_url": "...", "current": N, "total": N}
      {"type": "shot_error", "shot_id": N, "shot_name": "...", "message": "...", "current": N, "total": N}
      {"type": "done",       "total_shots": N}
      {"type": "shot_error", "shot_id": null, "message": "..."}  ← 规划阶段失败
    """
    from app.modules.retriever import Retriever
    from app.modules.storyboard import StoryboardGenerator

    generator = StoryboardGenerator()
    if not generator.is_enabled():
        raise HTTPException(status_code=503, detail="GLM_API_KEY 未配置，分镜服务不可用")

    # RAG 检索（同步，但轻量，直接在请求协程执行）
    try:
        retriever = Retriever()
        rag_result = retriever.smart_retrieve(request.sourceText)
        knowledge_blocks = [p.to_knowledge_block() for p in rag_result.poems]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG 检索失败：{exc}")

    async def event_generator():
        # 先推送一条 RAG 结果概况，让用户知道检索到了什么
        if rag_result.poems:
            best = rag_result.poems[0]
            intro = json.dumps({
                "type": "progress",
                "stage": "rag_done",
                "message": (
                    f"已检索到《{best.title}》（{best.dynasty}·{best.author}），"
                    f"开始规划分镜……"
                ),
                "current": 0,
                "total": 0,
            }, ensure_ascii=False)
            yield f"data: {intro}\n\n"

        try:
            async for event in generator.generate(request.sourceText, knowledge_blocks):
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except Exception as exc:
            err = json.dumps({
                "type": "shot_error",
                "shot_id": None,
                "message": f"分镜生成内部错误：{exc}",
            }, ensure_ascii=False)
            yield f"data: {err}\n\n"
            done = json.dumps({"type": "done", "total_shots": 0}, ensure_ascii=False)
            yield f"data: {done}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ══════════════════════════════════════════════════════════════════
#  Agent Chat  —  LangGraph ReAct + GLM + ChromaDB
# ══════════════════════════════════════════════════════════════════

# ── RAG 输出解析 ───────────────────────────────────────────────────────────

def _parse_search_poetry_output(output: str) -> dict | None:
    """
    将 search_poetry 工具返回的格式化文本解析为结构化数据，
    用于向前端推送 rag_result SSE 事件。

    精准模式（单首）格式：
        **《title》 — author（dynasty）**
        **原诗：**
        ...
        **白话译文：**
        ...
        相似度：0.xxx

    语义模式（多首）格式：
        找到 N 首相关诗词：
        **[1]** 《title》 — author（dynasty） 相似度 0.xx
        原诗：...
        译文：...
    """
    if not output:
        return None
    # 失败或超时的文本，不解析
    _bail_keywords = ("检索失败", "检索超时", "未在知识库")
    if any(k in output for k in _bail_keywords):
        return None

    poems: list[dict] = []

    # ── 精准模式（无"找到 N 首"行）──────────────────────────────────────
    if "找到" not in output:
        header_m = re.search(
            r"\*\*《(.+?)》\s*[—–\-]+\s*(.+?)（(.+?)）\*\*",
            output,
        )
        if not header_m:
            return None
        title, author, dynasty = [s.strip() for s in header_m.groups()]

        orig_m = re.search(
            r"\*\*原诗[：:]\*\*\s*\n([\s\S]+?)(?=\n\n\*\*白话译文|\Z)",
            output,
        )
        trans_m = re.search(
            r"\*\*白话译文[：:]\*\*\s*\n([\s\S]+?)(?=\n\n相似度|\Z)",
            output,
        )
        sim_m = re.search(r"相似度[：:]([\d.]+)", output)

        poems.append({
            "index": 1,
            "title": title,
            "author": author,
            "dynasty": dynasty,
            "original": orig_m.group(1).strip()[:300] if orig_m else "",
            "translation": trans_m.group(1).strip()[:300] if trans_m else "",
            "similarity": float(sim_m.group(1)) if sim_m else 0.0,
        })
        return {"mode": "exact", "poems": poems}

    # ── 语义模式（多首候选）──────────────────────────────────────────────
    entry_re = re.compile(
        r"\*\*\[(\d+)\]\*\*\s*《(.+?)》\s*[—–\-]+\s*(.+?)（(.+?)）\s*相似度\s*([\d.]+)([\s\S]+?)(?=\n\n\*\*\[|\n请告诉|\Z)",
        re.MULTILINE,
    )
    for m in entry_re.finditer(output):
        idx, title, author, dynasty, sim, body = m.groups()
        orig_m = re.search(r"原诗[：:]\s*(.+?)(?:\n|$)", body)
        trans_m = re.search(r"译文[：:]\s*(.+?)(?:\n|$)", body)
        poems.append({
            "index": int(idx),
            "title": title.strip(),
            "author": author.strip(),
            "dynasty": dynasty.strip(),
            "original": orig_m.group(1).strip() if orig_m else "",
            "translation": trans_m.group(1).strip().rstrip("……") if trans_m else "",
            "similarity": float(sim),
        })

    return {"mode": "semantic", "poems": poems} if poems else None


# ══════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""      # 留空则自动生成新会话


class SessionResponse(BaseModel):
    session_id: str


@app.post("/ai/api/v1/chat/session", response_model=SessionResponse)
async def create_session() -> SessionResponse:
    """创建新的对话会话，返回 session_id。"""
    return SessionResponse(session_id=str(uuid.uuid4()))


@app.get("/ai/api/v1/chat/session/{session_id}/history")
async def get_history(session_id: str):
    """
    获取指定会话的历史消息列表。
    返回格式：[{"role": "user"|"assistant", "content": "..."}]
    """
    from app.agent.graph import _memory, build_agent, get_thread_config

    agent = build_agent()
    if agent is None:
        raise HTTPException(status_code=503, detail="GLM_API_KEY 未配置，Agent 不可用")

    config = get_thread_config(session_id)
    state = agent.get_state(config)
    if not state or not state.values:
        return []

    messages = state.values.get("messages", [])
    history = []
    for msg in messages:
        role = "user" if msg.__class__.__name__ == "HumanMessage" else "assistant"
        if hasattr(msg, "content") and msg.content:
            history.append({"role": role, "content": msg.content})
    return history


@app.delete("/ai/api/v1/chat/session/{session_id}")
async def clear_session(session_id: str):
    """清空指定会话的历史记忆。"""
    from app.agent.graph import _memory, get_thread_config
    config = get_thread_config(session_id)
    # MemorySaver：直接覆盖写入空状态即可清空
    _memory.storage.pop(session_id, None)
    return {"ok": True, "session_id": session_id}


@app.post("/ai/api/v1/chat")
async def chat_stream(request: ChatRequest):
    """
    SSE 流式对话接口。

    返回 text/event-stream 格式，每个 SSE 事件结构：
        data: {"type": "token",        "content": "..."}            ← LLM 输出 token
        data: {"type": "tool",         "name": "...", "input": "..."}   ← 工具调用开始
        data: {"type": "tool_end",     "name": "...", "output": "..."}  ← 工具返回
        data: {"type": "node_progress","node": "agent|tools",
               "iteration": N, "label": "..."}                      ← 节点进度
        data: {"type": "rag_result",   "mode": "exact|semantic",
               "poems": [...]}                                        ← RAG 检索结果
        data: {"type": "done",         "session_id": "..."}           ← 完成
        data: {"type": "error",        "content": "..."}              ← 错误
    """
    from langchain_core.messages import HumanMessage
    from app.agent.graph import build_agent, get_thread_config

    agent = build_agent()
    if agent is None:
        raise HTTPException(status_code=503, detail="GLM_API_KEY 未配置，Agent 不可用")

    session_id = request.session_id or str(uuid.uuid4())
    config = get_thread_config(session_id)

    # 只允许这些节点的 LLM token 流式输出给用户
    _STREAMING_NODES = {"agent"}

    async def event_generator():
        tokens_emitted = False  # 标记是否已有 token 推送给用户
        agent_iteration = 0     # 记录 Agent 节点 LLM 调用次数（规划/回复）
        try:
            async for event in agent.astream_events(
                {"messages": [HumanMessage(content=request.message)]},
                config=config,
                version="v2",
            ):
                kind = event["event"]
                # 当前事件所在的节点名（planner_node 产生的 token 不对用户可见）
                node_name = event.get("metadata", {}).get("langgraph_node", "")

                # ── LLM 开始推理（节点进度）────────────────────────
                if kind == "on_chat_model_start" and node_name in _STREAMING_NODES:
                    agent_iteration += 1
                    if agent_iteration == 1:
                        label = "第 1 步：LLM 分析问题，规划是否需要检索或生图"
                    else:
                        label = f"第 {agent_iteration} 步：LLM 综合工具结果，生成最终回复"
                    payload = json.dumps(
                        {
                            "type": "node_progress",
                            "node": "agent",
                            "iteration": agent_iteration,
                            "label": label,
                        },
                        ensure_ascii=False,
                    )
                    yield f"data: {payload}\n\n"

                # ── LLM 流式 token（仅来自业务节点）──────────────
                elif kind == "on_chat_model_stream" and node_name in _STREAMING_NODES:
                    chunk = event["data"].get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        tokens_emitted = True
                        payload = json.dumps(
                            {"type": "token", "content": chunk.content},
                            ensure_ascii=False,
                        )
                        yield f"data: {payload}\n\n"

                # ── 工具调用开始 ────────────────────────────────
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    tool_input = event["data"].get("input", {})
                    display = {
                        "search_poetry":  "正在检索古诗词库……",
                        "visualize_poem": "正在生成意境插画（RAG → 提示词增强 → CogView-4）……",
                    }.get(tool_name, f"调用工具 {tool_name}……")
                    payload_str = str(tool_input)[:200]
                    payload = json.dumps(
                        {"type": "tool", "name": tool_name, "display": display, "input": payload_str},
                        ensure_ascii=False,
                    )
                    yield f"data: {payload}\n\n"
                    # 工具节点进度：告知前端进入工具执行阶段
                    node_payload = json.dumps(
                        {
                            "type": "node_progress",
                            "node": "tools",
                            "iteration": 0,
                            "label": f"工具节点：执行 {tool_name}",
                        },
                        ensure_ascii=False,
                    )
                    yield f"data: {node_payload}\n\n"

                # ── 工具调用结束 ────────────────────────────────
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "")
                    raw = event["data"].get("output", "")
                    # LangGraph astream_events v2 中 output 可能是 ToolMessage 对象
                    # 必须提取 .content 字段，否则 repr() 会将 \n 转为字面量 \n (2字符)
                    # 导致前端正则捕获到的 IMAGE_URL 带垃圾字符
                    if hasattr(raw, "content"):
                        raw_output = str(raw.content)
                    else:
                        raw_output = str(raw)
                    output = raw_output[:2000]  # IMAGE_URL 等字段需要完整
                    payload = json.dumps(
                        {"type": "tool_end", "name": tool_name, "output": output},
                        ensure_ascii=False,
                    )
                    yield f"data: {payload}\n\n"

                    # ── 额外推送：RAG 结构化检索结果 ────────────
                    if tool_name == "search_poetry":
                        rag_data = _parse_search_poetry_output(raw_output)
                        if rag_data:
                            rag_payload = json.dumps(
                                {"type": "rag_result", **rag_data},
                                ensure_ascii=False,
                            )
                            yield f"data: {rag_payload}\n\n"

            # ── 兜底：静态节点（visualize/clarify fallback）────────
            # 若整个流里没有输出任何 token（例如节点不调用 LLM 时），
            # 从图状态中读取最后一条 AI 消息补发给前端。
            if not tokens_emitted:
                try:
                    final_state = agent.get_state(config)
                    if final_state and final_state.values:
                        for msg in reversed(final_state.values.get("messages", [])):
                            from langchain_core.messages import AIMessage as _AI
                            if isinstance(msg, _AI) and msg.content:
                                payload = json.dumps(
                                    {"type": "token", "content": str(msg.content)},
                                    ensure_ascii=False,
                                )
                                yield f"data: {payload}\n\n"
                                break
                except Exception:
                    pass

            # ── 完成标记 ───────────────────────────────────────
            done = json.dumps({"type": "done", "session_id": session_id}, ensure_ascii=False)
            yield f"data: {done}\n\n"

        except Exception as exc:
            error = json.dumps({"type": "error", "content": str(exc)}, ensure_ascii=False)
            yield f"data: {error}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session_id,
        },
    )


@app.post("/ai/mock/callback")
async def mock_callback(body: CallbackBody, x_callback_token: str | None = Header(default=None)):
    record = {
        "taskId": body.taskId,
        "status": body.status,
        "errorMessage": body.errorMessage,
        "payload": body.payload.model_dump() if body.payload else None,
        "token": x_callback_token,
    }
    _mock_callbacks[body.taskId] = record
    _save_mock_callback(record)
    return {"ok": True, "taskId": body.taskId}


@app.get("/ai/mock/callback/{task_id}")
async def get_mock_callback(task_id: str):
    if task_id in _mock_callbacks:
        return _mock_callbacks[task_id]
    file_record = _load_mock_callback(task_id)
    if file_record is not None:
        return file_record
    return {"taskId": task_id, "status": "pending"}
