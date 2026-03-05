# 系统总览 — Architecture

> **Status**: Stable  
> **Version**: 1.0  
> **Last Updated**: 2026-03-05

---

## 1. 整体架构

```
                        ┌───────────────────────────────────────┐
                        │            Browser (Vue 3)            │
                        │  ① Submit Poem  ③ Poll Task  ④ SSE   │
                        └──────────────┬───────┬───────┬────────┘
                                       │       │       │
                              HTTP REST│       │       │SSE
                                       ▼       ▼       ▼
                        ┌─────────────────────────────────────────┐
                        │         Spring Boot Backend (8080)      │
                        │  /api/v1/poetry/*   /api/v1/auth/*      │
                        │         MyBatis-Plus ↕ MySQL            │
                        └──────────────┬──────────────────────────┘
                                       │ ② async HTTP POST
                                       ▼
                        ┌─────────────────────────────────────────┐
                        │       FastAPI AI Service (8000)         │
                        │  LangGraph Agent + GLM + ChromaDB       │
                        └───────────┬─────────────────────────────┘
                                    │ ⑤ Callback POST (X-Callback-Token)
                                    └──────────────────────────────▶ Backend
```

---

## 2. 组件职责

| 组件 | 技术栈 | 核心职责 |
|------|--------|---------|
| **Frontend** | Vue 3 + Vite + TypeScript | 用户交互、任务提交、结果展示、SSE 思考流 |
| **Backend** | Spring Boot 3 + MyBatis-Plus + MySQL | REST 网关、任务状态机、AI 服务调度、用户认证 |
| **AI Service** | FastAPI + LangGraph + GLM + ChromaDB | RAG 检索、Prompt 增强、图像生成（预留）|

---

## 3. 核心数据流

### 3.1 主流程（异步任务）

```
1. 浏览器 POST /api/v1/poetry/visualize  → taskId
2. Backend 写库 PENDING，POST AI Service /generate/async
3. AI Service 后台运行：RAG → GLM → (Diffusion)
4. AI 完成后 POST /api/v1/poetry/callback（带 token）
5. Backend 更新库 COMPLETED + imageUrl
6. 浏览器轮询 /api/v1/poetry/task/{taskId} 得到结果
```

### 3.2 思考流（SSE）

```
1. 浏览器 POST /api/v1/poetry/think-stream（携带诗句）
2. Backend 作为 SSE 代理，转发给 AI Service /generate/think-stream
3. GLM 推理过程逐 token 推送给浏览器
```

---

## 4. 部署模式

### 本地开发

| 服务 | 端口 | 启动方式 |
|------|------|---------|
| MySQL | 3306 | 本机安装 |
| AI Service | 8000 | `uvicorn app.main:app` |
| Backend | 8080 | `java -jar target/*.jar` |
| Frontend | 5173 | `npm run dev` |

### 环境变量（Backend）

| 变量 | 说明 |
|------|------|
| `DB_URL` | JDBC 连接串 |
| `DB_USERNAME` / `DB_PASSWORD` | MySQL 凭据 |
| `AI_SERVICE_URL` | `/ai/api/v1/generate/async` 完整 URL |
| `AI_CALLBACK_URL` | `/api/v1/poetry/callback` 完整 URL |
| `AI_CALLBACK_TOKEN` | 回调鉴权 token |

---

## 5. 安全边界

- 回调接口通过 `X-Callback-Token` 防止外部伪造
- JWT 认证保护用户相关接口（TODO：当前仅 auth 模块实现）
- AI Service 不直接对外暴露（仅 Backend 内部调用）

---

## 6. 相关文档

- [数据模型](data-model.md)
- [Backend OpenAPI](../openapi/backend.yaml)
- [AI Service OpenAPI](../openapi/ai-service.yaml)
- [Feature: 诗词可视化](../features/poetry-visualization.spec.md)
- [Feature: RAG Pipeline](../features/rag-pipeline.spec.md)
