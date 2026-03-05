<template>
  <div class="chat-page">
    <!-- Welcome Screen (no history) -->
    <transition name="fade-out">
      <div class="chat-welcome" v-if="tasks.length === 0">
        <div class="welcome-deco">
          <div class="ink-circle"></div>
          <div class="ink-circle ink-circle-2"></div>
        </div>
        <div class="welcome-badge">Agent  RAG  Stable Diffusion</div>
        <h1 class="welcome-title">诗词意境</h1>
        <p class="welcome-subtitle">与 AI 对话，探索古典诗词的意境世界</p>
        <div class="welcome-samples">
          <span class="samples-label">试试这些诗句</span>
          <div class="samples-grid">
            <button
              v-for="sample in samplePoems"
              :key="sample"
              class="sample-pill"
              @click="inputText = sample"
            >
              <span class="pill-inner">{{ sample }}</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Chat Message List -->
    <div class="chat-scroll" ref="messagesRef" v-show="tasks.length > 0">
      <div class="chat-inner">
        <div
          v-for="(task, index) in tasks"
          :key="task.taskId"
          class="chat-turn"
        >
          <!-- User Bubble -->
          <div class="turn-user">
            <div class="user-bubble">
              <span class="poem-text">{{ task.originalPoem }}</span>
            </div>
            <div class="user-avatar">{{ userInitial }}</div>
          </div>

          <!-- Agent Response -->
          <div class="turn-agent">
            <div class="agent-logo">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="12" cy="12" r="9"/>
                <circle cx="12" cy="12" r="4"/>
                <line x1="12" y1="7" x2="12" y2="5"/>
                <line x1="12" y1="19" x2="12" y2="17"/>
                <line x1="7" y1="12" x2="5" y2="12"/>
                <line x1="19" y1="12" x2="17" y2="12"/>
              </svg>
            </div>

            <div class="agent-body">
              <!-- Thinking Stream Block -->
              <div
                class="thinking-block"
                v-if="thinkingTexts[task.taskId] || thinkingActives[task.taskId]"
              >
                <div class="thinking-top">
                  <span class="thinking-chip">GLM Agent 推理</span>
                  <div class="thinking-pulse" v-if="thinkingActives[task.taskId]">
                    <span></span><span></span><span></span>
                  </div>
                  <span class="thinking-done" v-else> 完成</span>
                </div>
                <div
                  class="thinking-body"
                  :ref="(el) => setThinkingRef(task.taskId, el)"
                >
                  <span class="thinking-text">{{ thinkingTexts[task.taskId] }}</span>
                  <span class="cursor-blink" v-if="thinkingActives[task.taskId]"></span>
                </div>
              </div>

              <!-- Waiting dots (before pipeline starts) -->
              <div
                class="agent-waiting"
                v-if="(task.status === 'PENDING' || task.status === 'RUNNING')
                  && !task.retrievedText && !task.enhancedPrompt
                  && !thinkingTexts[task.taskId]"
              >
                <span class="dot-bounce"></span>
                <span class="dot-bounce"></span>
                <span class="dot-bounce"></span>
              </div>

              <!-- Pipeline Steps -->
              <PipelineSteps
                v-if="task.status === 'RUNNING' || task.status === 'COMPLETED'
                  || task.status === 'FAILED'
                  || task.retrievedText || task.enhancedPrompt"
                :status="task.status"
                :retrieved-text="task.retrievedText"
                :enhanced-prompt="task.enhancedPrompt"
                :result-image-url="task.resultImageUrl"
              />

              <!-- Error -->
              <div class="error-block" v-if="task.status === 'FAILED'">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="9"/>
                  <line x1="15" y1="9" x2="9" y2="15"/>
                  <line x1="9" y1="9" x2="15" y2="15"/>
                </svg>
                <span>{{ task.errorMessage || '生成失败，请稍后重试' }}</span>
              </div>

              <!-- Result Card -->
              <div class="result-card" v-if="task.status === 'COMPLETED' || task.resultImageUrl">
                <div class="result-image-wrap" v-if="task.resultImageUrl">
                  <img :src="task.resultImageUrl" alt="AI 意境生成图" class="result-img" loading="lazy"/>
                  <div class="image-overlay">
                    <a :href="task.resultImageUrl" target="_blank" class="view-full-btn">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
                        <polyline points="15,3 21,3 21,9"/>
                        <line x1="10" y1="14" x2="21" y2="3"/>
                      </svg>
                      查看原图
                    </a>
                  </div>
                </div>

                <details class="result-details" v-if="task.retrievedText || task.enhancedPrompt">
                  <summary class="details-summary">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="9"/>
                      <line x1="12" y1="8" x2="12" y2="12"/>
                      <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    RAG 检索  增强提示词
                    <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="6,9 12,15 18,9"/>
                    </svg>
                  </summary>
                  <div class="details-body">
                    <div class="detail-item" v-if="task.retrievedText">
                      <div class="detail-label">
                        <span class="label-dot rag"></span>RAG 检索结果
                      </div>
                      <p class="detail-text">{{ task.retrievedText }}</p>
                    </div>
                    <div class="detail-item" v-if="task.enhancedPrompt">
                      <div class="detail-label">
                        <span class="label-dot prompt"></span>增强提示词
                      </div>
                      <code class="detail-code">{{ task.enhancedPrompt }}</code>
                    </div>
                  </div>
                </details>
              </div>

            </div>
          </div>
        </div>

        <div style="height: 28px"></div>
      </div>
    </div>

    <!-- Input Dock -->
    <div class="input-dock">
      <div class="input-shell">
        <textarea
          v-model="inputText"
          ref="textareaRef"
          class="input-textarea"
          :placeholder="tasks.length === 0 ? '输入一句古诗词，例如：大漠孤烟直，长河落日圆' : '继续输入诗词，与 AI 对话'"
          rows="1"
          @input="autoResize"
          @keydown.enter.exact.prevent="handleSend"
          @keydown.shift.enter="appendNewline"
        ></textarea>
        <button
          class="send-btn"
          :class="{ 'send-loading': taskStore.submitting }"
          :disabled="!inputText.trim() || taskStore.submitting"
          @click="handleSend"
        >
          <svg v-if="!taskStore.submitting" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22,2 15,22 11,13 2,9"/>
          </svg>
          <div v-else class="send-spinner"></div>
        </button>
      </div>
      <div class="input-hint">Enter 发送  Shift + Enter 换行</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '../stores/task'
