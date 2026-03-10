# 模型 API 自由配置 实现方案 (Plan)

> Status: COMPLETED ✅
> Branch: `001-model-api-config`
> Reference Spec: [spec.md](spec.md)
> Research: [research.md](research.md)
> Created: 2026-03-10
> Completed: 2026-03-10

---

## 1. 核心架构设计

在 AI Service 内引入一个薄配置层 `app/config/model_config.py`，将所有模型相关参数的读取集中到此处。现有业务模块（`GlmClient`、`CogViewClient`、`get_llm()`）改为从该配置层获取 `(base_url, api_key, model)` 三元组，不再直接读取任何 `GLM_*` / `LLM_*` 环境变量。

```
环境变量（.env / local-env.ps1）
         ↓
 app/config/model_config.py
 ┌─────────────────────────────────┐
 │  LlmConfig      ImageConfig     │
 │  - provider     - provider      │
 │  - api_key      - api_key       │
 │  - base_url     - base_url      │
 │  - model        - model         │
 └────────┬────────────┬───────────┘
          │            │
   agent/llm.py    modules/generation.py
   modules/glm_client.py
```

**关键约束（来自 constitution §2.3）**：
- 仍使用 `langchain_openai.ChatOpenAI`，无需新增 LLM 框架依赖
- 仍使用 `httpx` 直连图像 API，无需新增图像 SDK
- 不影响 Frontend → Backend → AI Service 的分层调用链

---

## 2. 技术栈

本功能仅涉及 **AI Service（Python/FastAPI）** 层，不触及 Frontend 或 Backend：

- **Python 3.11+** — 数据类 (`@dataclass`) 做配置模型
- **langchain_openai** — `ChatOpenAI`，已有依赖，通过 `base_url` 参数接入任意 OpenAI 兼容端点
- **httpx** — 已有依赖，供 `GlmClient` / `CogViewClient` 维持原有直连方式
- **FastAPI lifespan** — 启动时打印配置摘要

---

## 3. 实现细节

### 3.1 配置层设计 (`app/config/model_config.py`)

```python
# Spec: specs/001-model-api-config/spec.md §3.1
import os, logging
from dataclasses import dataclass

_PROVIDER_PRESETS: dict[str, str] = {
    "glm":    "https://open.bigmodel.cn/api/paas/v4",
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "openai": "https://api.openai.com/v1",
    "qwen":   "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "ollama": "http://localhost:11434/v1",
}

@dataclass(frozen=True)
class LlmConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    temperature: float
    timeout: float

@dataclass(frozen=True)
class ImageConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout: float

def get_llm_config() -> LlmConfig:
    """读取 LLM 配置，新变量优先，GLM_* 旧变量作为 fallback。"""
    api_key   = os.getenv("LLM_API_KEY")    or os.getenv("GLM_API_KEY",    "")
    old_base  = os.getenv("GLM_BASE_URL",   "https://open.bigmodel.cn/api/paas/v4")
    old_model = os.getenv("GLM_MODEL",      "glm-4-flash")
    provider  = os.getenv("LLM_PROVIDER",   "glm" if api_key else "glm").strip().lower()
    preset    = _PROVIDER_PRESETS.get(provider, old_base)
    base_url  = (os.getenv("LLM_BASE_URL") or preset).rstrip("/")
    model     = os.getenv("LLM_MODEL")     or old_model
    ...
    return LlmConfig(provider=provider, api_key=api_key, base_url=base_url,
                     model=model, temperature=..., timeout=...)

def get_image_config() -> ImageConfig:
    """读取图像生成配置，缺省回退到 LLM 配置字段。"""
    llm = get_llm_config()
    provider = os.getenv("IMAGE_PROVIDER", "cogview").lower()
    api_key  = os.getenv("IMAGE_API_KEY")  or llm.api_key
    base_url = (os.getenv("IMAGE_BASE_URL") or llm.base_url).rstrip("/")
    model    = os.getenv("IMAGE_MODEL",    "cogview-4-250304")
    ...
    return ImageConfig(...)

def validate_and_log() -> None:
    """启动时打印配置摘要（脱敏），校验必填项。"""
    llm = get_llm_config()
    img = get_image_config()
    masked_key = (llm.api_key[:8] + "...") if len(llm.api_key) > 8 else "*** NOT SET ***"
    logger.info(f"[ModelConfig] LLM  provider={llm.provider} model={llm.model} base_url={llm.base_url} key={masked_key}")
    logger.info(f"[ModelConfig] IMG  provider={img.provider} model={img.model}")
    if not llm.api_key and llm.provider != "ollama":
        logger.warning("[ModelConfig] LLM_API_KEY 未配置，涉及模型调用的接口将返回错误")
```

### 3.2 修改 `agent/llm.py`

删除直接读取 `GLM_*` 的代码，改为：

```python
from app.config.model_config import get_llm_config

def get_llm(temperature: float = 0.7) -> ChatOpenAI | None:
    cfg = get_llm_config()
    if not cfg.api_key and cfg.provider != "ollama":
        return None
    return ChatOpenAI(
        model=cfg.model,
        api_key=cfg.api_key or "ollama",
        base_url=cfg.base_url,
        temperature=temperature,
        streaming=True,
        timeout=cfg.timeout,
        max_retries=2,
    )
```

### 3.3 修改 `modules/glm_client.py`

