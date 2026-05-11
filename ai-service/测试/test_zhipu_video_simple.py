"""简化的智谱视频测试"""
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env.local
env_path = Path(__file__).parent / ".env.local"
load_dotenv(env_path)

# 读取配置
api_key = os.getenv("VIDEO_API_KEY")
model = os.getenv("VIDEO_MODEL")

print(f"Model: {model}")
print(f"API Key: {api_key[:8]}...")

# 导入 SDK
from zai import ZhipuAiClient

# 创建客户端
client = ZhipuAiClient(api_key=api_key)

# 测试生成
prompt = "一只小狗在草地上追蝴蝶，阳光明媚，高清写实风格"
print(f"\n正在生成视频：{prompt}")

try:
    # 异步生成
    response = client.videos.generations(
        model=model,
        prompt=prompt,
        quality="quality",
        with_audio=True,
        size="1920x1080",
        fps=30,
    )
    
    task_id = response.id
    print(f"任务 ID: {task_id}")
    print("等待生成完成...")
    
    # 轮询结果（最多等待 10 分钟）
    max_wait = 600  # 秒
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        result = client.videos.retrieve_videos_result(id=task_id)
        elapsed = int(time.time() - start_time)
        print(f"[{elapsed}s] 状态：{result.task_status}")
        
        if result.task_status == "SUCCESS":
            print("[SUCCESS] 生成成功!")
            print(f"视频 URL: {result.video_result}")
            break
        elif result.task_status == "FAILED":
            print("[FAILED] 生成失败")
            break
        
        time.sleep(5)
    else:
        print(f"[TIMEOUT] 超时（{max_wait}秒）")
        
except Exception as e:
    print(f"[ERROR] 错误：{e}")
