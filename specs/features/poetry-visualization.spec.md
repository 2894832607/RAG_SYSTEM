# Feature Specification: 诗词可视化生成系统

**Feature Branch**: `main`  
**Created**: 2026-03-05  
**Updated**: 2026-03-06  
**Status**: In Progress（主流程已可用，功能持续迭代中）

---

## 概述

用户与 **LangGraph ReAct Agent** 对话，Agent 自主决策：
- 问答/赏析 → 调用 `search_poetry` 工具检索知识库并回答
- 生图需求 → 调用 `visualize_poem` 工具完成 RAG→提示词增强→CogView-4 生图
- 诗句输入（前端 `detectVisualizeIntent` 自动识别）→ 走独立 Storyboard 分镜流程，多张图逐步推送

> ⚠️ **注意**：主流程（对话 & 分镜）**经过 Backend 代理**，Frontend → Backend → AI Service。
> Backend 负责 JWT 认证、SSE 代理转发和历史记录持久化。
> 直连 AI Service 的通道已关闭（符合 constitution §3.1 分层规范）。

---

## ~~旧版说明（已废弃，仅供参考）~~

> ~~"用户输入中文诗句，系统通过 RAG + GLM LangGraph Agent 管道生成与诗意相符的可视化图像，并通过任务轮询将结果展示给用户"~~
>
> 此描述对应旧的"提交任务 → 轮询 → 回调"架构，**当前已被 SSE 直连架构取代**。
> 旧路径（`/api/v1/poetry/generate` + 轮询 + callback）仍保留在 Backend，供脚本测试使用，但不再是主 UX。

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

### 用户故事 2 — 诗词问答对话 [P1] ✅ 已实现

用户输入问题（如"李白最著名的几首诗"），ReAct Agent 检索知识库后流式输出回答。

**独立测试方式**: `curl -N -X POST http://localhost:8080/api/v1/poetry/chat -H "Authorization: Bearer <token>" -d '{"message":"静夜思写了什么","session_id":""}'`，能收到 SSE token 事件流。
**验收场景**:
1. **Given** 用户输入问答类文本，**When** 前端 `detectVisualizeIntent` 返回 false，**Then** 走 `/api/v1/poetry/chat`（经 Backend 代理）SSE 路径
2. **Given** Agent 需要查诗，**When** 推理，**Then** 自动调用 `search_poetry` 工具，前端收到 `tool` / `tool_end` / `rag_result` 事件
3. **Given** Agent 输出 token，**When** 流式推送，**Then** 前端逐字渲染回复文字
4. **Given** 多轮对话，**When** 使用同一 `session_id`，**Then** Agent 记忆上下文（MemorySaver）

---

### 用户故事 3 — 诗句分镜多图生成 [P1] ✅ 已实现 ⭐ 核心

用户输入诗句，前端自动识别并触发分镜流程：RAG 检索 → GLM 规划 → CogView-4 逐张生图推送。

**独立测试方式**: `curl -N -X POST http://localhost:8080/api/v1/poetry/storyboard -H "Authorization: Bearer <token>" -d '{"sourceText":"大漠孤烟直，长河落日圆"}'` 能收到 plan + shot_done 事件。
**验收场景**:
1. **Given** 用户输入≥10字中文诗句且无问句词，**When** `detectVisualizeIntent` 返回 true，**Then** 前端调用 `/api/v1/poetry/storyboard`（经 Backend 代理）
2. **Given** RAG 检索完成，**When** 推送 `progress` 事件，**Then** 前端显示检索到的诗词标题
3. **Given** GLM 规划完成，**When** 推送 `plan` 事件，**Then** 前端显示分镜标题/作者/朝代/总张数
4. **Given** 每张图生成完成，**When** 推送 `shot_done` 事件，**Then** 前端分镜网格逐格显示图片
5. **Given** 图生成中，**When** 尚未收到 `shot_done`，**Then** 前端显示骨架占位格
6. **Given** 全部完成，**When** 收到 `done` 事件，**Then** 前端状态文字更新为"全部完成"

---

### 用户故事 4 — 用户注册与登录 [P1] ✅ 已实现

**验收场景**:
1. **Given** 合法 username + password，**When** `POST /api/v1/auth/register`，**Then** 返回 HTTP 200 + `token` + `user`
2. **Given** 正确凭据，**When** `POST /api/v1/auth/login`，**Then** 返回 JWT token
3. **Given** 错误密码，**When** 登录，**Then** 返回 HTTP 401
4. **Given** 未携带 token，**When** 访问受保护 Backend 接口，**Then** 返回 HTTP 401

---

### 用户故事 5 — 历史任务记录浏览 [P2] ✅ 已实现

**验收场景**:
1. **Given** 用户有历史任务，**When** 进入历史页面，**Then** 按倒序展示任务卡片
2. **Given** 无历史任务，**When** 进入历史页面，**Then** 显示空状态 + 新建引导
3. **Given** 未登录，**When** 访问历史页面，**Then** 重定向到 `/login`

---

### 用户故事 6 — 对话建议词（Suggestions）[P2] ✅ 已实现

Agent 回复末尾推送 `💡` 建议块，前端解析为快捷按钮。

**验收场景**:
1. **Given** Agent 回复含 `💡` 块，**When** 前端解析，**Then** 渲染建议按钮
2. **Given** 点击建议按钮，**When** 触发，**Then** 直接发送该文本

---

### 边界与异常场景

