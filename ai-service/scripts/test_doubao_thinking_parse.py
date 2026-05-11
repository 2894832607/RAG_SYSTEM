import asyncio
import os

from app.modules.glm_client import GlmClient


async def main() -> None:
    os.environ["LLM_PROVIDER"] = "doubao"
    os.environ["LLM_MODEL"] = "doubao-seed-2-0-lite-260215"
    os.environ["LLM_BASE_URL"] = "https://ark.cn-beijing.volces.com/api/v3"
    os.environ["LLM_API_KEY"] = "a9610f41-5883-4e20-8324-e8fd6a974972"
    os.environ["LLM_TIMEOUT"] = "90"

    client = GlmClient()
    print("provider=", client.provider, "model=", client.model)

    chunks = 0
    chars = 0
    async for piece in client.stream_thinking("请先进行简短思考，再回答：春江花月夜的核心意境是什么？"):
        chunks += 1
        chars += len(piece)
        if chunks <= 8:
            print(f"chunk{chunks}: {piece[:60]!r}")
        if chunks >= 30:
            break

    print("chunks=", chunks, "chars=", chars)


if __name__ == "__main__":
    asyncio.run(main())
