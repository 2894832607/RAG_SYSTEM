# 诗境 Agent — 设计说明书 v1.0

> 本文档是「诗境」AI Agent 的完整技术与产品设计说明，面向开发者和提示词工程师。每节均标注对应的文件路径，方便直接定位修改。

---

## 1. 产品定位

「诗境」是一个以**中国古典诗词文化**为核心的 AI Agent。

| 维度 | 说明 |
|---|---|
| 核心人设 | 精通古典诗词的文化向导，语气优雅亲和 |
| 核心能力 | 诗词问答 · 意境检索 · 场景可视化 |
| 技术底座 | GLM-5 (推理模型) + ChromaDB (向量检索) + Stable Diffusion (图像生成) |
| 对话记忆 | 会话级记忆，同一 session 保持上下文连贯 |

---

## 2. 架构总览

```
用户消息
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PLANNER 层                                │
│   [planner_node]  → 读取 prompts/planner/intent_router.md       │
│   GLM-5 输出 JSON 意图分类：                                      │
│   { intent, confidence, subject, reason }                       │
└────────────────────────┬────────────────────────────────────────┘
                         │ 条件路由 (route_by_intent)
          ┌──────────────┼──────────────────────────┐
          │              │              │            │
      CHAT/CLARIFY  POETRY_QA     POETRY_SEARCH  VISUALIZE
          │          POETRY_SEARCH       │            │
          ▼              └───────────────┘            ▼
   ┌─────────────┐          ┌───────────────┐   ┌────────────────────────┐
   │  CHAT 层    │          │   QA 层       │   │   可视化链路           │
   │ chat_node   │          │ poetry_qa_node│   │ visualize_chain_node   │
   │             │          │               │   │                        │
   │ main_agent  │          │ main_agent +  │   │  Step 1: Retriever     │
   │ + general   │          │ poetry_qa     │   │  → ChromaDB 向量检索   │
   │ (direct LLM)│          │ (ReAct +      │   │                        │
   └─────────────┘          │  search tool) │   │  Step 2: PromptEnhancer│
                            └───────────────┘   │  → GLM 增强提示词      │
                                                │  (prompts/chains/      │
                                                │   visualize/02_enhance)│
                                                │                        │
                                                │  Step 3: DiffusionClient│
                                                │  → 调用 SD API 出图    │
                                                └────────────────────────┘
```

**文件对应：**
- Planner 节点：`app/agent/graph.py → planner_node()`
- Chat 节点：`app/agent/graph.py → chat_node()`
- QA 节点：`app/agent/graph.py → poetry_qa_node()`
- 可视化链路：`app/agent/graph.py → visualize_chain_node()` + `app/modules/{retriever,prompt,generation}.py`

---

## 3. Prompt 文件目录

所有 Prompt 放在 `app/prompts/`，与代码解耦。修改后重启服务生效。

```
app/prompts/
├── README.md                         ← 调优指南
├── system/
│   └── main_agent.md                 ← ★ Agent 人设、规则、能力列表（最重要）
├── planner/
│   └── intent_router.md              ← 意图分类（JSON 输出格式，含示例）
├── chains/
│   └── visualize/
│       ├── 01_retrieve.md            ← 检索结果整理（暂用于未来扩展）
│       ├── 02_enhance.md             ← SD 提示词生成（直接影响图像质量）★
│       └── 03_generate.md            ← 生成后回复模板
└── chat/
    ├── poetry_qa.md                  ← 问答结构规范（赏析格式、推荐格式）
    └── general.md                    ← 通用对话兜底规则
```

### 各文件调优优先级

| 文件 | 调优影响 | 建议方向 |
|---|---|---|
| `system/main_agent.md` | 影响所有节点 | 调整人设、禁止行为、回复风格 |
| `planner/intent_router.md` | 影响路由准确率 | 增加示例、调整意图描述 |
| `chains/visualize/02_enhance.md` | 影响图像生成质量 | 增加风格词、调整质量标签 |
| `chat/poetry_qa.md` | 影响问答结构 | 调整回答格式要求 |

---

## 4. 节点详细说明

### 4.1 Planner 节点

| 属性 | 值 |
|---|---|
| 文件 | `app/agent/graph.py → planner_node()` |
| Prompt | `app/prompts/planner/intent_router.md` |
| 输出 | `state.intent`, `state.subject`, `state.plan` |
| 容错 | JSON 解析失败时降级为 `CHAT` |

**意图标签：**

| 标签 | 触发条件 | 路由到 |
|---|---|---|
| `CHAT` | 闲聊、询问 Agent 自身 | `chat_node` |
| `POETRY_QA` | 诗词赏析/解释/注释 | `poetry_qa_node` |
| `POETRY_SEARCH` | 找诗/意境检索 | `poetry_qa_node` |
| `VISUALIZE` | 生成图片/可视化 | `visualize_chain_node` |
| `CLARIFY` | 意图不明 | `clarify_node` |

### 4.2 Chat 节点

| 属性 | 值 |
|---|---|
| 文件 | `app/agent/graph.py → chat_node()` |
| Prompt | `system/main_agent` + `chat/general` |
| 工具 | 无（直接 LLM 对话） |
| 适用 | 闲聊、功能询问、简单问题 |

### 4.3 诗词问答节点

