from pydantic import AnyHttpUrl, BaseModel
from typing import List, Optional, Literal
from datetime import datetime


class MediaFile(BaseModel):
    """媒体文件信息（用于 SSE 推送）。"""
    type: Literal["image", "video"]
    url: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None


class ProgressEvent(BaseModel):
    """SSE 进度事件。"""
    event_type: Literal["started", "retrieval_done", "shot_done", "video_done", "completed", "failed"]
    task_id: str
    timestamp: datetime
    stage: Optional[str] = None
    message: Optional[str] = None
    progress: Optional[float] = None  # 0.0 - 1.0
    media_files: Optional[List[MediaFile]] = None
    payload: Optional[dict] = None


class GenerationRequest(BaseModel):
    taskId: str
    poemText: str     # 对齐 specs/openapi/backend.yaml
    callbackUrl: AnyHttpUrl
    callbackToken: str


class CallbackPayload(BaseModel):
    retrievedText: str
    enhancedPrompt: str
    negativePrompt: Optional[str] = None
    imageUrl: str                       # 主图（第一张，向后兼容）
    imageUrls: Optional[List[str]] = None  # 所有生成的图片 URLs（新字段）
    videoUrl: Optional[str] = None         # 视频 URL（新字段）
    explanation: Optional[str] = None      # 诗词解释（新字段）


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
    videoUrl: Optional[str] = None
    mediaFiles: Optional[List[MediaFile]] = None


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
