from typing import Tuple

from app.agent.prompt_loader import load_prompt
from app.modules.glm_client import GlmClient

# 兜底负向提示词（中文，CogView-4 原生支持）
_FALLBACK_NEGATIVE = "低质量, 模糊, 水印, 文字, 现代建筑, 西方油画风格, 3D渲染, 动漫卡通"


class PromptEnhancer:
    def __init__(self) -> None:
        self.glm_client = GlmClient()

    def enrich(self, source_text: str, knowledge: list[str]) -> Tuple[str, str]:
        """
        增强提示词，返回 (positive_prompt, negative_prompt) 元组。

        GLM 按 02_enhance.md 模板输出两行：
            POSITIVE: ...
            NEGATIVE: ...
        若 GLM 未启用或调用失败，返回兜底 prompt。
        """
        # 将多条知识块合并，每条之间用两个换行分隔
        knowledge_text = "\n\n".join(knowledge).strip()

        fallback_positive = (
            f"高质量, 超精细, 8k分辨率, "
            f"{source_text}, 中国传统水墨画, 国画风格, 幽静恬淡"
        )

        if not self.glm_client.is_enabled():
            return fallback_positive, _FALLBACK_NEGATIVE

        # 从 prompts/chains/visualize/02_enhance.md 加载指令模板
        user_prompt = load_prompt(
            "chains/visualize/02_enhance",
            poem=source_text,
            knowledge=knowledge_text,
        )

        try:
            raw = self.glm_client.complete(user_prompt).strip()
            return _parse_dual_prompt(raw, fallback_positive)
        except Exception:
            return fallback_positive, _FALLBACK_NEGATIVE


def _parse_dual_prompt(raw: str, fallback_positive: str) -> Tuple[str, str]:
    """
    从 GLM 输出中解析 POSITIVE:/NEGATIVE: 两段。
    支持大小写不敏感，兼容多余空格/换行。
    """
    positive = fallback_positive
    negative = _FALLBACK_NEGATIVE

    for line in raw.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("POSITIVE:"):
            val = stripped[len("POSITIVE:"):].strip()
            if val:
                positive = val
        elif upper.startswith("NEGATIVE:"):
            val = stripped[len("NEGATIVE:"):].strip()
            if val:
                negative = val

    return positive, negative
