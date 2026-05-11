"""调试 CogViewClient 实际发送的 payload"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.modules.generation import CogViewClient
from app.config.model_config import get_image_config
import json

# 获取配置
config = get_image_config()
print("=" * 60)
print("图像生成配置")
print("=" * 60)
print(f"Provider: {config.provider}")
print(f"Model: {config.model}")
print(f"Base URL: {config.base_url}")
print(f"Size: {config.size}")
print(f"API Key: {'✅' if config.api_key else '❌'}")

# 创建客户端
client = CogViewClient()
print(f"\nClient Provider: {client.provider}")
print(f"Client Size: {client.size}")
print(f"Client Model: {client.model}")

# 构建 payload（模拟 _call_api 方法）
test_prompt = "一轮明月挂在天空，银色的月光洒在宁静的湖面上，湖面波光粼粼，远处有连绵的青山"
payload = {
    "model": client.model,
    "prompt": test_prompt,
    "size": client.size,
}

if client.provider == "seedream":
    payload["response_format"] = "url"
    payload["watermark"] = True

print("\n" + "=" * 60)
print("实际发送的 Payload")
print("=" * 60)
print(json.dumps(payload, ensure_ascii=False, indent=2))

# 尝试调用
print("\n" + "=" * 60)
print("开始调用 API...")
print("=" * 60)

import httpx

url = f"{client.base_url}/images/generations"
headers = {
    "Authorization": f"Bearer {client.api_key}",
    "Content-Type": "application/json",
}

try:
    with httpx.Client(timeout=client.timeout, trust_env=False) as http_client:
        resp = http_client.post(url, json=payload, headers=headers)
        print(f"状态码：{resp.status_code}")
        print(f"\n响应头:")
        for k, v in resp.headers.items():
            print(f"  {k}: {v}")
        print(f"\n响应内容:")
        print(resp.text)
        
        # 尝试解析
        try:
            data = resp.json()
            print(f"\nJSON 解析成功:")
            print(json.dumps(data, ensure_ascii=False, indent=2))
        except:
            print("\n无法解析为 JSON")
            
except Exception as e:
    print(f"异常：{e}")
    import traceback
    traceback.print_exc()
