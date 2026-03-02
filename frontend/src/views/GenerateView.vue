<template>
  <div class="generate-view">
    <!-- Hero Input Section -->
    <section class="input-section" :class="{ 'has-result': !!currentTask }">
      <div class="input-wrapper">
        <div class="input-header" v-if="!currentTask">
          <h1 class="main-title">诗词意境可视化</h1>
          <p class="main-desc">输入一首古诗词，AI 将通过 RAG 检索增强与 Stable Diffusion 为您生成对应的意境画面</p>
        </div>

        <div class="input-box">
          <textarea
            v-model="poemText"
            class="poem-textarea"
            :placeholder="placeholderText"
            :rows="currentTask ? 2 : 4"
            @keydown.ctrl.enter="handleSubmit"
          ></textarea>
          <div class="input-actions">
            <span class="input-hint">Ctrl + Enter 发送</span>
            <button
              class="submit-btn"
              :class="{ loading: taskStore.submitting }"
              :disabled="taskStore.submitting || !poemText.trim()"
              @click="handleSubmit"
            >
              <svg v-if="!taskStore.submitting" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22,2 15,22 11,13 2,9" />
              </svg>
              <div v-else class="btn-spinner"></div>
              <span>{{ taskStore.submitting ? '提交中…' : '开始生成' }}</span>
            </button>
          </div>
        </div>

        <!-- Sample Poems -->
        <div class="samples" v-if="!currentTask">
          <span class="samples-label">试试这些：</span>
          <button
            v-for="sample in samplePoems"
            :key="sample"
            class="sample-chip"
            @click="poemText = sample"
          >
            {{ sample }}
          </button>
        </div>
      </div>
    </section>

    <!-- Result Section -->
    <section class="result-section" v-if="currentTask">
      <!-- Pipeline Steps -->
      <PipelineSteps
        :status="currentTask.status"
        :retrieved-text="currentTask.retrievedText"
        :enhanced-prompt="currentTask.enhancedPrompt"
        :result-image-url="currentTask.resultImageUrl"
      />

      <!-- Error State -->
      <div v-if="currentTask.status === 'FAILED'" class="error-banner">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
        <div>
          <strong>生成失败</strong>
          <p>{{ currentTask.errorMessage || '未知错误，请稍后重试' }}</p>
        </div>
      </div>

      <!-- Result Content -->
      <div class="result-grid" v-if="currentTask.status === 'COMPLETED' || currentTask.retrievedText || currentTask.enhancedPrompt">
        <!-- Image Preview -->
        <div class="result-card image-card" v-if="currentTask.resultImageUrl">
          <div class="card-header">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21,15 16,10 5,21" />
            </svg>
            <span>生成结果</span>
          </div>
          <div class="image-wrapper">
            <img :src="currentTask.resultImageUrl" alt="AI 生成的诗词意境图" @load="imageLoaded = true" />
          </div>
        </div>

        <!-- Loading placeholder for image -->
        <div class="result-card image-card image-loading" v-else-if="currentTask.status !== 'COMPLETED'">
          <div class="card-header">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21,15 16,10 5,21" />
            </svg>
            <span>生成结果</span>
          </div>
          <div class="image-placeholder">
            <div class="placeholder-spinner"></div>
            <span>AI 正在绘制中…</span>
          </div>
        </div>

        <!-- Details Panel -->
        <div class="result-details">
          <!-- Original Poem -->
          <div class="result-card">
            <div class="card-header">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <polyline points="14,2 14,8 20,8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
              <span>原始诗句</span>
            </div>
            <p class="card-body poem-text">{{ currentTask.originalPoem }}</p>
          </div>

          <!-- Retrieved Knowledge -->
          <div class="result-card" v-if="currentTask.retrievedText">
            <div class="card-header">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span>RAG 检索结果</span>
              <span class="card-badge">Retrieval</span>
            </div>
            <p class="card-body">{{ currentTask.retrievedText }}</p>
          </div>

          <!-- Enhanced Prompt -->
          <div class="result-card" v-if="currentTask.enhancedPrompt">
            <div class="card-header">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
              </svg>
              <span>增强提示词</span>
              <span class="card-badge">Augmented</span>
            </div>
            <p class="card-body prompt-text">{{ currentTask.enhancedPrompt }}</p>
          </div>
        </div>
      </div>

      <!-- Waiting State -->
      <div class="waiting-state" v-else-if="currentTask.status === 'PENDING' || currentTask.status === 'RUNNING'">
        <div class="waiting-animation">
          <div class="wave-dot"></div>
          <div class="wave-dot"></div>
          <div class="wave-dot"></div>
        </div>
        <p>正在处理您的诗词，请稍候…</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '../stores/task'
