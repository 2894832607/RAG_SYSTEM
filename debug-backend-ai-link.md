# Debug Session: backend-ai-link [OPEN]

## Symptoms
- 后端“发信息”报错。
- 前端切换模型报错。
- 预期是 backend 能正常连接 ai-service，模型切换接口正常返回。

## Hypotheses
1. Backend 调用的 AI 服务地址或端口不一致，导致请求落空或超时。
2. AI 服务相关接口存在 4xx/5xx，但前端只看到统一“报错”。
3. Backend 代理到 AI 服务时，请求/响应结构与前端预期不一致。
4. 模型切换依赖的环境变量已变更，但运行中的 AI 进程没有按当前配置启动。
5. 前端请求路径或鉴权头不符合 backend 当前实现，导致聊天或模型切换接口失败。

## Evidence Plan
- 检查 frontend、backend、ai-service 的运行日志。
- 直接调用 backend 聊天/模型切换接口复现。
- 再直接调用 ai-service 对应接口，比较两边差异。

## Status
- Runtime evidence collected:
- Frontend dev proxy for `/ai/api/v1/config` points to `127.0.0.1:8000`.
- Current mac startup config runs `ai-service` on port `8001`.
- Direct call to `http://127.0.0.1:8001/ai/api/v1/config/model` succeeds.
- Direct call to backend chat SSE succeeds.
- Current frontend dev server was not listening on `5173` during reproduction.
