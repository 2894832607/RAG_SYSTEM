"""豆包图像生成测试（REST API）"""
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
provider = os.getenv("IMAGE_PROVIDER")
base_url = os.getenv("IMAGE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Base URL: {base_url}")
print(f"API Key: {api_key[:8]}...")

# 测试生成
prompt = "一只可爱的小猫咪，坐在阳光明媚的窗台上，高清写实风格"
print(f"\n正在生成图像：{prompt}")

try:
    # 豆包 Seedream 5.0 REST API - Images Generations
    response = requests.post(
        f"{base_url}/images/generations",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        json={
            "model": model,
            "prompt": prompt,
            "sequential_image_generation": "disabled",
            "response_format": "url",
            "size": "2K",
            "stream": False,
            "watermark": True
        }
    )
    
    print(f"\nHTTP Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("[SUCCESS] 生成成功!")
        
        # 解析响应 - 豆包图片 API 返回格式
        if 'data' in result and len(result['data']) > 0:
            img_data = result['data'][0]
            if 'url' in img_data:
                print(f"URL: {img_data['url']}")
            elif 'image_url' in img_data:
                print(f"URL: {img_data['image_url']['url']}")
        else:
            print(f"响应数据：{result}")
    else:
        print(f"[FAILED] 错误：{response.text}")
        
except Exception as e:
    print(f"[ERROR] 异常：{e}")
