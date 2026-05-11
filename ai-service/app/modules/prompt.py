import json
from dataclasses import dataclass
from typing import Tuple

from app.agent.prompt_loader import load_prompt
from app.modules.glm_client import GlmClient

# 兜底负向提示词（中文，CogView-4 原生支持）
_FALLBACK_NEGATIVE = "低质量, 模糊, 水印, 文字, 现代建筑, 西方油画风格, 3D渲染, 动漫卡通"

MAX_SCENES = 5


@dataclass
class ScenePrompt:
    """单个场景的提示词对。"""
    scene: int          # 场景编号，从 1 开始
    desc: str           # 场景对应译文片段（简短描述）
    positive: str
    negative: str


class PromptEnhancer:
    def __init__(self) -> None:
        self.glm_client = GlmClient()

    def split_scenes(self, source_text: str, knowledge: list[str]) -> list[ScenePrompt]:
        """
        将诗词拆分为 1~5 个场景，每个场景返回独立的正/负向提示词。

        LLM 按 02_split_scenes.md 模板输出，每行一个 JSON 对象：
            {"scene":1,"desc":"...","positive":"...","negative":"..."}
        GLM 未启用或解析失败时，回退到单场景兜底结果。
        """
        import logging
        logger = logging.getLogger(__name__)
        
        knowledge_text = "\n\n".join(knowledge).strip()

        if not self.glm_client.is_enabled():
            logger.warning("GLM 客户端未启用，使用兜底单场景")
            return [self._fallback_scene(source_text)]

        user_prompt = load_prompt(
            "chains/visualize/02_split_scenes",
            poem=source_text,
            knowledge=knowledge_text,
        )

        try:
            raw = self.glm_client.complete(user_prompt).strip()
            logger.info(f"GLM 返回原始内容 ({len(raw)} chars):\n{raw[:500]}...")
            
            scenes = _parse_scenes(raw)
            logger.info(f"解析成功：{len(scenes)} 个场景")
            
            if scenes:
                result = scenes[:MAX_SCENES]
                if len(scenes) > MAX_SCENES:
                    logger.warning(f"裁剪场景数：{len(scenes)} -> {MAX_SCENES}")
                return result
            
            logger.warning("解析结果为空，使用兜底单场景")
        except Exception as e:
            logger.error(f"场景拆分异常：{e}", exc_info=True)

        return [self._fallback_scene(source_text)]

    def _fallback_scene(self, source_text: str) -> ScenePrompt:
        positive = (
            f"高质量, 超精细, 8k分辨率, "
            f"{source_text}, 中国传统水墨画, 国画风格, 幽静恬淡"
        )
        return ScenePrompt(scene=1, desc=source_text[:10], positive=positive, negative=_FALLBACK_NEGATIVE)


def _parse_scenes(raw: str) -> list[ScenePrompt]:
    """
    解析 LLM 输出的多行 JSON，每行一个场景对象。
    兼容多种格式：
      1. 格式化 JSON（带换行缩进）：优先使用栈匹配解析
      2. 每行一个紧凑 JSON：{"scene":1,"desc":"...","positive":"...","negative":"..."}
      3. Markdown 代码块包裹
    """
    import logging
    logger = logging.getLogger(__name__)
    
    scenes: list[ScenePrompt] = []
    
    # 策略 1: 使用栈匹配解析格式化 JSON（支持多行缩进）
    logger.info("尝试使用栈匹配解析格式化 JSON...")
    stack = []
    start_idx = None
    
    for i, char in enumerate(raw):
        if char == '{':
            if not stack:  # 第一个左括号
                start_idx = i
            stack.append(char)
        elif char == '}':
            if stack:
                stack.pop()
                if not stack:  # 所有括号闭合
                    # 提取完整的 JSON 对象
                    json_str = raw[start_idx:i+1]
                    try:
                        obj = json.loads(json_str)
                        scene_prompt = ScenePrompt(
                            scene=int(obj.get("scene", len(scenes) + 1)),
                            desc=str(obj.get("desc", ""))[:20],
                            positive=str(obj.get("positive", "")),
                            negative=str(obj.get("negative", _FALLBACK_NEGATIVE)),
                        )
                        scenes.append(scene_prompt)
                        logger.debug(f"解析成功第{len(scenes)}个：场景{scene_prompt.scene} - {scene_prompt.desc}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON 解析失败 (栈匹配): {e} | 内容：'{json_str[:100]}...'")
                    except (KeyError, ValueError) as e:
                        logger.warning(f"字段验证失败 (栈匹配): {e} | 内容：'{json_str[:100]}...'")
                    start_idx = None
    
    if scenes:
        logger.info(f"栈匹配成功：解析出 {len(scenes)} 个场景")
        return scenes
    
    # 策略 2: 回退到逐行解析（兼容旧的紧凑格式）
    logger.info("栈匹配失败，尝试逐行解析")
    for i, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("```"):
            if line:
                logger.debug(f"跳过第{i}行：'{line[:50]}...'")
            continue
        try:
            obj = json.loads(line)
            scene_prompt = ScenePrompt(
                scene=int(obj.get("scene", len(scenes) + 1)),
                desc=str(obj.get("desc", ""))[:20],
                positive=str(obj.get("positive", "")),
                negative=str(obj.get("negative", _FALLBACK_NEGATIVE)),
            )
            scenes.append(scene_prompt)
            logger.debug(f"解析成功第{i}行：场景{scene_prompt.scene} - {scene_prompt.desc}")
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败 (第{i}行): {e} | 内容：'{line[:100]}...'")
        except (KeyError, ValueError) as e:
            logger.warning(f"字段验证失败 (第{i}行): {e} | 内容：'{line[:100]}...'")
    
    return scenes
