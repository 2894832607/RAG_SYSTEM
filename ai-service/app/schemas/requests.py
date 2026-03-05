from pydantic import AnyHttpUrl, BaseModel
from typing import Optional


class GenerationRequest(BaseModel):
    taskId: str
    sourceText: str
    callbackUrl: AnyHttpUrl
    callbackToken: str


class CallbackPayload(BaseModel):
    retrievedText: str
    enhancedPrompt: str
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
    imageUrl: str
