import asyncio
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config.model_config import get_image_config, get_llm_config, validate_and_log
from app.modules.cache import get_cache
from app.modules.glm_client import GlmClient
from app.modules.pipeline import generate_once, run_generation
from app.schemas.requests import CallbackBody, GenerationRequest, SimpleGenerationRequest, SimpleGenerationResponse

# ── Warmup 就绪标志（后台线程写入，事件循环只读）──────────────────────────
_retriever_ready: bool = False


def _warmup_retriever() -> None:
    """
    全量预热：在后台线程中一次性拉起所有懒加载组件，
    确保服务启动后所有功能立即就绪，无任何首次请求延迟。

    预热顺序：
      1. ChromaDB 连接
      2. BGE-M3 向量模型（~2GB，CPU，主要耗时）
      3. 所有 Prompt 文件（lru_cache 预填充）
      4. LangGraph ReAct Agent（build_agent，含 LLM 实例化）
    """
    global _retriever_ready
    import logging as _logging
    _wlog = _logging.getLogger(__name__)

    warmup_mode = (os.getenv("AI_WARMUP_MODE", "light") or "light").strip().lower()
    try:
        from app.modules.retriever import Retriever
        r = Retriever()
        r._get_collection()
        if warmup_mode == "full":
            r._get_embedder()
            _wlog.info("[Warmup] ChromaDB + BGE-M3 就绪")
        else:
            _wlog.info("[Warmup] ChromaDB 就绪，BGE-M3 延迟加载（AI_WARMUP_MODE=%s）", warmup_mode)
    except Exception as exc:
        _wlog.warning("[Warmup] Retriever 预热失败: %s", exc)

    _retriever_ready = True
    _wlog.info("[Warmup] Retriever ready 标志已设置")

    try:
        # ── 3: 预加载全部 Prompt 文件（lru_cache 填充）────────────────
        from app.agent.prompt_loader import _load_raw, _PROMPTS_ROOT
        for md_file in _PROMPTS_ROOT.rglob("*.md"):
            rel = md_file.relative_to(_PROMPTS_ROOT).with_suffix("").as_posix()
            try:
                _load_raw(rel)
            except Exception:
                pass
        _wlog.info("[Warmup] Prompt 文件缓存填充完毕")
    except Exception as exc:
        _wlog.warning("[Warmup] Prompt 预热失败: %s", exc)

    try:
        # ── 4: LangGraph ReAct Agent（含 LLM 实例化）─────────────────
        from app.agent.graph import build_agent
        agent = build_agent()
        if agent is not None:
            _wlog.info("[Warmup] LangGraph ReAct Agent 构建完成")
        else:
            _wlog.warning("[Warmup] LangGraph Agent 未构建（API Key 未配置？）")
    except Exception as exc:
        _wlog.warning("[Warmup] Agent 预热失败: %s", exc)

    _wlog.info("[Warmup] 后台预热流程结束")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期事件：启动时打印模型配置摘要，注册主事件循环，立即后台预热 Retriever。"""
    validate_and_log()
    loop = asyncio.get_running_loop()
    _set_main_loop(loop)
    # 立即在线程池预热 BGE-M3 + ChromaDB，不等待完成（非阻塞）
    # start-all.ps1 会轮询 /ai/health 的 retriever_ready 字段，就绪后才打开浏览器
    loop.run_in_executor(None, _warmup_retriever)
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
_local_chat_sessions: dict[str, list[dict[str, str]]] = {}
_mock_store = Path(__file__).resolve().parents[1] / "tmp" / "mock_callbacks.jsonl"
_mock_store.parent.mkdir(parents=True, exist_ok=True)

# ── Session-Scoped Event Queue（Phase 1）──────────────────────────
# 从 event_bus 统一管理，避免 tools.py ↔ main.py 循环导入
from app.event_bus import (
    _session_event_queues,
    _current_session_id,
    set_main_loop as _set_main_loop,
)


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
    """
    异步生成任务 - 支持 SSE 实时进度推送
    
    返回 202 Accepted 后立即响应，后台执行生成任务
    前端可通过 /ai/api/v1/generate/progress/{task_id} 订阅实时进度
    """
    background_tasks.add_task(run_generation_async, request)
    return {
        "message": "Task accepted",
        "taskId": request.taskId,
        "progressUrl": f"/ai/api/v1/generate/progress/{request.taskId}"
    }


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
    """health check — 返回当前配置的模型信息及 Redis 连接状态。"""
    llm = get_llm_config()
    img = get_image_config()
    cache = get_cache()
    cache_connected = await asyncio.to_thread(cache.get_connection_state, 30.0)
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
        "cache": {
            "provider":  "redis",
            "connected": cache_connected,
        },
        "retriever_ready": _retriever_ready,
    }


# ══════════════════════════════════════════════════════════════════
#  SSE 实时进度推送
# ══════════════════════════════════════════════════════════════════

@app.get("/ai/api/v1/generate/progress/{task_id}")
async def stream_progress(task_id: str):
    """
    SSE 端点：实时推送任务生成进度
    
    前端使用 EventSource 连接：
    ```javascript
    const es = new EventSource('/ai/api/v1/generate/progress/' + taskId);
    
    es.onmessage = (event) => {
        const data = JSON.parse(event.data);
        // data: {event_type, task_id, timestamp, stage, message, progress, media_files}
        
        switch(data.event_type) {
            case 'started':
                // 显示进度条，初始状态
                break;
            case 'retrieval_done':
                // 显示检索到的诗词
                break;
            case 'shot_done':
                // 显示新生成的图片（data.media_files[0].url）
                break;
            case 'video_done':
                // 显示生成的视频
                break;
            case 'completed':
                // 任务完成，关闭连接
                es.close();
                break;
            case 'failed':
                // 显示错误信息
                es.close();
                break;
        }
    };
    ```
    
    事件类型：
    - started: 任务开始
    - retrieval_done: RAG 检索完成
    - shot_done: 单张分镜生成完成（含 image_url）
    - video_done: 视频生成完成
    - completed: 全部完成
    - failed: 任务失败
    """
    from app.modules.sse_manager import sse_manager
    from app.schemas.requests import ProgressEvent
    
    async def event_generator():
        # 订阅该任务的进度事件
        queue = sse_manager.subscribe(task_id)
        
        try:
            while True:
                # 等待新事件
                event_data = await queue.get()
                yield event_data
                
                # 检查是否是结束事件
                if event_data.startswith('data: {'):
                    import json
                    try:
                        data = json.loads(event_data[6:])  # 去掉 "data: " 前缀
                        if data.get('event_type') in ['completed', 'failed']:
                            break
                    except:
                        pass
        except asyncio.CancelledError:
            # 客户端断开连接
            logger.info(f"[SSE] 客户端断开：task_id={task_id}")
        finally:
            # 取消订阅
            sse_manager.unsubscribe(task_id, queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


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


def _supports_tools_error(message: str) -> bool:
    lowered = (message or "").lower()
    return "does not support tools" in lowered or "tool" in lowered and "support" in lowered


_INVALID_CHAT_HISTORY_MARKER = "INVALID_CHAT_HISTORY"


def _clear_thread_checkpoint(session_id: str) -> None:
    """MemorySaver から session のチェックポイントを完全削除する。"""
    from app.agent.graph import _memory
    _memory.storage.pop(session_id, None)
    if hasattr(_memory, "writes"):
        _memory.writes.pop(session_id, None)
    _local_chat_sessions.pop(session_id, None)


def _has_dangling_tool_calls(session_id: str) -> bool:
    """
    MemorySaver のチェックポイントに未応答 tool_call が残っているか検査する。

    ツール呼び出し中にリクエストが中断（タイムアウト・切断等）された場合、
    AIMessage(tool_calls=[...]) に対応する ToolMessage がないまま保存される。
    次リクエストで LangGraph が INVALID_CHAT_HISTORY エラーを発生させる。
    """
    from app.agent.graph import _memory, get_thread_config
    config = get_thread_config(session_id)
    try:
        state = _memory.get(config)
        if state is None:
            return False
        messages = (state.get("channel_values") or {}).get("messages", [])
        answered_ids: set[str] = set()
        pending_ids: set[str] = set()
        for msg in messages:
            # ToolMessage: has tool_call_id attribute
            if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                answered_ids.add(msg.tool_call_id)
            # AIMessage: has tool_calls list
            if hasattr(msg, "tool_calls"):
                for tc in (msg.tool_calls or []):
                    pending_ids.add(tc["id"])
        return bool(pending_ids - answered_ids)
    except Exception:
        return False


def _should_use_local_tool_compat() -> bool:
    return get_llm_config().provider == "ollama"


def _strip_reasoning_markup(text: str) -> str:
    raw = text or ""
    # 先清理成对标签，再兜底清理未闭合的 <think> 到文本结尾。
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"<think>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)
    # 兼容部分本地模型输出的明文推理段（无 <think> 标签）。
    cleaned = re.sub(r"thinking\s*process\s*:[\s\S]*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"analysis\s*:[\s\S]*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _is_reasoning_leak(text: str) -> bool:
    lowered = (text or "").lower()
    leak_markers = (
        "<think",
        "thinking process:",
        "final json construction",
        "only output one valid json object",
        "decision rules",
    )
    return any(marker in lowered for marker in leak_markers)


def _extract_final_answer_text(raw: str) -> str:
    cleaned = _strip_reasoning_markup(raw)
    data = _extract_embedded_json(cleaned)
    if isinstance(data, dict) and data.get("final_answer"):
        return _strip_reasoning_markup(str(data["final_answer"]).strip())
    return _strip_reasoning_markup(cleaned)


def _history_text(session_id: str) -> str:
    history = _local_chat_sessions.get(session_id, [])[-8:]
    if not history:
        return "无"
    return "\n".join(f"{'用户' if item['role'] == 'user' else '助手'}：{item['content']}" for item in history)


def _append_local_history(session_id: str, role: str, content: str) -> None:
    _local_chat_sessions.setdefault(session_id, []).append({"role": role, "content": content})


def _extract_embedded_json(raw: str) -> dict | None:
    cleaned = (raw or "").strip()
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"<think>[\s\S]*$", "", cleaned, flags=re.IGNORECASE).strip()

    for candidate in (cleaned,):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if block:
        snippet = block.group(1).strip()
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


_VALID_TOOL_ACTIONS = {"search_poetry", "generate_image", "generate_video"}
_VALID_TERMINAL_ACTIONS = {"final_answer", "respond"}
_MAX_REACT_ITERATIONS = 5


def _plan_local_tool_action(message: str, session_id: str, observations: list[dict] | None = None) -> dict:
    """调用 Planner LLM 决定下一步动作。observations 是已完成的工具调用结果列表。"""
    from app.agent.prompt_loader import load_prompt

    obs_text = "无"
    if observations:
        lines = []
        for i, obs in enumerate(observations, 1):
            lines.append(f"第{i}次工具调用 [{obs['tool']}]\n输入：{obs['input']}\n结果：{obs['output'][:600]}")
        obs_text = "\n\n".join(lines)

    glm = GlmClient()
    prompt = load_prompt(
        "planner/local_tool_plan",
        history=_history_text(session_id),
        user_message=message,
        observations=obs_text,
    )
    raw = glm.complete(prompt, system_prompt="只输出一个合法 JSON 对象，不能有任何其他文字，不能有代码块。")
    plan = _extract_embedded_json(raw)
    if not isinstance(plan, dict):
        return {
            "action": "final_answer",
            "tool_input": "",
            "reply": "",
            "reason": "planner 输出不是合法 JSON，退化为直接回答",
        }

    action = str(plan.get("action", "final_answer")).strip()
    if action not in (_VALID_TOOL_ACTIONS | _VALID_TERMINAL_ACTIONS):
        action = "final_answer"

    return {
        "action": action,
        "tool_input": str(plan.get("tool_input", "")).strip(),
        "reply": _strip_reasoning_markup(str(plan.get("reply", "")).strip()),
        "reason": str(plan.get("reason", "")).strip(),
    }


def _normalize_tool_input(action: str, tool_input: str, user_message: str) -> str:
    text = (tool_input or user_message).strip()
    if action == "search_poetry":
        text = re.sub(r"(是哪首诗|出自哪首诗|是谁写的|什么意思|是什么诗|赏析一下).*$", "", text).strip()
        return text or user_message

    if action == "generate_image":
        text = re.sub(r"^(请|帮我|麻烦|把|将)", "", text).strip()
        text = re.sub(r"(生成(一幅)?|画成|画出|可视化成?|做成).*$", "", text).strip()
        return text or user_message

    return text


def _render_local_direct_answer(message: str, session_id: str, planner_reply: str = "") -> str:
    from app.agent.prompt_loader import load_prompt

    if planner_reply:
        return _strip_reasoning_markup(planner_reply)

    glm = GlmClient()
    prompt = load_prompt("chat/general")
    prompt = (
        f"{prompt}\n\n历史对话：\n{_history_text(session_id)}\n\n用户问题：\n{message}\n\n"
        "输出格式：只输出一个 JSON 对象，格式为 {\"final_answer\":\"你的回答\"}，不要有任何其他文字。"
    )
    return _extract_final_answer_text(glm.complete(prompt, system_prompt="你是古诗词助手。只输出 JSON，格式：{\"final_answer\":\"回答内容\"}。"))


def _run_local_compatible_tool(tool_name: str, tool_input: str) -> str:
    from app.agent.tools import run_search_poetry, run_generate_image, run_generate_video

    if tool_name == "search_poetry":
        return run_search_poetry(tool_input)
    if tool_name in ("generate_image", "visualize_poem"):
        return run_generate_image(tool_input)
    if tool_name == "generate_video":
        return run_generate_video(tool_input)
    raise ValueError(f"未知工具：{tool_name}")


def _render_tool_based_answer(message: str, session_id: str, tool_name: str, tool_output: str) -> str:
    if tool_name == "search_poetry":
        rag = _parse_search_poetry_output(tool_output)
        if rag and rag.get("poems"):
            poem = rag["poems"][0]
            return (
                f"这句诗出自{poem['author']}的《{poem['title']}》，属于{poem['dynasty']}。\n\n"
                f"原诗中的相关内容是：{poem['original']}\n\n"
                f"白话意思是：{poem['translation']}"
            )

        if "超时" in tool_output or "失败" in tool_output:
            return f"当前检索服务暂时不可用：{tool_output}。你可以稍后再试，或者直接让我先按常识为你解读这句诗。"

    if tool_name == "generate_image":
        poem_match = re.search(r"POEM:(.+)", tool_output)
        poem_info = poem_match.group(1).strip() if poem_match else "这首诗"
        # 新版多图格式 IMAGES_JSON:[{...},...]
        images_match = re.search(r"IMAGES_JSON:(\[.+\])", tool_output)
        if images_match:
            try:
                scenes = json.loads(images_match.group(1))
                urls = [s.get("image_url", "") for s in scenes if s.get("image_url")]
                if urls:
                    return f"已根据{poem_info}生成 {len(urls)} 张意境图，图片地址：" + "；".join(urls)
            except (json.JSONDecodeError, TypeError):
                pass
        # 旧版兼容 IMAGE_URL:...
        image_match = re.search(r"IMAGE_URL:(.+)", tool_output)
        if image_match:
            return f"已根据{poem_info}生成意境图，图片地址是：{image_match.group(1).strip()}"

        if "跳过生图" in tool_output:
            poem_info = poem_match.group(1).strip() if poem_match else "这首诗"
            return f"已经完成 {poem_info} 的意境图提示词增强，但当前图像模型未启用，所以这一步先跳过了。需要的话我可以继续帮你解读画面构图。"

        if "超时" in tool_output or "失败" in tool_output:
            return f"当前生图流程暂时不可用：{tool_output}。你可以稍后再试，或者我先把适合这首诗的画面描述整理给你。"

    from app.agent.prompt_loader import load_prompt

    glm = GlmClient()
    prompt = load_prompt(
        "chat/tool_result_answer",
        history=_history_text(session_id),
        user_message=message,
        tool_name=tool_name,
        tool_output=tool_output,
    )
    prompt = (
        f"{prompt}\n\n"
        "输出格式：只输出一个 JSON 对象，格式为 {\"final_answer\":\"你的回答\"}，不要有任何其他文字。"
    )
    return _extract_final_answer_text(glm.complete(prompt, system_prompt="你是古诗词助手。只输出 JSON，格式：{\"final_answer\":\"回答内容\"}。"))


async def _local_tool_compat_event_generator(message: str, session_id: str):
    """
    本地模型 ReAct 循环：
      思考（Planner JSON）→ 执行工具 → 观察结果 → 再思考 → … → final_answer
    最多循环 _MAX_REACT_ITERATIONS 轮，结构与 LangGraph 原生路径完全对齐。
    """
    import asyncio
    loop = asyncio.get_running_loop()

    # 本轮对话的观察结果列表，格式：[{"tool": str, "input": str, "output": str}]
    observations: list[dict] = []
    # 已调用过的工具集合，防止同一工具被无限重复调用
    called_tools: set[str] = set()
    agent_iteration = 0

    for react_step in range(1, _MAX_REACT_ITERATIONS + 1):
        # ── Planner 思考 ───────────────────────────────────────────
        agent_iteration += 1
        if agent_iteration == 1:
            label = "第 1 步：LLM 分析问题，规划是否需要检索或生图"
        else:
            label = f"第 {agent_iteration} 步：LLM 综合工具结果，生成最终回复"

        node_payload = json.dumps(
            {
                "type": "node_progress",
                "node": "agent",
                "iteration": agent_iteration,
                "label": label,
            },
            ensure_ascii=False,
        )
        yield f"data: {node_payload}\n\n"

        planner = await loop.run_in_executor(
            None, _plan_local_tool_action, message, session_id, observations
        )

        action = planner["action"]
        reason = planner.get("reason", "")

        # ── 终止动作：final_answer / respond ──────────────────────
        if action in _VALID_TERMINAL_ACTIONS:
            reply = planner.get("reply", "").strip()
            if reply and _is_reasoning_leak(reply):
                # 本地模型偶发泄露思维链时，强制走兜底回答路径。
                reply = ""
            if not reply:
                # Planner 没有填 reply，用 observations 兜底生成答案
                if observations:
                    last_obs = observations[-1]
                    reply = await loop.run_in_executor(
                        None,
                        _render_tool_based_answer,
                        message,
                        session_id,
                        last_obs["tool"],
                        last_obs["output"],
                    )
                else:
                    reply = await loop.run_in_executor(
                        None,
                        _render_local_direct_answer,
                        message,
                        session_id,
                        "",
                    )

            # 兜底回答再次净化，避免极端情况下残留推理文本。
            reply = _strip_reasoning_markup(reply)
            if _is_reasoning_leak(reply):
                reply = "抱歉，刚刚思路有点乱。你这句我来直接给结果：我可以马上为你找诗、赏析或生成意境图。"

            _append_local_history(session_id, "user", message)
            _append_local_history(session_id, "assistant", reply)
            token_payload = json.dumps({"type": "token", "content": reply}, ensure_ascii=False)
            yield f"data: {token_payload}\n\n"
            return

        # ── 工具动作：检查是否已调用过（防止重复） ────────────────
        if action not in _VALID_TOOL_ACTIONS:
            # 未知 action，直接输出 reason 作为答复
            fallback = reason or "抱歉，我暂时无法处理这个问题。"
            _append_local_history(session_id, "user", message)
            _append_local_history(session_id, "assistant", fallback)
            yield f"data: {json.dumps({'type': 'token', 'content': fallback}, ensure_ascii=False)}\n\n"
            return

        if action in called_tools:
            # 同一工具已调用过，强制进入 final_answer
            if observations:
                last_obs = observations[-1]
                reply = await loop.run_in_executor(
                    None,
                    _render_tool_based_answer,
                    message,
                    session_id,
                    last_obs["tool"],
                    last_obs["output"],
                )
            else:
                reply = "已完成检索，请告诉我你还需要了解哪些内容？"
            _append_local_history(session_id, "user", message)
            _append_local_history(session_id, "assistant", reply)
            yield f"data: {json.dumps({'type': 'token', 'content': reply}, ensure_ascii=False)}\n\n"
            return

        # ── 执行工具 ───────────────────────────────────────────────
        normalized_input = _normalize_tool_input(action, planner["tool_input"], message)

        display = {
            "search_poetry":  "正在检索古诗词库……",
            "generate_image": "正在生成意境插画（RAG → 提示词增强 → Seedream 图像生成）……",
            "generate_video": "正在生成分镜视频（RAG → 超级提示词 → Seedance 文生视频）……",
        }.get(action, f"调用工具 {action}……")
        tool_payload = json.dumps(
            {"type": "tool", "name": action, "display": display, "input": normalized_input},
            ensure_ascii=False,
        )
        yield f"data: {tool_payload}\n\n"

        tool_progress = json.dumps(
            {
                "type": "node_progress",
                "node": "tools",
                "iteration": 0,
                "label": f"工具节点：执行 {action}",
            },
            ensure_ascii=False,
        )
        yield f"data: {tool_progress}\n\n"

        tool_output = await loop.run_in_executor(None, _run_local_compatible_tool, action, normalized_input)
        called_tools.add(action)

        tool_end = json.dumps(
            {"type": "tool_end", "name": action, "output": tool_output[:2000]},
            ensure_ascii=False,
        )
        yield f"data: {tool_end}\n\n"

        # 推送 RAG 结构化结果（与原 LangGraph 路径一致）
        if action == "search_poetry":
            rag_data = _parse_search_poetry_output(tool_output)
            if rag_data:
                rag_payload = json.dumps({"type": "rag_result", **rag_data}, ensure_ascii=False)
                yield f"data: {rag_payload}\n\n"

        # 推送 generate_image 结构化结果
        if action == "generate_image":
            poem_match = re.search(r"POEM:(.+)", tool_output)
            poem_info = poem_match.group(1).strip() if poem_match else ""
            # 新版多图格式
            images_match = re.search(r"IMAGES_JSON:(\[.+\])", tool_output)
            if images_match:
                try:
                    scenes = json.loads(images_match.group(1))
                    all_image_urls = [s.get("image_url") for s in scenes if s.get("image_url")]
                    
                    # 为每张图片发送单独的 image_done 事件（向后兼容）
                    for scene in scenes:
                        if scene.get("image_url"):
                            img_payload = json.dumps({
                                "type": "image_done",
                                "image_url": scene["image_url"],
                                "scene": scene.get("scene", 1),
                                "desc": scene.get("desc", ""),
                                "poem_info": poem_info,
                            }, ensure_ascii=False)
                            yield f"data: {img_payload}\n\n"
                    
                    # 新增：发送包含所有图片数组的 image_done 事件（支持前端多图显示）
                    if all_image_urls:
                        final_img_payload_dict = {
                            "type": "image_done",
                            "image_url": all_image_urls[0],  # 主图（向后兼容）
                            "image_urls": all_image_urls,     # 所有图片数组（新字段）
                            "poem_info": poem_info,
                        }
                        print(f"🎯 [DEBUG] Sending final image_done with {len(all_image_urls)} images: {all_image_urls}")
                        final_img_payload = json.dumps(final_img_payload_dict, ensure_ascii=False)
                        yield f"data: {final_img_payload}\n\n"
                        
                except (json.JSONDecodeError, TypeError):
                    pass
            else:
                # 旧版兼容
                image_match = re.search(r"IMAGE_URL:(.+)", tool_output)
                if image_match:
                    img_payload = json.dumps({
                        "type": "image_done",
                        "image_url": image_match.group(1).strip(),
                        "poem_info": poem_info,
                    }, ensure_ascii=False)
                    yield f"data: {img_payload}\n\n"

        # 推送 generate_video 结构化结果（replay SSE events）
        if action == "generate_video" and tool_output.startswith("VIDEO_RESULT:"):
            try:
                video_data = json.loads(tool_output[len("VIDEO_RESULT:"):])
                if video_data.get("plan"):
                    yield f"data: {json.dumps(video_data['plan'], ensure_ascii=False)}\n\n"
                for frame in video_data.get("frames", []):
                    yield f"data: {json.dumps({'type': 'shot_done', **frame}, ensure_ascii=False)}\n\n"
                if video_data.get("video_url"):
                    yield f"data: {json.dumps({'type': 'video_done', 'video_url': video_data['video_url']}, ensure_ascii=False)}\n\n"
            except (json.JSONDecodeError, TypeError):
                pass

        # 记录观察结果，下一轮 Planner 可以看到
        observations.append({
            "tool":   action,
            "input":  normalized_input,
            "output": tool_output,
        })

    # ── 超出最大迭代次数，强制用最后一次工具结果生成答复 ─────────
    if observations:
        last_obs = observations[-1]
        answer = await loop.run_in_executor(
            None,
            _render_tool_based_answer,
            message,
            session_id,
            last_obs["tool"],
            last_obs["output"],
        )
    else:
        answer = "抱歉，我经过多轮思考后仍无法给出满意的答复，请换个方式再问我吧。"

    _append_local_history(session_id, "user", message)
    _append_local_history(session_id, "assistant", answer)
    yield f"data: {json.dumps({'type': 'token', 'content': answer}, ensure_ascii=False)}\n\n"


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
    if session_id in _local_chat_sessions:
        return _local_chat_sessions[session_id]

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
    _clear_thread_checkpoint(session_id)
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
        data: {"type": "storyboard_progress", "stage": "...", "message": "..."}  ← 分镜进度
        data: {"type": "tool_progress", "tool": "...", "stage": "...", "message": "..."}  ← 工具进度
        data: {"type": "plan",         "total_shots": N, "shots": [...]}  ← 分镜方案
        data: {"type": "shot_done",    "shot_id": N, "image_url": "..."}  ← 分镜完成
        data: {"type": "done",         "session_id": "..."}           ← 完成
        data: {"type": "error",        "content": "..."}              ← 错误
    """
    session_id = request.session_id or str(uuid.uuid4())

    if _should_use_local_tool_compat():
        # ── 本地 Ollama 路径：注册队列供工具使用，复用现有兼容路径 ──
        event_queue: asyncio.Queue = asyncio.Queue()
        _session_event_queues[session_id] = event_queue
        _current_session_id.set(session_id)

        async def local_event_generator():
            try:
                async for event in _local_tool_compat_event_generator(request.message, session_id):
                    yield event
                done = json.dumps({"type": "done", "session_id": session_id}, ensure_ascii=False)
                yield f"data: {done}\n\n"
            except Exception as exc:
                error = json.dumps({"type": "error", "content": str(exc)}, ensure_ascii=False)
                yield f"data: {error}\n\n"
            finally:
                _session_event_queues.pop(session_id, None)

        return StreamingResponse(
            local_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-Session-Id": session_id,
            },
        )

    from langchain_core.messages import HumanMessage
    from app.agent.graph import build_agent, get_thread_config

    agent = build_agent()
    if agent is None:
        raise HTTPException(status_code=503, detail="GLM_API_KEY 未配置，Agent 不可用")

    config = get_thread_config(session_id)

    # ── Session-Scoped Event Queue（Phase 1）──────────────────────
    # 为本次请求创建专属事件队列，注册到全局注册表
    # generate_storyboard 工具在 ThreadPool 中通过 run_coroutine_threadsafe push 进来
    event_queue: asyncio.Queue = asyncio.Queue()
    _session_event_queues[session_id] = event_queue
    _current_session_id.set(session_id)

    # 只允许这些节点的 LLM token 流式输出给用户
    _STREAMING_NODES = {"agent"}

    async def langgraph_producer():
        """
        在独立 Task 中运行 astream_events，将所有解析后的事件 push 进 event_queue。
        负责：LangGraph 事件解析 → 结构化 dict → queue.put()
        """

        # ── Pre-flight：检测并清除上次请求遗留的悬空 tool_call ──────────
        # 当工具执行超时或请求中断时，AIMessage(tool_calls=[...]) 会被保存到
        # MemorySaver，但对应的 ToolMessage 未写入，下次请求触发 INVALID_CHAT_HISTORY。
        if _has_dangling_tool_calls(session_id):
            logger.warning(
                "[Chat] session=%s 存在未完成的 tool_call，自动清除检查点", session_id
            )
            _clear_thread_checkpoint(session_id)

        tokens_emitted = False
        agent_iteration = 0
        
        try:
            async for event in agent.astream_events(
                {"messages": [HumanMessage(content=request.message)]},
                config=config,
                version="v2",
            ):
                kind = event["event"]
                node_name = event.get("metadata", {}).get("langgraph_node", "")

                # ── LLM 开始推理（节点进度）────────────────────────
                if kind == "on_chat_model_start" and node_name in _STREAMING_NODES:
                    agent_iteration += 1
                    if agent_iteration == 1:
                        label = "第 1 步：LLM 分析问题，规划是否需要检索或生图"
                    else:
                        label = f"第 {agent_iteration} 步：LLM 综合工具结果，生成最终回复"
                    await event_queue.put({
                        "type": "node_progress",
                        "node": "agent",
                        "iteration": agent_iteration,
                        "label": label,
                    })

                # ── LLM 流式 token ─────────────────────────────────
                elif kind == "on_chat_model_stream" and node_name in _STREAMING_NODES:
                    chunk = event["data"].get("chunk")
                    if chunk:
                        # 优先推送 reasoning_content（思考链），让前端看到 LLM 的思考过程
                        # GLM 推理模型的 reasoning_content 可能在 response_metadata 或 additional_kwargs 中
                        reasoning = None
                        if hasattr(chunk, "response_metadata") and chunk.response_metadata:
                            reasoning = chunk.response_metadata.get("reasoning_content")
                        if not reasoning and hasattr(chunk, "additional_kwargs") and chunk.additional_kwargs:
                            reasoning = chunk.additional_kwargs.get("reasoning_content")
                        if reasoning:
                            await event_queue.put({"type": "thinking", "content": reasoning})
                        
                        # 然后推送正文 token
                        if hasattr(chunk, "content") and chunk.content:
                            tokens_emitted = True
                            await event_queue.put({"type": "token", "content": chunk.content})

                # ── 工具调用开始 ────────────────────────────────────
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    tool_input = event["data"].get("input", {})
                    display = {
                        "search_poetry":      "正在检索古诗词库……",
                        "generate_image":     "正在生成意境插画（RAG → 提示词增强 → CogView 生图）……",
                        "generate_video":     "正在生成分镜视频（RAG → 超级提示词 → Seedance 文生视频）……",
                        "generate_storyboard": "正在规划分镜方案（RAG → GLM 规划 → CogView-4 逐张生图）……",
                    }.get(tool_name, f"调用工具 {tool_name}……")
                    await event_queue.put({
                        "type": "tool",
                        "name": tool_name,
                        "display": display,
                        "input": str(tool_input)[:200],
                    })
                    await event_queue.put({
                        "type": "node_progress",
                        "node": "tools",
                        "iteration": 0,
                        "label": f"工具节点：执行 {tool_name}",
                    })

                # ── 工具调用结束 ────────────────────────────────────
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "")
                    raw = event["data"].get("output", "")
                    if hasattr(raw, "content"):
                        raw_output = str(raw.content)
                    else:
                        raw_output = str(raw)
                    output = raw_output[:2000]
                    await event_queue.put({
                        "type": "tool_end",
                        "name": tool_name,
                        "output": output,
                    })

                    # 额外推送：RAG 结构化检索结果
                    if tool_name == "search_poetry":
                        rag_data = _parse_search_poetry_output(raw_output)
                        if rag_data:
                            await event_queue.put({"type": "rag_result", **rag_data})

                    # 额外推送：generate_image 结果
                    if tool_name == "generate_image":
                        poem_match = re.search(r"POEM:(.+)", raw_output)
                        poem_info = poem_match.group(1).strip() if poem_match else ""
                        # 新版多图格式
                        images_match = re.search(r"IMAGES_JSON:(\[.+\])", raw_output)
                        if images_match:
                            try:
                                scenes = json.loads(images_match.group(1))
                                all_image_urls = [s.get("image_url") for s in scenes if s.get("image_url")]
                                
                                # 为每张图片发送单独的 image_done 事件（向后兼容）
                                for scene in scenes:
                                    if scene.get("image_url"):
                                        await event_queue.put({
                                            "type": "image_done",
                                            "image_url": scene["image_url"],
                                            "scene": scene.get("scene", 1),
                                            "desc": scene.get("desc", ""),
                                            "poem_info": poem_info,
                                        })
                                
                                # 新增：发送包含所有图片数组的 image_done 事件（支持前端多图显示）
                                if all_image_urls:
                                    await event_queue.put({
                                        "type": "image_done",
                                        "image_url": all_image_urls[0],  # 主图（向后兼容）
                                        "image_urls": all_image_urls,     # 所有图片数组（新字段）
                                        "poem_info": poem_info,
                                    })
                            except (json.JSONDecodeError, TypeError):
                                pass
                        else:
                            # 旧版兼容
                            image_match = re.search(r"IMAGE_URL:(.+)", raw_output)
                            if image_match:
                                await event_queue.put({
                                    "type": "image_done",
                                    "image_url": image_match.group(1).strip(),
                                    "poem_info": poem_info,
                                })

                    # 额外推送：generate_video 结果（replay SSE events）
                    if tool_name == "generate_video" and raw_output.startswith("VIDEO_RESULT:"):
                        try:
                            video_data = json.loads(raw_output[len("VIDEO_RESULT:"):])
                            if video_data.get("plan"):
                                await event_queue.put(video_data["plan"])
                            for frame in video_data.get("frames", []):
                                await event_queue.put({"type": "shot_done", **frame})
                            if video_data.get("video_url"):
                                await event_queue.put({
                                    "type": "video_done",
                                    "video_url": video_data["video_url"],
                                })
                        except (json.JSONDecodeError, TypeError):
                            pass

                    # generate_storyboard：SSE 事件已由工具内部直接 push 到队列
                    # tool_end 时工具返回汇总字符串，队列中此时分镜事件已全部推送完毕

            # ── 兜底：若无 token 被推送，从图状态补发最后一条 AI 消息 ──
            if not tokens_emitted:
                try:
                    final_state = agent.get_state(config)
                    if final_state and final_state.values:
                        for msg in reversed(final_state.values.get("messages", [])):
                            from langchain_core.messages import AIMessage as _AI
                            if isinstance(msg, _AI) and msg.content:
                                await event_queue.put({
                                    "type": "token",
                                    "content": str(msg.content),
                                })
                                break
                except Exception:
                    pass

        except Exception as exc:
            exc_str = str(exc)
            if _INVALID_CHAT_HISTORY_MARKER in exc_str:
                # 上次请求中断导致 MemorySaver 保存了不完整的 tool_call 历史。
                # 清除检查点后立即重试一次（用户无感知）。
                logger.warning(
                    "[Chat] INVALID_CHAT_HISTORY detected for session=%s, "
                    "clearing checkpoint and retrying. detail: %s",
                    session_id, exc_str[:300],
                )
                _clear_thread_checkpoint(session_id)
                try:
                    async for event in agent.astream_events(
                        {"messages": [HumanMessage(content=request.message)]},
                        config=config,
                        version="v2",
                    ):
                        kind = event["event"]
                        node_name = event.get("metadata", {}).get("langgraph_node", "")
                        if kind == "on_chat_model_stream" and node_name in _STREAMING_NODES:
                            chunk = event["data"].get("chunk")
                            if chunk and hasattr(chunk, "content") and chunk.content:
                                await event_queue.put({"type": "token", "content": chunk.content})
                        elif kind == "on_tool_start":
                            await event_queue.put({"type": "tool", "name": event.get("name", ""), "display": "", "input": ""})
                        elif kind == "on_tool_end":
                            await event_queue.put({"type": "tool_end", "name": event.get("name", ""), "output": str(event["data"].get("output", ""))[:2000]})
                except Exception as retry_exc:
                    await event_queue.put({"type": "error", "content": str(retry_exc)})
            elif _supports_tools_error(exc_str):
                # 模型不支持 tools，降级到本地兼容路径
                try:
                    async for sse_line in _local_tool_compat_event_generator(
                        request.message, session_id
                    ):
                        sse_line = sse_line.strip()
                        if sse_line.startswith("data: "):
                            try:
                                parsed = json.loads(sse_line[6:])
                                if parsed.get("type") != "done":
                                    await event_queue.put(parsed)
                            except json.JSONDecodeError:
                                pass
                except Exception as inner_exc:
                    await event_queue.put({"type": "error", "content": str(inner_exc)})
            else:
                await event_queue.put({"type": "error", "content": exc_str})

        finally:
            # 推送 done 事件 + None 哨兵（触发 event_generator 退出循环）
            await event_queue.put({"type": "done", "session_id": session_id})
            await event_queue.put(None)

    async def event_generator():
        """
        唯一的 SSE 生产者：从 event_queue 消费 dict，序列化为 SSE 格式发给客户端。
        事件来源：langgraph_producer（LangGraph 事件）和 generate_storyboard 工具（分镜事件）。
        """
        producer_task = asyncio.create_task(langgraph_producer())
        try:
            while True:
                item = await event_queue.get()
                if item is None:  # 终止哨兵
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        finally:
            producer_task.cancel()
            _session_event_queues.pop(session_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session_id,
        },
    )


