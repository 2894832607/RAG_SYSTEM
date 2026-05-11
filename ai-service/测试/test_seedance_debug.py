"""调试 Seedance API 响应格式"""
import sys
import os
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
os.system(r'.\local-env.ps1 > $null')

from app.config.model_config import get_video_config
import requests

# 获取配置
config = get_video_config()
print("=" * 60)
print("视频生成配置")
print("=" * 60)
print(f"Provider: {config.provider}")
print(f"Model: {config.model}")
print(f"Base URL: {config.base_url}")
print(f"API Key: {'✅' if config.api_key else '❌'}")
print(f"Timeout: {config.timeout}s")

# 创建任务
print("\n" + "=" * 60)
print("步骤 1: 创建任务")
print("=" * 60)

url = f"{config.base_url}/contents/generations/tasks"
headers = {
    "Authorization": f"Bearer {config.api_key}",
    "Content-Type": "application/json",
}

test_prompt = "一轮明月挂在天空，银色的月光洒在宁静的湖面上"

payload = {
    "model": config.model,
    "prompt": test_prompt,
    "duration": "5s",
}

print(f"POST {url}")
print(f"Payload: {payload}")

try:
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    print(f"\n状态码：{resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"\n创建任务响应:")
        import json
        print(json.dumps(data, ensure_ascii=False, indent=2))
        
        task_id = data.get("id")
        print(f"\nTask ID: {task_id}")
        
        if task_id:
            # 轮询状态
            print("\n" + "=" * 60)
            print("步骤 2: 轮询任务状态")
            print("=" * 60)
            
            poll_url = f"{config.base_url}/contents/generations/tasks/{task_id}"
            print(f"GET {poll_url}")
            
            for i in range(10):  # 最多轮询 10 次
                time.sleep(5)
                
                resp = requests.get(poll_url, headers=headers, timeout=30)
                data = resp.json()
                
                print(f"\n[{i+1}] 状态：{data.get('status')}")
                print(f"响应内容:")
                print(json.dumps(data, ensure_ascii=False, indent=2))
                
                if data.get("status") == "succeeded":
                    print("\n✅ 任务完成！")
                    # 检查响应结构
                    print("\n分析响应结构:")
                    print(f"  data.get('content') 类型：{type(data.get('content'))}")
                    print(f"  data.get('content') 值：{data.get('content')}")
                    break
                elif data.get("status") == "failed":
                    print(f"\n❌ 任务失败：{data.get('error')}")
                    break
    else:
        print(f"\n错误响应：{resp.text}")
        
except Exception as e:
    print(f"异常：{e}")
    import traceback
    traceback.print_exc()
