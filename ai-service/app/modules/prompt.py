class PromptEnhancer:
    def enrich(self, source_text: str, knowledge: list[str]) -> str:
        summary = ' '.join(knowledge)
        stylized = '中国传统水墨, 青绿山水, 8k, 高光, 神秘氛围'
        return f"{source_text} | {summary} | {stylized}"