# ══════════════════════════════════════════════════════════════════
#  运行时模型配置  —  前端切换 LLM 无需重启服务
# ══════════════════════════════════════════════════════════════════

_PRESETS: dict[str, dict] = {
    "ollama": {
        "LLM_PROVIDER":   "ollama",
        "LLM_MODEL":      "qwen3.5:4b-q4_0",
        "LLM_BASE_URL":   "http://localhost:11434/v1",
        "LLM_API_KEY":    "ollama",
        "LLM_TIMEOUT":    "120",
        "IMAGE_PROVIDER": "local_sdxl",
        "IMAGE_MODEL":    "sdxl-turbo",
        "LOCAL_SDXL_URL": "http://localhost:8090/v1/images/generations",
        "COGVIEW_SIZE":   "1024x1024",
        "VIDEO_PROVIDER": "disabled",
    },
    "glm": {
        "LLM_PROVIDER":   "glm",
        "LLM_MODEL":      "glm-5",
        "LLM_BASE_URL":   "https://open.bigmodel.cn/api/paas/v4",
        "LLM_TIMEOUT":    "90",
        "IMAGE_PROVIDER": "cogview",
        "IMAGE_MODEL":    "cogview-4-250304",   # CogView-4 最新图像模型
        "IMAGE_BASE_URL": "",
        "COGVIEW_SIZE":   "1280x1280",
        "VIDEO_PROVIDER": "vidu",               # GLM Vidu 视频（/videos/generations）
        "VIDEO_MODEL":    "vidu2-reference",
        "VIDEO_BASE_URL": "https://open.bigmodel.cn/api/paas/v4",
    },
    "doubao": {
        "LLM_PROVIDER":   "doubao",
        "LLM_MODEL":      "doubao-seed-1-8-251228",
        "LLM_BASE_URL":   "https://ark.cn-beijing.volces.com/api/v3",
        "LLM_TIMEOUT":    "90",
        "IMAGE_PROVIDER": "seedream",
        "IMAGE_MODEL":    "doubao-seedream-4-5-251128",
        "IMAGE_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3",
        "COGVIEW_SIZE":   "2K",
        "VIDEO_PROVIDER": "seedance",           # 字节 Seedance
        "VIDEO_MODEL":    "doubao-seedance-1-5-pro-251215",
        "VIDEO_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3",
    },
}


