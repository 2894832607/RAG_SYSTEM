"""快速测试图片和视频生成链路 - 确保所有节点可用"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.modules.generation import CogViewClient
from app.modules.video_storyboard import SeedanceClient, ViduClient
from app.config.model_config import get_image_config, get_video_config


def test_image_config():
    """测试图像配置"""
    print("=" * 60)
    print("【1】图像生成配置测试")
    print("=" * 60)
    
    config = get_image_config()
    print(f"Provider: {config.provider}")
    print(f"Model: {config.model}")
    print(f"Base URL: {config.base_url}")
    print(f"API Key: {'✅ 已配置' if config.api_key else '❌ 未配置'}")
    print(f"Timeout: {config.timeout}s")
    
    if config.provider == "disabled":
        print("❌ 图像生成已禁用")
        return False
    
    if not config.api_key:
        print("❌ API Key 未配置，无法测试")
        return False
    
    print("✅ 配置检查通过")
    return True


def test_video_config():
    """测试视频配置"""
    print("\n" + "=" * 60)
    print("【2】视频生成配置测试")
    print("=" * 60)
    
    config = get_video_config()
    print(f"Provider: {config.provider}")
    print(f"Model: {config.model}")
    print(f"Base URL: {config.base_url}")
    print(f"API Key: {'✅ 已配置' if config.api_key else '❌ 未配置'}")
    print(f"Timeout: {config.timeout}s")
    print(f"Poll Interval: {config.poll_interval}s")
    
    if config.provider == "disabled":
        print("❌ 视频生成已禁用")
        return False
    
    if not config.api_key:
        print("❌ API Key 未配置，无法测试")
        return False
    
    print("✅ 配置检查通过")
    return True


def test_image_generation():
    """测试图像生成（单场景）"""
    print("\n" + "=" * 60)
    print("【3】图像生成实测 - 单场景测试")
    print("=" * 60)
    
    config = get_image_config()
    if config.provider == "disabled" or not config.api_key:
        print("⏭️  跳过图像生成测试（API 未配置）")
        return True
    
    client = CogViewClient()
    if not client.is_enabled():
        print("❌ CogViewClient 未启用")
        return False
    
    # 简单测试提示词
    test_prompt = "一轮明月挂在天空，银色的月光洒在宁静的湖面上，湖面波光粼粼，远处有连绵的青山"
    
    print(f"测试提示词：{test_prompt}")
    print("开始生成图片...")
    
    try:
        result = client.generate(test_prompt)
        
        # CogViewClient.generate() 返回 str（图片 URL）
        if result and isinstance(result, str) and (result.startswith("http") or result.startswith("/")):
            print(f"✅ 图片生成成功！")
            print(f"图片 URL: {result}")
            return True
        else:
            print(f"❌ 图片生成失败：{result}")
            return False
            
    except Exception as e:
        print(f"❌ 图片生成异常：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_video_generation():
    """测试视频生成（单镜头）"""
    print("\n" + "=" * 60)
    print("【4】视频生成实测 - 单镜头测试")
    print("=" * 60)
    
    config = get_video_config()
    if config.provider == "disabled" or not config.api_key:
        print("⏭️  跳过视频生成测试（API 未配置）")
        return True
    
    # 根据 provider 选择客户端
    if config.provider == "seedance":
        client = SeedanceClient.from_config()
    elif config.provider == "vidu":
        client = ViduClient.from_config()
    else:
        print(f"❌ 不支持的视频 provider: {config.provider}")
        return False
    
    # 简单测试提示词
    test_prompt = "一轮明月挂在天空，银色的月光洒在宁静的湖面上"
    
    print(f"Provider: {config.provider}")
    print(f"测试提示词：{test_prompt}")
    print("开始生成视频...")
    
    try:
        result = client.generate(test_prompt)
        
        if result and isinstance(result, dict) and result.get("video_url"):
            print(f"✅ 视频生成成功！")
            print(f"视频 URL: {result['video_url']}")
            return True
        else:
            print(f"❌ 视频生成失败：{result}")
            return False
            
    except Exception as e:
        print(f"❌ 视频生成异常：{e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试流程"""
    print("\n" + "🚀" * 30)
    print("Poetry-RAG 图片和视频生成链路快速测试")
def main():
    """主测试流程"""
    print("\n" + "🚀" * 30)
    print("Poetry-RAG 图片和视频生成链路快速测试")
    print("🚀" * 30 + "\n")
    
    # 配置检查
    image_config_ok = test_image_config()
    video_config_ok = test_video_config()
    
    # 实际生成测试
    image_ok = False
    video_ok = False
    
    if image_config_ok:
        image_ok = test_image_generation()
    
    if video_config_ok:
        video_ok = test_video_generation()
    
    # 总结
    print("\n" + "=" * 60)
    print("【测试总结】")
    print("=" * 60)
    print(f"图像配置：{'✅' if image_config_ok else '❌'}")
    print(f"图像生成：{'✅' if image_ok else '❌' if image_config_ok else '⏭️'}")
    print(f"视频配置：{'✅' if video_config_ok else '❌'}")
    print(f"视频生成：{'✅' if video_ok else '❌' if video_config_ok else '⏭️'}")
    
    all_ok = image_config_ok and image_ok and video_config_ok and video_ok
    print("\n" + ("🎉 全部测试通过！" if all_ok else "⚠️  部分测试失败，请检查配置"))
    
    return all_ok


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)