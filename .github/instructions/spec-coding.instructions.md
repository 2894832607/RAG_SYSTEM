---
description: "Spec Coding 规则：所有 AI 辅助编码必须先对齐 specs/ 目录中的规范文档，再生成或修改代码。适用于本项目所有模块。"
applyTo: "**"
---

# Spec Coding 规则

## 核心原则

**Spec First，Code Second。**  
在生成任何代码之前：
1. 先读 `.specify/memory/constitution.md`（项目宪章，最高规则）
2. 再查阅 `specs/` 目录中对应的规范文档
3. 如规范文档不存在或描述不清晰，**先更新规范，再写代码**

---

## 规范文档索引

| 场景 | 必读文档 |
|------|---------|
| 了解项目最高规则 | `.specify/memory/constitution.md` |
| 新增/修改 Backend REST 接口 | `specs/openapi/backend.yaml` |
| 新增/修改 AI Service 接口 | `specs/openapi/ai-service.yaml` |
| 修改诗词可视化主流程 | `specs/features/poetry-visualization.spec.md` |
| 查看实现方案 | `specs/features/poetry-visualization/plan.md` |
| 查看待执行任务 | `specs/features/poetry-visualization/tasks.md` |
| 修改 RAG/Agent/检索逻辑 | `specs/features/rag-pipeline.spec.md` |
| 修改数据库结构 | `specs/architecture/data-model.md` |
| 理解整体架构 | `specs/architecture/system-overview.md` |

---

## 编码规则

### R1 — 接口变更必须先更新 OpenAPI

- 任何 `@PostMapping` / `@GetMapping` 新增或参数变更，必须同步修改 `specs/openapi/backend.yaml`
- 任何 FastAPI `@app.post` / `@app.get` 变更，必须同步修改 `specs/openapi/ai-service.yaml`
- **禁止**直接改代码而不改 spec

### R2 — Feature Spec 是验收标准

- Feature Spec 中的验收标准（`- [ ]` 列表）是功能完成的判断依据
- 完成实现后，对应的 `- [ ]` 应改为 `- [x]`
- 发现现有代码不满足某条验收标准时，**必须修复代码，而不是删除验收标准**

### R3 — 数据模型变更必须同步 data-model.md

- 新增数据库字段/表时，先更新 `specs/architecture/data-model.md`
- 字段枚举值变更（如 taskStatus 新增状态）必须在 spec 中声明

### R4 — 环境变量必须在 spec 中声明

- 新增环境变量时，在对应 Feature Spec 的"环境变量规范"表格中添加
- 必须标明是否为必填（✅ / ❌）及示例值

### R5 — 错误处理必须遵循规范

- Backend 错误响应统一使用 `ErrorResponse` schema（见 backend.yaml）
- AI Service 失败必须通过 callback status=2 + errorMessage 上报，而不是直接抛 HTTP 500

### R6 — 新功能必须先有 spec

- 在 `specs/features/` 下创建新的 `{feature-name}.spec.md`
- 使用以下模板：
  ```markdown
  # Feature Spec: {功能名称}
  
  > Status: Draft
  > Version: 1.0
  
  ## 1. 概述
  ## 2. 用户故事
  ## 3. 功能要求
  ## 4. 验收标准
  ## 5. 接口引用
  ## 6. 开放问题
  ```
- spec 通过 Review 后，再开始编码

---

## 代码生成规范

当 AI（Copilot）生成代码时：

1. **引用 spec**：在注释中说明依据哪个 spec，例如：
   ```java
   // Spec: specs/features/poetry-visualization.spec.md §3.1
   ```

2. **不得偏离 schema**：生成的 DTO/Model 字段名必须与 OpenAPI schema 中的 `properties` 完全一致

3. **状态枚举**：所有 `taskStatus` 值只能使用 `PENDING / PROCESSING / COMPLETED / FAILED`

4. **禁止魔法字符串**：所有 HTTP 路径、状态值、token 头名 (`X-Callback-Token`) 必须与 spec 中定义一致

---

## Checklist（每次 PR 前）

- [ ] 新接口已在对应 OpenAPI yaml 中声明
- [ ] Feature Spec 验收标准已更新（完成的改为 `- [x]`）
- [ ] 环境变量已在 spec 中登记
- [ ] 数据模型变更已同步 data-model.md
- [ ] 错误响应格式符合 spec 中的 ErrorResponse schema
