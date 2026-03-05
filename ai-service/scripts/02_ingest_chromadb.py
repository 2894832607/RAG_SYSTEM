"""
第二阶段：JSONL → ChromaDB 向量入库

依赖：
    chromadb               向量数据库
    sentence-transformers  中文语义向量模型

运行方式（必须先跑完 01_clean_data.py）：
    D:/aaa111/Poetry-RAG-System/.venv/Scripts/python.exe ai-service/scripts/02_ingest_chromadb.py

向量模型：
    paraphrase-multilingual-MiniLM-L12-v2
    首次运行会自动从 HuggingFace 下载（约 120MB），之后缓存到本地。

存储位置：
    ai-service/data/chromadb/   ← ChromaDB 持久化目录
    集合名称：poetry_knowledge_base
"""
import json
import sys
from pathlib import Path

# ─── 路径配置 ─────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR   = SCRIPT_DIR.parent / "data"
JSONL_PATH = DATA_DIR / "gushiwen_cleaned.jsonl"
CHROMA_DIR = DATA_DIR / "chromadb"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

COLLECTION_NAME = "poetry_knowledge_base"
MODEL_NAME      = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE      = 200   # 每批写入条数

# ─── 检查源文件 ───────────────────────────────────────────────

if not JSONL_PATH.exists():
    print(f"[ERROR] 找不到清洗结果文件：{JSONL_PATH}")
    print("  请先运行：python ai-service/scripts/01_clean_data.py")
    sys.exit(1)

# ─── 加载依赖 ─────────────────────────────────────────────────

try:
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
except ImportError:
    print("[ERROR] 缺少 chromadb 依赖，请先安装：")
    print("  python -m pip install chromadb sentence-transformers")
    sys.exit(1)

# ─── 初始化 ChromaDB ──────────────────────────────────────────

print("=" * 60)
print("[1/3] 初始化 ChromaDB 和向量模型...")
print(f"  存储目录：{CHROMA_DIR}")
print(f"  向量模型：{MODEL_NAME}  （首次运行会自动下载）")
print("=" * 60)

embed_fn = SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)

client = chromadb.PersistentClient(path=str(CHROMA_DIR))

# 若集合已存在则删除后重建（全量重刷）
existing = [c.name for c in client.list_collections()]
if COLLECTION_NAME in existing:
    print(f"  集合 '{COLLECTION_NAME}' 已存在，删除后重建...")
    client.delete_collection(COLLECTION_NAME)

collection = client.create_collection(
    name=COLLECTION_NAME,
    embedding_function=embed_fn,
    metadata={"hnsw:space": "cosine"},   # 余弦相似度，适合语义检索
)
print(f"  ✓ 集合 '{COLLECTION_NAME}' 创建成功\n")

# ─── 读取 JSONL ───────────────────────────────────────────────

print("[2/3] 读取清洗后的 JSONL...")
docs = []
with open(JSONL_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            docs.append(json.loads(line))

print(f"  ✓ 共读取 {len(docs):,} 条\n")

# ─── 批量向量化写入 ───────────────────────────────────────────

print("[3/3] 向量化并写入 ChromaDB（按批次处理）...")
print(f"  批次大小：{BATCH_SIZE}")
print()

total = len(docs)
written = 0

for start in range(0, total, BATCH_SIZE):
    batch = docs[start: start + BATCH_SIZE]

    ids        = [d["id"]                              for d in batch]
    documents  = [d["search_payload"]                  for d in batch]
    metadatas  = [d["metadata"]                        for d in batch]

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    written += len(batch)
    pct = written / total * 100
    bar_done  = int(pct / 2)
    bar_left  = 50 - bar_done
    bar       = "█" * bar_done + "░" * bar_left
    print(f"  [{bar}] {pct:5.1f}%  {written:,}/{total:,}", end="\r", flush=True)

print(f"\n\n  ✓ 全部写入完成：{written:,} 条")

# ─── 快速验证 ─────────────────────────────────────────────────

print("\n" + "=" * 60)
print("验证查询（快速测试）")
print("=" * 60)

test_queries = [
    "大漠孤烟直，长河落日圆",
    "举头望明月，低头思故乡",
    "春风又绿江南岸",
]

for q in test_queries:
    results = collection.query(
        query_texts=[q],
        n_results=2,
        include=["documents", "metadatas", "distances"],
    )
    print(f"\n  查询：「{q}」")
    for i, (doc, meta, dist) in enumerate(
        zip(results["documents"][0],
            results["metadatas"][0],
            results["distances"][0])
    ):
        title  = meta.get("title", "?")
        author = meta.get("author", "?")
        sim    = 1 - dist   # cosine distance → similarity
        print(f"    Top-{i+1}  「{title}」{author}  相似度={sim:.3f}")
        print(f"           {meta.get('original_poem','')[:40]}")

print("\n" + "=" * 60)
print(f"ChromaDB 已持久化到：{CHROMA_DIR}")
print(f"集合名称：{COLLECTION_NAME}")
print(f"总条目数：{collection.count():,}")
print("=" * 60)
