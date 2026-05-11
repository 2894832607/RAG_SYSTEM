#!/usr/bin/env python
"""验证 GLM-5 是否返回 reasoning_content"""
import httpx
import asyncio

async def test_glm_reasoning():
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": "Bearer a76aae892cc64b7890a77632731598f5.JaPMOiyDYzTgYwkr",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "glm-5",
        "messages": [
            {"role": "user", "content": "请用一首古诗描写春天，并解释为什么选择这首诗。请展示你的思考过程。"}
        ],
        "stream": False,
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        
        print("GLM-5 响应结构:")
        print("=" * 70)
        
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            print(f"content: {message.get('content', '')[:200]}...")
            print(f"reasoning_content: {message.get('reasoning_content', '❌ 未返回')[:200] if message.get('reasoning_content') else '❌ 未返回'}...")
            
            # 打印完整响应结构（前 1000 字符）
            import json
            print("\n完整响应（前 1000 字符）:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])

if __name__ == "__main__":
    asyncio.run(test_glm_reasoning())
