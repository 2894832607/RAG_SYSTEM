---
description: 生成或更新项目宪章（constitution.md）
---

你是一位严格的技术架构师，现在要为项目生成「项目宪章（constitution.md）」。

## 前置步骤

先读取 `.specify/memory/constitution.md` 了解现有内容，再根据用户提供的新要求进行更新。

## 宪章必须包含的章节

```markdown
# [PROJECT_NAME] Constitution

## 1. 项目定位
（一句话说明系统核心价值）

## 2. 技术栈（MUST）
（每个模块的框架/语言/版本，用 MUST 明确约束）

## 3. 架构原则（MUST）
（分层规范、接口规范、状态枚举约束）

## 4. 代码质量要求（MUST）
（命名规范、错误处理、测试要求）

## 5. 禁止项（MUST NOT）
（明确列举绝对不允许的做法）

## 6. 新功能开发流程（MUST）
（标准化的 Spec→Plan→Tasks→Code 流程）

## 7. 关联规范文档
（指向 specs/ 下的各规范文件）

## Governance
（宪章是最高规则，高于所有其他实践；修订需文档化 + 迁移计划）

**Version**: X.Y | **Ratified**: YYYY-MM-DD | **Last Amended**: YYYY-MM-DD
```

## 规则

- 使用 `MUST` / `MUST NOT` / `SHOULD` 明确约束级别
- 宪章只定义全局规则，不涉及具体功能需求
- 生成完成后保存到 `.specify/memory/constitution.md`
- 同步更新 `.github/instructions/spec-coding.instructions.md` 中的规范文档索引表

---

用户输入的项目信息（技术栈、架构、规范约束）：

$ARGUMENTS
