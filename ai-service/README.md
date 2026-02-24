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

## Environment variables
- `CHROMADB_URI`: address of the vector store.
- ` CALLBACK_SECRET` (optional): shared secret to secure callbacks.
- `LOCAL_STORAGE_PATH`: where rendered images are cached before uploading.
