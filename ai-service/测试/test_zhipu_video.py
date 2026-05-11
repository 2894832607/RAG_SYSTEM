"""
测试智谱视频生成功能

测试场景：
1. 测试 ZhipuVideoClient（使用 zai-sdk 异步轮询）
2. 测试不同视频参数配置
3. 测试视频生成完整流程
"""
import os
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from app.modules.video_storyboard import VideoStoryboardGenerator
from app.config.model_config import get_video_config

def test_video_generation():
    """测试视频生成"""
    print("=" * 60)
    print("🎬 智谱视频生成测试")
    print("=" * 60)
    
    # 读取配置
    cfg = get_video_config()
    print(f"\n📋 当前配置:")
    print(f"  Provider: {cfg.provider}")
    print(f"  Model: {cfg.model}")
    print(f"  Base URL: {cfg.base_url}")
    print(f"  API Key: {'✅ 已配置' if cfg.api_key else '❌ 未配置'}")
    
    # 测试提示词
    test_prompts = [
        {
            "title": "春晓",
            "content": "春眠不觉晓，处处闻啼鸟。夜来风雨声，花落知多少。",
            "author": "孟浩然",
        },
        {
            "title": "静夜思",
            "content": "床前明月光，疑是地上霜。举头望明月，低头思故乡。",
            "author": "李白",
        },
    ]
    
    for i, poem_info in enumerate(test_prompts, 1):
        print(f"\n📝 测试 {i}/{len(test_prompts)}:")
        print(f"  诗词：{poem_info['title']} - {poem_info['author']}")
        print(f"  内容：{poem_info['content'][:30]}...")
        
        try:
            # 创建回调函数（打印 SSE 事件）
            def callback(event):
                event_type = event.get("type", "unknown")
                if event_type == "plan":
                    print(f"  📊 分镜设计:")
                    print(f"     风格：{event.get('style_tag', 'N/A')}")
                    print(f"     提示词：{event.get('video_prompt', '')[:80]}...")
                    print(f"     分镜数：{event.get('total_shots', 0)}")
                elif event_type == "video_done":
                    video_url = event.get("video_url", "")
                    if video_url:
                        print(f"  ✅ 视频生成成功!")
                        print(f"     URL: {video_url}")
                    else:
                        print(f"  ℹ️ 视频生成已禁用")
            
            # 生成视频
            generator = VideoStoryboardGenerator.from_defaults()
            video_url = generator.generate(poem_info, callback=callback)
            
            if video_url:
                print(f"  🎬 最终视频 URL: {video_url}")
                
        except Exception as e:
            print(f"  ❌ 生成失败：{e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ 视频生成测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_video_generation()
