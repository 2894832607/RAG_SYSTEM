# Implementation Plan: 接口通信协议及文档完善

> Status: IN_PROGRESS
> Reference Spec: [interface-communication.spec.md](../features/interface-communication.spec.md)

## 1. 核心架构设计
本方案旨在通过 "Spec-First" 的开发模式，强制要求前后端及 AI Service 模块对齐 OpenAPI 语义。我们将建立一套自动化的契约检查机制（后续可通过 CI/CD 增强），并更新现有代码库以符合规范。

- **Frontend**: 统一通过 `src/services/` 调用后端，使用 TypeScript 强类型约束业务 DTO。
- **Backend API**: 严格遵循 `specs/openapi/backend.yaml` 定义的 Path 与 Schema。
- **AI Logic**: 修复由于 `sourceText` 与 `poemText` 等命名冲突引起的字段不匹配问题。

## 2. 技术栈
- **API Spec**: OpenAPI 3.1.0 (YAML)
- **Frontend**: Vue 3 (Axios + TypeScript)
- **Backend**: Spring Boot 3 (Java 17)
- **AI Service**: FastAPI (Python 3.11 + Pydantic)

## 3. 实现节奏 (Phases)

### Phase 0: Outline & Research
- [x] 梳理现有通信链路冲突（`sourceText` vs `poemText`）。
- [x] 调研 Backend 校验逻辑中的拦截器是否全局生效。
- [x] 确认 AI Service 回调逻辑的 `X-Callback-Token` 传递方式。

### Phase 1: Design & Contracts
- [x] 创建 `specs/features/interface-communication.spec.md` (已完成)
- [ ] 导出 OpenAPI 描述文档至 `specs/architecture/contracts/`
- [ ] 更新 `quickstart.md` 中关于环境配置（CALLBACK_TOKEN）的说明。

### Phase 2: Refactoring & Alignment
- [ ] **Frontend**: 检查 `src/services/` 下所有 API 定义，确保字段与 `backend.yaml` 一致。
- [ ] **Backend**: 重构 `PoemController` 及其 DTO，使其符合通用响应结构。
- [ ] **AI Service**: 更新 `app/schemas/requests.py`，统一请求载荷格式。

## 4. 风险与权衡
- **命名规范冲突**: `backend` 和 `ai-service` 最初使用的是不同的字段命名（如 `poemText` vs `sourceText`），本方案将以 `backend.yaml` 为基准统一命名规范。
- **配置一致性**: 如果 `CALLBACK_TOKEN` 两侧配置不一致，将导致任务状态无法更新。

## 5. 验收
- 运行 `mvn spring-boot:run` 无启动错误。
- 自动化冒烟测试脚本 `smoke_test.py` 能够收到回调并成功通过 200。
