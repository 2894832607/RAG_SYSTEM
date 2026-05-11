"""豆包视频生成测试（REST API）"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import requests
import time

# 加载 .env.local
env_path = Path(__file__).parent / ".env.local"
load_dotenv(env_path)

# 读取配置
api_key = os.getenv("VIDEO_API_KEY")
model = os.getenv("VIDEO_MODEL")
provider = os.getenv("VIDEO_PROVIDER")
base_url = os.getenv("VIDEO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Base URL: {base_url}")
print(f"API Key: {api_key[:8]}...")

# 测试生成 - 文生视频
prompt = "无人机以极快速度穿越复杂山林，带来沉浸式飞行体验"
print(f"\n正在创建视频任务：{prompt}")

try:
    # Step 1: 创建视频生成任务
    response = requests.post(
        f"{base_url}/contents/generations/tasks",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        json={
            "model": model,
            "content": [
                {
                    "type": "text",
                    "text": f"{prompt} --duration 5 --watermark true"
                }
            ]
        }
    )
    
    print(f"\n创建任务 HTTP Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"[FAILED] 创建任务失败：{response.text}")
        sys.exit(1)
    
    # 解析任务 ID
    task_data = response.json()
    task_id = task_data.get('id')
    
    if not task_id:
        print(f"[FAILED] 未找到任务 ID: {task_data}")
        sys.exit(1)
    
    print(f"✅ 任务创建成功！Task ID: {task_id}")
    
    # Step 2: 轮询等待结果
    print("\n正在等待视频生成完成...")
    max_attempts = 60  # 最多等待 5 分钟
    poll_interval = 5  # 每 5 秒查询一次
    
    for attempt in range(max_attempts):
        time.sleep(poll_interval)
        
        # 查询任务状态
        status_response = requests.get(
            f"{base_url}/contents/generations/tasks/{task_id}",
            headers={
                "Authorization": f"Bearer {api_key}"
            }
        )
        
        if status_response.status_code != 200:
            print(f"查询状态失败：{status_response.text}")
            continue
        
        status_data = status_response.json()
        status = status_data.get('status')
        
        print(f"  [{attempt + 1}/{max_attempts}] 状态：{status}")
        
        if status == 'succeeded':
            print("\n✅ 视频生成成功！")
            
            # 提取视频 URL
            if 'results' in status_data and len(status_data['results']) > 0:
                video_url = status_data['results'][0].get('video_url', {}).get('url')
                if video_url:
                    print(f"🎬 视频 URL: {video_url}")
                    break
            
            print(f"完整响应：{status_data}")
            break
            
        elif status == 'failed':
            print(f"\n❌ 视频生成失败：{status_data.get('error', {})}")
            break
            
    else:
        print(f"\n⏱️ 超时：等待超过 {max_attempts * poll_interval} 秒")
        
except Exception as e:
    print(f"[ERROR] 异常：{e}")
    import traceback
    traceback.print_exc()
