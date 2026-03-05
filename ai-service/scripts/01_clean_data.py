"""
第一阶段：原始数据清洗 → 标准 JSONL

运行方式：
    D:/aaa111/Poetry-RAG-System/.venv/Scripts/python.exe ai-service/scripts/01_clean_data.py

输出：
    ai-service/data/gushiwen_cleaned.jsonl   ← 主力知识库（含译文的古诗）
    ai-service/data/fewshot_examples.json    ← Few-Shot 提示词范例（精校七绝对）

目标格式（每行一个 JSON）：
{
  "id": "gushiwen_唐_李白_001",
  "search_payload": "原诗：...  权威译文：...",
  "metadata": {
    "title": "...", "author": "...", "dynasty": "...",
    "original_poem": "...", "pure_translation": "..."
  }
}
"""
import json
import re
import sys
from pathlib import Path

# ─── 路径配置 ─────────────────────────────────────────────────

BASE_DIR   = Path(__file__).resolve().parents[2]          # Poetry-RAG-System/
DATA_DIR   = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

GW_JSON    = BASE_DIR / "rag数据初步资源/gushiwen-main/gushiwen.json/gushiwen.json"
IP_PM_TXT  = BASE_DIR / "rag数据初步资源/interpoetry_prodata/data/data_pad/poem_jueju7_para.pm.txt"
IP_SW_TXT  = BASE_DIR / "rag数据初步资源/interpoetry_prodata/data/data_pad/poem_jueju7_para.sw.txt"

OUT_GW     = DATA_DIR / "gushiwen_cleaned.jsonl"
OUT_FS     = DATA_DIR / "fewshot_examples.json"

# ─── 工具函数 ─────────────────────────────────────────────────

def clean_html(text: str) -> str:
    """去除 HTML 标签、实体并规范化空白"""
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = text.replace('&nbsp;', ' ')
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def extract_translation(sons: dict) -> str:
    """
    从 sons['译文及注释']['content'] 中只提取译文正文，
    丢弃注释、参考资料等噪声。
    """
    raw = sons.get("译文及注释", {}).get("content", "")
    if not raw:
        return ""
    cleaned = clean_html(raw)
    # 截取"译文"到"注释"之间，优先取最干净的部分
    m = re.search(r'译文\s*([\s\S]*?)(?:\n注释|\n参考资料|$)', cleaned)
    if m:
        result = m.group(1).strip()
    else:
        result = cleaned
    # 去掉段内多余空格、开头的"翻译"字样
    result = re.sub(r'^[翻译：\s]+', '', result)
    # 截断超长散文（赋、词序等），保留前 600 字符
    if len(result) > 600:
        # 尝试在句子边界截断
        cut = result[:600]
        last_period = max(cut.rfind('。'), cut.rfind('！'), cut.rfind('？'))
        if last_period > 300:
            result = cut[:last_period + 1]
        else:
            result = cut + '……'
    return result.strip()


def make_id(dynasty: str, author: str, seq: int) -> str:
    """生成唯一且可读的 ID"""
    d = dynasty.replace('代', '').replace('朝', '').strip() or 'unknown'
    a = author.strip() or 'unknown'
    return f"gushiwen_{d}_{a}_{seq:05d}"


def make_search_payload(original: str, translation: str) -> str:
    return f"原诗：{original}　权威译文：{translation}"


# ─── 清洗 gushiwen.json ───────────────────────────────────────

print("=" * 60)
print("[1/2] 清洗 gushiwen.json ...")
print("=" * 60)

with open(GW_JSON, encoding="utf-8") as f:
    raw_data = json.load(f)

print(f"  原始总条目：{len(raw_data):,}")

written   = 0
skipped_no_trans = 0
skipped_short    = 0

with open(OUT_GW, "w", encoding="utf-8") as fout:
    for seq, poem in enumerate(raw_data, start=1):
        sons = poem.get("sons", {})
        if not isinstance(sons, dict):
            skipped_no_trans += 1
            continue

        translation = extract_translation(sons)
        if not translation:
            skipped_no_trans += 1
            continue

        original_raw = clean_html(poem.get("content", ""))
        # 把内容换行合并为一行（以顿号/逗号分隔）——向量化时更紧凑
        original = re.sub(r'\n+', '，', original_raw).strip('，').strip()

        if len(original) < 4:
            skipped_short += 1
            continue

        dynasty = poem.get("dynasty", "")
        author  = poem.get("author", "")
        title   = poem.get("title", "")

        doc = {
            "id": make_id(dynasty, author, seq),
            "search_payload": make_search_payload(original, translation),
            "metadata": {
                "title": title,
                "author": author,
                "dynasty": dynasty,
                "original_poem": original,
                "pure_translation": translation,
            }
        }
        fout.write(json.dumps(doc, ensure_ascii=False) + "\n")
        written += 1

        if written % 1000 == 0:
            print(f"  已处理 {written:,} 条...", end="\r", flush=True)

print(f"\n  ✓ 写出有效条目：{written:,}")
print(f"  × 跳过（无译文）：{skipped_no_trans:,}")
print(f"  × 跳过（原文过短）：{skipped_short:,}")
print(f"  → 输出：{OUT_GW}\n")


# ─── 清洗 interpoetry poem_jueju7_para ────────────────────────

print("=" * 60)
print("[2/2] 清洗 interpoetry 精校七绝对（488 条）...")
print("=" * 60)

fewshot = []
with open(IP_PM_TXT, encoding="utf-8") as fp, \
     open(IP_SW_TXT, encoding="utf-8") as fs:
    for i, (pm_line, sw_line) in enumerate(zip(fp, fs)):
        pm_line = pm_line.strip()
        sw_line = sw_line.strip()
        if not pm_line or not sw_line:
            continue
        fewshot.append({
            "id": f"interpoetry_jueju7_{i+1:04d}",
            "search_payload": make_search_payload(pm_line, sw_line),
            "metadata": {
                "title": "（七言绝句）",
                "author": "（未标注）",
                "dynasty": "（未标注）",
                "original_poem": pm_line,
                "pure_translation": sw_line,
            }
        })

with open(OUT_FS, "w", encoding="utf-8") as f:
    json.dump(fewshot, f, ensure_ascii=False, indent=2)

print(f"  ✓ 精校七绝对：{len(fewshot)} 条")
print(f"  → 输出：{OUT_FS}\n")


# ─── 汇总 ─────────────────────────────────────────────────────

print("=" * 60)
print("清洗完成，统计汇总：")
print(f"  知识库 JSONL  → {OUT_GW.name}  ({written:,} 条)")
print(f"  Few-Shot JSON → {OUT_FS.name}  ({len(fewshot)} 条)")
print("=" * 60)
