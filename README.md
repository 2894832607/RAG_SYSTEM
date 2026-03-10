# Poetry RAG System

## Project Overview
A modular implementation scaffold for the research project described in the design docs. The system splits responsibilities across three layers:

1. **Presentation** – Vue 3 + Vite SPA that captures poem input, polls task status, and renders gallery content.
2. **Business Logic** – Spring Boot microservice that exposes REST endpoints, normalizes task state, and dispatches compute jobs.
3. **AI Microservice** – FastAPI + LangChain pipeline that handles embedding lookup, prompt augmentation, and Stable Diffusion inference.

## Directory layout
- `frontend/` – Vite + Vue 3 code with polling wrappers, auth placeholders, and a RAG flow UI component.
- `backend/` – Spring Boot project stub with REST controllers, DTOs, service layer, and database model mirroring `sys_generation_task`.
- `ai-service/` – FastAPI-based RAG pipeline with LangChain `Chain`, ChromaDB wrapper, Stable Diffusion triggers, and environment-ready config.

## Getting started
1. Create per-module `.env` files (see each module README) to map URLs, DB credentials, and GPU model weights.
   - **Important**: Ensure `CALLBACK_TOKEN` is consistent across **Backend** and **AI Service**.
2. Start the backend to expose `/api/v1/poetry/visualize` and `/api/v1/poetry/callback` endpoints.
3. Run the AI microservice (preferably under `uvicorn --reload`) and ensure it can reach ChromaDB/embedding storage.
4. Bootstrap the frontend via `npm install`/`npm run dev` while pointing to the backend gateway.

## Environment Variables
| Variable | Required | Description |
|---|---|---|
| `CALLBACK_TOKEN` | Yes | Shared secret for AI Service -> Backend callback authentication. |
| `AI_SERVICE_URL` | Yes | (Backend) Endpoint for the AI Microservice. |
| `CALLBACK_URL` | Yes | (AI Service) Webhook URL for posting generation results. |

## Next steps
- Populate the frontend with actual task polling (long-poll vs. websocket) and gallery persistence.
- Implement database schema migrations plus MyBatis-Plus mapper definitions for `sys_generation_task`.
- Wire up actual LangChain `RetrievalQA`/`SequentialChain` sequences, LoRA-loaded diffusion model, and blob storage uploads.