| 属性 | 值 |
|---|---|
| 文件 | `app/agent/graph.py → poetry_qa_node()` |
| Prompt | `system/main_agent` + `chat/poetry_qa` |
| 工具 | `search_poetry`（ChromaDB 语义检索） |
| 框架 | LangGraph `create_react_agent` (ReAct 循环) |
| 适用 | 赏析、注释、找诗、推荐 |

### 4.4 可视化链路（Core Skill）

| 步骤 | 模块 | Prompt 文件 | 说明 |
|---|---|---|---|
| Step 1：RAG 检索 | `app/modules/retriever.py` | — | ChromaDB 向量召回，返回相似诗词 |
| Step 2：提示词增强 | `app/modules/prompt.py` | `chains/visualize/02_enhance.md` | GLM 将诗句+知识转为 SD 英文提示词 |
| Step 3：图像生成 | `app/modules/generation.py` | — | 调用 Stable Diffusion API 出图 |
| Step 4：结果回复 | `app/agent/graph.py` | `chains/visualize/03_generate.md` | 向用户展示结果 |

---

## 5. API 端点说明

服务启动在 `http://localhost:8000`，通过 Spring Boot（8080）代理到前端。

| 端点 | 方法 | 说明 |
|---|---|---|
| `GET /ai/health` | GET | 健康检查 |
| `POST /ai/api/v1/generate/async` | POST | 异步可视化任务（Spring Boot 调用） |
| `POST /ai/api/v1/generate/simple` | POST | 同步可视化（测试用） |
| `POST /ai/api/v1/generate/think-stream` | POST | GLM 思维流 SSE（前端实时展示思考过程） |
| `POST /ai/api/v1/chat/session` | POST | 创建新对话会话 |
| `GET /ai/api/v1/chat/session/{id}/history` | GET | 获取会话历史 |
| `POST /ai/api/v1/chat/stream` | POST | Agent 对话（SSE 流式回复） |

---

## 6. 添加新 Capability（扩展指南）

以「古诗词生成」为例，介绍如何为 Agent 新增一个 Skill：

### Step 1：新增意图标签
编辑 `app/prompts/planner/intent_router.md`，在意图表格中添加：
```
| `COMPOSE` | 根据要求创作新古诗 | 写一首、作一首、仿照 |
```

### Step 2：新增 Prompt 文件
创建 `app/prompts/chains/compose/main.md`，写入创作指令。

### Step 3：新增节点函数
在 `app/agent/graph.py` 中添加：
```python
def compose_node(state: AgentState) -> dict:
    subject = state.get("subject", "")
    system = load_prompt("system/main_agent") + "\n\n" + load_prompt("chains/compose/main")
    response = get_llm().invoke([SystemMessage(content=system)] + list(state["messages"]))
    return {"messages": [response]}
```

### Step 4：注册到图
```python
builder.add_node("compose_node", compose_node)
builder.add_edge("compose_node", END)
```

### Step 5：更新路由函数
```python
if intent == "COMPOSE":
    return "compose_node"
```

---

## 7. 记忆与会话管理

- **记忆后端**：LangGraph `MemorySaver`（进程内内存，重启清空）
- **会话隔离**：每个 `session_id` 对应独立的对话历史
- **持久化**（TODO）：将 MemorySaver 替换为 `SqliteSaver` 或 `PostgresSaver`

---

## 8. 环境变量

| 变量名 | 必须 | 说明 |
|---|---|---|
| `GLM_API_KEY` | ✅ | 智谱 AI 开放平台 Key |
| `GLM_BASE_URL` | 否 | 默认 `https://open.bigmodel.cn/api/paas/v4` |
| `GLM_MODEL` | 否 | 默认 `glm-4-flash`，推荐 `glm-5` |
| `GLM_TIMEOUT` | 否 | 请求超时秒数，默认 90 |
| `SD_API_URL` | 否 | Stable Diffusion WebUI API，如未配置图像生成为 Mock |

---

## 9. 开发工作流

### 快速启动
```powershell
# 设置环境变量
$env:GLM_API_KEY='your-key'
$env:GLM_MODEL='glm-5'
$env:GLM_TIMEOUT='90'
$env:PYTHONPATH='D:\path\to\ai-service'

# 启动服务
.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Prompt 调优流程
1. 编辑 `app/prompts/` 下对应文件
2. 重启服务（或等待 `--reload` 触发）
3. 用 `curl` 或前端测试效果
4. 提交前在 `prompts/README.md` 中记录修改原因

### 测试单个节点
```powershell
# 测试思维流（验证 Planner + GLM-5 链路）
curl -X POST http://localhost:8000/ai/api/v1/generate/think-stream \
  -H "Content-Type: application/json" \
  -d '{"sourceText":"大漠孤烟直，长河落日圆"}'

# 测试 Agent 对话
curl -X POST http://localhost:8000/ai/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"帮我解释这句诗：春眠不觉晓","session_id":"test-001"}'
```

---

## 10. 已知限制与 TODO

| 项目 | 当前状态 | TODO |
|---|---|---|
| 记忆持久化 | 进程内，重启清空 | 接入 PostgreSQL / Redis |
| Planner 准确率 | GLM-5 约 90%+ | 增加 few-shot 示例 |
| 可视化链路 | SD Mock（无外网 SD 时返回占位图） | 接入本地 SD WebUI 或云 API |
| 流式回复 | think-stream 端点可用 | Agent chat 全链路流式 |
| 多模态输入 | 仅文本 | 支持图片输入（"这图对应哪首诗"） |
