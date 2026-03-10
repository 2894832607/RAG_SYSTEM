/**
 * Poetry Service — 封装所有与诗词相关的后端 API 调用
 *
 * Spec: specs/openapi/backend.yaml
 *   - POST /api/v1/poetry/chat/session  — 创建对话会话
 *   - POST /api/v1/poetry/chat          — 对话 SSE（必须用 fetch，Axios 不支持流式响应）
 *   - POST /api/v1/poetry/storyboard    — 分镜 SSE
 *   - GET  /api/v1/poetry/history       — 历史任务列表
 *
 * 调用方（GenerateView.vue）通过此文件统一访问后端，
 * 避免在视图层散落硬编码 URL 和请求逻辑。
 */

import { gateway } from './api'

// ── REST 调用（走 Axios gateway，自动附加 Bearer token）──────────────────────

/** 创建新的对话会话，返回 session_id */
export async function createChatSession(): Promise<string> {
  const res = await gateway.post('/poetry/chat/session')
  // Backend 将 AI Service 返回的 session_id 包装在 data.data.session_id
  return res.data?.data?.session_id || res.data?.session_id || ''
}

// ── SSE 工厂函数（必须使用 fetch，Axios 不支持流式响应）──────────────────────

/**
 * 构造诗词对话 SSE 请求（返回 Response，由调用方负责迭代 body reader）
 *
 * @param message  用户消息
 * @param sessionId  会话 ID
 * @param token  JWT token（Bearer）
 */
export function fetchChatStream(message: string, sessionId: string, token: string): Promise<Response> {
  return fetch('/api/v1/poetry/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
}

/**
 * 构造分镜生成 SSE 请求
 *
 * @param sourceText  源诗句文本
 * @param token  JWT token（Bearer）
 */
export function fetchStoryboardStream(sourceText: string, token: string): Promise<Response> {
  return fetch('/api/v1/poetry/storyboard', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ sourceText }),
  })
}

/** 查询当前用户历史分镜任务（走 Axios gateway） */
export function fetchHistory(page = 1, pageSize = 20) {
  return gateway.get('/poetry/history', { params: { page, pageSize } })
}
