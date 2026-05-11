"""
缓存策略配置

定义不同业务场景的 TTL 常量和 key 生成规则。

Spec: specs/001-model-api-config/spec.md §Redis 缓存扩展
"""

import hashlib


class CacheStrategy:
    """各业务场景的缓存 TTL（单位：秒）。"""

    # 诗词搜索结果缓存 — 1 小时
    # 理由：诗词内容不会改变，但新诗词可能入库
    POETRY_SEARCH_TTL: int = 3_600

    # 图像生成结果缓存 — 24 小时
    # 理由：同一 prompt 生成的图像几乎相同，节省 API 费用
    IMAGE_GENERATION_TTL: int = 86_400

    # Prompt 增强结果缓存 — 7 天
    # 理由：GLM 对相同诗词输出的 prompt 基本稳定
    PROMPT_ENHANCEMENT_TTL: int = 604_800

    # Embedding 向量缓存 — 永久（-1）
    # 理由：向量模型不变时，同文本 embedding 完全相同
    EMBEDDING_TTL: int = -1


def make_cache_key(prefix: str, *parts: str) -> str:
    """
    生成规范的缓存 key。

    格式：``{prefix}:{sha256_of_joined_parts[:16]}``

    使用哈希而非明文拼接，避免 key 过长（Redis 建议 key < 256 字节）
    以及特殊字符问题。

    Args:
        prefix: 业务前缀，如 ``poetry``、``image``、``prompt``
        *parts: 参与 key 生成的原始字符串（如 query、prompt 等）

    Returns:
        形如 ``poetry:a3f9c2b1d8e7f0a1`` 的缓存 key

    Examples:
        >>> make_cache_key("poetry", "床前明月光")
        'poetry:8b4a2f1d9c6e3a7b'
        >>> make_cache_key("image", "一幅水墨山水画", "1024x1024")
        'image:c7d2e5f8a1b4c9d6'
    """
    joined = ":".join(parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"
