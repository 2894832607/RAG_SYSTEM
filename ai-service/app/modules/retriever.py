"""
RAG 检索模块 — 混合检索架构（关键词 + 语义向量）

Spec: specs/features/rag-pipeline.spec.md

两种检索模式：
  1. 精准模式（用户输入诗句）→ 关键词匹配权重高，返回 1 条最匹配结果
  2. 模糊模式（用户输入描述）→ 语义向量权重高，返回 5 条候选供用户选择

判断逻辑：输入文本含有古诗典型特征（五/七言、对仗、典型意象词等）→ 精准；否则 → 模糊
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal

logger = logging.getLogger(__name__)

# ChromaDB 持久化目录
_CHROMA_DIR = Path(__file__).resolve().parents[2] / "data" / "chromadb"
_COLLECTION_NAME = "poetry_knowledge_base"
_EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# ── 诗句判定正则 ──────────────────────────────────────────────
# 匹配典型的古诗句式：五言/七言，含逗号/句号分割
_POEM_PATTERN = re.compile(
    r"[\u4e00-\u9fff]{3,7}[，,][\u4e00-\u9fff]{3,7}[。？！]?"  # 如 "大漠孤烟直，长河落日圆"
    r"|"
    r"[\u4e00-\u9fff]{3,7}[。？！]"                              # 如 "举头望明月。"
)
# 常见古诗结构词（帮助判断是否是诗句而非描述）
_POETRY_MARKERS = re.compile(
    r"[兮矣哉乎也欤焉耶]"
    r"|[春秋冬夏]风|明月|孤帆|落日|长河|大漠|黄河|长江"
    r"|不尽|何处|独[坐钓立]|举头|低头"
)


@dataclass
class RetrievedPoem:
    """单条召回结果，携带完整结构化信息"""
    title: str
    author: str
    dynasty: str
    original_poem: str
    translation: str          # 白话译文（完整）
    search_payload: str       # ChromaDB 存储的检索文本
    similarity: float         # 余弦相似度 [0, 1]

    def to_knowledge_block(self) -> str:
        """格式化为供 PE 使用的知识块"""
        return (
            f"【{self.dynasty}·{self.author}·《{self.title}》】\n"
            f"原诗：{self.original_poem}\n"
            f"白话译文：{self.translation}\n"
            f"（语义相似度：{self.similarity:.2f}）"
        )


@dataclass
class RetrievalResult:
    """检索结果包装，携带检索模式信息"""
    mode: Literal["exact", "fuzzy"]   # exact=精准匹配, fuzzy=语义模糊
    poems: List[RetrievedPoem] = field(default_factory=list)
    needs_user_choice: bool = False   # True 表示需要用户选择


def is_poem_query(text: str) -> bool:
    """判断用户输入是否是一句古诗（而非白话描述）。

    判定规则：
    - 长度 ≤ 30 字 且 匹配五/七言句式 → True
    - 包含古诗结构词 → True
    - 其他 → False
    """
    text = text.strip()
    # 去除引号
    text_clean = text.strip("「」""''\"'《》")

    # 规则1：匹配典型五/七言句式
    if _POEM_PATTERN.search(text_clean):
        return True

    # 规则2：极短（≤20字）且不含明显白话连接词
    if len(text_clean) <= 20 and not re.search(r"[的了吗吧呢啊哦嗯]", text_clean):
        # 纯汉字比例高
        han_count = len(re.findall(r"[\u4e00-\u9fff]", text_clean))
        if han_count >= len(text_clean) * 0.8:
            return True

    # 规则3：包含古诗常见标记词
    if _POETRY_MARKERS.search(text_clean):
        # 但需排除太长的白话句
        if len(text_clean) <= 30:
            return True

    return False


class Retriever:
    """混合检索客户端：关键词 + 语义向量，自动判断检索模式。"""

    def __init__(self) -> None:
        self._collection = None

    def _get_collection(self):
        """延迟初始化 ChromaDB 连接"""
        if self._collection is not None:
            return self._collection

        try:
            import chromadb
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        except ImportError as e:
            raise RuntimeError(
                "缺少依赖：chromadb / sentence-transformers，请先安装：\n"
                "  pip install chromadb sentence-transformers"
            ) from e

        if not _CHROMA_DIR.exists():
            raise RuntimeError(
                f"ChromaDB 目录不存在：{_CHROMA_DIR}\n"
                "请先运行：python ai-service/scripts/02_ingest_chromadb.py"
            )

        embed_fn = SentenceTransformerEmbeddingFunction(model_name=_EMBED_MODEL)
        client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
        self._collection = client.get_collection(
            name=_COLLECTION_NAME,
            embedding_function=embed_fn,
        )
        logger.info("ChromaDB 已连接，集合条目数：%d", self._collection.count())
        return self._collection

    # ── 统一入口 ──────────────────────────────────────────────

    def smart_retrieve(self, query: str) -> RetrievalResult:
        """自动判断检索模式并执行。

        - 精准模式：用户输入诗句 → 关键词优先，返回 1 条
        - 模糊模式：用户输入描述 → 语义优先，返回 5 条候选
        """
        if is_poem_query(query):
            return self._exact_retrieve(query)
        else:
            return self._fuzzy_retrieve(query)

    def _exact_retrieve(self, poem_text: str) -> RetrievalResult:
        """精准检索：诗句 → 唯一匹配的完整诗词 + 译文。

        策略：
        1. 先用 ChromaDB where 文档过滤做关键词子串匹配（original_poem 字段）
        2. 若关键词命中，取相似度最高的 1 条
        3. 若关键词未命中，回退到语义检索取 Top-1
        """
        collection = self._get_collection()

        # 清理用户输入：去标点、取核心片段
        clean = poem_text.strip("「」""''\"'《》，。！？、 ")

        # --- 策略1：先尝试关键词过滤（ChromaDB where_document） ---
        try:
            keyword_results = collection.query(
                query_texts=[clean],
                n_results=3,
                where_document={"$contains": clean[:10]},  # 用诗句前10字做子串匹配
                include=["documents", "metadatas", "distances"],
            )
            keyword_poems = self._parse_results(keyword_results)
            if keyword_poems:
                # 取关键词命中中相似度最高的
                best = max(keyword_poems, key=lambda p: p.similarity)
                logger.info("精准检索命中(关键词)：%s·《%s》 sim=%.3f",
                            best.author, best.title, best.similarity)
                return RetrievalResult(mode="exact", poems=[best])
        except Exception as e:
            logger.debug("关键词过滤失败，回退语义检索: %s", e)

        # --- 策略2：回退语义检索 Top-1 ---
        sem_results = collection.query(
            query_texts=[clean],
            n_results=1,
            include=["documents", "metadatas", "distances"],
        )
        sem_poems = self._parse_results(sem_results)
        if sem_poems:
            logger.info("精准检索命中(语义回退)：%s·《%s》 sim=%.3f",
                        sem_poems[0].author, sem_poems[0].title, sem_poems[0].similarity)
        return RetrievalResult(mode="exact", poems=sem_poems[:1])

    def _fuzzy_retrieve(self, description: str) -> RetrievalResult:
        """模糊检索：描述文本 → 语义向量检索，返回 5 条候选。"""
        collection = self._get_collection()

        results = collection.query(
            query_texts=[description],
            n_results=5,
            include=["documents", "metadatas", "distances"],
        )
        poems = self._parse_results(results)

        # 过滤掉相似度极低的（< 0.3）
        poems = [p for p in poems if p.similarity >= 0.3]

        logger.info("模糊检索：返回 %d 首候选", len(poems))
        return RetrievalResult(
            mode="fuzzy",
            poems=poems,
            needs_user_choice=len(poems) > 1,
        )

    # ── 兼容旧接口 ───────────────────────────────────────────

    def fetch(self, query: str, n_results: int = 3) -> List[str]:
        """兼容旧调用，返回格式化知识块列表。"""
        result = self.smart_retrieve(query)
        return [p.to_knowledge_block() for p in result.poems[:n_results]]

    def fetch_poems(self, query: str, n_results: int = 3) -> List[RetrievedPoem]:
        """兼容旧调用，返回 RetrievedPoem 列表。"""
        result = self.smart_retrieve(query)
        return result.poems[:n_results]

    # ── 内部解析 ──────────────────────────────────────────────

    def _parse_results(self, results: dict) -> List[RetrievedPoem]:
        """将 ChromaDB query 结果转为 RetrievedPoem 列表。"""
        if not results["documents"] or not results["documents"][0]:
            return []

        poems: List[RetrievedPoem] = []
        docs      = results["documents"][0]
        metas     = results["metadatas"][0]
        distances = results["distances"][0]

        for doc, meta, dist in zip(docs, metas, distances):
            similarity = max(0.0, 1.0 - dist)

            # FR-RAG-10: original_poem 为空时，从 search_payload 中 fallback 提取
            # search_payload 格式："原诗：{original}\u3000权威译文：{translation}"
            original_poem = meta.get("original_poem", "").strip()
            if not original_poem and doc:
                import re as _re
                _m = _re.search(r"原诗[：:](.+?)(?:\u3000权威译文|\n权威译文|$)", doc, _re.DOTALL)
                if _m:
                    original_poem = _m.group(1).strip()

            poems.append(RetrievedPoem(
                title         = meta.get("title", "未知"),
                author        = meta.get("author", "未知"),
                dynasty       = meta.get("dynasty", ""),
                original_poem = original_poem,
                translation   = meta.get("pure_translation", "").strip(),
                search_payload= doc,
                similarity    = similarity,
            ))

        return poems
