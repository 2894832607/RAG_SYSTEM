"""
测试智谱图像生成功能（独立版本，不依赖缓存模块）

测试场景：
1. 直接从环境变量读取配置
2. 使用 zai-sdk 生成图像
3. 测试不同提示词
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env.local 文件
env_path = Path(__file__).parent / ".env.local"
load_dotenv(env_path)

print("=" * 60)
print("🎨 智谱图像生成测试")
print("=" * 60)

# 直接读取环境变量
provider = os.getenv("IMAGE_PROVIDER", "zhipu")
api_key = os.getenv("IMAGE_API_KEY")
base_url = os.getenv("IMAGE_BASE_URL")
model = os.getenv("IMAGE_MODEL")
size = os.getenv("COGVIEW_SIZE", "1024x1024")

print(f"\n📋 当前配置:")
print(f"  Provider: {provider}")
print(f"  Model: {model}")
print(f"  Base URL: {base_url}")
print(f"  Size: {size}")
print(f"  API Key: {'✅ 已配置' if api_key else '❌ 未配置'}")

# 导入 zai SDK
try:
    from zai import ZhipuAiClient
    print(f"\n✅ zai-sdk 导入成功")
except ImportError as e:
    print(f"\n❌ zai-sdk 导入失败：{e}")
    sys.exit(1)

# 创建客户端
client = ZhipuAiClient(api_key=api_key)

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
        response = client.images.generations(
            model=model,
            prompt=prompt,
        )
        
        # 提取 URL
        if response and response.data and len(response.data) > 0:
            image_url = response.data[0].url
            print(f"  ✅ 生成成功!")
            print(f"  URL: {image_url}")
        else:
            print(f"  ❌ 响应为空")
            
    except Exception as e:
        print(f"  ❌ 生成失败：{e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("✅ 图像生成测试完成")
print("=" * 60)
