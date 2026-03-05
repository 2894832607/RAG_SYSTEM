from app.modules.pipeline import run_generation
from app.schemas.requests import GenerationRequest


if __name__ == "__main__":
    request = GenerationRequest(
        taskId="task-direct-001",
        sourceText="春风又绿江南岸",
        callbackUrl="http://127.0.0.1:8000/ai/mock/callback",
        callbackToken="demo-token",
    )
    run_generation(request)
    print("run_generation completed")
