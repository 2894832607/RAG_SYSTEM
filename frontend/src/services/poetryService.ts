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

function withTimeout(ms: number): AbortSignal {
  const controller = new AbortController()
  window.setTimeout(() => controller.abort(), ms)
  return controller.signal
}


export async function createChatSession(): Promise<string> {
  const res = await gateway.post('/poetry/chat/session')
  // Backend 将 AI Service 返回的 session_id 包装在 data.data.session_id
  return res.data?.data?.session_id || res.data?.session_id || ''
}

// ── SSE 工厂函数（必须使用 fetch，Axios 不支持流式响应）──────────────────────

/**
 
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
 * @deprecated Chat-First UX 重构后，分镜功能已统一由 Agent 通过 generate_storyboard
 * 工具处理，前端不再直接调用此端点。保留此函数仅供历史参考，请勿在新代码中使用。
 * @see fetchChatStream
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

// ── 模型配置（直连 AI Service /ai/api/v1/config，通过 vite proxy）────────────

export interface ModelConfig {
  provider: string
  model: string
  base_url: string
  api_key_set: boolean
  enabled: boolean
}

/** 获取当前运行时 LLM 配置 */
export async function fetchModelConfig(): Promise<ModelConfig> {
  const res = await fetch('/ai/api/v1/config/model', {
    signal: withTimeout(8000),
  })
  if (!res.ok) throw new Error(`模型配置查询失败 ${res.status}`)
  return res.json()
}

/** 切换 LLM 配置 */
export async function switchModelConfig(payload: {
  preset: 'ollama' | 'glm' | 'doubao' | 'custom'
  api_key?: string
  model?: string
  base_url?: string
}): Promise<{ ok: boolean; provider: string; model: string; enabled: boolean; warning: string | null }> {
  const res = await fetch('/ai/api/v1/config/model', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: withTimeout(30000),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `切换失败 ${res.status}`)
  }
  return res.json()
}
