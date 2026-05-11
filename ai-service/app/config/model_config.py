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
_VALID_IMAGE_PROVIDERS = {"cogview", "seedream", "local_sdxl", "zhipu", "disabled"}
_VALID_VIDEO_PROVIDERS = {"seedance", "vidu", "zhipu", "disabled"}


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
    # 超时设置：始终为 None（无限制）
    timeout = None

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
    """
    provider = (os.getenv("IMAGE_PROVIDER") or "seedream").strip().lower()
    if provider not in _VALID_IMAGE_PROVIDERS:
        logger.error(
            "[ModelConfig] 无效的 IMAGE_PROVIDER='%s'，回退到 'seedream'。"
            "支持值：%s",
            provider,
            ", ".join(sorted(_VALID_IMAGE_PROVIDERS)),
        )
        provider = "seedream"

    api_key = (
        os.getenv("IMAGE_API_KEY")
        or os.getenv("ARK_API_KEY")
        or os.getenv("LLM_API_KEY")
        or os.getenv("GLM_API_KEY")
        or ""
    ).strip()

    if provider == "disabled":
        base_url = ""
        model = "disabled"
    elif provider == "cogview":
        base_url = (os.getenv("IMAGE_BASE_URL") or _PROVIDER_PRESETS["glm"]).rstrip("/")
        model = (os.getenv("IMAGE_MODEL") or "cogview-4-250304").strip()
    elif provider == "local_sdxl":
        base_url = (os.getenv("LOCAL_SDXL_URL") or "http://127.0.0.1:8090/v1/images/generations").rstrip("/")
        model = (os.getenv("IMAGE_MODEL") or "sdxl-turbo").strip()
        api_key = (os.getenv("IMAGE_API_KEY") or "local").strip()
    else:
        base_url = (os.getenv("IMAGE_BASE_URL") or _PROVIDER_PRESETS["doubao"]).rstrip("/")
        model = (os.getenv("IMAGE_MODEL") or "doubao-seedream-5-0-260128").strip()

    size = (os.getenv("COGVIEW_SIZE") or "2K").strip()
    timeout = float(os.getenv("COGVIEW_TIMEOUT") or "300")

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
    启动时打印配置摘要（API Key 脱敏）。
    在 FastAPI lifespan 中调用。
    
    优先读取本地环境变量；未配置时回退到安全默认值。
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
        "[ModelConfig] IMG  provider=%s  model=%s  key=%s",
        img.provider, img.model, _mask(img.api_key),
    )

    logger.info("[ModelConfig] ✅ 已完成模型配置检查")


@dataclass(frozen=True)
class VideoConfig:
    """视频生成模型配置快照（Seedance / Vidu，异步轮询）。"""
    provider: str       # "seedance" | "vidu" | "disabled"
    model: str
    api_key: str
    base_url: str
    timeout: int
    poll_interval: int


def get_video_config() -> VideoConfig:
    """
    读取视频生成配置。
    VIDEO_PROVIDER=seedance → 字节 Seedance（/contents/generations/tasks）
    VIDEO_PROVIDER=vidu     → GLM Vidu2（/videos/generations）
    VIDEO_PROVIDER=zhipu    → GLM CogVideoX（使用 zai-sdk）
    VIDEO_PROVIDER=disabled → 跳过视频合成步骤
    默认继承 IMAGE_API_KEY 和 IMAGE_BASE_URL，可通过 VIDEO_* 独立覆盖。
    """
    img = get_image_config()
    provider = (os.getenv("VIDEO_PROVIDER") or "seedance").strip().lower()
    
    # zhipu 提供商使用智谱 CogVideoX 模型
    if provider == "zhipu":
        model = (os.getenv("VIDEO_MODEL") or "cogvideox-3").strip()
        api_key = (os.getenv("VIDEO_API_KEY") or img.api_key).strip()
        base_url = (os.getenv("VIDEO_BASE_URL") or _PROVIDER_PRESETS["glm"]).rstrip("/")
    # local_sdxl 的 api_key="local" 且 base_url 是完整端点路径，不能用于远端视频 API。
    # 此时优先取 ARK_API_KEY 和豆包预设端点，确保 Seedance 能正常调用。
    elif img.provider == "local_sdxl":
        model = (os.getenv("VIDEO_MODEL") or "doubao-seedance-1-5-pro-251215").strip()
        api_key = (os.getenv("VIDEO_API_KEY") or os.getenv("ARK_API_KEY") or "").strip()
        _fallback_base = _PROVIDER_PRESETS["doubao"]
        base_url = (os.getenv("VIDEO_BASE_URL") or _fallback_base).rstrip("/")
    else:
        model = (os.getenv("VIDEO_MODEL") or "doubao-seedance-1-5-pro-251215").strip()
        api_key = (os.getenv("VIDEO_API_KEY") or img.api_key).strip()
        _fallback_base = img.base_url
    base_url = (os.getenv("VIDEO_BASE_URL") or _fallback_base).rstrip("/")
    # 视频超时：默认 480 秒（8 分钟），包含分镜规划 +4 帧生成 +Seedance 合成（60-120s）
    # 拥堵时期可通过 VIDEO_TIMEOUT 延长至 600s（10 分钟）
    timeout = int(os.getenv("VIDEO_TIMEOUT") or "480")
    poll_interval = int(os.getenv("VIDEO_POLL_INTERVAL") or "5")
    return VideoConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        poll_interval=poll_interval,
    )
