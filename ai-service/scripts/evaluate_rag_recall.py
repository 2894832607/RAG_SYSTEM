"""
RAG 召回率评估脚本

测试场景：
1. 精准查询（诗句）— 验证是否能准确找到原诗
2. 模糊查询（描述）— 验证语义检索的相关性排序
3. 跨域查询（多首相似诗）— 测试去重与排序

输出指标：
  - Precision@1, Precision@5 — 前K个结果的准确率
  - Recall@5 — 召回率
  - MRR — 平均排名倒数
  - NDCG — 归一化折扣累积增益
"""
import sys
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict

# 设置 UTF-8 编码输出
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 添加 ai-service 到路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.retriever import Retriever, is_poem_query, RetrievalResult


# ── 测试集合 ──────────────────────────────────────────────────────────

TEST_CASES = [
    # 类型1：精准诗句查询 (exact 模式）
    {
        "query": "大漠孤烟直，长河落日圆",
        "type": "exact",
        "expected": [
            {"title": "使至塞上", "author": "王维"},  # 这是正确答案
        ],
        "description": "王维《使至塞上》最著名诗句"
    },
    {
        "query": "举头望明月，低头思故乡",
        "type": "exact",
        "expected": [
            {"title": "静夜思", "author": "李白"},
        ],
        "description": "李白《静夜思》全诗最后两句"
    },
    {
        "query": "春风又绿江南岸，明月何时照我还",
        "type": "exact",
        "expected": [
            {"title": "泊船瓜洲", "author": "王安石"},
        ],
        "description": "王安石《泊船瓜洲》名句"
    },
    {
        "query": "生当作人杰，死亦为鬼雄",
        "type": "exact",
        "expected": [
            {"title": "夏日绝句", "author": "李清照"},
        ],
        "description": "李清照《夏日绝句》"
    },
    {
        "query": "白日依山尽，黄河入海流",
        "type": "exact",
        "expected": [
            {"title": "登鹳雀楼", "author": "王之涣"},
        ],
        "description": "王之涣《登鹳雀楼》首句"
    },
    
    # 类型2：背景描述查询（fuzzy 模式）
    {
        "query": "山河壮阔，大漠荒凉的景象",
        "type": "fuzzy",
        "expected": [
            {"title": "使至塞上", "author": "王维"},
        ],
        "description": "通过景象描述找诗"
    },
    {
        "query": "月亮下思乡的心情",
        "type": "fuzzy",
        "expected": [
            {"title": "静夜思", "author": "李白"},
        ],
        "description": "通过情感主题找诗"
    },
    {
        "query": "船上远眺，思念家乡",
        "type": "fuzzy",
        "expected": [
            {"title": "泊船瓜洲", "author": "王安石"},
        ],
        "description": "场景与情感结合"
    },
    {
        "query": "女性的爱国情怀，视死如生",
        "type": "fuzzy",
        "expected": [
            {"title": "夏日绝句", "author": "李清照"},
        ],
        "description": "价值观与气节"
    },
    {
        "query": "登楼远眺，看日落黄河",
        "type": "fuzzy",
        "expected": [
            {"title": "登鹳雀楼", "author": "王之涣"},
        ],
        "description": "景象与俯视视角"
    },
]


def mean_reciprocal_rank(results: List[Dict], expected_titles: List[str]) -> float:
    """计算 MRR（平均排名倒数）
    
    如果预期诗词在第3个位置，MRR = 1/3
    """
    for rank, result in enumerate(results, 1):
        if result.get("title") in expected_titles:
            return 1.0 / rank
    return 0.0


def precision_at_k(results: List[Dict], expected_titles: List[str], k: int) -> float:
    """计算 Precision@K"""
    if not results:
        return 0.0
    top_k = results[:k]
    hits = sum(1 for r in top_k if r.get("title") in expected_titles)
    return hits / len(top_k)


def recall_at_k(results: List[Dict], expected_titles: List[str], k: int) -> float:
    """计算 Recall@K"""
    if not expected_titles:
        return 1.0
    top_k = results[:k]
    hits = sum(1 for r in top_k if r.get("title") in expected_titles)
    return hits / len(expected_titles)


def ndcg_at_k(results: List[Dict], expected_titles: List[str], k: int) -> float:
    """计算 NDCG@K（归一化折扣累积增益）"""
    top_k = results[:k]
    dcg = 0.0
    for rank, result in enumerate(top_k, 1):
        is_relevant = 1.0 if result.get("title") in expected_titles else 0.0
        dcg += is_relevant / (1.0 + rank)
    
    # 理想 NDCG（最好情况下所有预期诗词都排在前面）
    idcg = 0.0
    for rank in range(1, min(len(expected_titles) + 1, k + 1)):
        idcg += 1.0 / (1.0 + rank)
    
    return dcg / idcg if idcg > 0 else 0.0


