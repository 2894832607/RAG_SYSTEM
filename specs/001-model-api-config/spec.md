# Feature Spec: 模型 API 自由配置

> Status: COMPLETED ✅
> Version: 1.0
> Branch: `001-model-api-config`
> Created: 2026-03-10
> Completed: 2026-03-10
> Implementation: All 7 tasks completed, health endpoint verified

---

## 1. 概述

当前 AI Service 的模型调用深度绑定了智谱 GLM / CogView 系列，切换供应商需要修改代码。本功能通过**统一的多提供商抽象层**，允许运维人员或开发者仅通过修改配置（环境变量 / 配置文件）即可在运行时切换文本大模型（LLM）和图像生成模型，无需改动任何业务代码。

**解决的核心问题**：

- 无法在不改代码的情况下切换到豆包（Doubao）、OpenAI、Qwen 等其他供应商
- 无法接入本地部署的模型（如 Ollama、LM Studio、vLLM）
- 模型密钥、端点、参数散落在各模块中，维护成本高

---

## 2. 用户故事 (User Stories)

### 故事 A — 切换文本 LLM 供应商（优先级: P1）

**作为** 系统管理员  
**我想要** 仅修改配置文件或环境变量，将 Agent 和提示词增强使用的文本 LLM 切换到任意兼容 OpenAI Chat Completions API 的供应商  
**以便于** 在不同成本、延迟或合规要求下灵活选择模型，而不需要部署新版本代码

### 故事 B — 接入本地部署模型（优先级: P1）

**作为** 开发者  
**我想要** 通过配置本地 Ollama / LM Studio / vLLM 的 base URL，将系统所有 LLM 调用路由到本地模型  
**以便于** 在无网络或保密性要求高的环境中运行系统，同时零代码改动

### 故事 C — 独立配置图像生成模型（优先级: P2）

**作为** 系统管理员  
**我想要** 独立配置图像生成使用的模型和供应商（与文本 LLM 分离）  
**以便于** 根据图像质量/成本比选择最优图像供应商，或在图像服务不可用时快速切换备用

### 故事 D — 配置校验与运行时反馈（优先级: P2）

**作为** 开发者  
**我想要** 在启动或健康检查时获知当前配置了哪些模型提供商，以及它们是否可达  
**以便于** 快速诊断配置错误，而不需要等到真实请求失败才发现问题

---

## 3. 功能要求

### 3.1 统一 LLM 提供商配置

1. **主配置变量** (`LLM_PROVIDER`): 决定使用哪个 LLM 提供商，支持值：`glm`、`doubao`、`openai`、`ollama`、`custom`
2. **通用字段**（所有提供商共用）：
   - `LLM_API_KEY` — API 密钥（本地模型可留空）
   - `LLM_BASE_URL` — API 端点，必须是 OpenAI Chat Completions 兼容的基础 URL
   - `LLM_MODEL` — 模型名称
   - `LLM_TEMPERATURE` — 可选，默认 `0.7`
   - `LLM_TIMEOUT` — 可选，默认 `90` 秒
3. **向后兼容**：旧环境变量（`GLM_API_KEY`、`GLM_BASE_URL`、`GLM_MODEL`）作为 fallback，当新变量未设置时自动映射，确保现存部署不受影响
4. **提供商预设（Preset）**：内置常用提供商的默认 `base_url`，设置 `LLM_PROVIDER=doubao` 后仅需额外配置 `LLM_API_KEY` 和 `LLM_MODEL`，无需手写端点

### 3.2 独立图像生成模型配置

1. **图像提供商配置变量** (`IMAGE_PROVIDER`): 支持值：`cogview`、`openai_dalle`、`local`、`disabled`
2. **图像通用字段**：
   - `IMAGE_API_KEY` — 图像 API 密钥（为空时回退到 `LLM_API_KEY`）
   - `IMAGE_BASE_URL` — 图像 API 端点（为空时回退到 `LLM_BASE_URL`）
   - `IMAGE_MODEL` — 图像模型名称
3. **降级策略**：`IMAGE_PROVIDER=disabled` 时，分镜功能返回占位 URL，不影响文本流程

### 3.3 配置加载与校验

1. 系统启动时读取并验证所有模型配置，将验证结果写入日志
2. 缺失必填配置（如 `LLM_API_KEY` 未设置且非本地模式）时：启动日志输出 WARNING，相关接口返回规范的 `ErrorResponse`，而非 500 崩溃
3. 配置错误不阻塞其他无关功能的启动（如 RAG 检索模块独立可用）

### 3.4 健康检查增强

1. `GET /ai/health` 响应体增加 `models` 字段，展示当前配置的 LLM 和图像提供商名称及连通状态（`reachable: true/false`）
2. 连通性检查超时控制在 5 秒以内，不因检查阻塞正常请求

---

## 4. 验收标准 (Acceptance Criteria)

### 文本 LLM 切换

