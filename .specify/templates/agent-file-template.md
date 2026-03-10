# Agent 自动生成说明 (Agent Meta)

> 本文档描述如何通过 Agent 自动化该 Feature 的部分代码。

## 1. 预设 Prompt 路径
- [./prompts/backend-gen.md](./prompts/backend-gen.md)
- [./prompts/frontend-gen.md](./prompts/frontend-gen.md)

## 2. 上下文引用
- 请引用 `specs/features/xxx.spec.md`
- 请引用 `specs/architecture/data-model.md`

## 3. 生成策略
- 使用 `replace_string_in_file` 进行局部注入而非全文件覆盖。
- 确保 DTO 与 OpenAPI schema 完全对应。
