import httpx

from app.modules.generation import DiffusionClient
from app.modules.prompt import PromptEnhancer
from app.modules.retriever import Retriever
from app.schemas.requests import CallbackPayload, GenerationRequest


def run_generation(request: GenerationRequest) -> None:
    retriever = Retriever()
    knowledge = retriever.fetch(request.sourceText)
    enriched_prompt = PromptEnhancer().enrich(request.sourceText, knowledge)
    image_url = DiffusionClient().generate(enriched_prompt)
    payload = CallbackPayload(
        retrievedText=knowledge[0] if knowledge else request.sourceText,
        enhancedPrompt=enriched_prompt,
        imageUrl=image_url
    )
    send_callback(request.callbackUrl, request.taskId, payload)


def send_callback(callback_url: str, task_id: str, payload: CallbackPayload) -> None:
    body = {
        "taskId": task_id,
        "status": 1,
        "payload": payload.model_dump()
    }
    with httpx.Client(timeout=60.0) as client:
        client.post(callback_url, json=body)