def evaluate():
    """运行评估"""
    print("\n" + "=" * 80)
    print("RAG 召回率评估报告")
    print("=" * 80)
    
    retriever = Retriever()
    
    # 统计指标
    stats = {
        "total": 0,
        "found_top1": 0,
        "found_top5": 0,
        "found_top15": 0,
        "p@1": [],
        "p@5": [],
        "r@5": [],
        "r@15": [],
        "mrr": [],
        "ndcg@5": [],
        "by_type": defaultdict(lambda: {"count": 0, "success": 0})
    }
    
    start_time = time.time()
    
    for i, test_case in enumerate(TEST_CASES, 1):
        query = test_case["query"]
        expected = test_case["expected"]
        expected_titles = [e["title"] for e in expected]
        expected_str = " / ".join([f"{e['title']}({e['author']})" for e in expected])
        
        print(f"\n[Test {i}/{len(TEST_CASES)}] {test_case['description']}")
        print(f"  查询: {query}")
        print(f"  预期: {expected_str}")
        
        try:
            # 执行检索
            result: RetrievalResult = retriever.smart_retrieve(query)
            
            # 提取结果元数据
            retrieved_poems = [
                {
                    "title": p.title,
                    "author": p.author,
                    "dynasty": p.dynasty,
                    "similarity": p.similarity,
                }
                for p in result.poems
            ]
            
            # 计算指标
            p1 = precision_at_k(retrieved_poems, expected_titles, 1)
            p5 = precision_at_k(retrieved_poems, expected_titles, 5)
            r5 = recall_at_k(retrieved_poems, expected_titles, 5)
            r15 = recall_at_k(retrieved_poems, expected_titles, 15)
            mrr = mean_reciprocal_rank(retrieved_poems, expected_titles)
            ndcg = ndcg_at_k(retrieved_poems, expected_titles, 5)
            
            stats["total"] += 1
            stats["p@1"].append(p1)
            stats["p@5"].append(p5)
            stats["r@5"].append(r5)
            stats["r@15"].append(r15)
            stats["mrr"].append(mrr)
            stats["ndcg@5"].append(ndcg)
            stats["by_type"][test_case["type"]]["count"] += 1
            
            if p1 > 0:
                stats["found_top1"] += 1
                stats["by_type"][test_case["type"]]["success"] += 1
            if p5 > 0:
                stats["found_top5"] += 1
            if r15 > 0:
                stats["found_top15"] += 1
            
            # 打印结果
            if retrieved_poems:
                print(f"  结果 (前5):")
                for rank, poem in enumerate(retrieved_poems[:5], 1):
                    marker = "✓" if poem["title"] in expected_titles else "✗"
                    print(f"    {rank}. {marker} {poem['title']}({poem['author']}, {poem['dynasty']}) "
                          f"相似度: {poem['similarity']:.3f}")
                if len(retrieved_poems) > 5:
                    for rank in range(6, min(len(retrieved_poems) + 1, 16)):
                        poem = retrieved_poems[rank - 1]
                        marker = "✓" if poem["title"] in expected_titles else "✗"
                        if marker == "✓":
                            print(f"    {rank}. {marker} {poem['title']}({poem['author']}, {poem['dynasty']}) "
                                  f"相似度: {poem['similarity']:.3f}")
            else:
                print(f"  结果: 无")
            
            print(f"  指标: P@1={p1:.2f} P@5={p5:.2f} R@5={r5:.2f} R@15={r15:.2f} MRR={mrr:.2f} NDCG@5={ndcg:.2f}")
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            stats["total"] += 1
            stats["by_type"][test_case["type"]]["count"] += 1
    
    elapsed = time.time() - start_time
    
    # ── 汇总统计 ──────────────────────────────────
    print("\n" + "=" * 80)
    print("汇总统计")
    print("=" * 80)
    
    if stats["total"] > 0:
        avg_p1 = sum(stats["p@1"]) / len(stats["p@1"])
        avg_p5 = sum(stats["p@5"]) / len(stats["p@5"])
        avg_r5 = sum(stats["r@5"]) / len(stats["r@5"])
        avg_r15 = sum(stats["r@15"]) / len(stats["r@15"])
        avg_mrr = sum(stats["mrr"]) / len(stats["mrr"])
        avg_ndcg = sum(stats["ndcg@5"]) / len(stats["ndcg@5"])
        
        print(f"\n整体指标:")
        print(f"  Top-1准确率:     {stats['found_top1']}/{stats['total']} ({100*stats['found_top1']/stats['total']:.1f}%)")
        print(f"  Top-5找到率:     {stats['found_top5']}/{stats['total']} ({100*stats['found_top5']/stats['total']:.1f}%)")
        print(f"  Top-15找到率:    {stats['found_top15']}/{stats['total']} ({100*stats['found_top15']/stats['total']:.1f}%)")
        print(f"  平均 P@1:        {avg_p1:.3f}")
        print(f"  平均 P@5:        {avg_p5:.3f}")
        print(f"  平均 R@5:        {avg_r5:.3f}")
        print(f"  平均 R@15:       {avg_r15:.3f}")
        print(f"  平均 MRR:        {avg_mrr:.3f}")
        print(f"  平均 NDCG@5:     {avg_ndcg:.3f}")
        print(f"  总耗时:          {elapsed:.2f}s ({elapsed/stats['total']:.2f}s/查询)")
        
        # 按类型分类
        print(f"\n按查询类型分类:")
        for qtype, info in stats["by_type"].items():
            if info["count"] > 0:
                success_rate = 100 * info["success"] / info["count"]
                print(f"  {qtype:8s}: {info['success']}/{info['count']} ({success_rate:.1f}%)")
    
    print("\n" + "=" * 80)
    print("评估完成")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    evaluate()
