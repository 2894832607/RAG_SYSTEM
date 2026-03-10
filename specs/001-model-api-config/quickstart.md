# Quickstart: 模型 API 自由配置

> Feature: `001-model-api-config`  
> Updated: 2026-03-10

本指南展示如何通过环境变量切换 AI Service 使用的 LLM 和图像生成模型。

---

## 快速切换场景

### 场景 A — 使用智谱 GLM（默认）

```powershell
# ai-service/local-env.ps1
$env:LLM_PROVIDER  = 'glm'
$env:LLM_API_KEY   = 'your_key_here'
$env:LLM_MODEL     = 'glm-4-flash'
# base_url 自动使用预设 https://open.bigmodel.cn/api/paas/v4
```

也可以继续使用旧变量（向后兼容）：

```powershell
$env:GLM_API_KEY = 'your_key_here'  # DEPRECATED，仍有效
$env:GLM_MODEL   = 'glm-4-flash'
```

---

### 场景 B — 切换到豆包（ByteDance Ark）

```powershell
$env:LLM_PROVIDER = 'doubao'
$env:LLM_API_KEY  = 'your_ark_api_key'
$env:LLM_MODEL    = 'ep-xxxxxxxxxxxxxxxxxx'   # 推理接入点 ID
```

> `LLM_BASE_URL` 无需设置，`doubao` 预设已配置为 `https://ark.cn-beijing.volces.com/api/v3`

---

### 场景 C — 接入本地 Ollama

```powershell
$env:LLM_PROVIDER = 'ollama'
$env:LLM_MODEL    = 'llama3'        # 或 qwen2.5:14b 等已拉取的模型
# LLM_API_KEY 无需设置（Ollama 不需要鉴权）
# LLM_BASE_URL 自动使用 http://localhost:11434/v1
```

确保 Ollama 已安装并运行：

```bash
ollama serve
ollama pull llama3
```

---

### 场景 D — 使用自定义 OpenAI 兼容服务（如 vLLM / LM Studio）

```powershell
$env:LLM_PROVIDER = 'custom'
$env:LLM_BASE_URL = 'http://192.168.1.100:8080/v1'
$env:LLM_API_KEY  = 'token-if-required'
$env:LLM_MODEL    = 'Qwen2.5-7B-Instruct'
```

---

### 场景 E — 禁用图像生成（纯文本开发）

```powershell
$env:IMAGE_PROVIDER = 'disabled'
# 分镜接口仍可调用，shot_done 事件 image_url 返回占位图
```

---

### 场景 F — 图像与文本使用不同供应商

```powershell
# 文本 LLM → 豆包
$env:LLM_PROVIDER = 'doubao'
$env:LLM_API_KEY  = 'ark_key...'
$env:LLM_MODEL    = 'ep-xxxxxxxx'

# 图像 → 仍使用智谱 CogView（共用单独密钥）
$env:IMAGE_PROVIDER = 'cogview'
$env:IMAGE_API_KEY  = 'glm_key...'    # 可与 LLM_API_KEY 不同
$env:IMAGE_MODEL    = 'cogview-4-250304'
```

---

## 验证配置生效

启动 AI Service 后查看健康检查：

```bash
curl http://localhost:8000/ai/health | python -m json.tool
```

预期输出：

```json
{
  "status": "ok",
  "service": "poetry rag ai",
  "models": {
    "llm": {
      "provider": "doubao",
      "model": "ep-xxxxxxxxxx",
      "base_url": "https://ark.cn-beijing.volces.com/api/v3",
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

同时查看启动日志：

```
INFO: [ModelConfig] LLM  provider=doubao model=ep-xxxxxxxx base_url=https://ark.cn-beijing.volces.com/api/v3 key=sk-xxxx...
INFO: [ModelConfig] IMG  provider=cogview model=cogview-4-250304
```

---

## 环境变量完整参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_PROVIDER` | `glm` | `glm` / `doubao` / `openai` / `qwen` / `ollama` / `custom` |
| `LLM_API_KEY` | — | API 密钥（ollama 可留空） |
| `LLM_BASE_URL` | 由 provider 预设 | OpenAI 兼容的基础 URL |
| `LLM_MODEL` | `glm-4-flash` | 模型名称 |
| `LLM_TEMPERATURE` | `0.7` | — |
| `LLM_TIMEOUT` | `90` | 请求超时秒数 |
| `IMAGE_PROVIDER` | `cogview` | `cogview` / `disabled` |
| `IMAGE_API_KEY` | 同 `LLM_API_KEY` | 图像 API 密钥 |
| `IMAGE_BASE_URL` | 同 `LLM_BASE_URL` | 图像 API 端点 |
| `IMAGE_MODEL` | `cogview-4-250304` | 图像模型 |
| `GLM_API_KEY` | — | **[DEPRECATED]** 向后兼容 |
| `GLM_BASE_URL` | — | **[DEPRECATED]** 向后兼容 |
| `GLM_MODEL` | — | **[DEPRECATED]** 向后兼容 |
