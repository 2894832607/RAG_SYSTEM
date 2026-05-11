#!/usr/bin/env python
"""测试思维链功能（reasoning_content SSE 流）"""
import asyncio
import json
import httpx


async def test_reasoning_stream():
    """测试 /ai/api/v1/chat 端点的思维链接收"""
    url = "http://127.0.0.1:8000/ai/api/v1/chat"
    
    payload = {
        "message": "请用一首古诗来描写春天，并解释为什么选择这首诗",
        "session_id": "test-session-001"
    }
    
    print("=" * 70)
    print("测试思维链功能 (reasoning_content)")
    print(f"请求: POST {url}")
    print(f"消息: {payload['message']}")
    print("=" * 70)
    
    thinking_events = []
    token_events = []
    tool_events = []
    rag_events = []
    
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            async with client.stream("POST", url, json=payload) as response:
                print(f"\n响应状态: {response.status_code}")
                print("事件流:")
                print("-" * 70)
                
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data: "):
                        continue
                    
                    data_str = line[6:]
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    
                    event_type = event.get("type")
                    
                    # 只打印重要事件（思维链、token、工具、RAG）
                    if event_type == "thinking":
                        thinking_text = event.get("content", "")[:80]
                        thinking_events.append(event)
                        print(f"[思维链] {thinking_text}...")
                    
                    elif event_type == "token":
                        token_text = event.get("content", "")[:60]
                        token_events.append(event)
                        print(f"[回复] {token_text}", end="")
                    
                    elif event_type == "tool":
                        tool_events.append(event)
                        print(f"\n[工具] {event.get('name')}: {event.get('display')}")
                    
                    elif event_type == "rag_result":
                        rag_events.append(event)
                        print(f"[RAG] 检索到 {event.get('hits', 0)} 首诗词")
                    
                    elif event_type == "done":
                        print(f"\n[完成] session={event.get('session_id')}")
                
                print("\n" + "=" * 70)
                print("统计:")
                print(f"  思维链事件: {len(thinking_events)} 条")
                if thinking_events:
                    total_thinking = sum(len(e.get("content", "")) for e in thinking_events)
                    print(f"    共 {total_thinking} 个字符")
                print(f"  回复 token: {len(token_events)} 条")
                if token_events:
                    total_tokens = sum(len(e.get("content", "")) for e in token_events)
                    print(f"    共 {total_tokens} 个字符")
                print(f"  工具调用: {len(tool_events)} 次")
                print(f"  RAG 检索: {len(rag_events)} 次")
                print("=" * 70)
                
                # 最终诊断
                if thinking_events:
                    print("\n✅ 成功！思维链功能正常工作")
                    print("\n首条思维内容:")
                    print(f"  {thinking_events[0].get('content', '')[:200]}")
                else:
                    print("\n⚠️  警告：未收到任何思维链事件")
                    print("   检查 LLM_PROVIDER 是否为 'glm'")
                    print("   检查 GLM_API_KEY 是否有效")
        
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_reasoning_stream())
