from typing import List


class Retriever:
    """Placeholder retrieval client that mimics ChromaDB responses."""

    def fetch(self, source_text: str) -> List[str]:
        keywords = ["山水", "孤帆", "夕阳"]
        return [f"{source_text} => 重点意象包括：{', '.join(keywords)}。" for _ in range(2)]
