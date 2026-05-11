"""简化的豆包图像测试"""
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
provider = os.getenv("IMAGE_PROVIDER")

print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"API Key: {api_key[:8]}...")

# 根据 provider 选择 SDK
if provider == "seedream":
    from openai import OpenAI
    
    # 初始化客户端（豆包兼容 OpenAI API）
    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("IMAGE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    )
    
    # 测试生成
    prompt = "一只可爱的小猫咪，坐在阳光明媚的窗台上，高清写实风格"
    print(f"\n正在生成图像：{prompt}")
    
    try:
        # Seedream 5.0 调用（OpenAI 兼容格式）
        response = client.images.generate(
            model=model,
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        
        if response.data and len(response.data) > 0:
            print("[SUCCESS] 生成成功!")
            print(f"URL: {response.data[0].url}")
        else:
            print(f"[FAILED] 生成失败：{response}")
            
    except Exception as e:
        print(f"[ERROR] 错误：{e}")
else:
    print(f"不支持的 provider: {provider}")
