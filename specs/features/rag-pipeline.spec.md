# Feature Specification: RAG 检索增强生成管道

**Feature Branch**: `main`  
**Created**: 2026-03-05  
**Updated**: 2026-03-06  
**Status**: In Progress（核心链路已实现）

> RAG 管道在 AI 微服务内部执行，服务于两条路径：
> 1. **ReAct Agent 工具调用**：`search_poetry`（检索展示）、`visualize_poem`（检索→生图）
> 2. **Storyboard 分镜**：`Retriever.smart_retrieve()` → GLM 规划 → CogView-4

---

## 用户场景与测试

### 用户故事 1 — 诗句向量检索 [P1] ✅ 已实现

系统对输入诗句/意象描述进行 ChromaDB 语义检索，返回相关诗词片段。

**独立测试方式**: 直接调用 `scripts/smoke_test.py` 或 `Retriever().smart_retrieve("大漠孤烟直")`，断言返回至少 1 条结果。

**验收场景**:
1. **Given** 有效中文诗句，**When** 调用向量检索，**Then** 从 ChromaDB `poetry` Collection 返回至少 1 条相关文档
2. **Given** TOP_K=5，**When** 检索，**Then** 最多返回 5 条结果
3. **Given** 输入为精确诗句（高相似度），**When** `smart_retrieve`，**Then** 返回 `mode=exact`，首条匹配诗词含完整译文
4. **Given** 输入为白话意境描述，**When** `smart_retrieve`，**Then** 返回 `mode=semantic`，最多 5 首候选
5. **Given** ChromaDB 不可达，**When** 检索，**Then** 工具返回友好错误文本，不抛出未处理异常

---

### 用户故事 2 — ReAct Agent 推理与工具调用 [P1] ✅ 已实现

LangGraph ReAct Agent 自主决策：问答时调 `search_poetry`，生图时调 `visualize_poem`。

**独立测试方式**: POST `/ai/api/v1/chat` 发送含诗句的 message，能收到 `tool` 事件和最终回复。

**验收场景**:
1. **Given** 用户问"李白的静夜思"，**When** Agent 推理，**Then** 调用 `search_poetry`，返回诗词全文+译文
2. **Given** 用户要求"画出这首诗"，**When** Agent 推理，**Then** 调用 `visualize_poem`，前端收到图像 URL
3. **Given** 同一 session_id 多轮对话，**When** Agent 处理，**Then** MemorySaver 保持上下文，Agent 能引用上文
4. **Given** 工具调用完成，**When** 推送 `tool_end` 事件，**Then** `output` 字段包含格式化诗词文本或图像 URL

---

### 用户故事 3 — 分镜生图管道 [P1] ✅ 已实现

`StoryboardGenerator` 完成：RAG 检索 → GLM 规划分镜 → CogView-4 逐张生图。

**独立测试方式**: `curl -N POST /ai/api/v1/generate/storyboard -d '{"sourceText":"春江潮水连海平"}'`，能收到 `plan` 和 `shot_done` 事件。

**验收场景**:
1. **Given** 诗句输入，**When** RAG 检索，**Then** 推送 `progress` 事件含检索到的诗词标题
2. **Given** 检索完成，**When** GLM 规划，**Then** 返回分镜方案（全景基调 1 张 + 叙事 3-5 张），推送 `plan` 事件
3. **Given** 分镜方案确定，**When** CogView-4 生成每张图，**Then** 逐张推送 `shot_done`，含 image_url
4. **Given** 某张图生成失败，**When** 出错，**Then** 推送 `shot_error`，其余张继续
5. **Given** 全部完成，**When** 推送 `done`，**Then** `total_shots` 为实际完成张数

---

### 用户故事 4 — Legacy 异步回调通知 [P2] ✅ 已实现（非主 UX）

`/generate/async` 端点供脚本使用，生成完成后 POST 回调 Backend。

