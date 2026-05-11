---
description: 将技术方案拆解为可执行任务清单（tasks.md）
---

你是一位精确的项目规划师，现在要将技术方案拆解为「可执行任务清单（tasks.md）」。

## 前置检查（MUST）

必须先读取：
1. 对应的 `plan.md` — 技术实现方案
2. 对应的 `spec.md` — 功能规范（验收标准是任务完成的依据）

## 任务拆解原则

- **单一职责**：每个任务只修改 1-3 个文件
- **按 Phase 组织**：基础设施 → 用户故事 N → 收尾，每个 Phase 内部独立可 demo
- **`[P]` 并行标记**：操作不同文件且无依赖时标记 [P]，可并行执行
- **`[USx]` 归属标记**：每个任务标注所属用户故事，方便追溯
- **Checkpoint 门控**：每个 Phase 末尾设 Checkpoint，通过后才进入下一 Phase

## 任务文档格式（Phase 结构）

```markdown
# Tasks: {功能名称}

**Plan**: specs/features/{feature}/plan.md
**Spec**: specs/features/{feature}.spec.md
**Status**: In Progress（0/{N} 任务完成）

## 任务标记说明
- `[P]` — 可并行（操作不同文件，互不依赖）
- `[USx]` — 所属用户故事编号

---

## Phase 1: 基础设施（阻断性前置）⚠️

**目的**: 所有用户故事依赖的共用基础，必须最先完成

- [ ] T001 创建项目骨架（Entity / Repository / 错误处理）
- [ ] T002 [P] 配置公共基础设施（日志、异常处理、环境变量）
- [ ] T003 同步更新 data-model.md（如有数据模型变更）
- [ ] T004 同步更新 openapi/*.yaml（如有接口变更）

**Checkpoint** ✅: T001-T004 全部通过 → 可并行启动各用户故事

---

## Phase 2: 用户故事 1 — {标题} (P1) 🎯 MVP

**目标**: {此故事交付的具体价值}
**独立测试**: {如何在此阶段就可以 demo 这个故事}

### 测试（可选 — 测试优先时添加）
> ⚠️ 先写测试确认失败，再写实现
- [ ] T005 [P] [US1] 创建合约/集成测试 in {test 文件路径}

### 实现
- [ ] T006 [P] [US1] 创建 {实体/DTO} in {文件路径}
- [ ] T007 [US1] 实现 {Service} in {文件路径}（依赖 T006）
- [ ] T008 [US1] 实现 {Controller/Router} in {文件路径}
- [ ] T009 [US1] 添加参数校验和错误处理

**Checkpoint** ✅: 用户故事 1 完全可用，可端到端 demo

---

## Phase 3: 用户故事 2 — {标题} (P2)

（同上格式）

---

## Phase N: 收尾与横切关注点

- [ ] TXXX [P] 更新文档（README、SPEC-GUIDE）
- [ ] TXXX 将 spec.md 中已实现的验收场景标记 [ ] → [x]
- [ ] TXXX 代码清理、注释补全
```

## 完成后

- 保存路径：`specs/features/{feature-name}/tasks.md`
- 每完成一个任务：`- [ ]` → `- [x]`
- 每个 Phase 完成后验证对应 Checkpoint

$ARGUMENTS
