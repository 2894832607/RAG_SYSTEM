"""
统一模型配置模块

Spec: specs/001-model-api-config/spec.md §3.1

所有模型相关参数（LLM + 图像生成）的唯一读取入口。
业务模块不应直接读取 GLM_* / LLM_* / IMAGE_* 环境变量，
而应调用 get_llm_config() 或 get_image_config()。

环境变量优先级（文本 LLM）：
  LLM_API_KEY  > GLM_API_KEY  > ""
  LLM_BASE_URL > GLM_BASE_URL > provider preset
  LLM_MODEL    > GLM_MODEL    > "glm-4-flash"
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── 提供商预设端点 ─────────────────────────────────────────────────────────
_PROVIDER_PRESETS: dict[str, str] = {
    "glm":    "https://open.bigmodel.cn/api/paas/v4",
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "openai": "https://api.openai.com/v1",
    "qwen":   "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "ollama": "http://localhost:11434/v1",
}

_VALID_LLM_PROVIDERS = set(_PROVIDER_PRESETS.keys()) | {"custom"}
_VALID_IMAGE_PROVIDERS = {"cogview", "disabled"}


@dataclass(frozen=True)
class LlmConfig:
    """文本 LLM 配置快照（进程启动后不可变）。"""
    provider: str
    api_key: str
    base_url: str
    model: str
    temperature: float
    timeout: float


@dataclass(frozen=True)
class ImageConfig:
    """图像生成模型配置快照。"""
    provider: str
    api_key: str
    base_url: str
    model: str
    size: str
    timeout: float


def get_llm_config() -> LlmConfig:
    """
    读取 LLM 配置。新变量（LLM_*）优先，旧变量（GLM_*）作为 fallback。
    进程内多次调用返回相同对象（基于环境变量，进程运行期间不变）。
    """
    # 密钥：新变量优先 → 旧变量 fallback
    api_key = (os.getenv("LLM_API_KEY") or os.getenv("GLM_API_KEY") or "").strip()

    # 提供商：未设置时，若旧 GLM 密钥存在则默认 "glm"，否则也默认 "glm"
    provider = (os.getenv("LLM_PROVIDER") or "glm").strip().lower()
    if provider not in _VALID_LLM_PROVIDERS:
        logger.error(
            "[ModelConfig] 无效的 LLM_PROVIDER='%s'，回退到 'glm'。"
            "支持值：%s",
            provider,
            ", ".join(sorted(_VALID_LLM_PROVIDERS)),
        )
        provider = "glm"

    # base_url：新变量 > 旧变量 > provider 预设
    old_base = os.getenv("GLM_BASE_URL", "").strip()
    preset = _PROVIDER_PRESETS.get(provider, old_base or _PROVIDER_PRESETS["glm"])
    base_url = ((os.getenv("LLM_BASE_URL") or old_base or preset).rstrip("/"))

    # 模型名：新变量 > 旧变量 > 默认
    model = (
        os.getenv("LLM_MODEL")
        or os.getenv("GLM_MODEL")
        or "glm-4-flash"
    ).strip()

    temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    timeout = float(os.getenv("LLM_TIMEOUT", os.getenv("GLM_TIMEOUT", "90")))

    return LlmConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        timeout=timeout,
    )


def get_image_config() -> ImageConfig:
    """
    读取图像生成配置。
    默认继承 LLM 的 api_key 和 base_url，可通过 IMAGE_* 变量独立覆盖。
    IMAGE_PROVIDER=disabled 时 generate() 返回占位图 URL。
    """
    llm = get_llm_config()

    provider = (os.getenv("IMAGE_PROVIDER") or "cogview").strip().lower()
    if provider not in _VALID_IMAGE_PROVIDERS:
        logger.warning(
            "[ModelConfig] 无效的 IMAGE_PROVIDER='%s'，回退到 'cogview'。"
            "支持值：%s",
            provider,
            ", ".join(sorted(_VALID_IMAGE_PROVIDERS)),
        )
        provider = "cogview"

    api_key  = (os.getenv("IMAGE_API_KEY")  or llm.api_key).strip()
    base_url = (os.getenv("IMAGE_BASE_URL") or llm.base_url).rstrip("/")
    model    = (os.getenv("IMAGE_MODEL") or "cogview-4-250304").strip()
    size     = os.getenv("COGVIEW_SIZE", "1024x1024")
    timeout  = float(os.getenv("COGVIEW_TIMEOUT", "120"))

    return ImageConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        size=size,
        timeout=timeout,
    )


def validate_and_log() -> None:
    """
    启动时打印配置摘要（API Key 脱敏），并对必填项缺失输出 WARNING。
    在 FastAPI lifespan 中调用。
    """
    llm = get_llm_config()
    img = get_image_config()

    # 脱敏：只显示前 8 位
    def _mask(key: str) -> str:
        if not key:
            return "*** NOT SET ***"
        return key[:8] + "..." if len(key) > 8 else key[:4] + "..."

    logger.info(
        "[ModelConfig] LLM  provider=%s  model=%s  base_url=%s  key=%s",
        llm.provider, llm.model, llm.base_url, _mask(llm.api_key),
    )
    logger.info(
        "[ModelConfig] IMG  provider=%s  model=%s",
        img.provider, img.model,
    )

    if not llm.api_key and llm.provider != "ollama":
        logger.warning(
            "[ModelConfig] LLM_API_KEY 未配置，涉及模型调用的接口将返回错误。"
            "设置 LLM_API_KEY（或旧版 GLM_API_KEY）环境变量后重启服务。"
        )

    if img.provider != "disabled" and not img.api_key:
        logger.warning(
            "[ModelConfig] IMAGE_API_KEY 未配置，图像生成接口将失败。"
            "设置 IMAGE_API_KEY 或 LLM_API_KEY 环境变量后重启服务。"
        )