- 诗句含特殊字符/emoji：系统正常处理，不抛出 500
- GLM 不可达：前端收到 `error` 事件，显示错误提示
- session_id 留空：AI Service 自动生成新会话 UUID
- 分镜单张生成失败：推送 `shot_error` 事件，前端显示该格错误，其余格继续渲染

---

## 功能性要求

- **FR-001**: 前端 MUST 通过 `detectVisualizeIntent()` 自动路由，**不得有手动切换按钮**
- **FR-002**: 分镜生成 MUST 走 `/ai/api/v1/generate/storyboard` 独立 SSE 端点
- **FR-003**: 对话 MUST 走 `/ai/api/v1/chat` SSE 端点，由 LangGraph ReAct Agent 处理
- **FR-004**: Agent 工具调用 MUST 以 SSE 事件推送给前端（`tool` / `tool_end` / `rag_result`）
- **FR-005**: Backend JWT MUST 保护所有 `/api/v1/poetry/*` 及用户数据接口
- **FR-006**: Backend 错误响应 MUST 使用统一 `ErrorResponse` schema（见 backend.yaml）
- **FR-007**: poemText 长度 MUST 在 1-500 字符之间
- **FR-008**: 历史记录 MUST 只返回当前登录用户数据，不泄露他人

### 意图路由规则（前端 `detectVisualizeIntent`）

| 条件 | 路由到 |
|------|--------|
| 含关键词：生成图/画出/可视化/意境图/插画/分镜/生图/画一幅/画成 | `/generate/storyboard` |
| ≥10字中文，无问句词（什么/为什么/如何/怎么/谁/哪/是不是/吗/呢），不以？结尾 | `/generate/storyboard` |
| 其余 | `/chat` |

### 关键实体
- **ChatMessage**（前端）: id / role / userText / replyText / tools / ragResults / storyboardShots / storyboardPlan / isStreaming
- **StoryboardShot**: shot_id / shot_name / shot_type / poem_lines / camera_angle / emotion / positive_prompt / image_url
- **GenerationTask**（Backend MySQL）: taskId / userId / originalPoem / taskStatus / resultImageUrl / createdAt

---

## 成功指标

- **SC-001**: 对话首 token 到达延迟 < 3s
- **SC-002**: 分镜第一张图到达延迟 < 30s
- **SC-003**: 历史页面首屏加载 < 1s（不含图片）
- **SC-004**: `detectVisualizeIntent` 误判率 < 5%（典型诗句 & 问答各 20 条测试）

---

## 附录 A：非目标（本期不做）
- 图像存储至 OSS
- 任务失败自动重试
- 管理员后台
- 账号注销 / 修改密码
- 会话历史持久化到数据库（当前 MemorySaver 重启后丢失）

---

## 附录 B：环境变量规范

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `GLM_API_KEY` | ✅ | 智谱 AI API Key |
| `GLM_BASE_URL` | ✅ | GLM API Base URL |
| `GLM_MODEL` | ❌ | 模型名，默认 glm-4-flash |
| `GLM_TIMEOUT` | ❌ | 超时秒数，默认 60 |
| `CHROMA_PATH` | ❌ | ChromaDB 路径，默认 data/chromadb |
| `TOP_K` | ❌ | RAG 检索条数，默认 5 |
| `COGVIEW_MODEL` | ❌ | 生图模型，默认 cogview-4 |
| `DB_URL` | ✅ | (Backend) MySQL 连接串 |
| `DB_USERNAME` / `DB_PASSWORD` | ✅ | (Backend) 数据库凭据 |

---

## 附录 C：接口引用

- AI Service: [specs/openapi/ai-service.yaml](../openapi/ai-service.yaml)
  - `POST /ai/api/v1/chat` — ⭐ 主对话 SSE
  - `POST /ai/api/v1/generate/storyboard` — ⭐ 分镜生成 SSE
  - `POST /ai/api/v1/chat/session` — 创建会话
  - `GET /ai/api/v1/chat/session/{id}/history` — 历史消息
- Backend: [specs/openapi/backend.yaml](../openapi/backend.yaml)
  - `POST /api/v1/auth/register` / `POST /api/v1/auth/login`
  - `POST /api/v1/poetry/chat` — ⭐ 主对话 SSE 代理（JWT）
  - `POST /api/v1/poetry/storyboard` — ⭐ 分镜生成 SSE 代理（JWT）
  - `POST /api/v1/poetry/chat/session` — 创建会话（JWT）
  - `GET  /api/v1/poetry/history` — 历史记录（JWT）
- 数据模型: [specs/architecture/data-model.md](../architecture/data-model.md)
- 系统架构: [specs/architecture/system-overview.md](../architecture/system-overview.md)
- RAG 管道: [specs/features/rag-pipeline.spec.md](rag-pipeline.spec.md)

---

## 附录 D：开放问题

- [ ] `detectVisualizeIntent` 短诗句（<10字）目前走对话，是否需要更细粒度规则？
- [ ] `visualize_poem` 工具（单图）与 Storyboard 流程（多图）是两套生图逻辑，是否统一？
- [x] SSE 主流程生成的图像未写入 MySQL 历史，需补全写入逻辑（已完成：AiProxyController.storyboard() + saveStoryboardHistory()）
- [ ] MemorySaver 会话记忆重启后丢失，是否需要 Redis 持久化？
- [ ] 分镜 CogView-4 当前串行生图，是否改为并行提速？
