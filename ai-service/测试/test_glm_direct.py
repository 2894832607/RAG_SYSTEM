#!/usr/bin/env python
"""直接用 GlmClient 测试 GLM-5 思维链"""
import asyncio
from app.modules.glm_client import GlmClient


async def main():
    client = GlmClient()
    print(f"LLM Provider: {client.provider}")
    print(f"Model: {client.model}")
    print("=" * 70)
    print("流式输出 reasoning_content:")
    print("-" * 70)
    
    thinking_chars = 0
    token_chars = 0
    chunk_count = 0
    
    async for chunk in client.stream_thinking("简洁说明春天的特点（需要思考）"):
        chunk_count += 1
        print(chunk, end="", flush=True)
        thinking_chars += len(chunk)
    
    print("\n" + "=" * 70)
    print(f"总计: {chunk_count} 块，{thinking_chars} 字符")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
