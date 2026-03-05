# AI Microservice

The `ai-service` folder hosts the FastAPI-based RAG pipeline described in the system overview. It is responsible for:

1. Vectorizing poetry inputs via BGE/bge-large-zh-v1.5 or a compatible embedding service.
2. Executing a LangChain or template-driven prompt enhancement chain.
3. Driving Stable Diffusion (with country-specific LoRA weights) and uploading the final scene to shared storage.
4. Notifying the Java backend via the callback contract once generation completes or fails.

## Running locally
```bash
python -m venv .venv
source .venv/bin/activate # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Windows (from project root) recommended command:

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir ai-service --host 127.0.0.1 --port 8001
```

## Environment variables
- `CHROMADB_URI`: address of the vector store.
- ` CALLBACK_SECRET` (optional): shared secret to secure callbacks.
- `LOCAL_STORAGE_PATH`: where rendered images are cached before uploading.
- `GLM_API_KEY` (optional): Zhipu GLM API key. If empty, service falls back to local prompt template.
- `GLM_BASE_URL` (optional): default `https://open.bigmodel.cn/api/paas/v4`.
- `GLM_MODEL` (optional): default `glm-5`.
- `GLM_TIMEOUT` (optional): request timeout in seconds, default `30`.

## Quick smoke test (no callback required)
After starting the service, call:

```bash
curl -X POST "http://127.0.0.1:8000/ai/api/v1/generate/simple" \
	-H "Content-Type: application/json" \
	-d '{"sourceText":"大漠孤烟直，长河落日圆"}'
```

You should receive `retrievedText`, `enhancedPrompt`, and `imageUrl` in response.

## Async callback self-test (no Java backend)
1) Submit async task (callback points to local mock endpoint):

```bash
curl -X POST "http://127.0.0.1:8000/ai/api/v1/generate/async" \
	-H "Content-Type: application/json" \
	-d '{
		"taskId":"task-001",
		"sourceText":"明月松间照，清泉石上流",
		"callbackUrl":"http://127.0.0.1:8000/ai/mock/callback",
		"callbackToken":"demo-token"
	}'
```

2) Query callback result:

```bash
curl "http://127.0.0.1:8000/ai/mock/callback/task-001"
```

If local callback to the same service is inconvenient, you can start external mock receiver:

```bash
.venv\Scripts\python.exe ai-service\scripts\mock_callback_server.py
```

Then use `callbackUrl=http://127.0.0.1:8010/callback`.
