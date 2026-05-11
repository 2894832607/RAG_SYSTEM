"""端到端测试：验证豆包和 GLM 的真实链路集成

测试流程：
1. 测试 GLM 文本生成（思维链）
2. 测试豆包图像生成（Seedream 5.0）
3. 测试完整的诗歌→图像生成链路

Spec: specs/features/poetry-visualization.spec.md §4 验收标准
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env.local
env_path = Path(__file__).parent / ".env.local"
load_dotenv(env_path)

print("=" * 80)
print("端到端测试：豆包 + GLM 真实链路验证")
print("=" * 80)
print()


# =============================================================================
# 测试 1: GLM 文本生成
# =============================================================================
async def test_glm_text():
    """测试 GLM 文本生成（思维链模式）"""
    print("\n【测试 1】GLM 文本生成")
    print("-" * 80)
    
    try:
        from app.modules.glm_client import GlmClient
        
        client = GlmClient()
        print(f"✓ Provider: {client.provider}")
        print(f"✓ Model: {client.model}")
        print(f"✓ Base URL: {client.base_url}")
        
        if not client.is_enabled():
            print("✗ GLM 未启用，跳过测试")
            return False
        
        # 测试简单生成
        prompt = "请用一句话描述春天的美景"
        print(f"\n正在生成：{prompt}")
        result = client.complete(prompt)
        print(f"✓ 生成成功 ({len(result)} 字符)")
        print(f"内容：{result[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


# =============================================================================
# 测试 2: 豆包图像生成
# =============================================================================
def test_doubao_image():
    """测试豆包 Seedream 5.0 图像生成"""
    print("\n【测试 2】豆包图像生成")
    print("-" * 80)
    
    try:
        from app.modules.generation import CogViewClient
        
        client = CogViewClient()
        print(f"✓ Provider: {client.provider}")
        print(f"✓ Model: {client.model}")
        print(f"✓ Base URL: {client.base_url}")
        
        if not client.is_enabled():
            print("✗ 图像生成未启用，跳过测试")
            return False
        
        # 测试图像生成
        prompt = "一只可爱的小猫咪，坐在阳光明媚的窗台上，高清写实风格"
        print(f"\n正在生成图像：{prompt}")
        
        url = client.generate(prompt)
        print(f"✓ 生成成功")
        print(f"URL: {url[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


# =============================================================================
# 测试 3: 完整链路（诗歌→增强→图像）
# =============================================================================
def test_full_pipeline():
    """测试完整的诗歌可视化链路"""
    print("\n【测试 3】完整链路：诗歌→增强→图像生成")
    print("-" * 80)
    
    try:
        from app.modules.pipeline import generate_once
        
        # 测试诗歌
        poem = "春眠不觉晓，处处闻啼鸟。夜来风雨声，花落知多少。"
        print(f"输入诗歌：{poem}")
        
        print("\n正在执行完整链路...")
        print("1. 意图识别 → 2. 检索增强 → 3. Prompt 优化 → 4. 图像生成")
        
        result = generate_once(poem)
        
        print(f"\n✓ 链路执行成功")
        print(f"增强后的 Prompt: {result.enhancedPrompt[:100]}...")
        print(f"负面提示词：{result.negativePrompt or '无'}")
        print(f"图像 URL: {result.imageUrl[:80] if result.imageUrl else '未生成'}...")
        print(f"检索文本：{result.retrievedText[:100] if result.retrievedText else '无'}...")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


# =============================================================================
# 主函数
# =============================================================================
async def main():
    results = {
        "GLM 文本": await test_glm_text(),
        "豆包图像": test_doubao_image(),
        "完整链路": test_full_pipeline(),
    }
    
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(results.values())
    print("=" * 80)
    
    if all_passed:
        print("🎉 所有测试通过！豆包和 GLM 已成功集成到真实链路。")
        sys.exit(0)
    else:
        print("⚠ 部分测试失败，请检查日志。")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
