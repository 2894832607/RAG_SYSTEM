import httpx

from app.modules.generation import CogViewClient
from app.modules.prompt import PromptEnhancer
from app.modules.retriever import Retriever
from app.schemas.requests import CallbackBody, CallbackPayload, GenerationRequest, SimpleGenerationResponse


def generate_once(source_text: str) -> SimpleGenerationResponse:
    retriever = Retriever()

    # 混合检索：自动判断精准/模糊模式
    result = retriever.smart_retrieve(source_text)
    poems = result.poems

    # 将召回诗词格式化为知识块列表
    knowledge_blocks = [p.to_knowledge_block() for p in poems]

    # 取相似度最高的一首作为展示用 retrievedText
    best = poems[0] if poems else None
    retrieved_display = (
        f"【{best.dynasty}·{best.author}·《{best.title}》】\n{best.original_poem}"
        if best else source_text
    )

    # PE 增强，返回正向 + 负向两段提示词
    positive_prompt, negative_prompt = PromptEnhancer().enrich(source_text, knowledge_blocks)

    image_url = CogViewClient().generate(positive_prompt, negative_prompt)
    return SimpleGenerationResponse(
        retrievedText=retrieved_display,
        enhancedPrompt=positive_prompt,
        negativePrompt=negative_prompt,
        imageUrl=image_url,
    )


def run_generation(request: GenerationRequest) -> None:
    try:
        result = generate_once(request.sourceText)
        payload = CallbackPayload(
            retrievedText=result.retrievedText,
            enhancedPrompt=result.enhancedPrompt,
            negativePrompt=result.negativePrompt,
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
