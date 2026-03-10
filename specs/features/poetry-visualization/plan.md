# Plan: 诗词可视化生成

> **Spec**: [specs/features/poetry-visualization.spec.md](../poetry-visualization.spec.md)  
> **Status**: In Progress  
> **Version**: 2.0  
> **Last Updated**: 2026-03-06

---

## 1. 架构现状确认

| 检查项 | 结果 | 说明 |
|--------|------|------|
| Agent 框架（LangGraph ReAct） | ✅ | `create_react_agent` + MemorySaver，`agent/graph.py` |
| 前端直连 AI Service（主 UX） | ❌ → ✅ | **已迁移**：前端走 Backend 代理（`/api/v1/poetry/chat` / `/storyboard`），符合 constitution §3.1 |
| 两条 SSE 路径（chat / storyboard） | ✅ | 独立端点，职责分离 |
| 前端自动意图路由（无手动切换） | ✅ | `detectVisualizeIntent()` 实现 |
| RAG 检索（ChromaDB） | ✅ | `search_poetry` 工具 + `smart_retrieve` |
| 分镜生图（GLM规划 + CogView-4） | ✅ | `storyboard.py` 实现 |
| JWT 认证（Backend） | ✅ | `AuthController` + Spring Security |
| 历史页面（Frontend） | ✅ | `HistoryView.vue` |
| 分镜结果写入历史 | ✅ | **已实现**：`AiProxyController` 在 `done` 后写 `sys_generation_task` |
| Backend ErrorResponse 对齐 | ✅ | **已实现**：`GlobalExceptionHandler` 补充 timestamp 字段，`ResourceNotFoundException` 触发 404 |

---

## 2. 实际架构设计

```
浏览器（Vue 3）
  │
  ├── detectVisualizeIntent(text) == true
  │     │ POST /api/v1/poetry/storyboard (SSE, JWT)
  │     ▼
  │   Backend AiProxyController
  │     │ 代理到 AI Service
  │     ▼
  │   StoryboardGenerator
  │     ├─ Retriever.smart_retrieve()   ← ChromaDB
  │     ├─ GLM 规划分镜方案
  │     └─ CogView-4 逐张生图 → shot_done SSE → 写入 sys_generation_task
  │
  └── detectVisualizeIntent(text) == false
        │ POST /api/v1/poetry/chat (SSE, JWT)
        ▼
      Backend AiProxyController
        │ 代理到 AI Service
        ▼
      LangGraph ReAct Agent（GLM）
        ├─ search_poetry tool  ← ChromaDB
        └─ visualize_poem tool ← RAG→PE→CogView-4
```

---

## 3. 模块与文件现状

### AI Service（FastAPI）

| 文件 | 状态 | 说明 |
|------|------|------|
| `app/main.py` | ✅ 已有 | `/chat` SSE、`/generate/storyboard` SSE、session 管理 |
| `app/agent/graph.py` | ✅ 已有 | `create_react_agent` + MemorySaver |
| `app/agent/tools.py` | ✅ 已有 | `search_poetry` + `visualize_poem` |
| `app/agent/llm.py` | ✅ 已有 | GLM 客户端封装 |
| `app/agent/prompt_loader.py` | ✅ 已有 | 从 `prompts/` 加载 markdown prompt |
| `app/modules/retriever.py` | ✅ 已有 | ChromaDB 语义检索，`smart_retrieve` |
| `app/modules/storyboard.py` | ✅ 已有 | 分镜规划 + CogView-4 生图 |
| `app/modules/generation.py` | ✅ 已有 | CogView-4 客户端 |
| `app/modules/prompt.py` | ✅ 已有 | Prompt 增强（visualize_poem 内部使用）|
| `app/schemas/requests.py` | ✅ 已有 | Pydantic 模型 |
| `app/prompts/system/main_agent.md` | ✅ 已有 | Agent 系统提示 |
| `app/prompts/planner/intent_router.md` | ✅ 已有 | 意图路由 prompt（历史遗留，当前 ReAct 不主动使用）|