import { useAuthStore } from '../stores/auth'
import PipelineSteps from '../components/PipelineSteps.vue'

const taskStore = useTaskStore()
const authStore = useAuthStore()

const inputText = ref('')
const messagesRef = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

// Per-task thinking state
const thinkingTexts = reactive<Record<string, string>>({})
const thinkingActives = reactive<Record<string, boolean>>({})
const thinkingBodyEls: Record<string, HTMLElement | null> = {}
const thinkingControllers: Record<string, AbortController> = {}

const tasks = computed(() => taskStore.tasks)

const userInitial = computed(() => {
  const name = authStore.user?.nickname || authStore.user?.username || 'U'
  return name.slice(0, 1).toUpperCase()
})

const samplePoems = [
  '大漠孤烟直，长河落日圆',
  '孤帆远影碧空尽，唯见长江天际流',
  '月落乌啼霜满天，江枫渔火对愁眠',
  '千山鸟飞绝，万径人踪灭',
  '春江潮水连海平，海上明月共潮生',
]

const setThinkingRef = (taskId: string, el: any) => {
  thinkingBodyEls[taskId] = el as HTMLElement | null
}

const startThinkingStream = async (taskId: string, poem: string) => {
  if (thinkingControllers[taskId]) thinkingControllers[taskId].abort()
  thinkingControllers[taskId] = new AbortController()
  thinkingTexts[taskId] = ''
  thinkingActives[taskId] = true

  try {
    const response = await fetch('/api/v1/poetry/think-stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authStore.token}`
      },
      body: JSON.stringify({ poemText: poem }),
      signal: thinkingControllers[taskId].signal
    })

    if (!response.ok || !response.body) return

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) continue
        const data = trimmed.slice(5).trim()
        if (data === '[DONE]') { thinkingActives[taskId] = false; return }
        try {
          const parsed = JSON.parse(data)
          if (parsed.text) {
            thinkingTexts[taskId] += parsed.text
            await nextTick()
            const el = thinkingBodyEls[taskId]
            if (el) el.scrollTop = el.scrollHeight
            scrollToBottom()
          }
        } catch { /* ignore */ }
      }
    }
  } catch (err: any) {
    if (err?.name !== 'AbortError') console.warn('thinking stream error', err)
  } finally {
    thinkingActives[taskId] = false
  }
}

watch(
  () => tasks.value.map((t) => t.status),
  () => {
    tasks.value.forEach((task) => {
      if (task.status === 'COMPLETED' || task.status === 'FAILED') {
        const ctrl = thinkingControllers[task.taskId]
        if (ctrl) ctrl.abort()
        thinkingActives[task.taskId] = false
      }
    })
  }
)

