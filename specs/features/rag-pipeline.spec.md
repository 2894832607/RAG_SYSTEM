# Feature Specification: RAG 检索增强生成管道

**Feature Branch**: `main`  
**Created**: 2026-03-05  
**Status**: Draft  
**Input**: 用户描述: "AI 微服务接收诗句后，经向量检索与 LangGraph Agent 推理，输出高质量图像生成 Prompt，并回调 Backend 更新任务状态"

---

## 用户场景与测试 *(必填)*

<!--
  RAG 管道由 AI 微服务内部执行，"用户"为 Backend 服务或直接调用 API 的开发者。
  每条故事必须独立可测试。
-->

### 用户故事 1 - 诗句向量检索 (优先级: P1)

Backend 调用 AI 微服务触发管道后，系统对输入诗句进行 ChromaDB 语义检索，返回相关古诗文片段，为后续 Agent 推理提供上下文。

**为什么是 P1**: 检索是 RAG 管道的第一步，无检索则 Prompt 质量无保证。

**独立测试方式**: 直接调用 `retriever.py` 中的检索函数，传入任意诗句，断言返回至少 1 条相关文档，ChromaDB 正常可达。

**验收场景**:

1. **Given** 有效的中文诗句输入，**When** 调用向量检索，**Then** 从 ChromaDB `poetry` Collection 返回至少 1 条相关文档片段
2. **Given** Top-K 环境变量设为 5，**When** 检索，**Then** 最多返回 5 条结果
3. **Given** ChromaDB 不可达，**When** 触发检索，**Then** 抛出可捕获异常（不抛出未处理 500），并通过 callback status=2 上报

---

### 用户故事 2 - LangGraph Agent 推理增强 (优先级: P1) ⭐ 核心

系统将检索到的诗文片段与原始诗句注入 LangGraph Agent，由 GLM 生成适合 Stable Diffusion 输入的英文视觉描述 Prompt。

**为什么是 P1**: 这是 RAG 管道的核心增值步骤，直接决定图像生成质量。

**独立测试方式**: 构造 `sourceText` + `retrievedText`，直接调用 `graph.py` 中的 Agent，断言输出非空字符串且包含视觉描述词。

**验收场景**:

1. **Given** 有效的 `sourceText` + `retrievedText`，**When** Agent 执行推理，**Then** 输出非空 `enhancedPrompt`（英文或中英混合，包含视觉描述词）
2. **Given** Few-shot 示例已从 `data/fewshot_examples.json` 加载，**When** Agent 初始化，**Then** 示例注入 system prompt，推理结果质量可感知提升
3. **Given** GLM API 超时，**When** 推理，**Then** 重试最多 3 次（指数退避），仍失败则通过 callback status=2 上报错误
4. **Given** Agent 输出为空字符串，**When** 结果校验，**Then** 视为失败，触发 callback status=2

---

### 用户故事 3 - 异步回调通知 Backend (优先级: P1)

管道执行完成（无论成功或失败）后，AI 微服务主动 POST 回调 Backend，携带结果或错误信息。

**为什么是 P1**: 没有回调，Backend 无法更新任务状态，整个异步链路断裂。

**独立测试方式**: 启动 `scripts/mock_callback_server.py`，运行管道，验证 mock 服务器收到预期的回调 body。

**验收场景**:

1. **Given** 管道执行成功，**When** 触发回调，**Then** `POST callbackUrl` 携带 `X-Callback-Token`，body 包含 `status=1` 和非空 `payload.imageUrl`
2. **Given** 管道失败（任意环节），**When** 触发回调，**Then** body 包含 `status=2` 和非空 `errorMessage`
3. **Given** `X-Callback-Token` 不匹配，**When** Backend 收到回调，**Then** Backend 返回 HTTP 401，AI 微服务记录日志
4. **Given** 回调 URL 不可达（网络超时），**When** 回调失败，**Then** 记录日志，不抛出未捕获异常，HTTP 请求超时设为 10s

---

### 边界与异常场景

- Prompt 输出为空：视为失败，强制触发 callback status=2，不允许写入空结果
- GLM API 调用超时 (`GLM_TIMEOUT`)：指数退避重试 3 次后放弃
- ChromaDB 检索返回 0 条：降级处理（仅用原始诗句输入 Agent），不阻断管道
- callbackUrl 为空或格式非法：日志警告，跳过回调

---

## 功能性要求 *(必填)*

### 功能性需求

