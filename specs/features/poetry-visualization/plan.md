# Plan: 诗词可视化生成

> **Spec**: [specs/features/poetry-visualization.spec.md](../poetry-visualization.spec.md)  
> **Status**: Draft  
> **Version**: 1.0  
> **Last Updated**: 2026-03-05

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
