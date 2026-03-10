from pydantic import AnyHttpUrl, BaseModel
from typing import List, Optional


class GenerationRequest(BaseModel):
    taskId: str
    poemText: str     # 对齐 specs/openapi/backend.yaml
    callbackUrl: AnyHttpUrl
    callbackToken: str


class CallbackPayload(BaseModel):
    retrievedText: str
    enhancedPrompt: str
    negativePrompt: Optional[str] = None
    imageUrl: str


class CallbackBody(BaseModel):
    taskId: str
    status: int
    errorMessage: Optional[str] = None
    payload: Optional[CallbackPayload] = None


class SimpleGenerationRequest(BaseModel):
    sourceText: str


class SimpleGenerationResponse(BaseModel):
    retrievedText: str
    enhancedPrompt: str
    negativePrompt: Optional[str] = None
    imageUrl: str


# ── 分镜相关 ──────────────────────────────────────────────────────

class StoryboardShotResult(BaseModel):
    """单张分镜的生成结果（用于 SSE shot_done 事件）。"""
    shot_id: int
    shot_name: str
    shot_type: str          # establishing | medium | close_up | atmospheric
    poem_lines: List[str]
    translation_excerpt: str
    camera_angle: str
    emotion: str
    positive_prompt: str
    image_url: Optional[str] = None
    error: Optional[str] = None


class StoryboardPlanInfo(BaseModel):
    """分镜方案摘要（用于 SSE plan 事件）。"""
    poem_title: str
    author: str
    dynasty: str
    global_style: str
    total_shots: int
