"""
Agent Tools 定义 — ReAct 架构

两个工具，职责清晰：
1. search_poetry    - 检索古诗词，返回结构化文本供 Agent 展示/推理
2. visualize_poem   - 完整可视化链路：RAG → PE → CogView-4，返回图像结果
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from langchain_core.tools import tool


_TOOL_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-tool")


def _run_with_timeout(func, timeout_seconds: float, timeout_message: str) -> str:
    future = _TOOL_EXECUTOR.submit(func)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError:
        future.cancel()
        return timeout_message


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
    from app.modules.retriever import Retriever

    def _do_search() -> str:
        try:
            result = Retriever().smart_retrieve(query)

            if not result.poems:
                return "未在知识库中找到相关诗词，请尝试换个描述方式。"

            if result.mode == "exact":
                poem = result.poems[0]
                return (
                    f"**《{poem.title}》 — {poem.author}（{poem.dynasty}）**\n\n"
                    f"**原诗：**\n{poem.original_poem}\n\n"
                    f"**白话译文：**\n{poem.translation}\n\n"
                    f"相似度：{poem.similarity:.3f}"
                )

            lines = [f"找到 {len(result.poems)} 首相关诗词：\n"]
            for i, poem in enumerate(result.poems, 1):
                lines.append(
                    f"**[{i}]** 《{poem.title}》 — {poem.author}（{poem.dynasty}） "
                    f"相似度 {poem.similarity:.2f}\n"
                    f"原诗：{poem.original_poem}\n"
                    f"译文：{poem.translation[:80]}……\n"
                )
            lines.append("请告诉我选哪首，或让我直接生成其中一首的意境插画。")
            return "\n".join(lines)
        except Exception as exc:
            return f"检索失败：{exc}"

    return _run_with_timeout(
        _do_search,
        timeout_seconds=20,
        timeout_message="检索超时（20秒），可能是向量模型初始化或本地知识库负载过高，请稍后重试。"
    )


@tool
def visualize_poem(poem_text: str) -> str:
    """
    将一首古诗转化为意境插画。

    内部完成完整链路：RAG 检索译文 → GLM 提示词增强 → CogView-4 生图。
    仅在用户明确希望将某首诗生成为图像时调用。

    Args:
        poem_text: 古诗原文（一联、几句或整首均可）

    Returns:
        生成结果描述，包含图像 URL、使用的提示词、以及诗词信息
    """
    from app.modules.generation import CogViewClient
    from app.modules.prompt import PromptEnhancer
    from app.modules.retriever import Retriever

    def _do_visualize() -> str:
        try:
            result = Retriever().smart_retrieve(poem_text)
            poems = result.poems

            if poems:
                best = poems[0]
                knowledge_blocks = [best.to_knowledge_block()]
                poem_info = f"《{best.title}》 — {best.author}（{best.dynasty}）"
                full_poem = best.original_poem
            else:
                knowledge_blocks = []
                poem_info = poem_text
                full_poem = poem_text

            positive, negative = PromptEnhancer().enrich(poem_text, knowledge_blocks)

            client = CogViewClient()
            if not client.is_enabled():
                return (
                    f"已完成提示词增强，但 GLM_API_KEY 未配置，跳过生图。\n"
                    f"诗词：{poem_info}\n"
                    f"正向提示词：{positive[:150]}"
                )

            image_url = client.generate(positive, negative_prompt=negative)

            return (
                f"IMAGE_URL:{image_url}\n"
                f"POEM:{poem_info}\n"
                f"FULL_POEM:{full_poem}\n"
                f"POSITIVE_PROMPT:{positive[:200]}\n"
                f"NEGATIVE_PROMPT:{negative[:100]}"
            )
        except Exception as exc:
            return f"生成失败：{exc}"

    return _run_with_timeout(
        _do_visualize,
        timeout_seconds=120,
        timeout_message="生图超时（120秒），可能是上游模型拥堵或网络抖动，请稍后重试。"
    )
