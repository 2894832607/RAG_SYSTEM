# Feature Specification: 诗词可视化生成系统

**Feature Branch**: `main`  
**Created**: 2026-03-05  
**Status**: Draft  
**Input**: 用户描述: "用户输入中文诗句，系统通过 RAG + GLM LangGraph Agent 管道生成与诗意相符的可视化图像，并通过任务轮询将结果展示给用户；用户可在历史页面查看所有曾提交的任务"

---

## 用户场景与测试 *(必填)*

<!--
  每条用户故事必须独立可测试：仅实现其中一条，也能形成可演示的最小可用产品。
  优先级 P1 表示核心路径，P2 表示增强体验。
-->

### 用户故事 1 - 用户注册与登录 (优先级: P1)

用户在首次使用系统时创建账号，或用已有账号登录，获得 JWT Token 后才能访问其他功能。

**为什么是 P1**: 所有其他功能依赖认证，无认证无法使用系统。
**独立测试方式**: 使用全新数据库，能注册账号并拿到 token，用该 token 调通受保护接口即可。
**验收场景**:
1. **Given** 用户填写合法的 username + password，**When** 调用 `POST /api/v1/auth/register`，**Then** 返回 HTTP 200 并包含 `token` 和 `user` 对象
2. **Given** 已注册用户输入正确凭据，**When** 调用 `POST /api/v1/auth/login`，**Then** 返回 HTTP 200 + 新 JWT token
3. **Given** 登录成功，**When** 前端将 token 存入 localStorage 并附加到后续请求 `Authorization: Bearer {token}`，**Then** 受保护接口正常响应
4. **Given** 输入错误密码，**When** 调用登录接口，**Then** 返回 HTTP 401

---

### 用户故事 2 - 提交诗词生成任务 (优先级: P1) ⭐ 核心

已登录用户在工作台输入诗句，点击生成，系统异步触发 RAG 管道，并立即返回任务 ID。

**为什么是 P1**: 这是系统的核心价值主张。
**独立测试方式**: Mock AI 服务（返回 202），能提交诗句并拿到 taskId，数据库中出现 PENDING 记录。
**验收场景**:
1. **Given** 已登录用户输入 1-500 字符的诗句，**When** 调用 `POST /api/v1/poetry/generate`，**Then** 返回 HTTP 200 + `{ taskId: "uuid" }` 且数据库写入 PENDING 记录
2. **Given** 提交空诗句（poemText 为空或仅空白），**When** 提交，**Then** 返回 HTTP 400 + 错误信息
3. **Given** 提交超过 500 字符的诗句，**When** 提交，**Then** 返回 HTTP 400
4. **Given** 未携带 Bearer Token，**When** 提交，**Then** 返回 HTTP 401

---

### 用户故事 3 - 任务状态轮询与结果展示 (优先级: P1) ⭐ 核心

用户提交任务后，前端每 2 秒轮询任务状态，直到 COMPLETED 或 FAILED，随后展示图像或错误。

**为什么是 P1**: 没有结果展示，整个生成链路无意义。
**独立测试方式**: 手动将数据库某条任务改为 COMPLETED 并填入 resultImageUrl，轮询接口取到并前端渲染成功。
**验收场景**:
1. **Given** 有效 taskId，**When** 调用 `GET /api/v1/poetry/task/{taskId}`，**Then** 返回包含 `taskId / originalPoem / retrievedText / enhancedPrompt / resultImageUrl / taskStatus / errorMessage` 的对象
2. **Given** taskStatus=COMPLETED，**When** 前端收到响应，**Then** 停止轮询并渲染 `resultImageUrl` 图像
3. **Given** taskStatus=FAILED，**When** 前端收到响应，**Then** 停止轮询并展示 `errorMessage`
4. **Given** 不存在的 taskId，**When** 查询，**Then** 返回 HTTP 404
5. **Given** 任务处于 PENDING/PROCESSING，**When** 前端轮询，**Then** 继续每 2s 重复请求

---

