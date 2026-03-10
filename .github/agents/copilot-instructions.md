# Agent 上下文说明 — 001-model-api-config

> Feature Branch: `001-model-api-config`  
> Updated: 2026-03-10  
> Spec: [specs/001-model-api-config/spec.md](../../specs/001-model-api-config/spec.md)  
> Plan: [specs/001-model-api-config/plan.md](../../specs/001-model-api-config/plan.md)

## 1. 功能目标

将 AI Service 中硬编码的 GLM 模型依赖替换为可配置的统一抽象层，
支持通过环境变量自由切换 LLM（GLM / 豆包 / OpenAI / Ollama 等）和图像生成模型，**零代码改动**。

## 2. 关键上下文

### 新增文件
- `ai-service/app/config/model_config.py` — 统一配置模块（**唯一需要读 LLM_* 环境变量的地方**）

### 需要修改的文件
| 文件 | 改动要点 |
|------|---------|
| `ai-service/app/agent/llm.py` | 从 `get_llm_config()` 取参数，删除 `os.getenv("GLM_*")` |
| `ai-service/app/modules/glm_client.py` | `__init__` 从 `get_llm_config()` 取参数 |
| `ai-service/app/modules/generation.py` | `CogViewClient.__init__` 从 `get_image_config()` 取参数，支持 `disabled` |
| `ai-service/app/main.py` | lifespan 调用 `validate_and_log()`，health 接口返回 `models` 字段 |
| `ai-service/local-env.ps1.example` | 新增 `LLM_*` / `IMAGE_*`，旧 `GLM_*` 标注 DEPRECATED |

### 不需要修改的文件
- `app/modules/prompt.py`、`app/modules/storyboard.py`、`app/modules/pipeline.py`  
- `app/agent/graph.py`、`app/agent/tools.py`  
- 所有 Frontend、Backend 文件

## 3. 提供商预设（不要硬编码这些值到多处）

```python
_PROVIDER_PRESETS = {
    "glm":    "https://open.bigmodel.cn/api/paas/v4",
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "openai": "https://api.openai.com/v1",
    "qwen":   "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "ollama": "http://localhost:11434/v1",
}
```

## 4. 环境变量优先级

```
LLM_API_KEY  → fallback GLM_API_KEY  → ""
LLM_BASE_URL → fallback GLM_BASE_URL → provider preset
LLM_MODEL    → fallback GLM_MODEL    → "glm-4-flash"
LLM_PROVIDER → "glm" (默认)
```

## 5. 生成策略

- 使用 `replace_string_in_file` 进行局部修改，不全文覆盖现有文件
- 新增 `model_config.py` 时使用 `create_file` 工具
- 每次改动后对照 spec.md §4 验收标准逐条核对
- 确保 health 接口响应与 `specs/openapi/ai-service.yaml` 的 `HealthResponse` schema 完全对应

## 6. 测试入口

```bash
# 启动 AI Service 后验证（以豆包为例）
$env:LLM_PROVIDER="doubao"; $env:LLM_API_KEY="ark_key"; $env:LLM_MODEL="ep-xxx"
uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/ai/health
```
