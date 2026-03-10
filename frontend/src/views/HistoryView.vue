<template>
  <div class="history-view">
    <div class="history-header">
      <h1>生成历史</h1>
      <p>查看您提交过的所有诗词可视化任务</p>
    </div>

    <!-- Loading State -->
    <div class="empty-state" v-if="loading">
      <p>加载中…</p>
    </div>

    <!-- Error State -->
    <div class="empty-state" v-else-if="error">
      <p style="color: var(--danger)">{{ error }}</p>
    </div>

    <!-- Empty State -->
    <div class="empty-state" v-else-if="historyTasks.length === 0">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.2">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <polyline points="21,15 16,10 5,21" />
      </svg>
      <h3>暂无生成记录</h3>
      <p>前往工作台提交您的第一首诗词</p>
      <button class="go-btn" @click="$router.push('/')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        新建生成
      </button>
    </div>

    <!-- Task Grid -->
    <div class="task-grid" v-else>
      <div
        v-for="task in historyTasks"
        :key="task.taskId"
        class="task-card"
        @click="handleView(task.taskId)"
      >
        <!-- Image or Placeholder -->
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

        <!-- Info -->
        <div class="task-info">
          <p class="task-poem">{{ task.originalPoem }}</p>
          <div class="task-meta">
            <span class="status-tag" :class="statusClass(task.taskStatus)">
              {{ statusLabel(task.taskStatus) }}
            </span>
            <span class="task-time">{{ formatTime(task.createdAt) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchHistory } from '../services/api'

interface HistoryTask {
  taskId: string
  originalPoem: string
  resultImageUrl: string
  taskStatus: string
  createdAt: string
}

const router = useRouter()
const historyTasks = ref<HistoryTask[]>([])
const loading = ref(false)
const error = ref('')

onMounted(async () => {
  loading.value = true
  try {
    const res = await fetchHistory()
    historyTasks.value = res.data?.data?.items || []
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '加载历史失败'
    error.value = msg
  } finally {
    loading.value = false
  }
})

const handleView = (_taskId: string) => {
  router.push('/')
}

const statusClass = (s: string) => ({
  'tag-pending': s === 'PENDING',
  'tag-success': s === 'COMPLETED',
  'tag-error': s === 'FAILED'
})

const statusLabel = (s: string) => {
  const map: Record<string, string> = {
    PENDING: '排队中',
    COMPLETED: '已完成',
    FAILED: '失败'
  }
  return map[s] || s
}

const formatTime = (iso: string) => {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso.slice(0, 16).replace('T', ' ')
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<style scoped>
.history-view {
  max-width: 960px;
  margin: 0 auto;
  padding: 40px 24px 60px;
}
.history-header {
  margin-bottom: 32px;
}
.history-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
}
.history-header p {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-muted);
}
.empty-state h3 {
  margin: 20px 0 8px;
  font-size: 18px;
  color: var(--text-secondary);
}
.empty-state p {
  margin: 0 0 24px;
  font-size: 14px;
}
.go-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 22px;
  border-radius: 10px;
  border: none;
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.go-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px var(--accent-glow);
}

/* Task Grid */
.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.task-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
}
.task-card:hover {
  transform: translateY(-2px);
  border-color: var(--accent);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}
.task-thumb {
  height: 160px;
  background: var(--bg-tertiary);
  overflow: hidden;
}
.task-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}
.task-info {
  padding: 14px 16px;
}
.task-poem {
  margin: 0 0 10px;
  font-size: 14px;
  color: var(--text-primary);
  font-family: 'Noto Serif SC', 'Source Han Serif SC', serif;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.task-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.status-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}
.tag-pending {
  background: rgba(245, 158, 11, 0.12);
  color: var(--warning);
}
.tag-success {
  background: var(--accent-subtle);
  color: var(--accent);
}
.tag-error {
  background: rgba(239, 68, 68, 0.1);
  color: var(--danger);
}
.task-time {
  font-size: 12px;
  color: var(--text-muted);
}
</style>
