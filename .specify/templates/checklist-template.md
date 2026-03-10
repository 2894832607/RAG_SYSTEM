# 任务完成自测清单 (Checklist)

> Feature: {Feature Name}

## 1. 代码质量
- [ ] [R5] 错误处理遵循规范
- [ ] 无魔法字符串，使用常量定义
- [ ] 删除了所有调试用的 `console.log` 或 `print`

## 2. 规范同步
- [ ] [R1] OpenAPI yaml 已更新
- [ ] [R3] `data-model.md` 已同步数据库变更
- [ ] [R4] 环境变量已在 Spec 中声明

## 3. 功能测试
- [ ] 前端 UI 渲染正常
- [ ] SSE 链路通畅 (Frontend -> Backend -> AI Service)
- [ ] 边界条件下系统不崩溃

## 4. 文档
- [ ] `tasks.md` 中的所有任务已标记为 `[x]`
- [ ] 如果有新增环境变量，已更新 `.env.example`