### Frontend（Vue 3）

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/views/GenerateView.vue` | ✅ 已有 | 主对话页：chat + storyboard 双路 SSE |
| `src/views/HistoryView.vue` | ✅ 已有 | 历史任务列表 |
| `src/stores/auth.ts` | ✅ 已有 | JWT 状态管理 |
| `src/router/` | ✅ 已有 | 路由守卫（未登录→/login）|

### Backend（Spring Boot）

| 文件 | 状态 | 说明 |
|------|------|------|
| `AuthController.java` | ✅ 已有 | register / login |
| `PoetryVisualizationController.java` | ✅ 已有 | Legacy 端点（generate/task/callback）+ 新增 `/history` |
| `AiProxyController.java` | ✅ 新增 | SSE 代理（`/chat`、`/storyboard`、`/chat/session`），JWT 认证后转发 AI Service |
| `GlobalExceptionHandler.java` | ✅ 已对齐 | ErrorResponse schema 含 timestamp，ResourceNotFoundException → 404 |
| `TaskDispatchService.java` | ✅ 已有 | Legacy 任务管理 |

---

## 4. 数据模型

以 `specs/architecture/data-model.md` 为准。  
当前主 UX（SSE 流）生成的图像**尚未写入** `sys_generation_task`，待 T001 补齐。

---

## 5. 接口变更记录

| 版本 | 变更 |
|------|------|
| v2.0（当前） | 新增 `/ai/api/v1/chat`（ReAct SSE）、`/ai/api/v1/generate/storyboard`（分镜 SSE）、session 管理接口 |
| v1.0（Legacy） | `/ai/api/v1/generate/async`（异步回调模式），保留供脚本测试 |

---

## 6. 待办优先级

见 [tasks.md](tasks.md)：T001（写历史）和 T006（ErrorResponse）为 P1，下一阶段优先完成。

---

## 1. Constitution Check

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 技术栈对齐（Spring Boot 3 / FastAPI） | ✅ | 完全对齐宪章 |
| 架构分层（Frontend→Backend→AI Service） | ✅ | Frontend 不直接调 AI Service |
| 状态枚举（PENDING/PROCESSING/COMPLETED/FAILED） | ✅ | 已在 data-model.md 中声明 |
| 错误响应格式统一（ErrorResponse schema） | ✅ | GlobalExceptionHandler 处理 |
| 回调接口校验 X-Callback-Token | ✅ | 已在 controller 层实现 |
| OpenAPI spec 同步 | ✅ | backend.yaml + ai-service.yaml 已声明 |

---

## 2. 架构设计

```
浏览器
  │ POST /api/v1/poetry/visualize
  ▼
PoetryVisualizationController
  │ createTask()
  ▼
TaskDispatchService
  │ 写库 PENDING → 异步调用 AI
  ▼
AI Service /ai/api/v1/generate/async
  │ 后台：RAG → GLM → 图像生成
  ▼
  POST /api/v1/poetry/callback (X-Callback-Token)
  ▼
TaskDispatchService.updateFromCallback()
  │ 更新库 COMPLETED/FAILED
  ▼
浏览器轮询 /api/v1/poetry/task/{taskId}
```

---

## 3. 模块与文件结构

### Backend（Spring Boot）

| 文件 | 状态 | 说明 |
|------|------|------|
| `controller/PoetryVisualizationController.java` | ✅ 已有 | 4 个端点：visualize/task/callback/think-stream |
| `controller/AuthController.java` | ✅ 已有 | register/login |
| `controller/GlobalExceptionHandler.java` | ✅ 已有 | 统一异常处理 |
| `service/TaskDispatchService.java` | ✅ 已有 | 任务创建、查询、回调更新 |
| `dto/PoemTaskRequest.java` | ✅ 已有 | poemText 字段 |
| `dto/PoetryCallbackRequest.java` | ✅ 已有 | 回调请求体 |
| `entity/GenerationTask.java` | ✅ 已有 | 对应 sys_generation_task 表 |
| `config/AiServiceProperties.java` | ✅ 已有 | AI 服务 URL + token 配置 |

**待完善**：
- [ ] `GlobalExceptionHandler` 返回格式需与 `ErrorResponse` schema 完全一致
- [ ] `ResourceNotFoundException` 统一 404 处理

### AI Service（FastAPI）

| 文件 | 状态 | 说明 |
|------|------|------|
| `app/main.py` | ✅ 已有 | 3 个端点：async/simple/think-stream |
| `app/modules/pipeline.py` | ✅ 已有 | 异步生成管道（RAG→GLM→callback）|
| `app/agent/graph.py` | ✅ 已有 | LangGraph Agent |
| `app/schemas/requests.py` | ✅ 已有 | Pydantic 请求/响应模型 |

---

## 4. 数据模型

以 `specs/architecture/data-model.md` 为准，核心表为 `sys_generation_task`。  
当前 Entity 字段已对齐，无变更。

---

## 5. 接口变更

以 `specs/openapi/backend.yaml` 和 `specs/openapi/ai-service.yaml` 为准。  
当前接口已全部声明，无新增。

---

## 6. 测试策略

| 测试层 | 范围 | 方法 |
|--------|------|------|
| Backend 单元测试 | TaskDispatchService 核心逻辑 | JUnit 5 + Mockito |
| Backend 集成测试 | callback 鉴权逻辑 | MockMvc |
| AI Service 冒烟测试 | `/generate/simple` 端点 | `scripts/smoke_test.py` |
| E2E 手动测试 | 完整 visualize→poll→result 流程 | `scripts/run_pipeline_once.py` |

---

## 7. 风险与注意事项

| 风险 | 影响 | 规避方案 |
|------|------|---------|
| GLM API 超时 | 任务永久 PROCESSING | AI Service 加超时重试，最终回调 status=2 |
| callbackUrl 不可达 | Backend 状态无法更新 | AI Service 记录失败日志，Backend 可设超时兜底 |
| ChromaDB 无索引数据 | 检索结果为空 | 启动前运行 `scripts/02_ingest_chromadb.py` |
