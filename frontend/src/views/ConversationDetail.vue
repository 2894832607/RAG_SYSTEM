<template>
  <div class="conversation-detail">
    <div class="detail-header">
      <button class="back-btn" @click="goBack">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15,18 9,12 15,6" />
        </svg>
        返回历史
      </button>
      <div class="header-info">
        <h1>对话详情</h1>
        <p class="session-info">会话 ID: {{ sessionId }}</p>
      </div>
    </div>

    <div class="loading-state" v-if="loading">
      <div class="spinner"></div>
      <p>加载中...</p>
    </div>

    <div class="error-state" v-else-if="error">
      <p>{{ error }}</p>
      <button class="retry-btn" @click="loadConversation">重试</button>
    </div>

    <div class="empty-state" v-else-if="messages.length === 0">
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
      <h3>暂无消息</h3>
      <p>这条对话记录是空的</p>
    </div>

    <div class="messages-container" v-else>
      <div class="message-group" v-for="(msg, index) in messages" :key="msg.id">
        <div class="message-row user-message">
          <div class="message-avatar user-avatar">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <div class="message-content">
            <div class="message-header">
              <span class="sender-name">你</span>
              <span class="message-time">{{ formatTime(msg.createdAt) }}</span>
            </div>
            <div class="message-body">
              <p>{{ msg.userMessage }}</p>
            </div>
          </div>
        </div>

        <div class="message-row ai-message" v-if="msg.aiReply">
          <div class="message-avatar ai-avatar">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21,15 16,10 5,21" />
            </svg>
          </div>
          <div class="message-content">
            <div class="message-header">
              <span class="sender-name">AI 助手</span>
              <span class="message-time">{{ formatTime(msg.createdAt) }}</span>
            </div>
            <div class="message-body ai-body">
              <div class="ai-response" v-html="formatAiResponse(msg.aiReply)"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchChatHistory } from '../services/api'

interface ChatMessage {
  id: number
  sessionId: string
  userMessage: string
  aiReply: string
  createdAt: string
}

const route = useRoute()
const router = useRouter()

const sessionId = route.params.sessionId as string
const messages = ref<ChatMessage[]>([])
const loading = ref(true)
const error = ref('')

async function loadConversation() {
  loading.value = true
  error.value = ''
  
  try {
    // 加载该会话的所有消息
    const res = await fetchChatHistory(1, 100)
    const data = res.data?.data
    const allMessages = data?.items || []
    
    // 过滤出当前会话的消息
    messages.value = allMessages.filter((msg: ChatMessage) => msg.sessionId === sessionId)
    
    if (messages.value.length === 0) {
      error.value = '未找到该会话的消息'
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push('/history')
}

function formatTime(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso.slice(0, 16).replace('T', ' ')
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatAiResponse(text: string) {
  // 简单的格式化：换行转<br>，代码块保留
  return text
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
}

onMounted(() => {
  if (sessionId) {
    loadConversation()
  } else {
    error.value = '缺少会话 ID'
    loading.value = false
  }
})
</script>

<style scoped>
.conversation-detail {
  min-height: 100vh;
  padding: 2rem;
  background: var(--bg-primary);
}

.detail-header {
  margin-bottom: 2rem;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  cursor: pointer;
  font-size: 0.95rem;
  transition: all 0.2s;
}

.back-btn:hover {
  background: var(--bg-secondary);
  border-color: var(--accent);
}

.header-info {
  margin-top: 1.5rem;
}

.header-info h1 {
  font-size: 1.75rem;
  color: var(--text-primary);
  margin: 0 0 0.5rem 0;
}

.session-info {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.loading-state, .error-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  text-align: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-state p {
  color: var(--danger);
  margin-bottom: 1rem;
}

.retry-btn {
  padding: 0.75rem 1.5rem;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
}

.empty-state svg {
  opacity: 0.5;
  margin-bottom: 1rem;
}

.empty-state h3 {
  color: var(--text-primary);
  margin: 0 0 0.5rem 0;
}

.empty-state p {
  color: var(--text-muted);
  margin: 0;
}

.messages-container {
  max-width: 900px;
  margin: 0 auto;
}

.message-group {
  margin-bottom: 2rem;
}

.message-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.user-message {
  flex-direction: row;
}

.ai-message {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-avatar {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.ai-avatar {
  background: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
}

.message-content {
  flex: 1;
  max-width: 70%;
}

.user-message .message-content {
  text-align: left;
}

.ai-message .message-content {
  text-align: right;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.sender-name {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.message-time {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.message-body {
  background: var(--bg-secondary);
  padding: 1rem 1.25rem;
  border-radius: 12px;
  word-wrap: break-word;
}

.user-message .message-body {
  background: rgba(59, 130, 246, 0.1);
  border-left: 3px solid #3b82f6;
}

.ai-message .message-body {
  background: rgba(139, 92, 246, 0.1);
  border-right: 3px solid #8b5cf6;
  text-align: left;
}

.ai-body {
  line-height: 1.6;
}

.ai-response {
  white-space: pre-wrap;
}

@media (max-width: 768px) {
  .conversation-detail {
    padding: 1rem;
  }
  
  .message-content {
    max-width: 85%;
  }
}
</style>