import PipelineSteps from '../components/PipelineSteps.vue'

const taskStore = useTaskStore()
const poemText = ref('')
const imageLoaded = ref(false)

const currentTask = computed(() => taskStore.currentTask)

const samplePoems = [
  '大漠孤烟直，长河落日圆',
  '孤帆远影碧空尽，唯见长江天际流',
  '月落乌啼霜满天，江枫渔火对愁眠',
  '千山鸟飞绝，万径人踪灭'
]

const placeholderText = '请输入一首古诗词，例如：大漠孤烟直，长河落日圆…'

const handleSubmit = async () => {
  const text = poemText.value.trim()
  if (!text) {
    ElMessage.warning('请输入诗句内容')
    return
  }
  try {
    await taskStore.addTask(text)
    poemText.value = ''
    ElMessage.success('任务已提交，正在处理中')
  } catch {
    ElMessage.error('提交失败，请检查网络连接')
  }
}
</script>

<style scoped>
.generate-view {
  max-width: 960px;
  margin: 0 auto;
  padding: 40px 24px 60px;
  min-height: 100vh;
}

/* ===== Input Section ===== */
.input-section {
  transition: all 0.4s ease;
}
.input-section:not(.has-result) {
  padding-top: 12vh;
}
.input-section.has-result {
  padding-top: 0;
}
.input-wrapper {
  max-width: 720px;
  margin: 0 auto;
}
.input-header {
  text-align: center;
  margin-bottom: 32px;
}
.main-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 12px;
  letter-spacing: -0.02em;
}
.main-desc {
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}

.input-box {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 16px;
  transition: border-color 0.2s;
}
.input-box:focus-within {
  border-color: var(--accent);
}
.poem-textarea {
  width: 100%;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.7;
  resize: none;
  outline: none;
  font-family: 'Noto Serif SC', 'Source Han Serif SC', 'PingFang SC', serif;
}
.poem-textarea::placeholder {
  color: var(--text-muted);
}
.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}
.input-hint {
  font-size: 12px;
  color: var(--text-muted);
}
.submit-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 22px;
  border-radius: 10px;
  border: none;
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.submit-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px var(--accent-glow);
}
.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Samples */
.samples {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
}
.samples-label {
  font-size: 13px;
  color: var(--text-muted);
}
.sample-chip {
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: 'Noto Serif SC', 'Source Han Serif SC', serif;
}
.sample-chip:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-subtle);
}

/* ===== Result Section ===== */
.result-section {
  margin-top: 32px;
}

/* Error Banner */
.error-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 20px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: var(--danger);
  margin-top: 20px;
}
.error-banner strong {
  display: block;
  margin-bottom: 4px;
  font-size: 14px;
}
.error-banner p {
  margin: 0;
  font-size: 13px;
  opacity: 0.85;
}

/* Result Grid */
.result-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-top: 24px;
}
@media (max-width: 768px) {
  .result-grid {
    grid-template-columns: 1fr;
  }
}

.result-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-color);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}
.card-badge {
  margin-left: auto;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  background: var(--accent-subtle);
  color: var(--accent);
}
.card-body {
  padding: 16px 18px;
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
}
.poem-text {
  font-family: 'Noto Serif SC', 'Source Han Serif SC', serif;
  font-size: 16px;
  letter-spacing: 0.05em;
}
.prompt-text {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12.5px;
  color: var(--text-secondary);
  word-break: break-all;
}

/* Image Card */
.image-card {
  grid-row: span 3;
}
.image-wrapper {
  padding: 12px;
}
.image-wrapper img {
  width: 100%;
  border-radius: 8px;
  display: block;
}
.image-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: var(--text-muted);
  gap: 16px;
}
.placeholder-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

/* Result Details */
.result-details {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Waiting State */
.waiting-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 0 40px;
  color: var(--text-muted);
  gap: 20px;
}
.waiting-animation {
  display: flex;
  gap: 8px;
}
.wave-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
  animation: wave 1.4s ease-in-out infinite;
}
.wave-dot:nth-child(2) { animation-delay: 0.16s; }
.wave-dot:nth-child(3) { animation-delay: 0.32s; }
@keyframes wave {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}
</style>
