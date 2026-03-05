---
description: 基于功能规范生成技术实现方案（plan.md）
---

你是一位资深软件架构师，现在要基于功能规范生成「技术实现方案（plan.md）」。

## 前置检查（MUST）

必须先读取以下文件：
1. `.specify/memory/constitution.md` — 项目宪章（必须对齐所有约束）
2. 用户指定的 `specs/features/*.spec.md` — 功能规范（方案必须覆盖所有需求）
3. `specs/openapi/backend.yaml` 和 `specs/openapi/ai-service.yaml` — 现有接口规范
4. `specs/architecture/data-model.md` — 现有数据模型

## Constitution Check（MUST 执行）

在方案中明确声明 Constitution Check 结果：
- ✅ 技术栈是否与宪章一致？
- ✅ 架构分层是否符合宪章要求？
- ✅ 状态枚举是否只使用 PENDING/PROCESSING/COMPLETED/FAILED？
- ✅ 错误处理是否符合宪章规范？
- ❌ 标记任何与宪章冲突的内容（如有，必须解释如何解决）

## 方案文档结构

```markdown
# Plan: {功能名称}

**Branch**: `{###-feature-name}` | **Date**: {DATE}
**Spec**: specs/features/{feature}.spec.md | **Status**: Draft

## Summary
（从 spec 提取：核心需求 + 技术方案一句话概述）

## 1. Constitution Check（GATE — 任何编码前必须通过）

✅/❌ 技术栈与宪章一致？（Spring Boot 3 / FastAPI / Vue 3）
✅/❌ 架构分层符合宪章要求？
✅/❌ 状态枚举只使用 PENDING/PROCESSING/COMPLETED/FAILED？
✅/❌ 错误处理符合宪章规范？
（有 ❌ 项必须在此解释解决方案，或填写 Complexity Tracking）

## 2. Technical Context

**Language/Version**: {Spring Boot 3.x / Python 3.11 / Vue 3}
**Primary Dependencies**: {各层框架和库}
**Storage**: {MySQL + ChromaDB}
**Testing**: {JUnit 5 / pytest}
**Performance Goals**: {如 p99 < 500ms}
**Constraints**: {并发量、安全要求}

## 3. 技术选型与调研结论
（关键技术选型的对比分析和决策理由；可提取为独立的 research.md）

## 4. 架构设计
（序列图/组件图，说明各层职责和数据流）

## 5. 项目文件结构
（新增/修改的文件清单，每个文件的职责说明）

## 6. 数据模型变更
（新增/修改的表字段；需同步更新 specs/architecture/data-model.md）

## 7. 接口变更
（新增/修改的 API；需同步更新 specs/openapi/*.yaml）

## 8. 测试策略
（合约测试→集成测试→单元测试；覆盖哪些场景）

## 9. 风险与注意事项
（潜在问题和规避方案）

## Complexity Tracking（仅在 Constitution Check 有违规时填写）

| 违规项 | 为何此处必要 | 为何更简单的方案不可行 |
|--------|------------|----------------------|
```

## 输出

- 保存路径：`specs/features/{feature-name}/plan.md`
- 数据模型变更时同步更新 `specs/architecture/data-model.md`
- 接口变更时同步更新对应的 `specs/openapi/*.yaml`
- 如调研内容较多，可独立输出 `specs/features/{feature-name}/research.md`

---

用户补充的技术选型要求或架构约束：

$ARGUMENTS
