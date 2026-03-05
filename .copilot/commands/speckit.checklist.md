---
description: 生成质量检查清单，验证需求完整性、清晰度和一致性（在 /speckit.plan 之后运行）
---

你是一位严格的质量审计员，现在要基于已有规范文档生成「质量检查清单」。

## 前置检查（MUST）

必须先读取：
1. `.specify/memory/constitution.md` — 项目宪章
2. 对应的 `specs/features/*.spec.md` — 功能规范
3. 对应的 `plan.md`（如已存在）

## 检查清单类型

根据用户需求生成以下一类或多类检查清单：

### A. 需求完整性检查
- 用户故事是否覆盖所有主要场景？
- 边界条件和异常场景是否已定义？
- 验收标准是否可测试？
- 非功能需求（性能、安全）是否已声明？

### B. 规范清晰度检查
- 是否存在歧义的描述（如"尽快"、"合理"）？
- 枚举值是否完整定义？
- 依赖关系是否明确？

### C. Constitution 合规检查
- 接口是否在 OpenAPI yaml 中声明？
- 状态枚举是否只使用 `PENDING/PROCESSING/COMPLETED/FAILED`？
- 环境变量是否在 spec 中登记？
- 错误处理是否符合规范？

### D. 实现就绪度检查（plan 完成后）
- 所有 spec 需求是否在 plan 中有对应实现方案？
- 数据模型是否与 data-model.md 同步？
- 测试策略是否明确？

## 输出格式

参考 `.specify/templates/checklist-template.md` 的格式：

```markdown
# [类型] 检查清单: {功能名称}

**目的**: {本检查清单的用途}
**创建时间**: {日期}
**关联 Spec**: {spec.md 路径}

## {检查类别}

- [ ] CHK001 {具体可操作的检查项}
- [ ] CHK002 {具体可操作的检查项}
...

## 备注

{说明未通过的检查项如何修复}
```

## 完成后

- 保存路径：`specs/features/{feature-name}/checklist.md`
- 状态为 `- [ ]` 的项目需要在编码前修复

---

用户指定的检查类型（可选，默认生成全部类型）：

$ARGUMENTS
