# Research: 模型 API 自由配置

> Phase 0 Research for `001-model-api-config`
> Date: 2026-03-10

---

## R1 — 文本 LLM 提供商端点（OpenAI Chat Completions 兼容）

**Decision**: 内置 5 个预设提供商，`custom` 模式由用户自行提供 `LLM_BASE_URL`

| Provider Key | base_url 预设 | 备注 |
|---|---|---|
| `glm` | `https://open.bigmodel.cn/api/paas/v4` | 默认值，向后兼容旧 GLM 配置 |
| `doubao` | `https://ark.cn-beijing.volces.com/api/v3` | ByteDance Ark 平台，完全 OpenAI 兼容 |
| `openai` | `https://api.openai.com/v1` | GPT-4/o 系列 |
| `qwen` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 阿里通义千问 |
| `ollama` | `http://localhost:11434/v1` | 本地部署，api_key 设置为 `"ollama"` |
| `custom` | 由 `LLM_BASE_URL` 指定 | 任意 OpenAI 兼容服务 |

**Rationale**: 所有主流云 LLM 均已提供 OpenAI 兼容层，因此抽象层只需管理 `(base_url, api_key, model)` 三元组，复用现有 `langchain_openai.ChatOpenAI` 即可，无需引入新依赖。

**Alternatives considered**:
- 引入 `litellm` 统一路由层：功能强大但引入超重依赖，且项目已经全部使用 OpenAI 兼容接口，不需要额外的适配层
- 自定义 LLM 基类：过度工程，直接配置 `ChatOpenAI` 的 `base_url` 已足够

---

## R2 — GlmClient (httpx) 的配置化方式

**Decision**: `GlmClient` 保留，但在构造函数中从新的 `ModelConfig` 读取参数，而不是直接读 `GLM_*` 环境变量

**Rationale**: `GlmClient` 使用 raw httpx（非 langchain），主要用于分镜规划（`/chat/completions`）和提示词增强。它只需要 `(base_url, api_key, model)` 三元组，因此直接从 `ModelConfig` 取即可，内部逻辑不变。

---

## R3 — CogViewClient 的配置化方式

**Decision**: `CogViewClient` 从新的 `ImageModelConfig` 读取参数，`IMAGE_PROVIDER=disabled` 时返回固定占位 URL

占位 URL 格式：`/statics/outputs/placeholder.svg`（前端已有骨架屏逻辑，占位不影响 UX）

**Rationale**: 图像生成与文本 LLM 应独立配置（成本和延迟差异大），`disabled` 模式使本地开发/CI 不需要真实图像 API。

---

## R4 — langchain `get_llm()` 单例缓存问题

**Decision**: `@lru_cache(maxsize=1)` 需要修改。新的 `ModelConfig` 在模块级别读取一次，`get_llm()` 利用 config 对象而不是 `temperature` float 作为缓存 key

**Rationale**: `lru_cache` 目前只传入 `temperature`，新增配置项后缓存 key 不变还是安全的（进程启动后配置固定）。但更清晰的做法是在模块加载时初始化一次 `_llm_instance`，避免 `lru_cache` 在参数变化时失效。

---

## R5 — 启动时配置校验

**Decision**: 在 `app/config/model_config.py` 中的 `ModelConfig.__post_init__` 或独立函数 `validate_and_log()` 中打印配置摘要，向量库、文本LLM、图像LLM各一行，并对必填项缺失输出 WARNING

**Rationale**: FastAPI lifespan event 在 `@app.on_event("startup")` 中调用 `validate_and_log()`，既在日志中可见，又不阻塞进程启动。

---

## R6 — 健康检查 `/ai/health` 增强

**Decision**: 响应新增 `models` 字段，不做实时 ping（避免 health check 因网络超时拖慢 K8s 探针）

```json
{
  "status": "ok",
  "service": "poetry rag ai",
  "models": {
    "llm": {
      "provider": "glm",
      "model": "glm-4-flash",
      "base_url": "https://open.bigmodel.cn/...",
      "enabled": true
    },
    "image": {
      "provider": "cogview",
      "model": "cogview-4-250304",
      "enabled": true
    }
  }
}
```

**Alternatives considered**: 实时 TCP ping `base_url` — 增加复杂性，且 health check 不应有副作用，放弃。

---

## R7 — 向后兼容 fallback 策略

**Decision**: 优先级 `新变量 > 旧GLM变量 > 内置默认值`

```
LLM_API_KEY  → fallback to GLM_API_KEY
LLM_BASE_URL → fallback to GLM_BASE_URL → fallback to provider preset
LLM_MODEL    → fallback to GLM_MODEL    → fallback to "glm-4-flash"
```

只有当 `LLM_PROVIDER` 未设置且 `GLM_API_KEY` 存在时，隐式设定 `provider="glm"`。

**Rationale**: 所有现存 `.env` 只设置了 `GLM_*`，必须零改造兼容。

---

## R8 — 代码改动范围（最小化）

受影响文件：

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `app/config/model_config.py` | **NEW** | 统一配置读取，提供 `get_llm_config()` 和 `get_image_config()` |
| `app/agent/llm.py` | MODIFY | 从 `model_config` 取配置，删除直接读 `GLM_*` 变量 |
| `app/modules/glm_client.py` | MODIFY | 构造函数从 `model_config` 取参数 |
| `app/modules/generation.py` | MODIFY | `CogViewClient` 构造函数从 `image_config` 取参数 |
| `app/main.py` | MODIFY | health 接口返回 models 字段；startup 打印配置摘要 |
| `ai-service/local-env.ps1.example` | MODIFY | 新增新变量，旧变量标注 DEPRECATED |
| `specs/openapi/ai-service.yaml` | MODIFY | health response schema 新增 `models` |

**不需要修改**：`prompt.py`、`storyboard.py`、`pipeline.py`、`retriever.py`、`graph.py`（它们通过 `GlmClient()` / `CogViewClient()` / `get_llm()` 间接使用，无需知道配置细节）
