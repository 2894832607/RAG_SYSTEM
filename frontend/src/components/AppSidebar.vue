<template>
  <aside class="sidebar">
    <!-- Brand -->
    <div class="sidebar-brand">
      <div class="brand-icon">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M3 17c3-3 5-8 9-8s6 5 9 8" stroke-linecap="round"/>
          <path d="M3 12c2-3 4-6 9-6s7 3 9 6" stroke-linecap="round"/>
          <path d="M12 21v-3" stroke-linecap="round"/>
        </svg>
      </div>
      <div class="brand-text">
        <span class="brand-name">诗词意境</span>
        <span class="brand-sub">Poetry RAG Agent</span>
      </div>
    </div>

    <!-- New Chat Button -->
    <button class="new-task-btn" @click="handleNewChat">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
        <line x1="12" y1="8" x2="12" y2="14"/>
        <line x1="9" y1="11" x2="15" y2="11"/>
      </svg>
      新对话
    </button>

    <!-- Navigation -->
    <nav class="sidebar-nav">
      <router-link to="/" class="nav-item" :class="{ active: $route.path === '/' }">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
        <span>生成工作台</span>
      </router-link>
      <router-link to="/history" class="nav-item" :class="{ active: $route.path === '/history' }">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <circle cx="12" cy="12" r="9" />
          <polyline points="12,7 12,12 16,14" />
        </svg>
        <span>生成历史</span>
      </router-link>
    </nav>

    <!-- Recent Chats -->
    <div class="sidebar-section" v-if="taskStore.tasks.length > 0">
      <div class="section-label">对话历史</div>
      <div class="recent-list">
        <div
          v-for="task in recentTasks"
          :key="task.taskId"
          class="recent-item"
          :class="{ active: taskStore.currentTask?.taskId === task.taskId }"
          @click="handleSelectTask(task.taskId)"
        >
          <div class="recent-dot" :class="statusClass(task.status)"></div>
          <span class="recent-text">{{ truncate(task.originalPoem, 16) }}</span>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="sidebar-footer">
      <div class="user-row">
        <div class="user-avatar">{{ userInitial }}</div>
        <div class="user-meta">
          <div class="user-name">{{ authStore.user?.nickname || authStore.user?.username || '未登录' }}</div>
          <div class="user-sub">在线</div>
        </div>
      </div>
      <button class="logout-btn" @click="handleLogout">退出登录</button>
      <div class="footer-info">
        <span>RAG + Stable Diffusion</span>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '../stores/task'
import { useAuthStore } from '../stores/auth'

const taskStore = useTaskStore()
const authStore = useAuthStore()
const router = useRouter()

const recentTasks = computed(() => taskStore.tasks.slice(0, 12))

const truncate = (text: string, max: number) =>
  text.length > max ? text.slice(0, max) + '…' : text

const statusClass = (status: string) => ({
  'dot-pending': status === 'PENDING' || status === 'RUNNING',
  'dot-success': status === 'COMPLETED',
  'dot-error': status === 'FAILED'
})

const handleSelectTask = (taskId: string) => {
  taskStore.selectTask(taskId)
  router.push('/')
}

const handleNewChat = () => {
  router.push('/')
}

const userInitial = computed(() => {
  const name = authStore.user?.nickname || authStore.user?.username || 'U'
  return name.slice(0, 1).toUpperCase()
})

const handleLogout = async () => {
  await authStore.logout()
  taskStore.clearPolling()
  router.push('/login')
}
</script>

<style scoped>
.sidebar {
  width: 260px;
  height: 100vh;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  padding: 0;
  position: fixed;
  left: 0;
  top: 0;
  z-index: 100;
  overflow-y: auto;
}

/* Brand */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 20px 16px;
}
.brand-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--accent-subtle);
  border: 1px solid rgba(201, 168, 76, 0.22);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  flex-shrink: 0;
}
.brand-text {
  display: flex;
  flex-direction: column;
}
.brand-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}
.brand-sub {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 1px;
}

/* New Task Button */
.new-task-btn {
  margin: 4px 16px 16px;
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px dashed var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
}
.new-task-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-subtle);
}

/* Navigation */
.sidebar-nav {
  padding: 0 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13.5px;
  transition: all 0.15s;
}
.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.nav-item.active {
  background: var(--bg-active);
  color: var(--text-primary);
  font-weight: 500;
}

/* Recent Tasks */
.sidebar-section {
  margin-top: 20px;
  padding: 0 12px;
  flex: 1;
}
.section-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  padding: 0 12px 8px;
}
.recent-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.recent-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 7px;
  cursor: pointer;
  transition: background 0.15s;
}
.recent-item:hover {
  background: var(--bg-hover);
}
.recent-item.active {
  background: var(--bg-active);
}
.recent-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-pending {
  background: var(--warning);
}
.dot-success {
  background: var(--accent);
}
.dot-error {
  background: var(--danger);
}
.recent-text {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.recent-item.active .recent-text {
  color: var(--text-primary);
}

/* Footer */
.sidebar-footer {
  padding: 16px 20px;
  margin-top: auto;
  border-top: 1px solid var(--border-color);
}
.user-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent-subtle);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}
.user-meta {
  min-width: 0;
}
.user-name {
  color: var(--text-primary);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.user-sub {
  color: var(--text-muted);
  font-size: 11px;
}
.logout-btn {
  width: 100%;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  font-size: 12px;
  margin-bottom: 10px;
}
.logout-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.footer-info {
  font-size: 11px;
  color: var(--text-muted);
}
</style>
