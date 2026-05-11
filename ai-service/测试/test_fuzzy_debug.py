"""快速测试模糊检索的排序情况"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.retriever import Retriever

retriever = Retriever()

# 测试情感主题查询
query = "月亮下思乡的心情"
print(f"查询：{query}\n")
print(f"预期：静夜思(李白)\n")

result = retriever.smart_retrieve(query)

print(f"获得 {len(result.poems)} 首诗词：")
for i, poem in enumerate(result.poems[:10], 1):
    print(f"{i:2d}. {poem.title:20s} ({poem.author:8s}) | 相似度: {poem.similarity:.3f}")
    print(f"    译文: {poem.translation[:60]}...")
    print()
