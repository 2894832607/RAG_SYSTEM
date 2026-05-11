# Project Constitution — Poetry RAG System

> **版本**: 1.0  
> **生效日期**: 2026-03-05  
> **状态**: Active  
>
> ⚠️ 本文件是项目最高规则，所有代码生成、方案设计、接口定义必须无条件对齐此宪章。

---

## 1. 项目定位

**Poetry RAG System** 是一套面向中文古诗词的 RAG（检索增强生成）可视化系统，
通过语义检索 + LLM + 图像生成，将诗句意境转化为可视图像。

---

## 2. 技术栈（MUST 严格遵守）

### 2.1 Frontend
- **框架**: Vue 3 + Vite + TypeScript
- **状态管理**: Pinia
- **HTTP 客户端**: Axios
- 路由: Vue Router 4
- MUST: 所有类型声明使用 TypeScript，禁止 `any`

### 2.2 Backend
- **框架**: Spring Boot 3 + Java 17
- **ORM**: MyBatis-Plus
- **数据库**: MySQL 8+
- **构建**: Maven
- MUST: 参数校验使用 Jakarta Bean Validation（`@Valid` / `@Validated`）
- MUST: 统一响应结构为 `{ code, message, data }`
- MUST: 统一异常处理由 `@RestControllerAdvice` 的 `GlobalExceptionHandler` 处理
- MUST NOT: HTTP 500 不得向前端暴露内部堆栈信息

### 2.3 AI Service
- **框架**: FastAPI + Python 3.11+
- **Agent 框架**: LangGraph
- **LLM**: GLM（通过 `GLM_MODEL` 环境变量指定）
- **向量库**: ChromaDB（本地持久化）
- **依赖管理**: pip + requirements.txt
- MUST: 所有 Pydantic 模型字段名与 `specs/openapi/ai-service.yaml` 完全一致
- MUST: 业务失败通过 callback status=2 上报，不得直接返回 HTTP 500

---

## 3. 架构原则（MUST）

### 3.1 分层规范
```
Frontend  →  Backend REST  →  AI Service
              ↕ MySQL
```
- Backend 是唯一对外 REST 网关，Frontend 不直接调用 AI Service
- AI Service 只接受 Backend 的调用，通过 `callbackUrl` 异步回传结果
- MUST NOT: Frontend 不得直接调用 AI Service 的任何接口

### 3.2 接口规范
- 所有 Backend REST 接口 MUST 在 `specs/openapi/backend.yaml` 中声明
- 所有 AI Service 接口 MUST 在 `specs/openapi/ai-service.yaml` 中声明
- 字段名 MUST 与 OpenAPI schema `properties` 完全一致，不得自行创造字段
- MUST NOT: 先改代码接口，后补 spec

### 3.3 任务状态枚举
任何地方引用任务状态，**只允许**使用以下四个值：
```
PENDING | PROCESSING | COMPLETED | FAILED
```
MUST NOT 使用其他状态值（如 RUNNING、SUCCESS、ERROR 等）

### 3.4 安全规范
- 回调接口 MUST 校验 `X-Callback-Token`，token 不匹配返回 401
- JWT 认证 MUST 保护所有用户相关接口
- MUST NOT: 在响应体中暴露数据库 ID 以外的内部实现信息

---

## 4. 代码质量要求（MUST）

### 4.1 Backend
- 所有 DTO 字段 MUST 与 OpenAPI schema 一致
- Service 层 MUST 有接口（interface）+ 实现类分离
- MUST: 404 场景抛 `ResourceNotFoundException`
- MUST: 新接口写完后在对应 Feature Spec 中将验收标准 `[ ]` 改为 `[x]`

### 4.2 AI Service
- MUST: 每个 endpoint 有 Pydantic 请求/响应模型
- MUST: background task 异常 MUST 捕获并通过 callback 上报，不得静默失败
- MUST: 环境变量必须在对应 Feature Spec 的"环境变量规范"表中声明

### 4.3 Frontend
- MUST: API 调用通过 `services/api.ts` 统一封装，不得在组件中直接写 axios 调用
- MUST: 轮询状态展示对应 `PENDING/PROCESSING/COMPLETED/FAILED` 四种 UI 状态

---

## 5. 禁止项（MUST NOT）

- ❌ 直接改代码而不更新 spec
- ❌ 新增数据库字段而不更新 `specs/architecture/data-model.md`
- ❌ 使用 `taskStatus` 枚举以外的状态值
- ❌ 硬编码 `X-Callback-Token` 的值到代码中（必须从环境变量读取）
- ❌ AI Service 抛出未捕获的 HTTP 500
- ❌ Frontend 绕过 Backend 直接调用 AI Service
- ❌ 跳过 spec 阶段直接写代码

---

## 6. 新功能开发流程（MUST 遵守）

```
1. 创建/更新 Feature Spec（specs/features/）
   ↓
2. 如有新接口 → 更新 OpenAPI yaml（specs/openapi/）
   ↓
3. 如有数据模型变更 → 更新 data-model.md
   ↓
4. 生成 plan.md（技术方案）
   ↓
5. 生成 tasks.md（任务拆解）
   ↓
6. 编码实现（严格对齐以上规范）
   ↓
7. 在 Feature Spec 中标记验收完成（[ ] → [x]）
```

---

## 7. 关联规范文档

| 文档 | 路径 |
|------|------|
| Backend OpenAPI | `specs/openapi/backend.yaml` |
| AI Service OpenAPI | `specs/openapi/ai-service.yaml` |
| 诗词可视化 Feature Spec | `specs/features/poetry-visualization.spec.md` |
| RAG Pipeline Feature Spec | `specs/features/rag-pipeline.spec.md` |
| 系统架构 | `specs/architecture/system-overview.md` |
| 数据模型 | `specs/architecture/data-model.md` |
