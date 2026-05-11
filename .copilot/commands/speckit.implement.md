---
description: 按任务清单逐一实现代码（严格对齐所有规范）
---

你是一位严格遵循规范的高级工程师，现在要按任务清单**逐一**实现代码。

## 前置检查（MUST 全部读取）

在生成任何代码之前，必须先读取：
1. `.specify/memory/constitution.md` — 项目宪章（最高规则）
2. 对应的 `specs/features/*.spec.md` — 功能规范（验收标准）
3. 对应的 `plan.md` — 技术方案（实现指导）
4. 对应的 `tasks.md` — 任务清单（执行顺序）
5. 相关的 `specs/openapi/*.yaml` — 接口 schema（字段名权威来源）

## 实现规则（MUST）

### R1 — 逐任务执行
- 每次只执行 **一个任务**
- 每个任务完成后：
  1. 向用户展示修改的文件清单和关键变更
  2. 在 `tasks.md` 中将对应任务的 `- [ ]` 改为 `- [x]`
  3. 等待用户确认后再执行下一任务

### R2 — 严格对齐 Schema
- DTO / Pydantic Model 的字段名 MUST 与 OpenAPI schema 中的 `properties` 完全一致
- 状态值 MUST 只使用 `PENDING / PROCESSING / COMPLETED / FAILED`
- HTTP 路径 MUST 与 OpenAPI 中的 `paths` 完全一致

### R3 — 代码质量
- 每个新方法必须包含：
  - 功能注释（说明依据哪个 spec §X.X）
  - 参数校验
  - 异常处理
- Backend：错误通过 `GlobalExceptionHandler` 处理，返回 `ErrorResponse`
- AI Service：失败通过 callback status=2 上报

### R4 — 任务范围控制
- 只修改当前任务范围内的文件
- MUST NOT 未经任务声明擅自修改其他文件

### R5 — 完成后更新 Spec
- 当所有任务完成后，在对应的 `spec.md` 中将已实现的验收标准 `- [ ]` 改为 `- [x]`

## 开始实现

读取 `tasks.md`，从第一个未完成（`- [ ]`）的任务开始。  
如果用户通过 `$ARGUMENTS` 指定了起点（如 `T003` 或 `Phase 2`），从该任务/阶段开始。

---

用户附加说明（可选，如 "从 T005 开始" 或 "只做 Phase 2"）：

$ARGUMENTS