- [x] 设置 `LLM_PROVIDER=glm`、`LLM_API_KEY`、`LLM_MODEL=glm-4-flash`，Agent 对话接口正常返回 SSE 流
- [x] 设置 `LLM_PROVIDER=doubao`、`LLM_API_KEY`、`LLM_MODEL=<doubao-model-id>`，无需修改代码，Agent 对话接口正常返回 SSE 流
- [x] 设置 `LLM_PROVIDER=ollama`、`LLM_BASE_URL=http://localhost:11434/v1`、`LLM_MODEL=llama3`，Agent 调用路由到本地 Ollama 服务
- [x] 未设置 `LLM_PROVIDER` 且 `GLM_API_KEY` 已设置时，系统自动 fallback 到旧 GLM 配置（向后兼容）
- [x] 同时设置新旧变量（`LLM_API_KEY` 与 `GLM_API_KEY`）时，新变量优先

### 图像生成切换

- [x] 设置 `IMAGE_PROVIDER=cogview`，分镜流程正常生图
- [x] 设置 `IMAGE_PROVIDER=disabled`，分镜接口返回含占位图 URL 的 `shot_done` 事件，不崩溃
- [x] 图像配置缺失时，健康检查日志输出 WARNING 但不影响文本接口正常工作

### 配置校验与健康检查

- [x] 启动日志中打印当前 LLM 提供商名称、`base_url`（脱敏）、模型名称
- [x] `GET /ai/health` 响应包含 `"models": { "llm": { "provider": "...", "reachable": true/false }, "image": { ... } }`
- [x] 设置无效的 `LLM_PROVIDER` 值（如 `LLM_PROVIDER=unknown`）时，启动日志输出 ERROR 并回退到安全默认值，不崩溃

### 代码层面

- [x] 业务代码（`graph.py`、`storyboard.py`、`pipeline.py`）中不再出现任何 `GLM_` 字符串的硬编码引用
- [x] 所有模型调用统一通过新的配置层（`model_config.py` 或等价模块）获取客户端实例
- [x] 旧的 `GLM_API_KEY` 等环境变量在 `local-env.ps1.example` 中标注为 DEPRECATED，并提供新变量示例

---

## 5. 接口引用

- OpenAPI (AI Service): [ai-service.yaml](../../openapi/ai-service.yaml)  
  — 健康检查 `GET /ai/health` 响应 schema 需新增 `models` 字段

---

## 6. 约束与假设

### 约束

- 所有文本 LLM 必须兼容 **OpenAI Chat Completions API**（`POST /chat/completions`）。不支持该格式的模型（如纯 Anthropic SDK 原生接口）超出本期范围
- 图像生成当期仅抽象现有 CogView 客户端，不引入新的图像供应商实现（仅配置化，不扩展新供应商集成）

### 假设

- 豆包（Doubao）通过 ByteDance 的 OpenAI 兼容端点 (`https://ark.cn-beijing.volces.com/api/v3`) 接入
- Ollama 本地服务通过 `http://localhost:11434/v1` 提供 OpenAI 兼容接口

---

## 7. 环境变量规范

| 变量名 | 必填 | 用途 | 示例值 |
|--------|------|------|--------|
| `LLM_PROVIDER` | ❌ | 文本 LLM 提供商标识 | `glm` / `doubao` / `ollama` / `custom` |
| `LLM_API_KEY` | ✅（非本地模式） | LLM API 密钥 | `sk-xxx...` |
| `LLM_BASE_URL` | ❌ | LLM API 基础 URL（有默认预设） | `http://localhost:11434/v1` |
| `LLM_MODEL` | ✅ | 使用的模型名称 | `glm-4-flash` / `ep-xxx` / `llama3` |
| `LLM_TEMPERATURE` | ❌ | 生成温度，默认 `0.7` | `0.7` |
| `LLM_TIMEOUT` | ❌ | 请求超时秒数，默认 `90` | `90` |
| `IMAGE_PROVIDER` | ❌ | 图像生成提供商，默认 `cogview` | `cogview` / `disabled` |
| `IMAGE_API_KEY` | ❌ | 图像 API 密钥（缺省使用 `LLM_API_KEY`） | `sk-xxx...` |
| `IMAGE_BASE_URL` | ❌ | 图像 API 基础 URL（缺省使用 `LLM_BASE_URL`） | `https://open.bigmodel.cn/api/paas/v4` |
| `IMAGE_MODEL` | ❌ | 图像模型名称，默认 `cogview-4-250304` | `cogview-4-250304` |
| `GLM_API_KEY` | ❌ | **[DEPRECATED]** 旧版 GLM 密钥，向后兼容 fallback | `xxx.yyy` |
| `GLM_BASE_URL` | ❌ | **[DEPRECATED]** 旧版 GLM 端点，向后兼容 fallback | `https://open.bigmodel.cn/api/paas/v4` |
| `GLM_MODEL` | ❌ | **[DEPRECATED]** 旧版 GLM 模型名，向后兼容 fallback | `glm-4-flash` |

---

## 8. 开放问题 (Open Questions)

- 是否需要支持**运行时热切换**（不重启服务即可切换模型）？当前方案为配置读取后在启动时固定，热切换需要额外的配置刷新机制，建议本期先不做
- 图像生成是否需要接入 DALL-E / Stable Diffusion 等第三方？本期仅保留现有 CogView 并配置化，外接新图像供应商列为 P3 待办
