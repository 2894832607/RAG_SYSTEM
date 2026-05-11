"""简化的智谱图像测试"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env.local
env_path = Path(__file__).parent / ".env.local"
load_dotenv(env_path)

# 读取配置
api_key = os.getenv("IMAGE_API_KEY")
model = os.getenv("IMAGE_MODEL")

print(f"Model: {model}")
print(f"API Key: {api_key[:8]}...")

# 导入 SDK
from zai import ZhipuAiClient

# 创建客户端
client = ZhipuAiClient(api_key=api_key)

# 测试生成
prompt = "一只可爱的小猫咪，坐在阳光明媚的窗台上"
print(f"\n正在生成图像：{prompt}")

try:
    response = client.images.generations(
        model=model,
        prompt=prompt,
    )
    
    if response and response.data and len(response.data) > 0:
        url = response.data[0].url
        print(f"✅ 生成成功!")
        print(f"URL: {url}")
    else:
        print("❌ 响应为空")
        
except Exception as e:
    print(f"❌ 失败：{e}")
    import traceback
    traceback.print_exc()
