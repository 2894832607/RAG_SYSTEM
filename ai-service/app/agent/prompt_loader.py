"""
prompt_loader.py — Prompt 文件加载器

将 prompts/ 目录下的 .md 文件加载为字符串，支持变量插值。

使用方式：
    from app.agent.prompt_loader import load_prompt

    # 静态加载（无变量）
    system_prompt = load_prompt("system/main_agent")

    # 带变量插值
    router_prompt = load_prompt(
        "planner/intent_router",
        user_message="帮我画首诗",
        history="无"
    )

文件路径规则：
    load_prompt("system/main_agent")
    → <project_root>/app/prompts/system/main_agent.md

注意：
    - .md 文件中以 `# ` 开头的注释行（首部元数据段）会被自动剥离
    - 变量插值使用正则替换（仅替换 {ASCII标识符} 形式的占位符），其余 {} 原样保留
    - 文件不存在时抛出 FileNotFoundError（不静默，方便调试）
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

# prompts/ 目录的绝对路径
_PROMPTS_ROOT = Path(__file__).resolve().parents[1] / "prompts"


def _strip_meta_comments(text: str) -> str:
    """去掉文件顶部以 `# ` 开头的注释行（提示词元数据），保留正文。"""
    lines = text.splitlines()
    # 跳过顶部连续的注释行（以 # 开头）及空行
    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or stripped == "":
            start = i + 1
        else:
            break
    return "\n".join(lines[start:]).strip()


@lru_cache(maxsize=64)
def _load_raw(relative_path: str) -> str:
    """从磁盘读取原始 .md 文件内容（带 LRU 缓存，进程内只读一次）。"""
    path = _PROMPTS_ROOT / f"{relative_path}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"[PromptLoader] Prompt 文件不存在: {path}\n"
            f"请检查 app/prompts/{relative_path}.md 是否存在。"
        )
    return path.read_text(encoding="utf-8")


# 只匹配 {纯字母下划线标识符}，跳过 JSON 示例中含数字/标点的花括号
_VAR_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def load_prompt(relative_path: str, **kwargs: str) -> str:
    """
    加载并返回 prompt 文本。

    使用正则替换而非 str.format_map()，避免 prompt 文件中
    JSON 示例的花括号被误当成 Python 格式占位符（Invalid format specifier）。
    只替换 {纯标识符} 形式的占位符，其余 { } 原样保留。
    """
    raw = _load_raw(relative_path)
    text = _strip_meta_comments(raw)
    if kwargs:
        text = _VAR_RE.sub(lambda m: kwargs.get(m.group(1), m.group(0)), text)
    return text


def reload_prompt(relative_path: str, **kwargs: str) -> str:
    """强制重新读取文件（绕过缓存），用于开发期热加载。"""
    _load_raw.cache_clear()
    return load_prompt(relative_path, **kwargs)


class _SafeDict(dict):
    """向后兼容保留，新代码已不再使用 format_map。"""
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
