from pydantic import BaseModel, HttpUrl


class GenerationRequest(BaseModel):
    taskId: str
    sourceText: str
    callbackUrl: HttpUrl


class CallbackPayload(BaseModel):
    retrievedText: str
    enhancedPrompt: str
    imageUrl: str
