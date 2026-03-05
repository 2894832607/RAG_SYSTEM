"""
Agent Tools 定义

三个工具：
1. search_poetry      - 用自然语言在 ChromaDB 向量库中检索相关古诗
2. enhance_prompt     - 基于诗句和用户意图，调用 GLM 生成 Stable Diffusion 提示词
3. generate_image     - 调用扩散模型生成图像（当前为 Mock，接口已定义）
"""
import os
import uuid
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

# ── ChromaDB ────────────────────────────────────────────────────

def _get_collection():
    """懒加载 ChromaDB collection，避免启动时阻塞。"""
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    chroma_dir = Path(__file__).resolve().parents[2] / "data" / "chromadb"
    embed_fn = SentenceTransformerEmbeddingFunction(
        model_name="paraphrase-multilingual-MiniLM-L12-v2"
    )
    client = chromadb.PersistentClient(path=str(chroma_dir))
    return client.get_collection(
        name="poetry_knowledge_base",
        embedding_function=embed_fn,
    )


_collection = None  # 全局缓存


def _collection_instance():
    global _collection
    if _collection is None:
        _collection = _get_collection()
    return _collection


# ── Tool 1: 检索诗词 ────────────────────────────────────────────

@tool
def search_poetry(query: str, n_results: int = 3) -> str:
    """
    根据自然语言描述在古诗词知识库中语义检索最相关的诗词。

    适用场景：
    - 用户描述某种意境/情感/场景，需要找到匹配的古诗
    - 用户提供白话文，需要找到对应的古诗原文
    - 用户输入古诗残句，需要补全或找出处

    Args:
        query: 检索查询，可以是白话文描述、意境描述或古诗残句
        n_results: 返回结果数量，默认 3

    Returns:
        格式化的检索结果文本，包含原诗、译文和相似度
    """
    try:
        collection = _collection_instance()
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        docs      = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        if not docs:
            return "未找到相关诗词。"

        lines = ["**检索到以下相关古诗：**\n"]
        for i, (meta, dist) in enumerate(zip(metadatas, distances), 1):
            similarity = round(1 - dist, 3)
            lines.append(
                f"**[{i}] 《{meta.get('title', '?')}》 — {meta.get('author', '?')}（{meta.get('dynasty', '?')}）**\n"
                f"原诗：{meta.get('original_poem', '')}\n"
                f"译文：{meta.get('pure_translation', '')[:120]}……\n"
                f"相似度：{similarity}\n"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"检索失败：{e}"


# ── Tool 2: 增强提示词 ──────────────────────────────────────────

@tool
def enhance_prompt(poem_text: str, user_description: str = "") -> str:
    """
    将古诗原文和用户的场景描述融合，生成适合 Stable Diffusion 的图像生成提示词。

    适用场景：
    - 用户确认了某首诗后，需要生成配套插画
    - 用户提供了自己的意境描述需要转为提示词

    Args:
        poem_text: 古诗原文（一联或完整诗）
        user_description: 用户对构图/风格/场景的额外要求（可留空）

    Returns:
        适合 Stable Diffusion 的英文/中文混合提示词字符串
    """
    from app.agent.llm import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm(temperature=0.6)

    fallback = (
        f"{poem_text} | {user_description} | "
        "中国传统水墨画, 青绿山水, 工笔重彩, 8k 超清, 电影级光影, 意境悠远"
    )

    if llm is None:
        return fallback

    system = SystemMessage(content=(
        "你是一位专业的 AI 图像提示词工程师，擅长将中国古典诗词转化为"
        "富有画面感的 Stable Diffusion 提示词。\n"
        "要求：\n"
        "1. 提炼诗词中的物象（山、水、月、云等）、色彩、时间、情感\n"
        "2. 输出格式：中文意象短语 + 逗号分隔 + 画风标签\n"
        "3. 只输出最终提示词，不要任何解释"
    ))
    user = HumanMessage(content=(
        f"古诗：{poem_text}\n"
        f"用户额外要求：{user_description or '无'}\n\n"
        "请生成 Stable Diffusion 提示词："
    ))

    try:
        response = llm.invoke([system, user])
        return response.content.strip() or fallback
    except Exception:
        return fallback


# ── Tool 3: 生成图像 ────────────────────────────────────────────

@tool
def generate_image(prompt: str) -> str:
    """
    根据提示词生成古诗意境插画。

    Args:
        prompt: Stable Diffusion 风格提示词

    Returns:
        图像访问 URL
    """
    # TODO: 接入真实 Stable Diffusion API（ComfyUI / 商业 API）
    image_name = f"{uuid.uuid4()}.png"
    image_url  = f"/statics/outputs/{image_name}"
    return (
        f"图像已生成！\n"
        f"访问地址：{image_url}\n"
        f"使用提示词：{prompt[:80]}……"
    )