### 用户故事 4 - AI 回调处理 (优先级: P1)

AI 微服务处理完成后，主动 POST 回调 Backend，Backend 更新任务状态和结果字段。

**为什么是 P1**: 没有回调，任务永远停留在 PROCESSING。
**独立测试方式**: 用 curl 直接调用 `POST /api/v1/poetry/callback`，验证数据库字段更新。
**验收场景**:
1. **Given** 正确的 `X-Callback-Token` + status=1 + imageUrl，**When** 调用回调接口，**Then** 数据库 taskStatus=COMPLETED、resultImageUrl 被写入
2. **Given** 正确 token + status=2 + errorMessage，**When** 调用回调接口，**Then** 数据库 taskStatus=FAILED、errorMessage 被写入
3. **Given** `X-Callback-Token` 不匹配，**When** 调用回调接口，**Then** 返回 HTTP 401，数据库不变

---

### 用户故事 5 - GLM 思考流 SSE (优先级: P2)

生成过程中，前端通过 SSE 实时展示 GLM Agent 的思考过程文字流。

**为什么是 P2**: 增强用户体验，核心链路不依赖此功能。
**独立测试方式**: 使用 `curl -N {sse_url}` 能持续收到 `data:` 事件直到 `[DONE]`。
**验收场景**:
1. **Given** 有效 taskId 且任务处于 PROCESSING，**When** 连接 SSE 端点，**Then** 收到 `Content-Type: text/event-stream`，持续推送 `data: {"text":"..."}\n\n`
2. **Given** AI 完成，**When** SSE 流结束，**Then** 推送 `data: [DONE]\n\n` 并关闭连接
3. **Given** 前端连接超过 120s，**When** 超时，**Then** 前端断开并展示超时提示

---

### 用户故事 6 - 历史任务记录浏览 (优先级: P2)

已登录用户在历史页面查看自己提交过的所有任务，含图像缩略图、状态和提交时间。

**为什么是 P2**: 便于查看过往成果，但不影响核心生成链路。
**独立测试方式**: 数据库中写入 3 条与当前用户关联的记录（不同状态），历史页面正确渲染列表。
**验收场景**:
1. **Given** 当前用户有 N 条历史任务，**When** 进入历史页面，**Then** 按创建时间倒序展示卡片（含缩略图/状态/时间）
2. **Given** 用户无历史任务，**When** 进入历史页面，**Then** 显示"暂无生成记录"和"新建生成"引导按钮
3. **Given** 点击历史卡片，**When** 跳转，**Then** 进入该任务的详情/结果页
4. **Given** 未登录，**When** 访问历史页面，**Then** 被重定向到 `/login`

### 边界与异常场景

- 并发提交同一账号多个任务：每个任务独立 UUID，互不影响
- AI 服务不可达：任务写入 PENDING，当前版本不自动重试（见开放问题）
- token 过期：前端清除 localStorage 并重定向到 `/login`
- 诗句包含特殊字符/emoji：系统应正常处理，不抛出 500

---

## 功能性要求 *(必填)*

### 功能性需求
- **FR-001**: 系统 MUST 在收到提交请求后 300ms 内返回 taskId（不含 AI 处理时间）
- **FR-002**: 系统 MUST 通过 JWT Bearer Token 保护所有 `/api/v1/poetry/*` 接口
- **FR-003**: 系统 MUST 用 `X-Callback-Token` 鉴权所有回调请求，Token 不匹配时返回 401
- **FR-004**: 系统 MUST 仅使用 `PENDING / PROCESSING / COMPLETED / FAILED` 四种任务状态
- **FR-005**: 用户 MUST 能通过 SSE 实时接收 GLM 思考过程推流
- **FR-006**: 系统 MUST 保证历史记录只返回当前登录用户的任务（不泄露他人数据）
- **FR-007**: Backend 错误响应 MUST 使用统一 `ErrorResponse` schema（见 backend.yaml）
- **FR-008**: poemText 长度 MUST 在 1-500 字符之间，否则返回 HTTP 400

