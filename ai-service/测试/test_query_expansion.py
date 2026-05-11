#!/usr/bin/env python3
"""
测试查询扩展 + 多路融合功能
用于验证 Tier 1 创新点的改进效果
"""
import sys
import os
import time
from pathlib import Path
from typing import List, Dict

# 添加 ai-service 到路径
sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from app.modules.retriever import Retriever


def test_query_expansion():
    """测试单个模糊查询的改进效果"""
    retriever = Retriever()
    
    test_queries = [
        {
            "query": "女性的爱国情怀，视死如生",
            "expected_title": "夏日绝句",
            "expected_author": "李清照",
            "desc": "Test 8 - 高度抽象查询"
        },
        {
            "query": "月亮下思乡的心情",
            "expected_title": "静夜思",
            "expected_author": "李白",
            "desc": "Test 7 - 情感主题"
        },
        {
            "query": "登楼远眺，看日落黄河",
            "expected_title": "登鹳雀楼",
            "expected_author": "王之涣",
            "desc": "Test 10 - 场景结合"
        },
        {
            "query": "船上远眺，思念家乡",
            "expected_title": "泊船瓜洲",
            "expected_author": "王安石",
            "desc": "Test 9 - 场景与情感"
        },
    ]
    
    results_summary = {
        "top1_hit": 0,
        "top5_hit": 0,
        "top15_hit": 0,
        "mrr": 0.0,
        "total_time": 0.0,
    }
    
    print("\n" + "="*80)
    print("测试查询扩展 + 多路融合效果")
    print("="*80)
    
    for i, test_case in enumerate(test_queries, 1):
        query = test_case["query"]
        expected_title = test_case["expected_title"]
        expected_author = test_case["expected_author"]
        
        print(f"\n【Test {i}】{test_case['desc']}")
        print(f"查询: {query}")
        print(f"预期: 《{expected_title}》- {expected_author}")
        
        start = time.time()
        result = retriever.smart_retrieve(query)
        elapsed = time.time() - start
        results_summary["total_time"] += elapsed
        
        print(f"\n返回 {len(result.poems)} 首诗词（耗时 {elapsed:.2f}s）:")
        
        found_rank = None
        for rank, poem in enumerate(result.poems, 1):
            marker = ""
            if poem.title == expected_title and poem.author == expected_author:
                found_rank = rank
                marker = " ✓ 【找到！】"
            print(f"  {rank:2d}. {poem.dynasty}·{poem.author}·《{poem.title}》"
                  f" (相似度: {poem.similarity:.3f}){marker}")
        
        # 统计指标
        if found_rank:
            print(f"\n✅ 在第 {found_rank} 位找到预期诗词")
            if found_rank <= 1:
                results_summary["top1_hit"] += 1
            if found_rank <= 5:
                results_summary["top5_hit"] += 1
            if found_rank <= 15:
                results_summary["top15_hit"] += 1
            results_summary["mrr"] += 1.0 / found_rank
        else:
            print(f"\n❌ 未在Top15中找到预期诗词")
    
    # 打印汇总
    print("\n" + "="*80)
    print("【汇总统计】")
    print("="*80)
    print(f"Top-1准确率:     {results_summary['top1_hit']}/{len(test_queries)} "
          f"({100*results_summary['top1_hit']/len(test_queries):.1f}%)")
    print(f"Top-5找到率:     {results_summary['top5_hit']}/{len(test_queries)} "
          f"({100*results_summary['top5_hit']/len(test_queries):.1f}%)")
    print(f"Top-15找到率:    {results_summary['top15_hit']}/{len(test_queries)} "
          f"({100*results_summary['top15_hit']/len(test_queries):.1f}%)")
    print(f"平均 MRR:       {results_summary['mrr']/len(test_queries):.3f}")
    print(f"总耗时:         {results_summary['total_time']:.2f}s")
    print(f"平均耗时/查询:  {results_summary['total_time']/len(test_queries):.2f}s")
    print()


if __name__ == "__main__":
    test_query_expansion()