class ModelSwitchRequest(BaseModel):
    preset: str                   # "ollama" | "glm" | "doubao" | "custom"
    api_key: str = ""             # 切换到云端时必填
    model: str = ""               # 可选覆盖
    base_url: str = ""            # 可选覆盖（preset=custom 时必填）


@app.get("/ai/api/v1/config/model")
async def get_model_config():
    """返回当前运行时 LLM 配置（供前端展示）。"""
    cfg = get_llm_config()
    return {
        "provider":    cfg.provider,
        "model":       cfg.model,
        "base_url":    cfg.base_url,
        "api_key_set": bool(cfg.api_key and cfg.api_key not in ("ollama", "")),
        "enabled":     bool(cfg.api_key) or cfg.provider == "ollama",
    }


@app.post("/ai/api/v1/config/model")
async def switch_model_config(req: ModelSwitchRequest):
    """
    运行时切换 LLM 配置，立即生效（修改进程内 os.environ）。

    - preset=ollama  → 无需 api_key，切到本地部署模型
    - preset=glm     → 必须提供 api_key
    - preset=custom  → 需要 api_key + base_url，model 可选
    """
    import os
    from app.agent.graph import reset_agent

    if req.preset not in _PRESETS and req.preset != "custom":
        raise HTTPException(status_code=400, detail=f"未知 preset='{req.preset}'，支持：ollama / glm / doubao / custom")

    if req.preset == "custom":
        if not req.base_url:
            raise HTTPException(status_code=400, detail="preset=custom 时 base_url 不能为空")
        os.environ["LLM_PROVIDER"] = "custom"
        os.environ["LLM_BASE_URL"] = req.base_url
        if req.model:
            os.environ["LLM_MODEL"] = req.model
        if req.api_key:
            os.environ["LLM_API_KEY"] = req.api_key
    else:
        preset_env = _PRESETS[req.preset]
        for k, v in preset_env.items():
            os.environ[k] = v
        
        # api_key 处理：优先用前端传入的 Key，否则检查环境变量
        actual_api_key = req.api_key
        if not actual_api_key:
            # 如果前端没传 Key，尝试从环境变量读取（由 start-all.ps1 或系统环境预设）
            if req.preset == "doubao":
                actual_api_key = os.getenv("ARK_API_KEY", "").strip()
            else:  # glm
                actual_api_key = os.getenv("GLM_API_KEY", "").strip() or os.getenv("LLM_API_KEY", "").strip()
        
        # 设置 api_key：确保 LLM/Image/Video 三个链路都使用正确的 Key
        if actual_api_key:
            os.environ["LLM_API_KEY"] = actual_api_key
            if req.preset == "doubao":
                # 豆包：三个链路都使用 ARK_API_KEY
                os.environ["IMAGE_API_KEY"] = actual_api_key
                os.environ["VIDEO_API_KEY"] = actual_api_key
            else:
                # GLM/Ollama：清除豆包的专用 Key，让 Image/Video 回退到 LLM_API_KEY
                os.environ.pop("IMAGE_API_KEY", None)
                os.environ.pop("VIDEO_API_KEY", None)
        else:
            raise HTTPException(status_code=400, detail=f"preset={req.preset} 需要 API Key，请在环境变量中设置或通过 api_key 参数提供")
        
        if req.model:
            os.environ["LLM_MODEL"] = req.model

    # 验证切换后配置是否 enabled
    reset_agent()
    cfg = get_llm_config()
    enabled = bool(cfg.api_key) or cfg.provider == "ollama"
    return {
        "ok":       True,
        "provider": cfg.provider,
        "model":    cfg.model,
        "base_url": cfg.base_url,
        "enabled":  enabled,
        "warning":  None if enabled else "api_key 未设置，LLM 功能不可用",
    }


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