**验收场景**:
1. **Given** 脚本调用 `/generate/async`，**When** 生成完成，**Then** POST `callback_url` 含 result
2. **Given** 回调失败，**When** 网络超时，**Then** 记录日志，不影响主 SSE 流程

---

## 功能需求（FR）

| ID | 需求 | 优先级 | 状态 |
|----|------|--------|------|
| FR-RAG-01 | `Retriever.smart_retrieve()` 支持 exact/semantic 双模式 | P1 | ✅ 已实现 |
| FR-RAG-02 | ChromaDB 不可达时工具返回友好降级文本 | P1 | ✅ 已实现 |
| FR-RAG-03 | ReAct Agent 工具超时保护（search 20s，visualize 120s） | P1 | ✅ 已实现 |
| FR-RAG-04 | 分镜管道 SSE 流式推送进度事件 | P1 | ✅ 已实现 |
| FR-RAG-05 | 分镜内某张图失败不中断整体流程 | P1 | ✅ 已实现 |
| FR-RAG-06 | MemorySaver 跨轮次保持会话上下文 | P1 | ✅ 已实现 |
| FR-RAG-07 | 分镜生成结果写入历史记录（MySQL） | P1 | ❌ 待实现 (T001) |
| FR-RAG-08 | 分镜 CogView-4 并行生图（asyncio.gather） | P2 | 🔄 评估中 (T004) |
| FR-RAG-09 | Session 内存持久化（Redis checkpoint） | P2 | 🔄 评估中 (T003) |
| FR-RAG-10 | `original_poem` 为空时从 `search_payload` fallback | P1 | ✅ 已修复 |
| FR-RAG-11 | `prompt_loader` 使用正则替换避免 JSON 花括号误解析 | P1 | ✅ 已修复（需重启服务） |

---

## 性能指标

| 指标 | 目标 | 当前状态 |
|------|------|----------|
| ChromaDB 检索延迟 | < 500ms | 达标 |
| `search_poetry` 工具超时 | 20s | 已配置 |
| `visualize_poem` 工具超时 | 120s | 已配置 |
| 分镜全流程（3 张图） | < 90s | 依赖 CogView-4 API |
| Agent SSE 首 token | < 2s | 达标 |

---

## 附录 A：数据模型

```
ChromaDB Collection: poetry
  - id: string
  - document: string（诗词全文+字段 JSON）
  - embedding: float[]（text-embedding-v2, 1536 维）
  - metadata: { title, author, dynasty, tags[] }
```

数据来源：`data/gushiwen_cleaned.jsonl`（约 6000 首），通过 `scripts/02_ingest_chromadb.py` 导入。

---

## 附录 B：SSE 事件格式

### `/chat` 事件
```jsonc
{ "type": "token",       "content": "..." }
{ "type": "tool",        "tool": "search_poetry", "input": {...} }
{ "type": "tool_end",    "tool": "search_poetry", "output": "..." }
{ "type": "rag_result",  "poems": [...] }
{ "type": "node_progress","node": "...", "status": "..." }
{ "type": "done",        "session_id": "..." }
{ "type": "error",       "message": "..." }
```

### `/generate/storyboard` 事件
```jsonc
{ "type": "progress",   "message": "检索到：静夜思..." }
{ "type": "plan",       "shots": [{"index":1, "prompt":"..."}, ...] }
{ "type": "shot_done",  "index": 1, "image_url": "https://..." }
{ "type": "shot_error", "index": 2, "message": "..." }
{ "type": "done",       "total_shots": 4 }
```

---

## 附录 C：开放问题

- [ ] 分镜 CogView-4 当前串行，是否改 `asyncio.gather` 并行（详见 tasks.md T004）？
- [ ] `visualize_poem` 单图工具与 Storyboard 多图是否统一为同一入口（详见 tasks.md T005）？
- [ ] Few-shot 示例（`data/fewshot_examples.json`）是否需要定期更新机制？
- [ ] ChromaDB 检索返回 0 条的降级策略是否需要文档化并加测试？

