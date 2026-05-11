<template>
  <div class="history-view">
    <div class="history-header">
      <h1>生成历史</h1>
      <p>查看您提交过的所有诗词可视化任务与对话记录</p>
    </div>

    <!-- Tab switcher -->
    <div class="tab-bar">
      <button :class="['tab-btn', activeTab === 'tasks' ? 'active' : '']" @click="switchTab('tasks')">分镜生成</button>
      <button :class="['tab-btn', activeTab === 'chat' ? 'active' : '']" @click="switchTab('chat')">对话记录</button>
    </div>

    <!-- 分镜历史 Tab -->
    <template v-if="activeTab === 'tasks'">
      <div class="empty-state" v-if="loading">
        <p>加载中</p>
      </div>
      <div class="empty-state" v-else-if="error">
        <p style="color: var(--danger)">{{ error }}</p>
      </div>
      <div class="empty-state" v-else-if="historyTasks.length === 0">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.2">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21,15 16,10 5,21" />
        </svg>
        <h3>暂无生成记录</h3>
        <p>前往工作台提交您的第一首诗词</p>
        <button class="go-btn" @click="$router.push('/')">新建生成</button>
      </div>
      <div class="task-grid" v-else>
        <div v-for="task in historyTasks" :key="task.taskId" class="task-card" @click="handleView(task.taskId)">
          <div class="task-thumb">
            <img v-if="task.resultImageUrl" :src="task.resultImageUrl" alt="" />
            <div v-else class="thumb-placeholder">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <polyline points="21,15 16,10 5,21" />
              </svg>
            </div>
          </div>
          <div class="task-info">
            <p class="task-poem">{{ task.originalPoem }}</p>
            <div class="task-meta">
              <span class="status-tag" :class="statusClass(task.taskStatus)">{{ statusLabel(task.taskStatus) }}</span>
              <span class="task-time">{{ formatTime(task.createdAt) }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 对话记录 Tab -->
    <template v-if="activeTab === 'chat'">
      <div class="empty-state" v-if="chatLoading">
        <p>加载中</p>
      </div>
      <div class="empty-state" v-else-if="chatError">
        <p style="color: var(--danger)">{{ chatError }}</p>
      </div>
      <div class="empty-state" v-else-if="chatMessages.length === 0">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <h3>暂无对话记录</h3>
        <p>快去和诗词助手聊聊吧</p>
        <button class="go-btn" @click="$router.push('/')">开始对话</button>
      </div>
      <div class="chat-list" v-else>
        <div class="chat-round" v-for="msg in chatMessages" :key="msg.id" @click="viewConversation(msg.sessionId)" style="cursor: pointer;">
          <div class="chat-meta-row">
            <span class="chat-time">{{ formatTime(msg.createdAt) }}</span>
            <span class="session-badge">会话 {{ msg.sessionId.slice(0, 8) }}</span>
          </div>
          <div class="chat-bubble user-bubble">
            <span class="bubble-label">你</span>
            <p class="bubble-text">{{ msg.userMessage }}</p>
          </div>
          <div class="chat-bubble ai-bubble">
            <span class="bubble-label">AI</span>
            <p class="bubble-text">{{ truncate(msg.aiReply, 300) }}</p>
          </div>
        </div>
        <div class="load-more-row" v-if="chatTotal > chatMessages.length">
          <button class="load-more-btn" @click="loadMoreChat" :disabled="chatLoading">加载更多（{{ chatMessages.length }}/{{ chatTotal }}）</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchHistory, fetchChatHistory } from '../services/api'

interface HistoryTask {
  taskId: string
  originalPoem: string
  resultImageUrl: string
  taskStatus: string
  createdAt: string
}

interface ChatMsg {
  id: number
  sessionId: string
  userMessage: string
  aiReply: string
  createdAt: string
}

const router = useRouter()
const historyTasks = ref<HistoryTask[]>([])
const loading = ref(false)
const error = ref('')

const chatMessages = ref<ChatMsg[]>([])
const chatLoading = ref(false)
const chatError = ref('')
const chatTotal = ref(0)
const chatPage = ref(1)

const activeTab = ref<'tasks' | 'chat'>('tasks')

async function loadTasks() {
  if (historyTasks.value.length > 0) return
  loading.value = true
  try {
    const res = await fetchHistory()
    historyTasks.value = res.data?.data?.items || []
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载历史失败'
  } finally {
    loading.value = false
  }
}

async function loadChat(page = 1) {
  chatLoading.value = true
  try {
    const res = await fetchChatHistory(page, 20)
    const data = res.data?.data
    chatTotal.value = data?.total ?? 0
    if (page === 1) {
      chatMessages.value = data?.items || []
    } else {
      chatMessages.value = [...chatMessages.value, ...(data?.items || [])]
    }
    chatPage.value = page
  } catch (e: unknown) {
    chatError.value = e instanceof Error ? e.message : '加载对话记录失败'
  } finally {
    chatLoading.value = false
  }
}

async function loadMoreChat() {
  await loadChat(chatPage.value + 1)
}

