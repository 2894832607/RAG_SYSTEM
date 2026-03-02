import httpx

from app.modules.generation import DiffusionClient
from app.modules.prompt import PromptEnhancer
from app.modules.retriever import Retriever
from app.schemas.requests import CallbackBody, CallbackPayload, GenerationRequest


def run_generation(request: GenerationRequest) -> None:
    try:
        retriever = Retriever()
        knowledge = retriever.fetch(request.sourceText)
        enriched_prompt = PromptEnhancer().enrich(request.sourceText, knowledge)
        image_url = DiffusionClient().generate(enriched_prompt)
        payload = CallbackPayload(
            retrievedText=knowledge[0] if knowledge else request.sourceText,
            enhancedPrompt=enriched_prompt,
            imageUrl=image_url
        )
        send_callback(
            callback_url=str(request.callbackUrl),
            body=CallbackBody(taskId=request.taskId, status=1, payload=payload)
        )
    except Exception as exc:
        send_callback(
            callback_url=str(request.callbackUrl),
            body=CallbackBody(taskId=request.taskId, status=2, errorMessage=str(exc))
        )


def send_callback(callback_url: str, body: CallbackBody) -> None:
    with httpx.Client(timeout=60.0) as client:
        client.post(callback_url, json=body.model_dump(exclude_none=True))
