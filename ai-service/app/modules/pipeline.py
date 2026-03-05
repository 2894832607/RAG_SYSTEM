import httpx

from app.modules.generation import DiffusionClient
from app.modules.prompt import PromptEnhancer
from app.modules.retriever import Retriever
from app.schemas.requests import CallbackBody, CallbackPayload, GenerationRequest, SimpleGenerationResponse


def generate_once(source_text: str) -> SimpleGenerationResponse:
    retriever = Retriever()
    knowledge = retriever.fetch(source_text)
    enriched_prompt = PromptEnhancer().enrich(source_text, knowledge)
    image_url = DiffusionClient().generate(enriched_prompt)
    return SimpleGenerationResponse(
        retrievedText=knowledge[0] if knowledge else source_text,
        enhancedPrompt=enriched_prompt,
        imageUrl=image_url,
    )


def run_generation(request: GenerationRequest) -> None:
    try:
        result = generate_once(request.sourceText)
        payload = CallbackPayload(
            retrievedText=result.retrievedText,
            enhancedPrompt=result.enhancedPrompt,
            imageUrl=result.imageUrl
        )
        send_callback(
            callback_url=str(request.callbackUrl),
            callback_token=request.callbackToken,
            body=CallbackBody(taskId=request.taskId, status=1, payload=payload)
        )
    except Exception as exc:
        send_callback(
            callback_url=str(request.callbackUrl),
            callback_token=request.callbackToken,
            body=CallbackBody(taskId=request.taskId, status=2, errorMessage=str(exc))
        )


def send_callback(callback_url: str, callback_token: str, body: CallbackBody) -> None:
    with httpx.Client(timeout=60.0, trust_env=False) as client:
        response = client.post(
            callback_url,
            json=body.model_dump(exclude_none=True),
            headers={"X-Callback-Token": callback_token}
        )
        response.raise_for_status()
