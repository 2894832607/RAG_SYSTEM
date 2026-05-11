"""
RAG 检索模块 — 混合检索架构（关键词 + 语义向量）

Spec: specs/features/rag-pipeline.spec.md

两种检索模式：
  1. 精准模式（用户输入诗句）→ 关键词匹配权重高，返回 1 条最匹配结果
  2. 模糊模式（用户输入描述）→ 语义向量权重高，返回 5 条候选供用户选择

判断逻辑：输入文本含有古诗典型特征（五/七言、对仗、典型意象词等）→ 精准；否则 → 模糊
"""

import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)

# ChromaDB 持久化目录
_CHROMA_DIR = Path(__file__).resolve().parents[2] / "data" / "chromadb"
_JSONL_PATH = Path(__file__).resolve().parents[2] / "data" / "gushiwen_cleaned.jsonl"
_COLLECTION_NAME = "poetry_knowledge_base"
_EMBED_MODEL = "BAAI/bge-m3"
_LOCAL_EMBED_MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "bge-m3"
_EXACT_QUERY_CANDIDATES = 12
_FUZZY_QUERY_CANDIDATES = 12
_MAX_SEMANTIC_BRANCHES = 1
_MAX_KEYWORD_BRANCHES = 1
_MAX_SENTIMENT_BRANCHES = 1
_BRANCH_TOP_K = 8
_MAX_PRE_RERANK_CANDIDATES = 20
_RERANK_BYPASS_TOP1_MIN = 0.82
_RERANK_BYPASS_MARGIN_MIN = 0.08
_FUZZY_HYBRID_TOP_K = 8

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


@dataclass
class _LocalPoemRecord:
    title: str
    author: str
    dynasty: str
    original_poem: str
    translation: str
    search_payload: str


def _get_llm_client():
    """延迟获取 LLM 客户端，用于查询扩展。"""
    try:
        from app.agent.llm import get_llm
        return get_llm(temperature=0.3)
    except Exception as e:
        logger.debug("LLM 客户端不可用（查询扩展将跳过）: %s", e)
        return None


def is_poem_query(text: str) -> bool:
    """判断用户输入是否是一句古诗（而非白话描述）。

    判定规则（改进版本 v2，考虑查询扩展场景）：
    - 包含明显的白话连接词 → False （优先级最高，避免误判描述为诗句）
    - 长度 ≤ 15 字 且 匹配五/七言句式且无白话词 → True
    - 其他 → False （保留为模糊查询，触发查询扩展）
    """
    text = text.strip()
    # 去除引号
    text_clean = text.strip("「」""''\"'《》")

    # 规则0（优先）：包含明显的白话连接词 → 一定是描述（模糊查询）
    if re.search(r"[的了吗吧呢啊哦嗯，，。].*[的了吗吧呢啊哦嗯]", text_clean):
        # 含有多个白话词或白话词在中间 → 描述
        return False
    
    # 规则1：匹配典型五/七言句式（但长度不要太长）
    if len(text_clean) <= 20 and _POEM_PATTERN.search(text_clean):
        # 进一步检查：确实没有白话连接词
        if not re.search(r"[的了吗吧呢啊哦嗯]", text_clean):
            return True

    # 规则2：极短（≤15字）且全是汉字 + 古诗标记
    if len(text_clean) <= 15 and _POETRY_MARKERS.search(text_clean):
        # 纯汉字比例高且无白话词
        han_count = len(re.findall(r"[\u4e00-\u9fff]", text_clean))
        if han_count >= len(text_clean) * 0.9 and not re.search(r"[的了吗吧呢啊哦嗯]", text_clean):
            return True

    # 其他情况 → 模糊查询（触发查询扩展）
    return False


