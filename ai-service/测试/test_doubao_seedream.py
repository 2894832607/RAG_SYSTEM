"""豆包图像生成测试（正确的 API）"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import requests

# 加载 .env.local
env_path = Path(__file__).parent / ".env.local"
load_dotenv(env_path)

# 读取配置
api_key = os.getenv("IMAGE_API_KEY")
model = os.getenv("IMAGE_MODEL")

print(f"Model: {model}")
print(f"API Key: {api_key[:8]}...")

# 测试生成
prompt = "一只可爱的小猫咪，坐在阳光明媚的窗台上，高清写实风格"
print(f"\n正在生成图像：{prompt}")

try:
    # 豆包 Seedream 5.0 正确的 API endpoint
    # 注意：Seedream 5.0 要求图像尺寸至少 3686400 像素 (如 1920x1920=3686400)
    response = requests.post(
        "https://ark.cn-beijing.volces.com/api/v3/images/generations",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        json={
            "model": model,
            "prompt": prompt,
            "size": "1920x1920",  # 3686400 像素，满足最低要求
            "num_images": 1
        }
    )
    
    print(f"\nHTTP Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("[SUCCESS] 生成成功!")
        print(f"响应：{result}")
    else:
        print(f"[FAILED] 错误：{response.text}")
        
except Exception as e:
    print(f"[ERROR] 异常：{e}")
    import traceback
    traceback.print_exc()
