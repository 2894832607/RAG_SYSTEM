from app.agent.prompt_loader import load_prompt
from app.modules.glm_client import GlmClient


class PromptEnhancer:
    def __init__(self) -> None:
        self.glm_client = GlmClient()

    def enrich(self, source_text: str, knowledge: list[str]) -> str:
        summary = " ".join(knowledge).strip()
        fallback = f"{source_text} | {summary} | 中国传统水墨, 青绿山水, 8k, 高光, 神秘氛围"

        if not self.glm_client.is_enabled():
            return fallback

        # 从 prompts/chains/visualize/02_enhance.md 加载指令模板
        user_prompt = load_prompt(
            "chains/visualize/02_enhance",
            poem=source_text,
            knowledge=summary,
        )

        try:
            return self.glm_client.complete(user_prompt)
        except Exception:
            return fallback