async function switchTab(tab: 'tasks' | 'chat') {
  activeTab.value = tab
  if (tab === 'tasks') {
    await loadTasks()
  } else {
    if (chatMessages.value.length === 0) await loadChat(1)
  }
}

onMounted(async () => {
  await loadTasks()
})

const handleView = (_taskId: string) => {
  router.push('/')
}

const viewConversation = (sessionId: string) => {
  router.push(`/conversation/${sessionId}`)
}

const statusClass = (s: string) => ({
  'tag-pending': s === 'PENDING',
  'tag-success': s === 'COMPLETED',
  'tag-error': s === 'FAILED'
})

const statusLabel = (s: string) => {
  const map: Record<string, string> = { PENDING: '排队中', COMPLETED: '已完成', FAILED: '失败' }
  return map[s] || s
}

const formatTime = (iso: string) => {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso.slice(0, 16).replace('T', ' ')
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const truncate = (text: string, maxLen: number) => {
  if (!text) return ''
  return text.length > maxLen ? text.slice(0, maxLen) + '' : text
}
</script>

<style scoped>
.history-view { max-width: 960px; margin: 0 auto; padding: 40px 24px 60px; }
.history-header { margin-bottom: 24px; }
.history-header h1 { font-size: 24px; font-weight: 600; color: var(--text-primary); margin: 0 0 8px; }
.history-header p { font-size: 14px; color: var(--text-secondary); margin: 0; }
.tab-bar { display: flex; gap: 16px; margin-bottom: 24px; border-bottom: 1px solid var(--border-color); padding-bottom: 0; }
.tab-btn { padding: 8px 16px; border: none; background: transparent; color: var(--text-muted); font-size: 15px; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; transition: all 0.2s; }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 500; }
.tab-btn:hover:not(.active) { color: var(--text-primary); }
.empty-state { text-align: center; padding: 80px 20px; color: var(--text-muted); }
.empty-state h3 { margin: 20px 0 8px; font-size: 18px; color: var(--text-secondary); }
.empty-state p { margin: 0 0 24px; font-size: 14px; }
.go-btn { display: inline-flex; align-items: center; gap: 8px; padding: 10px 22px; border-radius: 10px; border: none; background: var(--accent); color: #fff; font-size: 14px; cursor: pointer; transition: background 0.2s; }
.go-btn:hover { background: var(--accent-hover); }
.task-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
.task-card { background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: 12px; overflow: hidden; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }
.task-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-sm); border-color: var(--border-hover); }
.task-thumb { width: 100%; aspect-ratio: 16 / 9; background: var(--bg-sidebar); display: flex; align-items: center; justify-content: center; overflow: hidden; border-bottom: 1px solid var(--border-color); }
.task-thumb img { width: 100%; height: 100%; object-fit: cover; }
.thumb-placeholder { color: var(--text-muted); opacity: 0.5; }
.task-info { padding: 16px; }
.task-poem { margin: 0 0 12px; font-size: 15px; color: var(--text-primary); line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.task-meta { display: flex; justify-content: space-between; align-items: center; }
.task-time { font-size: 12px; color: var(--text-muted); }
.status-tag { font-size: 12px; padding: 2px 8px; border-radius: 4px; background: var(--bg-sidebar); }
.tag-pending { color: #f59e0b; background: rgba(245, 158, 11, 0.1); }
.tag-success { color: var(--accent); background: var(--accent-subtle); }
.tag-error   { color: var(--danger); background: rgba(239, 68, 68, 0.1); }
.chat-list { display: flex; flex-direction: column; gap: 24px; }
.chat-round { display: flex; flex-direction: column; gap: 12px; padding-bottom: 24px; border-bottom: 1px dashed var(--border-color); transition: all 0.2s; border-radius: 8px; padding: 16px; margin: -16px; }
.chat-round:hover { background: var(--bg-secondary); border-bottom-color: var(--border-color); }
.chat-round:active { transform: scale(0.995); }
.chat-round:last-child { border-bottom: none; }
.chat-meta-row { display: flex; align-items: center; gap: 12px; }
.chat-time { font-size: 12px; color: var(--text-muted); }
.session-badge { font-size: 11px; color: var(--text-muted); background: var(--bg-sidebar); padding: 2px 6px; border-radius: 4px; }
.chat-bubble { display: flex; gap: 12px; align-items: flex-start; }
.bubble-label { font-size: 11px; font-weight: 600; padding: 4px 8px; border-radius: 6px; flex-shrink: 0; }
.user-bubble .bubble-label { background: rgba(96, 165, 250, 0.12); color: #60a5fa; }
.ai-bubble .bubble-label { background: var(--accent-subtle, rgba(99, 102, 241, 0.12)); color: var(--accent, #818cf8); }
.bubble-text { margin: 0; font-size: 14px; color: var(--text-primary); line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.load-more-row { text-align: center; padding-top: 8px; }
.load-more-btn { padding: 8px 20px; border: 1px solid var(--border-color); border-radius: 8px; background: transparent; color: var(--text-secondary); font-size: 13px; cursor: pointer; transition: border-color 0.15s, color 0.15s; }
.load-more-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.load-more-btn:disabled { opacity: 0.5; cursor: default; }
</style>
