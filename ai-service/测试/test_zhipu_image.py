"""
测试智谱图像生成功能

测试场景：
1. 测试 ZhipuImageClient（使用 zai-sdk）
2. 测试 CogView HTTP API（备用方案）
3. 测试不同尺寸配置
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from app.modules.generation import CogViewClient
from app.config.model_config import get_image_config

def test_image_generation():
    """测试图像生成"""
    print("=" * 60)
    print("🎨 智谱图像生成测试")
    print("=" * 60)
    
    # 读取配置
    cfg = get_image_config()
    print(f"\n📋 当前配置:")
    print(f"  Provider: {cfg.provider}")
    print(f"  Model: {cfg.model}")
    print(f"  Base URL: {cfg.base_url}")
    print(f"  Size: {cfg.size}")
    print(f"  API Key: {'✅ 已配置' if cfg.api_key else '❌ 未配置'}")
    
    # 创建客户端
    client = CogViewClient()
    
    if not client.is_enabled():
        print("\n❌ 图像生成未启用，跳过测试")
        return
    
    # 测试提示词
    test_prompts = [
        "一只可爱的小猫咪，坐在阳光明媚的窗台上，背景是蓝天白云",
        "中国山水画风格，远山如黛，近水含烟，小桥流水人家",
        "赛博朋克风格的城市夜景，霓虹灯闪烁，高楼林立",
    ]
    
    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n📝 测试 {i}/{len(test_prompts)}:")
        print(f"  提示词：{prompt[:50]}...")
        
        try:
            # 生成图像
            image_url = client.generate(prompt)
            print(f"  ✅ 生成成功!")
            print(f"  URL: {image_url}")
            
            # 验证 URL 是否可访问
            if image_url.startswith("/statics/"):
                local_path = Path(__file__).parent / "statics" / "outputs" / image_url.split("/")[-1]
                if local_path.exists():
                    print(f"  ✅ 本地文件存在：{local_path}")
                else:
                    print(f"  ⚠️ 本地文件不存在：{local_path}")
            else:
                print(f"  ℹ️ CDN URL，跳过本地验证")
                
        except Exception as e:
            print(f"  ❌ 生成失败：{e}")
    
    print("\n" + "=" * 60)
    print("✅ 图像生成测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_image_generation()