const scrollToBottom = async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTo({ top: messagesRef.value.scrollHeight, behavior: 'smooth' })
  }
}

watch(() => tasks.value.length, scrollToBottom)
watch(thinkingTexts, scrollToBottom, { deep: true })

const autoResize = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

const appendNewline = (e: KeyboardEvent) => {
  e.preventDefault()
  inputText.value += '\n'
  nextTick(autoResize)
}

const handleSend = async () => {
  const text = inputText.value.trim()
  if (!text) return
  try {
    const task = await taskStore.addTask(text)
    inputText.value = ''
    await nextTick()
    if (textareaRef.value) textareaRef.value.style.height = 'auto'
    scrollToBottom()
    startThinkingStream(task.taskId, text)
  } catch {
    ElMessage.error('提交失败，请检查网络连接')
  }
}
</script>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  position: relative;
  background: var(--bg-main);
}

/*  Welcome  */
.chat-welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 24px 180px;
  position: relative;
  overflow: hidden;
  text-align: center;
  animation: fadeInUp 0.6s ease both;
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}
.fade-out-leave-active { transition: opacity 0.2s, transform 0.2s; }
.fade-out-leave-to { opacity: 0; transform: scale(0.97); }

.welcome-deco {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.ink-circle {
  position: absolute;
  width: 500px;
  height: 500px;
  border-radius: 50%;
  border: 1px solid rgba(201, 168, 76, 0.055);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation: rotateSlow 40s linear infinite;
}
.ink-circle-2 {
  width: 760px;
  height: 760px;
  border-color: rgba(201, 168, 76, 0.025);
  animation-duration: 60s;
  animation-direction: reverse;
}
@keyframes rotateSlow { to { transform: translate(-50%, -50%) rotate(360deg); } }

.welcome-badge {
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
  background: var(--accent-subtle);
  border: 1px solid rgba(201, 168, 76, 0.22);
  padding: 4px 16px;
  border-radius: 20px;
  margin-bottom: 28px;
}
.welcome-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 62px;
  font-weight: 600;
  margin: 0 0 14px;
  letter-spacing: 0.15em;
  background: linear-gradient(135deg, #e8d8a0 0%, #c9a84c 55%, #9a6f1e 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1.1;
}
.welcome-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0 0 44px;
  line-height: 1.7;
}
.welcome-samples {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.samples-label {
  font-size: 11.5px;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.samples-grid {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}
.sample-pill {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 24px;
  padding: 0;
  cursor: pointer;
  transition: all 0.2s;
  overflow: hidden;
}
.pill-inner {
  display: block;
  padding: 9px 20px;
  font-family: 'Noto Serif SC', serif;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
}
.sample-pill:hover {
  border-color: var(--accent);
  background: var(--accent-subtle);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px var(--accent-glow);
}
.sample-pill:hover .pill-inner { color: var(--accent); }

/*  Chat Scroll  */
.chat-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-bottom: 140px;
}
.chat-scroll::-webkit-scrollbar { width: 4px; }
.chat-scroll::-webkit-scrollbar-track { background: transparent; }
.chat-scroll::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 2px; }

.chat-inner {
  max-width: 860px;
  margin: 0 auto;
  padding: 36px 24px 0;
}

/*  Turn  */
.chat-turn {
  margin-bottom: 48px;
  animation: turnSlide 0.4s ease both;
}
@keyframes turnSlide {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* User side */
.turn-user {
  display: flex;
  justify-content: flex-end;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 20px;
}
.user-bubble {
  max-width: 65%;
  background: var(--bg-card);
  border: 1px solid rgba(201, 168, 76, 0.18);
  border-radius: 16px 4px 16px 16px;
  padding: 14px 20px;
}
.poem-text {
  font-family: 'Noto Serif SC', serif;
  font-size: 16px;
  line-height: 1.85;
  color: var(--text-primary);
  letter-spacing: 0.06em;
  white-space: pre-wrap;
}
.user-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--accent-subtle);
  border: 1px solid rgba(201, 168, 76, 0.28);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 2px;
}

/* Agent side */
.turn-agent {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}
.agent-logo {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(201, 168, 76, 0.15), rgba(201, 168, 76, 0.05));
  border: 1px solid rgba(201, 168, 76, 0.22);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}
.agent-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Waiting dots */
.agent-waiting {
  display: flex;
  gap: 6px;
  padding: 12px 0 4px;
  align-items: center;
}
.dot-bounce {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  display: inline-block;
  animation: dotBounce 1.3s ease-in-out infinite;
}
.dot-bounce:nth-child(2) { animation-delay: 0.15s; }
.dot-bounce:nth-child(3) { animation-delay: 0.30s; }
@keyframes dotBounce {
  0%, 80%, 100% { transform: scale(0.5); opacity: 0.3; }
  40% { transform: scale(1); opacity: 1; }
}

