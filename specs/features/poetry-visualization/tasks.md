# Tasks: 诗词可视化生成

> **Plan**: [specs/features/poetry-visualization/plan.md](plan.md)  
> **Spec**: [specs/features/poetry-visualization.spec.md](../poetry-visualization.spec.md)  
> **Status**: In Progress（0/8 任务完成）

---

## 任务清单

### T001 — 对齐 ErrorResponse schema [P0]
- **目标**: 确保 `GlobalExceptionHandler` 的返回格式与 `backend.yaml` 中 `ErrorResponse` schema 完全一致
- **文件**: `backend/src/main/java/com/example/poetryvisualization/controller/GlobalExceptionHandler.java`
- **实现范围**:
  - 返回字段包含 `code / message / timestamp`
  - timestamp 使用 ISO-8601 格式
  - 404 场景由 `ResourceNotFoundException` 触发，返回 code=404
- **验收标准**: 调用不存在的 taskId，返回 `{"code":404,"message":"...","timestamp":"..."}`
- **依赖**: 无
- **状态**: - [ ]

---

### T002 — 补充 ResourceNotFoundException [P0]
- **目标**: 创建统一的 404 异常类，供 Service 层抛出
- **文件**: `backend/src/main/java/com/example/poetryvisualization/exception/ResourceNotFoundException.java`
- **实现范围**:
  - 继承 `RuntimeException`
  - 构造函数接收 `String message`
- **验收标准**: `TaskDispatchService.findByTaskId()` 找不到记录时抛此异常，Controller 返回 HTTP 404
- **依赖**: T001
- **状态**: - [ ]

---

### T003 — AI Service 回调失败兜底 [P1]
- **目标**: pipeline.py 中 callback 请求失败时记录日志，不抛未捕获异常
- **文件**: `ai-service/app/modules/pipeline.py`
- **实现范围**:
  - callback POST 失败（网络异常/超时）捕获 Exception
  - 记录 `logger.error("Callback failed for taskId={}: {}", taskId, e)`
  - 不向外传播异常
- **验收标准**: 将 callbackUrl 改为无效地址，`run_pipeline_once.py` 不崩溃，日志有错误记录
- **依赖**: 无 [P]（可与 T001 并行）
- **状态**: - [ ]

---

### T004 — 验证 think-stream SSE 端到端 [P1]
- **目标**: 确认 `/api/v1/poetry/think-stream` → `/ai/api/v1/generate/think-stream` 代理链路正常
- **文件**: `backend/src/main/java/com/example/poetryvisualization/controller/PoetryVisualizationController.java`
- **实现范围**:
  - 确认 thinkUrl 替换逻辑正确（async → think-stream）
  - 确认 SseEmitter 超时 120s
  - 确认异常时 emitter 正确 completeWithError
- **验收标准**: curl 调用 think-stream 端点能收到 SSE 事件
- **依赖**: 无 [P]
- **状态**: - [ ]

---

### T005 — Backend 环境变量配置检查 [P0]
- **目标**: 确认所有必填环境变量在 application.yml 中有对应配置项且不硬编码
- **文件**: `backend/src/main/resources/application.yml`
- **实现范围**:
  - `AI_SERVICE_URL` → `ai.service.url`
  - `AI_CALLBACK_URL` → `ai.callback.url`
  - `AI_CALLBACK_TOKEN` → `ai.callback.token`
  - 确认无默认硬编码 token 值
- **验收标准**: 未设置 `AI_CALLBACK_TOKEN` 时启动报错或有明确警告
- **依赖**: 无 [P]
- **状态**: - [ ]

---

### T006 — AI Service 任务状态推进到 PROCESSING [P1]
- **目标**: AI Service 接收任务后，立即回调 Backend 将状态从 PENDING 改为 PROCESSING
- **文件**: `ai-service/app/modules/pipeline.py`
- **实现范围**:
  - 在 pipeline 开始执行时，POST callback 设置 `status=3`（或 Backend 增加 PROCESSING 回调协议）
  - 或：Backend 在发出 AI 请求后主动将状态改为 PROCESSING
- **验收标准**: 提交任务后，状态从 PENDING 变为 PROCESSING，再变为 COMPLETED/FAILED
- **依赖**: T001, T002
- **状态**: - [ ]

---

### T007 — Frontend 轮询四状态 UI [P1]
- **目标**: 前端轮询时根据 taskStatus 显示不同 UI 状态
- **文件**: `frontend/src/views/GenerateView.vue`（或对应组件）
- **实现范围**:
  - PENDING：显示"等待中..."
  - PROCESSING：显示"AI 处理中..."（可加进度动画）
  - COMPLETED：显示生成图像
  - FAILED：显示 errorMessage
- **验收标准**: 手动模拟四种状态，UI 能正确切换
- **依赖**: T001
- **状态**: - [ ]

---

### T008 — 更新 Feature Spec 验收标准 [P2]
- **目标**: T001~T007 完成后，将 spec.md 中对应的 `- [ ]` 改为 `- [x]`
- **文件**: `specs/features/poetry-visualization.spec.md`
- **实现范围**: 逐条对照已实现的功能，标记完成
- **验收标准**: spec.md 验收标准的完成率 ≥ 80%
- **依赖**: T001~T007
- **状态**: - [ ]

---

## 实现顺序

```
T001 → T002 → T006 → T008
  ↘ T003 [P]
  ↘ T004 [P]
  ↘ T005 [P]
         → T007 → T008
```

> 标注 [P] 的任务可与前序任务并行执行。
