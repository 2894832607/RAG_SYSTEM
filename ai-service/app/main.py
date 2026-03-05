import json
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.modules.glm_client import GlmClient
from app.modules.pipeline import generate_once, run_generation
from app.schemas.requests import CallbackBody, GenerationRequest, SimpleGenerationRequest, SimpleGenerationResponse

app = FastAPI(
    title="Poetry RAG AI Service",
    version="0.2.0",
    description="Poetry RAG Agent — LangGraph + GLM + ChromaDB."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "poetry rag ai"}


# ══════════════════════════════════════════════════════════════════
#  Agent Chat  —  LangGraph ReAct + GLM + ChromaDB
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
        data: {"type": "token",    "content": "..."}   ← LLM 输出 token
        data: {"type": "tool",     "name": "...", "input": "..."}  ← 工具调用
        data: {"type": "tool_end", "name": "...", "output": "..."} ← 工具返回
        data: {"type": "done",     "session_id": "..."}            ← 完成
        data: {"type": "error",    "content": "..."}               ← 错误
    """
    from langchain_core.messages import HumanMessage
    from app.agent.graph import build_agent, get_thread_config

    agent = build_agent()
    if agent is None:
        raise HTTPException(status_code=503, detail="GLM_API_KEY 未配置，Agent 不可用")

    session_id = request.session_id or str(uuid.uuid4())
    config = get_thread_config(session_id)

    async def event_generator():
        try:
            async for event in agent.astream_events(
                {"messages": [HumanMessage(content=request.message)]},
                config=config,
                version="v2",
            ):
                kind = event["event"]

                # ── LLM 流式 token ──────────────────────────────
                if kind == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        payload = json.dumps({"type": "token", "content": chunk.content}, ensure_ascii=False)
                        yield f"data: {payload}\n\n"

                # ── 工具调用开始 ────────────────────────────────
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    tool_input = event["data"].get("input", {})
                    # 将内部工具名映射为用户友好名称
                    display = {
                        "search_poetry":  "正在检索古诗词库……",
                        "enhance_prompt": "正在生成意境提示词……",
                        "generate_image": "正在生成插画……",
                    }.get(tool_name, f"调用工具 {tool_name}……")

                    payload_str = str(tool_input)[:200]
                    payload = json.dumps(
                        {"type": "tool", "name": tool_name, "display": display, "input": payload_str},
                        ensure_ascii=False
                    )
                    yield f"data: {payload}\n\n"

                # ── 工具调用结束 ────────────────────────────────
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "")
                    output = str(event["data"].get("output", ""))[:500]
                    payload = json.dumps(
                        {"type": "tool_end", "name": tool_name, "output": output},
                        ensure_ascii=False
                    )
                    yield f"data: {payload}\n\n"

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
