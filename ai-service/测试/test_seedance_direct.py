"""直接测试 Seedance API，打印原始响应"""
import sys
import requests
import time
from app.config.model_config import get_video_config

config = get_video_config()
print(f"Provider: {config.provider}")
print(f"Model: {config.model}")
print(f"API Key: {config.api_key[:20]}...")
print(f"Base URL: {config.base_url}")

# 手动调用 API
headers = {
    "Authorization": f"Bearer {config.api_key}",
    "Content-Type": "application/json"
}

# 步骤 1: 创建任务
create_payload = {
    "model": config.model,
    "prompt": "一轮明月挂在天空，银色的月光洒在宁静的湖面上",
    "duration": "5s"
}

print("\n【步骤 1】创建任务...")
resp = requests.post(
    f"{config.base_url}/tasks/generations",
    headers=headers,
    json=create_payload,
    timeout=30
)
print(f"状态码：{resp.status_code}")
print(f"响应：{resp.text}")

if resp.status_code != 200:
    print(f"❌ 创建任务失败：{resp.status_code}")
    sys.exit(1)

task_data = resp.json()
task_id = task_data.get("id")
print(f"✅ Task ID: {task_id}")

# 步骤 2: 轮询状态
print(f"\n【步骤 2】轮询任务状态...")
for i in range(10):
    time.sleep(3)
    
    resp = requests.get(
        f"{config.base_url}/contents/generations/tasks/{task_id}",
        headers=headers,
        timeout=30
    )
    
    data = resp.json()
    status = data.get("status", "")
    print(f"第{i+1}次轮询 - 状态：{status}")
    
    if status == "succeeded":
        print("\n✅ 任务成功！完整响应：")
        import json
        print(json.dumps(data, ensure_ascii=False, indent=2))
        
        # 分析 content 字段
        content = data.get("content")
        print(f"\ncontent 字段类型：{type(content)}")
        print(f"content 内容：{content}")
        
        if isinstance(content, list):
            print(f"content 是数组，长度：{len(content)}")
            if len(content) > 0:
                print(f"content[0] 类型：{type(content[0])}")
                print(f"content[0] 内容：{content[0]}")
        elif isinstance(content, dict):
            print(f"content 是对象，keys: {content.keys()}")
        
        break
    
    if status == "failed":
        print(f"\n❌ 任务失败：{data.get('error')}")
        break
