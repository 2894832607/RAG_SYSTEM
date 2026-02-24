from fastapi import BackgroundTasks, FastAPI

from app.modules.pipeline import run_generation
from app.schemas.requests import GenerationRequest

app = FastAPI(
    title="Poetry RAG AI Service",
    version="0.1.0",
    description="Handles retrieval, prompt enhancement, and diffusion inference."
)


@app.post("/ai/api/v1/generate/async", status_code=202)
async def queue_generation(request: GenerationRequest, background_tasks: BackgroundTasks):
    """Launches the RAG pipeline as a background job matching the async contract."""
    background_tasks.add_task(run_generation, request)
    return {"message": "Task accepted", "taskId": request.taskId}


@app.get("/ai/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "poetry rag ai"}