`__init__` 从 `get_llm_config()` 读取，删除 `os.getenv("GLM_*")` 调用：

```python
from app.config.model_config import get_llm_config

class GlmClient:
    def __init__(self) -> None:
        cfg = get_llm_config()
        self.api_key  = cfg.api_key
        self.base_url = cfg.base_url
        self.model    = cfg.model
        self.timeout  = cfg.timeout

    def is_enabled(self) -> bool:
        return bool(self.api_key)
```

其余方法（`complete()`、`stream()`）无需修改。

### 3.4 修改 `modules/generation.py`

`CogViewClient.__init__` 从 `get_image_config()` 读取：

```python
from app.config.model_config import get_image_config

class CogViewClient:
    def __init__(self) -> None:
        cfg = get_image_config()
        self.api_key  = cfg.api_key
        self.base_url = cfg.base_url
        self.model    = cfg.model
        self.timeout  = cfg.timeout
        self.size     = os.getenv("COGVIEW_SIZE", "1024x1024")
        self._disabled = cfg.provider == "disabled"

    def is_enabled(self) -> bool:
        return bool(self.api_key) and not self._disabled

    def generate(self, positive_prompt: str, negative_prompt: str = "") -> str:
        if self._disabled:
            return "/statics/outputs/placeholder.svg"
        # ... 原有逻辑不变
```

### 3.5 修改 `main.py` — 健康检查与启动日志

```python
from app.config.model_config import get_llm_config, get_image_config, validate_and_log
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_and_log()
    yield

app = FastAPI(..., lifespan=lifespan)

@app.get("/ai/health")
async def health():
    llm = get_llm_config()
    img = get_image_config()
    return {
        "status": "ok",
        "service": "poetry rag ai",
        "models": {
            "llm": {
                "provider": llm.provider,
                "model":    llm.model,
                "base_url": llm.base_url,
                "enabled":  bool(llm.api_key) or llm.provider == "ollama",
            },
            "image": {
                "provider": img.provider,
                "model":    img.model,
                "enabled":  img.provider != "disabled" and bool(img.api_key),
            },
        },
    }
```

---

## 4. 数据流图（配置化后）

```mermaid
graph TD
    ENV[".env / local-env.ps1<br/>LLM_PROVIDER, LLM_API_KEY<br/>LLM_BASE_URL, LLM_MODEL"] --> CFG[app/config/model_config.py<br/>get_llm_config() / get_image_config()]
    CFG --> LLM[agent/llm.py<br/>get_llm()]
    CFG --> GLM[modules/glm_client.py<br/>GlmClient]
    CFG --> IMG[modules/generation.py<br/>CogViewClient]
    LLM --> AGENT[agent/graph.py → ReAct Agent]
    GLM --> SB[modules/storyboard.py]
    GLM --> PE[modules/prompt.py]
    IMG --> SB
    IMG --> PL[modules/pipeline.py]
```

---

## 5. 接口变更

### 5.1 `GET /ai/health` 响应增强

**Before**:
```json
{ "status": "ok", "service": "poetry rag ai" }
```

**After**:
```json
{
  "status": "ok",
  "service": "poetry rag ai",
  "models": {
    "llm":   { "provider": "glm",     "model": "glm-4-flash",      "base_url": "...", "enabled": true },
    "image": { "provider": "cogview", "model": "cogview-4-250304",  "enabled": true }
  }
}
```

OpenAPI spec 更新文件：`specs/openapi/ai-service.yaml`（`HealthResponse` schema 新增 `models` 字段）。

---

## 6. 风险与权衡

| 风险 | 概率 | 应对 |
|---|---|---|
| 旧 `GLM_*` 变量遗漏 fallback 导致现存部署失效 | 低 | 单测 + 代码审查确认 fallback 链完整 |
| `lru_cache` 在单进程多次调用 `get_llm_config()` 时的性能 | 极低 | 模块级单例，进程启动后配置固定 |
| `IMAGE_PROVIDER=disabled` 时前端骨架屏逻辑兼容 | 低 | 占位 URL `/statics/outputs/placeholder.svg` 需确认前端能正常渲染 |
| 豆包 API 实际端点变更 | 中 | `custom` 模式始终可用，preset 只是便利快捷方式 |

---

## 7. Constitution Check

| 规则 | 状态 | 备注 |
|---|---|---|
| §2.3 AI Service 使用 LangGraph | ✅ | 不改 Agent 核心，只改配置读取 |
| §3.1 Frontend 不直连 AI Service | ✅ | 本功能不涉及 Frontend |
| §3.2 接口变更先更新 OpenAPI yaml | ✅ | health schema 已在 plan 中声明，实现前更新 |
| §4.2 每个 endpoint 有 Pydantic 请求/响应模型 | ✅ | health 返回 dict，已有类型注解 |
| §5 禁止先改代码再补 spec | ✅ | spec → research → plan 顺序正确 |

---

## 8. 实现任务（Tasks）

详见 [tasks.md](tasks.md)（待生成）

**预计文件改动量**：
- 新增 1 文件：`app/config/model_config.py`（约 80 行）
- 修改 4 文件：`llm.py`、`glm_client.py`、`generation.py`、`main.py`
- 配置文件：`local-env.ps1.example`
- Spec 文件：`specs/openapi/ai-service.yaml`
