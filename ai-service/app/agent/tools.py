"""
Agent Tools 定义 — ReAct 架构

四个工具，职责清晰：
1. search_poetry      - 检索古诗词，返回结构化文本供 Agent 展示/推理
2. generate_image     - 完整可视化链路：RAG → PE → CogView，返回图像结果
3. generate_video     - 分镜视频链路：RAG → 分镜规划 → 逐帧 → Seedance 合成
4. generate_storyboard- 实时分镜看板：RAG → GLM 规划 → CogView-4 逐张生图，通过
                        事件总线将每一步进度实时推送给 SSE 客户端
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from langchain_core.tools import tool
from app.modules.cache import get_cache
from app.modules.cache_strategies import CacheStrategy, make_cache_key


_TOOL_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-tool")


def _run_with_timeout(func, timeout_seconds: float, timeout_message: str) -> str:
    future = _TOOL_EXECUTOR.submit(func)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError:
        future.cancel()
        return timeout_message


def _push_progress(
    session_id: str,
    tool_name: str,
    stage: str,
    message: str,
    detail: dict | None = None,
) -> None:
    """向当前 session 的事件队列推送 tool_progress 事件（队列不存在时静默忽略）。"""
    if not session_id:
        return
    from app.event_bus import push_session_event
    event: dict = {"type": "tool_progress", "tool": tool_name, "stage": stage, "message": message}
    if detail is not None:
        event["detail"] = detail
    push_session_event(session_id, event)


def _push_rag_results(session_id: str, poems: list, mode: str) -> None:
    """向前端推送完整 RAG 检索结果（rag_result 事件），供过程面板实时渲染。

    poems: list[RetrievedPoem]  — Retriever 返回的 poems 列表
    mode:  "exact" | "fuzzy"   — "fuzzy" 前端映射为 "semantic"
    """
    if not session_id or not poems:
        return
    from app.event_bus import push_session_event
    frontend_mode = "exact" if mode == "exact" else "semantic"
    push_session_event(session_id, {
        "type": "rag_result",
        "mode": frontend_mode,
        "poems": [
            {
                "index": i + 1,
                "title": p.title,
                "author": p.author,
                "dynasty": p.dynasty,
                "similarity": round(p.similarity, 3),
                "original": p.original_poem,
                "translation": p.translation,
            }
            for i, p in enumerate(poems)
        ],
    })


def _search_poetry_impl(query: str, session_id: str = "") -> str:
    """供 LangGraph tools 与本地 JSON 工具兼容线路复用的纯函数入口。"""
    from app.modules.retriever import Retriever

    cache = get_cache()
    cache_key = make_cache_key("poetry", query)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        _push_progress(session_id, "search_poetry", "start", "正在检索诗词知识库…")
        result = Retriever().smart_retrieve(query)

        if not result.poems:
            return "未在知识库中找到相关诗词，请尝试换个描述方式。"

        # 立即将完整检索结果推送到前端过程面板
        _push_rag_results(session_id, result.poems, result.mode)

        best = result.poems[0]
        _push_progress(
            session_id, "search_poetry", "done",
            f"找到 {len(result.poems)} 首，最佳《{best.title}》相似度 {best.similarity:.0%}",
            detail={"title": best.title, "author": best.author, "similarity": round(best.similarity, 3)},
        )

        if result.mode == "exact":
            poem = best
            text = (
                f"**《{poem.title}》 — {poem.author}（{poem.dynasty}）**\n\n"
                f"**原诗：**\n{poem.original_poem}\n\n"
                f"**白话译文：**\n{poem.translation}\n\n"
                f"相似度：{poem.similarity:.3f}"
            )
        else:
            lines = [f"找到 {len(result.poems)} 首相关诗词：\n"]
            for i, poem in enumerate(result.poems, 1):
                lines.append(
                    f"**[{i}]** 《{poem.title}》 — {poem.author}（{poem.dynasty}） "
                    f"相似度 {poem.similarity:.2f}\n"
                    f"原诗：{poem.original_poem}\n"
                    f"译文：{poem.translation[:80]}……\n"
                )
            lines.append("请告诉我选哪首，或让我直接生成其中一首的意境插画。")
            text = "\n".join(lines)

        cache.set(cache_key, text, CacheStrategy.POETRY_SEARCH_TTL)
        return text
    except Exception as exc:
        return f"检索失败：{exc}"


def run_search_poetry(query: str) -> str:
    from app.event_bus import _current_session_id
    return _search_poetry_impl(query, _current_session_id.get(""))


def _generate_image_impl(poem_text: str, session_id: str = "") -> str:
    """供 LangGraph tools 与本地 JSON 工具兼容线路复用的纯函数入口。

    流程：
      1. RAG 检索最相关诗词
      2. PromptEnhancer.split_scenes() — LLM 将译文拆分成 1~5 个场景提示词
      3. CogViewClient.generate_scenes() — 并行生成每个场景的图片
      4. 返回多图结果字符串（IMAGES_JSON:{...}），供 Agent 和前端解析
    """
    from app.modules.generation import CogViewClient
    from app.modules.prompt import PromptEnhancer
    from app.modules.retriever import Retriever

    try:
        _push_progress(session_id, "generate_image", "rag_start", "正在检索诗词知识库…")
        result = Retriever().smart_retrieve(poem_text)
        poems = result.poems

        if poems:
            best = poems[0]
            _push_rag_results(session_id, poems, result.mode)
            knowledge_blocks = [best.to_knowledge_block()]
            poem_info = f"《{best.title}》 — {best.author}（{best.dynasty}）"
            full_poem = best.original_poem
            _push_progress(
                session_id, "generate_image", "rag_done",
                f"RAG 检索完成：{poem_info}",
                detail={"title": best.title, "author": best.author},
            )
        else:
            knowledge_blocks = []
            poem_info = poem_text
            full_poem = poem_text

        _push_progress(session_id, "generate_image", "prompt_split", "正在分析场景，拆分提示词…")
        scenes = PromptEnhancer().split_scenes(poem_text, knowledge_blocks)
        _push_progress(
            session_id, "generate_image", "generating",
            f"正在并行生成 {len(scenes)} 张意境图，请稍候…",
            detail={"total": len(scenes)},
        )

        client = CogViewClient()
        if not client.is_enabled():
            return (
                f"已完成场景拆分（{len(scenes)} 个场景），但图像 API 未配置，跳过生图。\n"
                f"诗词：{poem_info}\n"
                f"场景提示词：{'; '.join(s.desc for s in scenes)}"
            )

        scene_results = client.generate_scenes(scenes)

        # 逐张推送进度事件
        for r in scene_results:
            if r["image_url"]:
                _push_progress(
                    session_id, "generate_image", "scene_done",
                    f"场景 {r['scene']} 生成完成：{r['desc']}",
                    detail={"scene": r["scene"], "image_url": r["image_url"], "desc": r["desc"]},
                )

        import json as _json
        images_json = _json.dumps(scene_results, ensure_ascii=False)
        return (
            f"IMAGES_JSON:{images_json}\n"
            f"POEM:{poem_info}\n"
            f"FULL_POEM:{full_poem}"
        )
    except Exception as exc:
        return f"生成失败：{exc}"


def run_generate_image(poem_text: str) -> str:
    from app.event_bus import _current_session_id
    return _generate_image_impl(poem_text, _current_session_id.get(""))


# 向后兼容旧函数名（main.py 迁移前）
run_visualize_poem = run_generate_image


@tool
def search_poetry(query: str) -> str:
    """
    根据用户输入在古诗词知识库中检索。

    自动判断模式：
    - 输入为诗句（典型古文特征）→ 精准模式，返回 1 首最匹配的完整诗词+译文
    - 输入为白话描述/意境词 → 模糊语义模式，返回 5 首候选，带编号供用户选择

    适用场景：用户想查找/赏析/了解某首诗，或根据意境找诗，或确认某首诗的全文和译文。
    不适合直接用于生成插画——需要生成插画时，用 visualize_poem 工具。

    Args:
        query: 古诗句原文 或 白话意境描述

    Returns:
        格式化文本：精准模式直接展示诗词全文，模糊模式展示带编号的候选列表
    """
    from app.event_bus import _current_session_id
    session_id = _current_session_id.get("")
    return _run_with_timeout(
        lambda: _search_poetry_impl(query, session_id),
        timeout_seconds=45,
        timeout_message="检索超时（45秒），可能是向量模型初始化或本地知识库负载过高，请稍后重试。"
    )


@tool
def generate_image(poem_text: str) -> str:
    """
    将一首古诗转化为多张意境插画（最多 5 张）。

    内部完整链路：RAG 检索译文 → 场景拆分（1-5 个场景）→ 并行生图。
    每个场景对应译文中一个独立画面，并行生成，提高效率。
    仅在用户明确选择"生成图片"（而非视频）时调用。

    Args:
        poem_text: 古诗原文（一联、几句或整首均可）

    Returns:
        多图结果描述，格式：
        IMAGES_JSON:[{"scene":1,"desc":"...","image_url":"...","positive":"...","negative":"..."},...]
        POEM:{诗词信息}
        FULL_POEM:{原诗全文}
    """
    from app.event_bus import _current_session_id
    import os
    session_id = _current_session_id.get("")
    # 超时配置：180s（3 分钟）基础超时，支持 COGVIEW_TIMEOUT 环境变量覆盖
    return _run_with_timeout(
        lambda: _generate_image_impl(poem_text, session_id),
        timeout_seconds=int(float(os.getenv("COGVIEW_TIMEOUT", "180"))),
        timeout_message="生图超时，可能是上游模型拥堵或网络抖动。建议：1) 稍后重试 2) 设置 COGVIEW_TIMEOUT=240 延长超时 3) 尝试降低图片质量（COGVIEW_SIZE=768x768）",
    )


# 向后兼容旧工具名（graph.py 未迁移期间）
visualize_poem = generate_image


def _generate_video_impl(poem_text: str, session_id: str = "") -> str:
    """
    LangGraph 路径的同步视频生成（阻塞执行，返回 VIDEO_RESULT:{json}）。
    流程：RAG 检索 → LLM 生成超级提示词 → Seedance 文生视频（无图像生成步骤）。
    """
    from app.modules.retriever import Retriever
    from app.modules.video_storyboard import VideoStoryboardGenerator
    import json as _json

    try:
        _push_progress(session_id, "generate_video", "rag_start", "正在检索诗词知识库…")
        result = Retriever().smart_retrieve(poem_text)
        if result.poems:
            best = result.poems[0]
            _push_rag_results(session_id, result.poems, result.mode)
            poem_info = {
                "title": best.title,
                "content": best.original_poem,
                "author": best.author,
                "translation": best.translation,
            }
            _push_progress(
                session_id, "generate_video", "rag_done",
                f"RAG 检索完成：《{best.title}》",
                detail={"title": best.title, "author": best.author},
            )
        else:
            poem_info = {
                "title": poem_text[:20],
                "content": poem_text,
                "author": "",
                "translation": poem_text,
            }

        _push_progress(session_id, "generate_video", "planning", "正在生成超级提示词…")
        generator = VideoStoryboardGenerator.from_defaults()

        plan_data: dict = {}

        def _collect(event: dict) -> None:
            if event.get("type") == "plan":
                plan_data.update(event)
                shots_count = len(event.get("shots", []))
                _push_progress(
                    session_id, "generate_video", "generating",
                    f"超级提示词生成完成（{shots_count} 个分镜设计），正在合成视频…",
                )

        video_url = generator.generate(poem_info, callback=_collect)
        _push_progress(session_id, "generate_video", "synthesizing", "视频合成完成")

        result_payload = {
            "plan": plan_data,
            "frames": [],
            "video_url": video_url,
            "error": None,
        }
        return f"VIDEO_RESULT:{_json.dumps(result_payload, ensure_ascii=False)}"

    except Exception as exc:
        import json as _json
        return f"VIDEO_RESULT:{_json.dumps({'plan': {}, 'frames': [], 'video_url': '', 'error': str(exc)}, ensure_ascii=False)}"


def run_generate_video(poem_text: str) -> str:
    from app.event_bus import _current_session_id
    return _generate_video_impl(poem_text, _current_session_id.get(""))


@tool
def generate_video(poem_text: str) -> str:
    """
    将一首古诗转化为完整分镜视频（4帧图片 + Seedance 视频合成）。

    内部完成完整链路：RAG 检索 → LLM 规划 4 镜头 → Seedream 逐帧生成（帧间视觉参考）
    → Seedance 异步视频合成（约 60-120 秒）。

    仅在用户明确选择"生成视频"时调用。调用前必须先经用户确认。
    注意：视频生成耗时较长（约 2-3 分钟），应提前告知用户。

    Args:
        poem_text: 古诗原文（推荐传入完整诗文）

    Returns:
        VIDEO_RESULT:{json} 格式字符串，包含 plan、frames 列表（含每帧 image_url）、video_url
    """
    from app.event_bus import _current_session_id
    import os
    session_id = _current_session_id.get("")
    # 超时配置：480s（8 分钟）基础超时，支持 VIDEO_TIMEOUT 环境变量覆盖
    # 视频生成包含：分镜规划 (30s) + 4 帧图像 (120s) + Seedance 合成 (60-120s) + 缓冲
    return _run_with_timeout(
        lambda: _generate_video_impl(poem_text, session_id),
        timeout_seconds=int(os.getenv("VIDEO_TIMEOUT", "480")),
        timeout_message='视频生成超时，可能是 API 拥堵或网络问题。建议：1) 稍后重试 2) 设置 VIDEO_TIMEOUT=600 延长超时 3) 检查 API 配额',
    )


# ─────────────────────────────────────────────────────────────────
# generate_storyboard 工具：实时分镜看板
# 与 generate_video 的区别：
#   - generate_video  : 静默阻塞执行，工具结束后一次性返回所有帧 URL
#   - generate_storyboard: 通过 event_bus 实时推送每一步进度事件到 SSE 客户端
#                          让前端能逐帧显示生成进度
# ─────────────────────────────────────────────────────────────────

def _generate_storyboard_impl(poem_text: str, session_id: str) -> str:
    """
    在 ThreadPool 线程中运行的同步实现。
    内部：
      1. RAG 检索 → 提取知识块
      2. 用独立事件循环驱动 StoryboardGenerator.generate()（async generator）
      3. 每个事件通过 event_bus.push_session_event() 实时推送到主循环的 Queue
      4. 返回结构化摘要字符串供 LangGraph agent 使用
    """
    import asyncio as _asyncio
    import json as _json
    from app.modules.retriever import Retriever
    from app.modules.storyboard import StoryboardGenerator
    from app.event_bus import push_session_event

    def _push(event: dict) -> None:
        """将分镜事件封装后推送到 session 队列（storyboard_ 前缀区分来源）。"""
        push_session_event(session_id, event)

    try:
        # Step 1: RAG 检索
        result = Retriever().smart_retrieve(poem_text)
        if result.poems:
            best = result.poems[0]
            poem_info = {
                "title": best.title,
                "content": best.original_poem,
                "author": best.author,
                "dynasty": best.dynasty,
            }
            knowledge_blocks = [best.to_knowledge_block()]
            poem_display = f"《{best.title}》—— {best.author}（{best.dynasty}）"
        else:
            poem_info = {"title": poem_text[:20], "content": poem_text, "author": ""}
            knowledge_blocks = []
            poem_display = poem_text[:40]

        # 通知前端 RAG 检索完成
        _push({
            "type": "storyboard_progress",
            "stage": "rag_done",
            "message": f"[完成] RAG 检索完成：{poem_display}",
        })

        # Step 2: 在独立事件循环中驱动 async generator
        collected_shots: list[dict] = []
        total_shots = 0

        async def _run_storyboard():
            nonlocal total_shots
            generator = StoryboardGenerator()
            poem_str = (
                f"《{poem_info.get('title', '')}》"
                f" {poem_info.get('author', '')} ({poem_info.get('dynasty', '')})\n\n"
                f"{poem_info.get('content', poem_text)}"
            ).strip()
            async for event in generator.generate(poem_str, knowledge_blocks):
                etype = event.get("type", "")

                if etype == "progress":
                    stage = event.get("stage", "")
                    stage_labels = {
                        "planning":    "[制作中] 正在规划分镜方案……",
                        "generating":  "[画图中] 正在逐帧生成画面……",
                        "done":        "[完成] 分镜生成完毕",
                    }
                    _push({
                        "type": "storyboard_progress",
                        "stage": stage,
                        "message": stage_labels.get(stage, f"进行中：{stage}"),
                    })

                elif etype == "plan":
                    nonlocal total_shots
                    shots = event.get("shots", [])
                    total_shots = len(shots)
                    _push({
                        "type": "plan",
                        "total_shots": total_shots,
                        "shots": shots,
                        "title": poem_info.get("title", ""),
                        "author": poem_info.get("author", ""),
                    })

                elif etype == "shot_done":
                    collected_shots.append(event)
                    _push({
                        "type": "shot_done",
                        "shot_id":   event.get("shot_id", 0),
                        "shot_name": event.get("shot_name", ""),
                        "image_url": event.get("image_url", ""),
                        "current":   event.get("current", len(collected_shots)),
                        "total":     event.get("total", total_shots),
                    })

                elif etype == "shot_error":
                    _push({
                        "type": "shot_error",
                        "shot_id":  event.get("shot_id", 0),
                        "message":  event.get("message", "生图失败"),
                    })

        _asyncio.run(_run_storyboard())

        # 返回摘要给 LangGraph Agent（用于生成最终回复）
        urls = [s.get("image_url", "") for s in collected_shots if s.get("image_url")]
        return (
            f"STORYBOARD_DONE\n"
            f"诗词：{poem_display}\n"
            f"共生成 {len(urls)}/{total_shots} 张分镜画面\n"
            f"图像 URL 列表：{_json.dumps(urls, ensure_ascii=False)}"
        )

    except Exception as exc:
        _push({
            "type": "storyboard_progress",
            "stage": "error",
            "message": f"❌ 分镜生成失败：{exc}",
        })
        return f"分镜生成失败：{exc}"


@tool
def generate_storyboard(poem_text: str) -> str:
    """
    将一首古诗转化为实时分镜看板（逐帧生成画面，边生成边展示）。

    内部完成完整链路：RAG 检索 → GLM 规划多个镜头（通常 4 帧）→ CogView-4 逐张生图。
    与 generate_video 的区别：本工具会在生成过程中**实时推送每一张图的进度**到客户端，
    用户可以看到分镜画面一张一张出现，而 generate_video 等全部完成后才推送视频 URL。

    适合"让我看看分镜效果"、"生成分镜方案"等场景；
    如果用户明确要生成视频（mp4），请改用 generate_video。
    调用前必须先经用户确认。

    Args:
        poem_text: 古诗原文（推荐传入完整诗文，一联也可）

    Returns:
        STORYBOARD_DONE 开头的摘要字符串，包含总帧数和图像 URL 列表；
        实时进度事件已在执行过程中通过 SSE 推送给前端。
    """
    from app.event_bus import _current_session_id
    session_id = _current_session_id.get()

    return _run_with_timeout(
        lambda: _generate_storyboard_impl(poem_text, session_id),
        timeout_seconds=300,
        timeout_message="STORYBOARD_DONE\n分镜生成超时（300秒），请稍后重试。",
    )