### 关键实体
- **GenerationTask**: taskId(UUID) / userId / originalPoem / retrievedText / enhancedPrompt / resultImageUrl / taskStatus / errorMessage / createdAt / updatedAt
- **User**: id / username / passwordHash / nickname / createdAt

---

## 成功指标 *(必填)*

### 可量化成果

- **SC-001**: 提交接口 p99 延迟 < 300ms（不含 AI 处理）
- **SC-002**: 支持 10 路并发任务无状态错乱
- **SC-003**: 回调 token 校验失败率 0%（不可绕过）
- **SC-004**: 前端轮询误差在 2s ± 200ms 内
- **SC-005**: 历史页面加载（首屏）< 1s（不含图片加载）

---

## 附录 A：非目标（本期不做）
- 图像存储至 OSS（当前返回 mock URL）
- 任务失败后自动重试
- 多语言支持（中文界面固定）
- 管理员后台
- 账号注销 / 修改密码

---

## 附录 B：环境变量规范

| 变量名 | 必填 | 示例值 | 说明 |
|--------|------|--------|------|
| `DB_URL` | ✅ | `jdbc:mysql://localhost:3306/poetry_rag` | MySQL 连接串 |
| `DB_USERNAME` | ✅ | `root` | 数据库用户名 |
| `DB_PASSWORD` | ✅ | `secret` | 数据库密码 |
| `AI_SERVICE_URL` | ✅ | `http://127.0.0.1:8000/ai/api/v1/generate/async` | AI Service 异步触发地址 |
| `AI_CALLBACK_URL` | ✅ | `http://127.0.0.1:8080/api/v1/poetry/callback` | Backend 回调地址（AI Service 使用）|
| `AI_CALLBACK_TOKEN` | ✅ | `poetry-callback-token-change-me` | 回调鉴权 token |
| `GLM_API_KEY` | ✅ | `xxx.yyy` | 智谱 AI API Key |
| `GLM_BASE_URL` | ✅ | `https://open.bigmodel.cn/api/paas/v4` | GLM API Base URL |
| `GLM_MODEL` | ❌ | `glm-4-flash` | 使用的模型（glm-4-flash / glm-5）|
| `GLM_TIMEOUT` | ❌ | `90` | GLM 请求超时秒数，默认 60 |
| `CHROMA_PATH` | ❌ | `data/chromadb` | ChromaDB 本地路径 |
| `TOP_K` | ❌ | `5` | RAG 检索条数，默认 5 |

---

## 附录 C：接口引用

- Backend REST API: [specs/openapi/backend.yaml](../openapi/backend.yaml)
  - `POST /api/v1/auth/register`  注册
  - `POST /api/v1/auth/login`  登录（返回 JWT）
  - `POST /api/v1/poetry/generate`  提交任务
  - `GET  /api/v1/poetry/task/{taskId}`  查询状态
  - `POST /api/v1/poetry/callback`  AI 回调（X-Callback-Token 鉴权）
  - `GET  /api/v1/poetry/task/{taskId}/stream`  SSE 思考流
- AI Service API: [specs/openapi/ai-service.yaml](../openapi/ai-service.yaml)
  - `POST /ai/api/v1/generate/async`  异步触发管道
- 数据模型: [specs/architecture/data-model.md](../architecture/data-model.md)
- 系统架构: [specs/architecture/system-overview.md](../architecture/system-overview.md)
- RAG 管道详情: [specs/features/rag-pipeline.spec.md](rag-pipeline.spec.md)

---

## 附录 D：开放问题

- [ ] 图像存储方案最终选型：本地文件系统 / 对象存储 / Base64 内嵌？
- [ ] AI 服务不可达时是否需要队列重试机制（当前版本不做）？
- [ ] 任务历史数据保留策略：永久保留 / 定期清理？
- [ ] `enhancedPrompt` 是否需要翻译为标准 Stable Diffusion 标签格式？
- [ ] 图像生成当前是否已集成（还是仍返回 mock URL）？需明确里程碑