- **FR-001**: 系统 MUST 使用 ChromaDB Collection `poetry` 进行向量检索，Top-K 默认 5 且可配置
- **FR-002**: 系统 MUST 使用 LangGraph 状态图框架调度 Agent，不允许直接调用 LLM 绕过图结构
- **FR-003**: `enhancedPrompt` MUST 为非空字符串，且包含英文视觉描述词
- **FR-004**: GLM API 失败 MUST 触发最多 3 次重试（指数退避），最终失败必须通过 callback status=2 上报
- **FR-005**: 回调请求 MUST 携带 `X-Callback-Token` 请求头，超时设为 10s
- **FR-006**: 管道失败 MUST 通过 callback status=2 + errorMessage 上报，严禁直接抛出 HTTP 500
- **FR-007**: Few-shot 示例 MUST 从 `data/fewshot_examples.json` 加载并注入 system prompt

### 关键实体

- **PipelineInput**: `taskId` / `sourceText` / `callbackUrl` / `callbackToken`
- **PipelineResult**: `taskId` / `retrievedText` / `enhancedPrompt` / `imageUrl`（预留）
- **CallbackBody**: `taskId` / `status`(1=成功, 2=失败) / `payload.imageUrl` / `errorMessage`

---

## 成功指标 *(必填)*

### 可量化成果

- **SC-001**: 向量检索 p99 延迟 < 500ms（本地 ChromaDB）
- **SC-002**: Agent 推理成功率 > 95%（含重试，测试集 100 条诗句）
- **SC-003**: `enhancedPrompt` 非空率 = 100%（失败时通过回调上报，不写入空值）
- **SC-004**: 回调送达率 > 99%（callbackUrl 可达时）
- **SC-005**: 单次管道端到端处理时间（不含图像生成）< 30s

---

## 附录 A：管道架构

```
sourceText
  │
  ▼
① Embed & Retrieve（ChromaDB 语义检索）
  │  ← gushiwen_cleaned.jsonl 预索引
  │
  ▼
② LangGraph Agent（GLM 增强 Prompt）
  │  ← system/main_agent.md 系统提示
  │  ← fewshot_examples.json 少样本示例
  │
  ▼
③ Prompt 标准化输出
  │
  ▼
④ （预留）Stable Diffusion / 图像 API 调用
  │
  ▼
⑤ Callback → Backend
```

---

## 附录 B：LangGraph Agent 技术规格

| 项目 | 要求 |
|------|------|
| Agent 框架 | LangGraph（状态图）|
| LLM | GLM-4-Flash / GLM-5（由 `GLM_MODEL` 环境变量控制）|
| 输入 | `sourceText` + `retrievedText` |
| 输出 | `enhancedPrompt`（英文，适合 Stable Diffusion 输入）|
| Few-shot | 从 `data/fewshot_examples.json` 加载，注入 system prompt |
| 重试次数 | 最多 3 次（指数退避）|

---

## 附录 C：环境变量规范

| 变量名 | 必填 | 示例值 | 说明 |
|--------|------|--------|------|
| `GLM_API_KEY` | ✅ | `xxx.yyy` | 智谱 AI 密钥 |
| `GLM_BASE_URL` | ✅ | `https://open.bigmodel.cn/api/paas/v4` | API base URL |
| `GLM_MODEL` | ✅ | `glm-4-flash` | 使用的模型名 |
| `GLM_TIMEOUT` | ❌ | `90` | 请求超时秒数，默认 60 |
| `CHROMA_PATH` | ❌ | `data/chromadb` | ChromaDB 本地路径 |
| `TOP_K` | ❌ | `5` | 检索条数 |

---

## 附录 D：错误处理规范

| 场景 | 处理方式 |
|------|---------|
| GLM API 超时 | 重试 3 次（指数退避），仍失败则回调 status=2 |
| ChromaDB 不可达 | 直接回调 status=2 + errorMessage |
| Prompt 输出为空 | 视为失败，回调 status=2 |
| callbackUrl 不可达 | 写入本地日志，不重试 |

---

## 附录 E：接口引用

- AI Service OpenAPI: [specs/openapi/ai-service.yaml](../openapi/ai-service.yaml)

---

## 附录 F：开放问题

- [ ] 是否需要把 `enhancedPrompt` 翻译成标准 Stable Diffusion 标签格式？
- [ ] 图像生成目前是否已集成，还是仍返回 mock URL？
- [ ] Few-shot 示例是否需要定期更新机制？
- [ ] ChromaDB 检索返回 0 条时，是否需要降级策略文档化？
