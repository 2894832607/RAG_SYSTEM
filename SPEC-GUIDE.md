# SPEC-GUIDE — Spec Coding 快速入门

> Poetry RAG System 的规范驱动开发指南。  
> **Spec First，Code Second.**

---

## 为什么要 Spec Coding？

| Vibe Coding | Spec Coding |
|-------------|-------------|
| AI 凭感觉生成代码，字段名随机 | AI 严格按 OpenAPI schema 生成 |
| 接口改了没人知道，前后端对齐靠人肉 | `specs/openapi/*.yaml` 是唯一真相来源 |
| 功能"完成"全凭感觉 | Feature Spec 验收标准 checklist 驱动 |
| 数据库字段靠翻代码 | `data-model.md` 是权威文档 |
| 环境变量靠文档或经验 | 每个 spec 有独立的环境变量表 |
| 上下文丢失，AI 每次重新猜 | Constitution 宪章 + spec 上下文始终对齐 |

---

## 完整目录结构

```
.specify/
└── memory/
    └── constitution.md        ← ⭐ 项目宪章（最高规则，所有生成必须对齐）

.copilot/
└── commands/
    ├── speckit.constitution.md  ← /speckit.constitution 斜杠命令
    ├── speckit.specify.md       ← /speckit.specify
    ├── speckit.clarify.md       ← /speckit.clarify
    ├── speckit.plan.md          ← /speckit.plan
    ├── speckit.tasks.md         ← /speckit.tasks
    ├── speckit.analyze.md       ← /speckit.analyze
    └── speckit.implement.md     ← /speckit.implement

specs/
├── openapi/
│   ├── backend.yaml             ← Spring Boot 接口规范（OpenAPI 3.1）
│   └── ai-service.yaml          ← FastAPI AI 服务接口规范（OpenAPI 3.1）
├── features/
│   ├── poetry-visualization.spec.md   ← Feature Spec
│   ├── poetry-visualization/
│   │   ├── plan.md                    ← 技术实现方案
│   │   └── tasks.md                   ← 可执行任务清单
│   └── rag-pipeline.spec.md           ← Feature Spec
└── architecture/
    ├── system-overview.md       ← 系统架构总览
    └── data-model.md            ← 数据库 + 向量库数据模型
```

---

## 标准工作流（9 阶段）

```
阶段 1  宪章      /speckit.constitution  → .specify/memory/constitution.md
阶段 2  功能规范  /speckit.specify       → specs/features/{feature}.spec.md
阶段 3  需求澄清  /speckit.clarify       → 更新 spec.md
阶段 4  技术方案  /speckit.plan          → specs/features/{feature}/plan.md
阶段 5  任务拆解  /speckit.tasks         → specs/features/{feature}/tasks.md
阶段 6  一致性校验 /speckit.analyze      → 校验报告
阶段 7  代码实现  /speckit.implement     → 按 tasks.md 逐任务生成代码
阶段 8  验收标记  （自动）               → spec.md [ ] → [x]
阶段 9  归档提交  git commit             → 规范文档随代码一起保存
```

> 简单功能可合并阶段：specify → plan → implement（跳过 clarify + analyze）

---

## 如何使用斜杠命令

在 VS Code Copilot Chat 中直接输入（可触发自动补全）：

```
/speckit.specify  做一个 XXX 功能，需求是...
/speckit.plan     补充技术约束：使用 XX 框架，按照 XX 架构...
/speckit.tasks
/speckit.implement
```

Copilot 会自动读取 `.specify/memory/constitution.md` 和相关 spec 文件作为上下文。

---

## 工作流：修改现有接口

```
1. 先修改 specs/openapi/backend.yaml 或 ai-service.yaml
   ↓
2. 同步更新 Feature Spec 的验收标准
   ↓
3. 再修改代码
```

> ❌ 禁止：先改代码，再补 spec

---

## 快速查找表

| 我想做… | 先读哪个文档 |
|--------|------------|
| 了解项目最高规则 | [.specify/memory/constitution.md](.specify/memory/constitution.md) |
| 加一个后端 REST 接口 | [specs/openapi/backend.yaml](specs/openapi/backend.yaml) |
| 加一个 AI Service 接口 | [specs/openapi/ai-service.yaml](specs/openapi/ai-service.yaml) |
| 改任务状态流转逻辑 | [specs/features/poetry-visualization.spec.md](specs/features/poetry-visualization.spec.md) |
| 看诗词可视化的实现计划 | [specs/features/poetry-visualization/plan.md](specs/features/poetry-visualization/plan.md) |
| 看待执行的任务清单 | [specs/features/poetry-visualization/tasks.md](specs/features/poetry-visualization/tasks.md) |
| 改 RAG 检索或 Agent | [specs/features/rag-pipeline.spec.md](specs/features/rag-pipeline.spec.md) |
| 加数据库字段 | [specs/architecture/data-model.md](specs/architecture/data-model.md) |
| 理解系统架构 | [specs/architecture/system-overview.md](specs/architecture/system-overview.md) |

---

## Copilot Chat 最佳提示词

```
# ✅ Spec Coding 风格（推荐）
"先读 .specify/memory/constitution.md 和
specs/openapi/backend.yaml，
然后按照 TaskDetail schema 实现 getTask 的 Service 层。
404 时抛出 ResourceNotFoundException，
taskStatus 只能使用 PENDING/PROCESSING/COMPLETED/FAILED。"

# ❌ Vibe Coding 风格（避免）
"帮我写一个查询任务的接口"
```

---

## PR 前 Checklist

- [ ] 新接口已在对应 OpenAPI yaml 中声明
- [ ] Feature Spec 验收标准已更新（完成的改为 `[x]`）
- [ ] 环境变量已在 spec 中登记
- [ ] 数据模型变更已同步 data-model.md
- [ ] 错误响应格式符合 ErrorResponse schema
- [ ] tasks.md 中本次实现的任务已标记完成