class Retriever:
    """混合检索客户端：关键词 + 语义向量，自动判断检索模式。"""

    _local_records: List[_LocalPoemRecord] | None = None
    _shared_collection = None
    _shared_embedder = None
    _shared_collection_lock = threading.Lock()
    _shared_embedder_lock = threading.Lock()

    def __init__(self) -> None:
        self._collection = Retriever._shared_collection
        self._embedder = Retriever._shared_embedder
        self._retrieval_profile = os.getenv("RAG_RETRIEVAL_PROFILE", "balanced").strip().lower()

    def _fuzzy_runtime_config(self) -> Dict[str, float | int | bool]:
        """读取模糊检索运行配置。

        profile:
          - fast: 追求低时延
          - balanced: 默认模式（速度/精度均衡）
          - accurate: 更高召回覆盖
        """
        profile = self._retrieval_profile
        if profile == "fast":
            return {
                "n_candidates": 8,
                "max_semantic_branches": 1,
                "max_keyword_branches": 0,
                "max_sentiment_branches": 0,
                "branch_top_k": 6,
                "pre_rerank_candidates": 12,
                "enable_query_expansion": False,
            }
        if profile == "accurate":
            return {
                "n_candidates": 18,
                "max_semantic_branches": 2,
                "max_keyword_branches": 2,
                "max_sentiment_branches": 1,
                "branch_top_k": 10,
                "pre_rerank_candidates": 24,
                "enable_query_expansion": True,
            }
        return {
            "n_candidates": _FUZZY_QUERY_CANDIDATES,
            "max_semantic_branches": _MAX_SEMANTIC_BRANCHES,
            "max_keyword_branches": _MAX_KEYWORD_BRANCHES,
            "max_sentiment_branches": _MAX_SENTIMENT_BRANCHES,
            "branch_top_k": _BRANCH_TOP_K,
            "pre_rerank_candidates": _MAX_PRE_RERANK_CANDIDATES,
            "enable_query_expansion": True,
        }

    @staticmethod
    def _should_bypass_translation_rerank(poems: List[RetrievedPoem]) -> bool:
        """当融合排序已经高度确定时，跳过译文重排以节省时延。"""
        if len(poems) < 2:
            return True
        top1 = poems[0].similarity
        top2 = poems[1].similarity
        return top1 >= _RERANK_BYPASS_TOP1_MIN and (top1 - top2) >= _RERANK_BYPASS_MARGIN_MIN

    def _get_collection(self):
        """延迟初始化 ChromaDB 连接"""
        if Retriever._shared_collection is not None:
            self._collection = Retriever._shared_collection
            return Retriever._shared_collection

        with Retriever._shared_collection_lock:
            if Retriever._shared_collection is not None:
                self._collection = Retriever._shared_collection
                return Retriever._shared_collection

            try:
                import chromadb
            except ImportError as e:
                raise RuntimeError(
                    "缺少依赖：chromadb / sentence-transformers，请先安装：\n"
                    "  pip install chromadb sentence-transformers"
                ) from e

            chroma_env = os.getenv("CHROMA_PATH")
            if chroma_env:
                chroma_dir = Path(chroma_env)
                if not chroma_dir.is_absolute():
                    chroma_dir = Path(__file__).resolve().parents[2] / chroma_dir
                chroma_dir = chroma_dir.resolve()
            else:
                chroma_dir = _CHROMA_DIR
            if not chroma_dir.exists():
                raise RuntimeError(
                    f"ChromaDB 目录不存在：{chroma_dir}\n"
                    "请先运行：python ai-service/scripts/02_ingest_chromadb.py"
                )

            client = chromadb.PersistentClient(path=str(chroma_dir))
            Retriever._shared_collection = client.get_collection(name=_COLLECTION_NAME)
            self._collection = Retriever._shared_collection
            logger.info(
                "ChromaDB 已连接，目录=%s, 集合=%s, 条目数=%d",
                chroma_dir,
                _COLLECTION_NAME,
                Retriever._shared_collection.count(),
            )
        return Retriever._shared_collection

    def _get_embedder(self):
        """延迟初始化查询向量模型，优先使用本地 bge-m3。"""
        if Retriever._shared_embedder is not None:
            self._embedder = Retriever._shared_embedder
            return Retriever._shared_embedder

        with Retriever._shared_embedder_lock:
            if Retriever._shared_embedder is not None:
                self._embedder = Retriever._shared_embedder
                return Retriever._shared_embedder

            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise RuntimeError("缺少依赖：sentence-transformers") from e

            model_source = str(_LOCAL_EMBED_MODEL_DIR) if _LOCAL_EMBED_MODEL_DIR.exists() else _EMBED_MODEL
            Retriever._shared_embedder = SentenceTransformer(model_source, device="cpu")
            self._embedder = Retriever._shared_embedder
            logger.info("查询向量模型已加载：%s", model_source)
        return Retriever._shared_embedder

    def _query_collection(self, query: str, n_results: int) -> dict:
        """显式生成查询向量，避免 Chroma embedding function 配置冲突。"""
        embedder = self._get_embedder()
        embedding = embedder.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).tolist()
        collection = self._get_collection()
        return collection.query(
            query_embeddings=embedding,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", "", text.strip())

    @classmethod
    def _query_terms(cls, text: str) -> List[str]:
        """抽取关键词：中文词块 + ASCII 词，兼容短诗句和白话描述。"""
        normalized = cls._normalize_text(text)
        terms: List[str] = []
        for token in re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]{2,}", normalized):
            terms.append(token.lower())
            if len(token) >= 4 and re.search(r"[\u4e00-\u9fff]", token):
                terms.extend(token[i:i + 2] for i in range(0, len(token) - 1))
        return list(dict.fromkeys(terms))

    @classmethod
    def _keyword_score(cls, query: str, poem: RetrievedPoem) -> float:
        """关键词匹配分：用于和语义分融合，范围 [0,1]。"""
        q = cls._normalize_text(query)
        if not q:
            return 0.0

        corpus = cls._normalize_text(
            "\n".join([
                poem.title,
                poem.author,
                poem.dynasty,
                poem.original_poem,
                poem.translation,
                poem.search_payload,
            ])
        ).lower()

        score = 0.0
        if q in cls._normalize_text(poem.original_poem):
            score += 0.65
        if q in cls._normalize_text(poem.title):
            score += 0.25

        terms = cls._query_terms(q)
        if terms:
            hit = sum(1 for t in terms if t in corpus)
            score += 0.35 * (hit / len(terms))

        return min(score, 1.0)

    @classmethod
    def _blend_score(
        cls,
        query: str,
        poem: RetrievedPoem,
        semantic_weight: float,
        keyword_weight: float,
    ) -> float:
        sem = max(0.0, min(poem.similarity, 1.0))
        lex = cls._keyword_score(query, poem)
        return max(0.0, min(semantic_weight * sem + keyword_weight * lex, 1.0))

    def _hybrid_rank(
        self,
        query: str,
        poems: List[RetrievedPoem],
        semantic_weight: float,
        keyword_weight: float,
    ) -> List[RetrievedPoem]:
        ranked = sorted(
            poems,
            key=lambda p: self._blend_score(query, p, semantic_weight, keyword_weight),
            reverse=True,
        )

        reranked: List[RetrievedPoem] = []
        for poem in ranked:
            # 将融合分回写到 similarity，方便下游直接使用统一分数。
            fused = self._blend_score(query, poem, semantic_weight, keyword_weight)
            reranked.append(
                RetrievedPoem(
                    title=poem.title,
                    author=poem.author,
                    dynasty=poem.dynasty,
                    original_poem=poem.original_poem,
                    translation=poem.translation,
                    search_payload=poem.search_payload,
                    similarity=fused,
                )
            )
        return reranked

    @classmethod
    def _load_local_records(cls) -> List[_LocalPoemRecord]:
        if cls._local_records is not None:
            return cls._local_records

        if not _JSONL_PATH.exists():
            raise RuntimeError(f"知识库源文件不存在：{_JSONL_PATH}")

        records: List[_LocalPoemRecord] = []
        with _JSONL_PATH.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                meta = item.get("metadata", {})
                records.append(_LocalPoemRecord(
                    title=meta.get("title", "未知"),
                    author=meta.get("author", "未知"),
                    dynasty=meta.get("dynasty", ""),
                    original_poem=meta.get("original_poem", "").strip(),
                    translation=meta.get("pure_translation", "").strip(),
                    search_payload=item.get("search_payload", ""),
                ))

        cls._local_records = records
        logger.info("本地知识库已加载，条目数：%d", len(records))
        return records

    def _fallback_exact_retrieve(self, poem_text: str) -> RetrievalResult:
        clean = poem_text.strip("「」''\"'《》，。！？、 ")
        poems = self._local_search(clean, limit=1, exact_mode=True)
        if poems:
            logger.info("精准检索命中(本地兜底)：%s·《%s》 sim=%.3f",
                        poems[0].author, poems[0].title, poems[0].similarity)
        return RetrievalResult(mode="exact", poems=poems[:1])

    def _fallback_fuzzy_retrieve(self, description: str) -> RetrievalResult:
        poems = self._local_search(description, limit=5, exact_mode=False)
        poems = [p for p in poems if p.similarity >= 0.15]
        logger.info("模糊检索(本地兜底)：返回 %d 首候选", len(poems))
        return RetrievalResult(
            mode="fuzzy",
            poems=poems,
            needs_user_choice=len(poems) > 1,
        )

    def _fast_fuzzy_retrieve_local(self, description: str) -> RetrievalResult:
        """极速模糊检索：纯本地 lexical 评分，避免向量模型冷启动耗时。"""
        expanded = self._rule_based_expand_query(description)
        desc_norm = self._normalize_text(description)

        need_female = any(w in desc_norm for w in ["女性", "女子", "女诗", "巾帼"])
        need_patriot = any(w in desc_norm for w in ["爱国", "报国", "祖国", "家国"])
        need_courage = any(w in desc_norm for w in ["视死如生", "气节", "牺牲", "慷慨", "悲壮"])

        female_terms = ["女性", "女子", "巾帼", "女侠", "女民兵", "秋瑾"]
        patriot_terms = ["爱国", "报国", "祖国", "家国", "中华", "为国", "救国", "忠义"]
        courage_terms = ["视死如生", "气节", "牺牲", "慷慨", "悲壮", "不屈", "赴死", "英烈"]

        weighted_queries: List[tuple[str, float]] = [(description, 1.0)]
        weighted_queries.extend((q, 0.55) for q in expanded.get("semantic", [])[:2])
        weighted_queries.extend((q, 0.45) for q in expanded.get("keywords", [])[:3])
        weighted_queries.extend((q, 0.35) for q in expanded.get("sentiment", [])[:2])

        dedup_weighted: List[tuple[str, float]] = []
        seen = set()
        for q, w in weighted_queries:
            nq = self._normalize_text(q)
            if not nq or nq in seen:
                continue
            seen.add(nq)
            dedup_weighted.append((q, w))

        scored_rows: List[RetrievedPoem] = []
        for record in self._load_local_records():
            text_title = self._normalize_text(record.title)
            text_poem = self._normalize_text(record.original_poem)
            text_trans = self._normalize_text(record.translation)
            text_all = (text_title + text_poem + text_trans + self._normalize_text(record.search_payload)).lower()

            total = 0.0
            for q, w in dedup_weighted:
                qn = self._normalize_text(q)
                if not qn:
                    continue

                local = 0.0
                if qn in text_title:
                    local += 0.42
                if qn in text_poem:
                    local += 0.58
                if qn in text_trans:
                    local += 0.72

                terms = self._query_terms(q)
                if terms:
                    hits = sum(1 for t in terms if self._normalize_text(t).lower() in text_all)
                    local += 0.55 * (hits / len(terms))

                total += w * min(local, 1.2)

            if total <= 0.08:
                continue

            # 意图约束：保证“女性/爱国/气节”类查询不被泛化“慷慨悲歌”文本干扰。
            if need_female and not any(t in text_all for t in female_terms):
                total *= 0.55
            if need_patriot and not any(t in text_all for t in patriot_terms):
                total *= 0.55
            if need_courage and not any(t in text_all for t in courage_terms):
                total *= 0.75

            if total <= 0.06:
                continue

            score = min(total / max(1.0, len(dedup_weighted) * 0.65), 0.99)
            scored_rows.append(
                RetrievedPoem(
                    title=record.title,
                    author=record.author,
                    dynasty=record.dynasty,
                    original_poem=record.original_poem,
                    translation=record.translation,
                    search_payload=record.search_payload,
                    similarity=score,
                )
            )

        scored_rows.sort(key=lambda p: p.similarity, reverse=True)
        top_poems = scored_rows[:15]
        logger.info("极速模糊检索(本地)：返回 %d 首候选", len(top_poems))
        return RetrievalResult(
            mode="fuzzy",
            poems=top_poems,
            needs_user_choice=len(top_poems) > 1,
        )

    def _keyword_first_retrieve(self, description: str, limit: int = _FUZZY_HYBRID_TOP_K) -> List[RetrievedPoem]:
        """关键词优先检索：命中高时直接返回，避免进入更重的语义链路。"""
        records = self._load_local_records()
        terms = self._query_terms(description)
        if not terms:
            return []

        scored: List[RetrievedPoem] = []
        for record in records:
            title = self._normalize_text(record.title).lower()
            poem = self._normalize_text(record.original_poem).lower()
            trans = self._normalize_text(record.translation).lower()
            payload = self._normalize_text(record.search_payload).lower()

            strong_hits = 0
            total = 0.0
            for t in terms:
                n = self._normalize_text(t).lower()
                if not n:
                    continue
                local = 0.0
                if n in title:
                    local += 0.45
                if n in poem:
                    local += 0.65
                if n in trans:
                    local += 0.80
                if n in payload:
                    local += 0.25
                if local >= 0.65:
                    strong_hits += 1
                total += min(local, 1.0)

            if not terms:
                continue
            score = total / len(terms)

            # 至少有一个强命中，且整体分数足够高，才认为关键词检索有效。
            if strong_hits < 1 or score < 0.42:
                continue

            scored.append(
                RetrievedPoem(
                    title=record.title,
                    author=record.author,
                    dynasty=record.dynasty,
                    original_poem=record.original_poem,
                    translation=record.translation,
                    search_payload=record.search_payload,
                    similarity=min(score, 0.99),
                )
            )

        scored.sort(key=lambda p: p.similarity, reverse=True)
        return scored[:limit]

    def _should_accept_keyword_results(self, description: str, poems: List[RetrievedPoem]) -> bool:
        """关键词优先置信门控：不够稳时继续走混合召回+精排。"""
        if not poems:
            return False

        top1 = poems[0].similarity
        top2 = poems[1].similarity if len(poems) > 1 else 0.0
        margin = top1 - top2
        term_count = len(self._query_terms(description))

        # 短查询更容易歧义，适当提高门槛；高分且有明显边际优势才短路返回。
        base_threshold = 0.56 if term_count <= 4 else 0.52
        if top1 >= 0.72:
            return True
        if top1 >= base_threshold and (len(poems) == 1 or margin >= 0.08):
            return True
        return False

    def _expand_query_with_llm(self, description: str) -> Optional[Dict[str, List[str]]]:
        """用 LLM 将查询扩展为多个语义维度。
        
        返回格式：{
            "semantic": ["扩展查询 1", "扩展查询 2", ...],
            "keywords": ["关键词 1", "关键词 2", ...],
            "sentiment": ["情感维度 1", ...]
        }
        若 LLM 不可用，返回 None。
        """
        llm = _get_llm_client()
        if llm is None:
            return self._rule_based_expand_query(description)

        prompt = f"""请将这个古诗描述分解为多个语义维度，用于向量检索优化。

用户描述：{description}

请返回 JSON 格式的扩展查询（只返回 JSON，无其他文本）：
{{
    "semantic": ["语义扩展 1", "语义扩展 2"],
    "keywords": ["关键词 1", "关键词 2"],
    "sentiment": ["情感维度"]
}}

要求：
- 保留原始含义
- 每个维度 1-3 个表达
- 避免过于宽泛或偏离主题"""

        try:
            # LLM 扩展设置短超时，避免网络抖动拖慢主检索链路。
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(llm.invoke, prompt)
                response = future.result(timeout=2.5)
            content = response.content.strip()
            # 尝试从回复中提取 JSON
            import json as json_lib
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                result = json_lib.loads(json_str)
                logger.info("查询扩展成功：%s", list(result.keys()))
                return result
        except FuturesTimeoutError:
            logger.debug("LLM 查询扩展超时，使用规则扩展")
        except Exception as e:
            logger.debug("LLM 查询扩展失败，继续单路检索: %s", e)

        return self._rule_based_expand_query(description)

    def _rule_based_expand_query(self, description: str) -> Dict[str, List[str]]:
        """规则兜底的查询扩展（无 LLM 时使用）。"""
        text = self._normalize_text(description)
        keywords = self._query_terms(description)[:6]

        semantic: List[str] = []
        sentiment: List[str] = []

        # 主题词桥接（针对古诗常见抽象表达）
        bridges = {
            "思乡": ["怀乡", "故乡", "乡愁"],
            "月亮": ["明月", "月夜", "望月"],
            "爱国": ["报国", "家国", "忠义"],
            "女性": ["女子", "巾帼", "女诗人"],
            "视死如生": ["生死", "气节", "慷慨"],
            "登楼": ["高楼", "远眺", "登高"],
            "黄河": ["大河", "河流", "落日"],
            "大漠": ["边塞", "荒凉", "塞外"],
        }

        for k, expands in bridges.items():
            if k in text:
                semantic.extend(expands)

        # 简单情绪维度补充
        if any(w in text for w in ["思", "愁", "念", "乡"]):
            sentiment.extend(["思念", "乡愁"])
        if any(w in text for w in ["爱国", "气节", "报国", "忠义"]):
            sentiment.extend(["慷慨", "悲壮"])

        expanded = {
            "semantic": list(dict.fromkeys([description, *semantic]))[:4],
            "keywords": list(dict.fromkeys(keywords))[:6],
            "sentiment": list(dict.fromkeys(sentiment))[:3],
        }
        logger.info("规则查询扩展生效：semantic=%d keywords=%d sentiment=%d",
                    len(expanded["semantic"]),
                    len(expanded["keywords"]),
                    len(expanded["sentiment"]))
        return expanded

    def _multi_path_search(
        self,
        description: str,
        expanded_queries: Optional[Dict[str, List[str]]],
        n_candidates: int = _FUZZY_QUERY_CANDIDATES,
        max_semantic_branches: int = _MAX_SEMANTIC_BRANCHES,
        max_keyword_branches: int = _MAX_KEYWORD_BRANCHES,
        max_sentiment_branches: int = _MAX_SENTIMENT_BRANCHES,
        branch_top_k: int = _BRANCH_TOP_K,
    ) -> List[RetrievedPoem]:
        """多路并行检索并融合结果。

        关键变更：每个分支内部都执行混合检索（语义 + 关键词），
        而不是仅做纯向量检索。
        """
        branch_specs: List[dict] = [
            {
                "name": "original",
                "query": description,
                "semantic_weight": 0.68,
                "keyword_weight": 0.32,
            }
        ]

        if expanded_queries:
            for i, q in enumerate(expanded_queries.get("semantic", [])[:max_semantic_branches]):
                branch_specs.append(
                    {
                        "name": f"semantic_{i}",
                        "query": q,
                        "semantic_weight": 0.72,
                        "keyword_weight": 0.28,
                    }
                )

            for i, q in enumerate(expanded_queries.get("keywords", [])[:max_keyword_branches]):
                branch_specs.append(
                    {
                        "name": f"keyword_{i}",
                        "query": q,
                        "semantic_weight": 0.55,
                        "keyword_weight": 0.45,
                    }
                )

            for i, q in enumerate(expanded_queries.get("sentiment", [])[:max_sentiment_branches]):
                branch_specs.append(
                    {
                        "name": f"sentiment_{i}",
                        "query": q,
                        "semantic_weight": 0.70,
                        "keyword_weight": 0.30,
                    }
                )

        # 去掉重复查询，避免重复计算
        deduped_specs: List[dict] = []
        seen_queries = set()
        for spec in branch_specs:
            normalized_q = self._normalize_text(spec["query"])
            if not normalized_q or normalized_q in seen_queries:
                continue
            seen_queries.add(normalized_q)
            deduped_specs.append(spec)

        # key -> {poem, max_score, sum_score, hits}
        aggregated: Dict[str, dict] = {}

        # 使用线程池并行执行多路检索（每个分支内部做混合检索）
        with ThreadPoolExecutor(max_workers=min(4, len(deduped_specs))) as executor:
            future_to_spec = {}
            for spec in deduped_specs:
                future = executor.submit(
                    self._query_collection,
                    spec["query"],
                    n_candidates,
                )
                future_to_spec[future] = spec

            for future in as_completed(future_to_spec):
                spec = future_to_spec[future]
                try:
                    results = future.result(timeout=6)
                    poems = self._parse_results(results)
                    if not poems:
                        continue

                    # 分支内执行混合检索（语义 + 关键词）
                    branch_ranked = self._hybrid_rank(
                        spec["query"],
                        poems,
                        semantic_weight=spec["semantic_weight"],
                        keyword_weight=spec["keyword_weight"],
                    )
                    branch_ranked = branch_ranked[:branch_top_k]

                    for poem in branch_ranked:
                        key = f"{poem.title}@{poem.author}"
                        if key not in aggregated:
                            aggregated[key] = {
                                "poem": poem,
                                "max_score": poem.similarity,
                                "sum_score": poem.similarity,
                                "hits": 1,
                            }
                        else:
                            row = aggregated[key]
                            row["sum_score"] += poem.similarity
                            row["hits"] += 1
                            if poem.similarity > row["max_score"]:
                                row["max_score"] = poem.similarity
                                row["poem"] = poem

                    logger.debug(
                        "多路分支[%s] 混合检索完成：query='%s' poems=%d weights=(%.2f,%.2f)",
                        spec["name"],
                        spec["query"],
                        len(branch_ranked),
                        spec["semantic_weight"],
                        spec["keyword_weight"],
                    )
                except Exception as e:
                    logger.debug("多路检索 [%s] 失败: %s", spec["name"], e)

        if not aggregated:
            logger.info("多路并行检索：无统一结果")
            return []

        # 跨分支融合：以 max score 为主，平均分为辅
        fused_poems: List[RetrievedPoem] = []
        for item in aggregated.values():
            poem = item["poem"]
            avg_score = item["sum_score"] / max(1, item["hits"])
            final_score = max(0.0, min(0.7 * item["max_score"] + 0.3 * avg_score, 1.0))
            fused_poems.append(
                RetrievedPoem(
                    title=poem.title,
                    author=poem.author,
                    dynasty=poem.dynasty,
                    original_poem=poem.original_poem,
                    translation=poem.translation,
                    search_payload=poem.search_payload,
                    similarity=final_score,
                )
            )

        fused_poems.sort(key=lambda p: p.similarity, reverse=True)
        logger.info(
            "多路并行检索：分支=%d 去重候选=%d（每分支均为混合检索）",
            len(deduped_specs),
            len(fused_poems),
        )
        return fused_poems

    def _local_search(self, query: str, limit: int, exact_mode: bool) -> List[RetrievedPoem]:
        query = query.strip()
        if not query:
            return []

        query_chars = {ch for ch in query if '\u4e00' <= ch <= '\u9fff'}
        scored: List[RetrievedPoem] = []

        for record in self._load_local_records():
            haystack = "\n".join([
                record.title,
                record.author,
                record.dynasty,
                record.original_poem,
                record.translation,
                record.search_payload,
            ])

            score = 0.0
            if query in record.original_poem:
                score += 1.0
            if query in record.title:
                score += 0.7

            if query_chars:
                matched = sum(1 for ch in query_chars if ch in haystack)
                score += matched / max(len(query_chars), 1)

            if exact_mode:
                compact_poem = re.sub(r"[^\u4e00-\u9fff]", "", record.original_poem)
                compact_query = re.sub(r"[^\u4e00-\u9fff]", "", query)
                if compact_query and compact_query in compact_poem:
                    score += 1.2

            if score <= 0:
                continue

            similarity = min(score / (2.5 if exact_mode else 2.0), 0.99)
            scored.append(RetrievedPoem(
                title=record.title,
                author=record.author,
                dynasty=record.dynasty,
                original_poem=record.original_poem,
                translation=record.translation,
                search_payload=record.search_payload,
                similarity=similarity,
            ))

        scored.sort(key=lambda poem: poem.similarity, reverse=True)
        return scored[:limit]

    # ── 统一入口 ──────────────────────────────────────────────

    def smart_retrieve(self, query: str) -> RetrievalResult:
        """自动判断检索模式并执行。

        - 精准模式：用户输入诗句 → 关键词优先，返回 1 条
        - 模糊模式：用户输入描述 → 语义优先，返回 5 条候选
        """
        if is_poem_query(query):
            # 冷启动优化：诗句型输入先走本地关键词直达，避免首轮加载向量模型导致超时。
            local_hit = self._fallback_exact_retrieve(query)
            if local_hit.poems and local_hit.poems[0].similarity >= 0.75:
                return local_hit
            return self._exact_retrieve(query)

        return self._fuzzy_retrieve(query)

    def _exact_retrieve(self, poem_text: str) -> RetrievalResult:
        """精准检索：诗句 → 唯一匹配的完整诗词 + 译文。

        策略：
        1. 先用 ChromaDB where 文档过滤做关键词子串匹配（original_poem 字段）
        2. 若关键词命中，取相似度最高的 1 条
        3. 若关键词未命中，回退到语义检索取 Top-1
        """
        try:
            self._get_collection()
        except Exception as e:
            logger.warning("ChromaDB / embedding 初始化失败，切换到本地兜底检索: %s", e)
            return self._fallback_exact_retrieve(poem_text)

        # 清理用户输入：去标点、取核心片段
        clean = poem_text.strip("「」""''\"'《》，。！？、 ")

        try:
            hybrid_candidates = self._query_collection(clean, _EXACT_QUERY_CANDIDATES)
            ranked_poems = self._hybrid_rank(
                clean,
                self._parse_results(hybrid_candidates),
                semantic_weight=0.55,
                keyword_weight=0.45,
            )
            if ranked_poems:
                best = ranked_poems[0]
                if best.similarity < 0.45:
                    fallback = self._fallback_exact_retrieve(poem_text)
                    if fallback.poems:
                        fb = fallback.poems[0]
                        logger.info(
                            "精准检索向量得分较低(%.3f)，回退关键词兜底：%s·《%s》",
                            best.similarity,
                            fb.author,
                            fb.title,
                        )
                        return RetrievalResult(mode="exact", poems=[fb])
                logger.info("精准检索命中(关键词)：%s·《%s》 sim=%.3f",
                            best.author, best.title, best.similarity)
                return RetrievalResult(mode="exact", poems=[best])
        except Exception as e:
            logger.debug("混合检索失败，回退语义检索: %s", e)

        # --- 策略2：回退语义检索 Top-1 ---
        try:
            sem_results = self._query_collection(clean, 1)
            sem_poems = self._hybrid_rank(
                clean,
                self._parse_results(sem_results),
                semantic_weight=0.6,
                keyword_weight=0.4,
            )
            if sem_poems:
                logger.info("精准检索命中(语义回退)：%s·《%s》 sim=%.3f",
                            sem_poems[0].author, sem_poems[0].title, sem_poems[0].similarity)
            return RetrievalResult(mode="exact", poems=sem_poems[:1])
        except Exception as e:
            logger.warning("ChromaDB 精准检索失败，切换到本地兜底检索: %s", e)
            return self._fallback_exact_retrieve(poem_text)

    def _fuzzy_retrieve(self, description: str) -> RetrievalResult:
        """模糊检索【方案C+Tier1扩展】：查询扩展 + 多路融合 + 译文相似度排序。
        
        策略：
        1. 用 LLM 扩展查询到多个语义维度（可选）
        2. 并行执行多路向量检索并融合（原始查询 + 扩展查询）
        3. 对每个候选的译文单独计算相似度
        4. 按照译文相似度重新排序，取 Top 15
        5. 返回给用户以供选择
        """
        try:
            self._get_collection()
        except Exception as e:
            logger.warning("ChromaDB / embedding 初始化失败，切换到本地兜底检索: %s", e)
            return self._fallback_fuzzy_retrieve(description)

        # 步骤0：关键词优先。仅高置信时短路返回；否则继续混合召回+精排。
        keyword_poems = self._keyword_first_retrieve(description, limit=_FUZZY_HYBRID_TOP_K)
        if keyword_poems and self._should_accept_keyword_results(description, keyword_poems):
            logger.info("模糊检索关键词命中：返回 %d 首候选", len(keyword_poems))
            return RetrievalResult(
                mode="fuzzy",
                poems=keyword_poems,
                needs_user_choice=len(keyword_poems) > 1,
            )
        if keyword_poems:
            logger.info("模糊检索关键词命中但置信不足，继续混合召回+精排")

        cfg = self._fuzzy_runtime_config()

        # 步骤1：查询扩展（可选）
        expanded_queries = self._expand_query_with_llm(description) if bool(cfg["enable_query_expansion"]) else None
        
        try:
            # 步骤2：多路并行检索并融合
            poems = self._multi_path_search(
                description,
                expanded_queries,
                n_candidates=min(_FUZZY_HYBRID_TOP_K, int(cfg["n_candidates"])),
                max_semantic_branches=int(cfg["max_semantic_branches"]),
                max_keyword_branches=int(cfg["max_keyword_branches"]),
                max_sentiment_branches=int(cfg["max_sentiment_branches"]),
                branch_top_k=int(cfg["branch_top_k"]),
            )
            if not poems:
                # 回退到单路检索
                logger.info("多路检索无结果，回退到单路检索")
                results = self._query_collection(description, min(_FUZZY_HYBRID_TOP_K, int(cfg["n_candidates"])))
                poems = self._parse_results(results)
        except Exception as e:
            logger.warning("多路融合检索失败，回退到单路检索: %s", e)
            try:
                results = self._query_collection(description, min(_FUZZY_HYBRID_TOP_K, int(cfg["n_candidates"])))
                poems = self._parse_results(results)
            except Exception as e2:
                logger.warning("ChromaDB 模糊检索失败，切换到本地兜底检索: %s", e2)
                return self._fallback_fuzzy_retrieve(description)

        if not poems:
            logger.info("模糊检索：无候选结果")
            return RetrievalResult(mode="fuzzy", poems=[], needs_user_choice=False)

        # 高置信度快路径：融合排序已明显区分时，直接返回，减少一次批量 embedding。
        if self._should_bypass_translation_rerank(poems):
            fast_poems = [p for p in poems if p.similarity >= 0.2][:_FUZZY_HYBRID_TOP_K]
            logger.info("模糊检索快路径：跳过译文重排，返回 %d 首候选", len(fast_poems))
            return RetrievalResult(
                mode="fuzzy",
                poems=fast_poems,
                needs_user_choice=len(fast_poems) > 1,
            )

        # 步骤2：为每首诗的译文计算相似度（译文是检索关键）
        try:
            embedder = self._get_embedder()
            query_vec = embedder.encode(
                [description],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )[0]
            
            # 先截断候选规模，再做译文重排，避免 CPU 编码成为瓶颈。
            poems = poems[: min(_FUZZY_HYBRID_TOP_K, int(cfg["pre_rerank_candidates"]))]
            translations = [p.translation for p in poems]
            translation_vecs = embedder.encode(
                translations,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
                batch_size=32,
            )
            
            # 计算余弦相似度
            import numpy as np
            translation_similarities = np.dot(translation_vecs, query_vec).tolist()
            
            # 给每首诗赋予的相似度为其译文相似度（不是原诗的相似度）
            scored_poems = []
            for poem, trans_sim in zip(poems, translation_similarities):
                scored_poems.append(RetrievedPoem(
                    title=poem.title,
                    author=poem.author,
                    dynasty=poem.dynasty,
                    original_poem=poem.original_poem,
                    translation=poem.translation,
                    search_payload=poem.search_payload,
                    similarity=max(0.0, min(float(trans_sim), 1.0)),  # 确保在 [0,1] 范围
                ))
            
            # 步骤3：按译文相似度排序，取 Top 8
            scored_poems.sort(key=lambda p: p.similarity, reverse=True)
            top_poems = scored_poems[:_FUZZY_HYBRID_TOP_K]
            
            # 过滤掉相似度过低的（降低阈值到 0.2）
            top_poems = [p for p in top_poems if p.similarity >= 0.2]
            
            logger.info("模糊检索【方案C】：返回 %d 首候选（按译文相似度排序）", len(top_poems))
            return RetrievalResult(
                mode="fuzzy",
                poems=top_poems,
                needs_user_choice=len(top_poems) > 1,
            )
            
        except Exception as e:
            logger.warning("译文相似度计算失败，回退到原始排序: %s", e)
            # 回退到原始的混合排序
            poems = self._hybrid_rank(
                description,
                poems,
                semantic_weight=0.7,
                keyword_weight=0.3,
            )
            poems = [p for p in poems if p.similarity >= 0.2][:_FUZZY_HYBRID_TOP_K]
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
        if not results.get("documents") or not results["documents"][0]:
            return []

        poems: List[RetrievedPoem] = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not metas:
            metas = [{} for _ in docs]
        if not distances:
            distances = [1.0 for _ in docs]

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