/* Thinking block */
.thinking-block {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  animation: fadeIn 0.3s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.thinking-top {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
}
.thinking-chip {
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--accent);
  background: var(--accent-subtle);
  border: 1px solid rgba(201, 168, 76, 0.2);
  padding: 3px 10px;
  border-radius: 12px;
}
.thinking-pulse {
  display: flex;
  gap: 4px;
  align-items: center;
}
.thinking-pulse span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
  display: inline-block;
  animation: dotBounce 1.2s ease-in-out infinite;
}
.thinking-pulse span:nth-child(2) { animation-delay: 0.12s; }
.thinking-pulse span:nth-child(3) { animation-delay: 0.24s; }
.thinking-done {
  font-size: 11px;
  color: var(--success);
  margin-left: auto;
}
.thinking-body {
  padding: 14px 18px;
  max-height: 200px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--border-color) transparent;
}
.thinking-text {
  font-size: 12.5px;
  line-height: 1.9;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}
.cursor-blink {
  display: inline-block;
  color: var(--accent);
  animation: cursorFlash 0.8s step-end infinite;
  margin-left: 1px;
}
@keyframes cursorFlash { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

/* Error */
.error-block {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  border-radius: 10px;
  background: rgba(192, 57, 43, 0.08);
  border: 1px solid rgba(192, 57, 43, 0.2);
  color: var(--danger);
  font-size: 13.5px;
}

/* Result card */
.result-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  overflow: hidden;
}
.result-image-wrap {
  position: relative;
  overflow: hidden;
}
.result-img {
  display: block;
  width: 100%;
  max-height: 440px;
  object-fit: cover;
  transition: transform 0.5s ease;
}
.result-image-wrap:hover .result-img { transform: scale(1.01); }
.image-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0,0,0,0.55));
  padding: 28px 16px 14px;
  opacity: 0;
  transition: opacity 0.25s;
  display: flex;
  justify-content: flex-end;
}
.result-image-wrap:hover .image-overlay { opacity: 1; }
.view-full-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  background: rgba(255,255,255,0.14);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 8px;
  color: #fff;
  font-size: 12px;
  text-decoration: none;
  backdrop-filter: blur(6px);
  transition: background 0.2s;
}
.view-full-btn:hover { background: rgba(255,255,255,0.22); }

/* Details accordion */
.result-details { border-top: 1px solid var(--border-color); }
.details-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 18px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-muted);
  list-style: none;
  user-select: none;
  transition: color 0.15s;
}
.details-summary::-webkit-details-marker { display: none; }
.details-summary:hover { color: var(--text-secondary); }
.details-summary .chevron { margin-left: auto; transition: transform 0.2s; }
.result-details[open] .details-summary {
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
}
.result-details[open] .details-summary .chevron { transform: rotate(180deg); }
.details-body {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.detail-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.label-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.label-dot.rag { background: var(--warning); }
.label-dot.prompt { background: var(--accent); }
.detail-text {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--text-secondary);
}
.detail-code {
  display: block;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-secondary);
  word-break: break-all;
  background: var(--bg-tertiary);
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

/*  Input Dock  */
.input-dock {
  position: fixed;
  bottom: 0;
  left: 260px;
  right: 0;
  padding: 14px 24px 22px;
  background: linear-gradient(transparent, var(--bg-main) 30%);
  z-index: 50;
}
.input-shell {
  max-width: 860px;
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 12px 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.input-shell:focus-within {
  border-color: rgba(201, 168, 76, 0.38);
  box-shadow: 0 0 0 3px var(--accent-glow);
}
.input-textarea {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.65;
  font-family: 'Noto Serif SC', serif;
  min-height: 24px;
  max-height: 160px;
  overflow-y: auto;
  scrollbar-width: thin;
}
.input-textarea::placeholder {
  color: var(--text-muted);
  font-family: -apple-system, 'PingFang SC', sans-serif;
  font-size: 14px;
}
.send-btn {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  border: none;
  background: var(--accent);
  color: var(--bg-base);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
}
.send-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 14px var(--accent-glow);
}
.send-btn:disabled {
  opacity: 0.36;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}
.send-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(11, 10, 8, 0.25);
  border-top-color: var(--bg-base);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.input-hint {
  max-width: 860px;
  margin: 5px auto 0;
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}
</style>