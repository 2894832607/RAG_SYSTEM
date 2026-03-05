---
description: 全链路一致性校验（spec→plan→tasks→constitution）
---

你是一位严格的质量审计员，现在要对「spec → plan → tasks」全链路进行一致性校验。

## 校验范围

必须读取并分析：
1. `.specify/memory/constitution.md`
2. 对应的 `specs/features/*.spec.md`
3. 对应的 `plan.md`
4. 对应的 `tasks.md`
5. 相关的 `specs/openapi/*.yaml`

## 校验维度

### A. Spec → Plan 覆盖性
- spec 中每条**验收标准**是否在 plan 中有对应的技术实现？
- spec 中每个**功能要求**是否在 plan 中有对应的模块设计？
- spec 中的**边界情况**是否在 plan 的错误处理中被覆盖？

### B. Plan → Tasks 落地性
- plan 中每个**新增/修改文件**是否在 tasks 中有对应任务？
- plan 中每个**接口变更**是否在 tasks 中有对应的 openapi 更新任务？
- plan 中每个**数据模型变更**是否在 tasks 中有对应的 data-model 更新任务？

### C. Constitution 合规性
- plan 的技术选型是否违反宪章的 MUST/MUST NOT 约束？
- tasks 中是否存在宪章禁止的做法？

## 输出格式

```markdown
## 一致性校验报告

### ✅ 合规项
- {合规描述}

### ❌ 问题项（需修复后再编码）
- **[严重]** {问题描述}
  → 建议修复：{具体修复方案}
- **[警告]** {问题描述}
  → 建议修复：{具体修复方案}

### 📊 覆盖率统计
- Spec 验收标准覆盖：{X}/{N}
- Plan 文件任务覆盖：{X}/{N}
- Constitution 合规：{通过/X 项违规}
```

## 完成后

发现 ❌ 问题项时，提示用户先修复规范文档，再执行 `/speckit.implement`。

---

需要分析的功能名称或 spec 路径（可选，默认分析最近修改的功能）：

$ARGUMENTS
