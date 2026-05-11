"""
第二阶段：JSONL -> ChromaDB 向量入库（稳定高吞吐版）

说明：
- 默认使用 BAAI/bge-m3
- 优先使用 GPU（若 torch.cuda.is_available()）
- Windows 下使用单进程编码，避免 multiprocessing spawn 问题
- 输出使用 ASCII 进度字符，避免 GBK 控制台编码报错
"""

import json
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"
JSONL_PATH = DATA_DIR / "gushiwen_cleaned.jsonl"
CHROMA_DIR = DATA_DIR / "chromadb"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

COLLECTION_NAME = "poetry_knowledge_base"
MODEL_NAME = "BAAI/bge-m3"
LOCAL_MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "bge-m3"

# 可通过环境变量覆盖
BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "64"))
MAX_SEQ_LEN = int(os.getenv("EMBED_MAX_SEQ_LEN", "192"))
CPU_THREADS = int(os.getenv("EMBED_CPU_THREADS", "8"))
EMBED_PRECISION = os.getenv("EMBED_PRECISION", "int8")

if not JSONL_PATH.exists():
    print(f"[ERROR] 找不到清洗文件: {JSONL_PATH}")
    sys.exit(1)

try:
    import chromadb
    import torch
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("[ERROR] 缺少依赖，请安装: chromadb sentence-transformers torch")
    sys.exit(1)

print("=" * 60)
print("[1/3] 初始化 ChromaDB 和向量模型...")
print(f"  存储目录: {CHROMA_DIR}")
print(f"  向量模型: {MODEL_NAME}")
print("=" * 60)

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"  推理设备: {device}")

if LOCAL_MODEL_DIR.exists():
    model_source = str(LOCAL_MODEL_DIR)
    print(f"  模型来源: 本地目录 {model_source}")
else:
    model_source = MODEL_NAME
    print("  模型来源: HuggingFace")

st_model = SentenceTransformer(model_source, device=device)
if device == "cuda":
    st_model = st_model.half()
else:
    st_model.max_seq_length = MAX_SEQ_LEN
    if CPU_THREADS > 0:
        torch.set_num_threads(CPU_THREADS)
        torch.set_num_interop_threads(max(1, min(4, CPU_THREADS // 2)))

print(f"  max_seq_length: {st_model.max_seq_length}")
if device == "cpu":
    print(f"  cpu_threads: {torch.get_num_threads()} | precision: {EMBED_PRECISION}")

client = chromadb.PersistentClient(path=str(CHROMA_DIR))
existing = [c.name for c in client.list_collections()]
if COLLECTION_NAME in existing:
    print(f"  集合 '{COLLECTION_NAME}' 已存在，删除后重建...")
    client.delete_collection(COLLECTION_NAME)

collection = client.create_collection(
    name=COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},
)
print(f"  [OK] 集合 '{COLLECTION_NAME}' 创建成功\n")

print("[2/3] 读取清洗后的 JSONL...")
docs = []
with open(JSONL_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            docs.append(json.loads(line))
print(f"  [OK] 共读取 {len(docs):,} 条\n")

print("[3/3] 向量化并写入 ChromaDB...")
print(f"  批次大小: {BATCH_SIZE}")

all_ids = [d["id"] for d in docs]
all_documents = [d["search_payload"] for d in docs]
all_metadatas = [d["metadata"] for d in docs]

total = len(docs)
written = 0
t_all = time.perf_counter()
for start in range(0, total, BATCH_SIZE):
    t_batch = time.perf_counter()
    end = min(start + BATCH_SIZE, total)
    batch_docs = all_documents[start:end]

    if device == "cpu":
        batch_embeddings = st_model.encode(
            batch_docs,
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
            precision=EMBED_PRECISION,
        ).tolist()
    else:
        batch_embeddings = st_model.encode(
            batch_docs,
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).tolist()

    collection.add(
        ids=all_ids[start:end],
        documents=batch_docs,
        metadatas=all_metadatas[start:end],
        embeddings=batch_embeddings,
    )

    written += (end - start)
    pct = written / total * 100
    elapsed = time.perf_counter() - t_batch
    done = int(pct / 2)
    bar = "#" * done + "-" * (50 - done)
    print(f"  [{bar}] {pct:5.1f}% {written:,}/{total:,} batch={elapsed:.2f}s", end="\r", flush=True)

print("\n")
print(f"  [OK] 全部写入完成: {written:,} 条")
print(f"  [OK] 总耗时: {time.perf_counter() - t_all:.1f}s")

print("\n" + "=" * 60)
print("快速验证")
print("=" * 60)
for q in ["大漠孤烟直，长河落日圆", "举头望明月，低头思故乡", "春风又绿江南岸"]:
    r = collection.query(query_texts=[q], n_results=2, include=["metadatas", "distances"])
    print(f"\n  查询: {q}")
    for i, (meta, dist) in enumerate(zip(r["metadatas"][0], r["distances"][0]), start=1):
        sim = 1 - dist
        print(f"    Top-{i} {meta.get('title', '?')} {meta.get('author', '?')} sim={sim:.3f}")

print("\n" + "=" * 60)
print(f"集合名称: {COLLECTION_NAME}")
print(f"总条目数: {collection.count():,}")
print("=" * 60)
