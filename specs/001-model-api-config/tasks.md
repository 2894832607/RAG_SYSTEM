# 模型 API 自由配置 任务拆解 (Tasks)

> Status: 7 / 7 Completed ✅
> Reference Plan: [plan.md](plan.md)
> Branch: `001-model-api-config`
> Last Verified: 2026-03-10 (Health endpoint returns correct model config)

## AI Service 开发

- [x] [TASK-001] 新增 `app/config/model_config.py` — 统一配置读取模块
- [x] [TASK-002] 修改 `app/agent/llm.py` — 从 model_config 取参数
- [x] [TASK-003] 修改 `app/modules/glm_client.py` — 从 model_config 取参数
- [x] [TASK-004] 修改 `app/modules/generation.py` — CogViewClient 支持 IMAGE_PROVIDER 配置
- [x] [TASK-005] 修改 `app/main.py` — lifespan 日志 + health 接口增加 models 字段
- [x] [TASK-006] 更新 `local-env.ps1.example` — 新增 LLM_*/IMAGE_* 变量，旧变量标注 DEPRECATED

## 验收

- [x] [TASK-007] 启动服务验证 health 接口返回正确的 models 字段
