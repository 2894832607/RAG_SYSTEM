<template>
  <div class="chat-page">
    <!-- Welcome Screen -->
    <transition name="fade-out">
      <div class="chat-welcome" v-if="messages.length === 0">
        <div class="welcome-deco">
          <div class="ink-circle"></div>
          <div class="ink-circle ink-circle-2"></div>
        </div>
        <div class="welcome-badge">Agent · RAG · 意境生图</div>
        <h1 class="welcome-title">诗词意境</h1>
        <p class="welcome-subtitle">与 AI 对话，探索古典诗词的意境世界<br>也可输入诗句，让 AI 为你生成一幅意境插画</p>
        <div class="welcome-samples">
          <span class="samples-label">试试这些</span>
          <div class="samples-grid">
            <button v-for="s in sampleInputs" :key="s.text" class="sample-pill"
              @click="inputText = s.text; $nextTick(() => textareaRef?.focus())">
              <span class="pill-inner">
                <span class="pill-tag">{{ s.tag }}</span>{{ s.text }}
              </span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Chat Messages -->
    <div class="chat-scroll" ref="messagesRef" v-show="messages.length > 0">
      <div class="chat-inner">
        <div v-for="msg in messages" :key="msg.id" class="chat-turn">

          <!-- User Bubble -->
          <div class="turn-user" v-if="msg.role === 'user'">
            <div class="user-bubble">
              <span class="poem-text">{{ msg.userText }}</span>
            </div>
            <div class="user-avatar">{{ userInitial }}</div>
          </div>

          <!-- Agent Bubble -->
          <div class="turn-agent" v-else>
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
              <!-- ── Process Panel（统一推理过程面板，立即显示） ── -->
              <div
                class="process-panel"
                v-if="msg.isStreaming || msg.tools.length > 0 || msg.thinkingLogs.length > 0"
                :class="{ done: !msg.isStreaming, collapsed: msg.thinkingCollapsed }"
              >
                <!-- 头部：状态 + 工具徽章 + 折叠 -->
                <div class="process-header" @click="msg.thinkingCollapsed = !msg.thinkingCollapsed">
                  <div class="process-header-left">
                    <div class="process-ring" :class="{ spinning: msg.isStreaming }">
                      <svg v-if="!msg.isStreaming" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="3.5"><polyline points="20,6 9,17 4,12"/></svg>
                    </div>
                    <span class="process-status-text">
                      {{ msg.isStreaming ? (msg.statusText || '思考中…') : `完成推理 · 用时 ${msg.waitSeconds}s` }}
                    </span>
                  </div>
                  <div class="process-header-right">
                    <span v-for="tool in msg.tools" :key="tool.name" class="tool-badge" :class="tool.status">
                      {{ tool.display }}<span v-if="tool.count > 1" class="badge-count"> ×{{ tool.count }}</span>
                      <svg v-if="tool.status === 'done'" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20,6 9,17 4,12"/></svg>
                      <div v-else class="badge-spinner"></div>
                    </span>
                    <svg class="collapse-chevron" :class="{ open: !msg.thinkingCollapsed }" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6,9 12,15 18,9"/></svg>
                  </div>
                </div>

                <!-- 阶段时间线（展开时显示） -->
                <div class="process-phases" v-if="!msg.thinkingCollapsed">
                  <template v-for="(ph, i) in buildPhases(msg)" :key="ph.key">
                    <div class="phase-step" :class="ph.status" v-if="ph.visible">
                      <div class="phase-icon-wrap">
                        <svg v-if="ph.status === 'done'" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5"><polyline points="20,6 9,17 4,12"/></svg>
                        <div v-else-if="ph.status === 'active'" class="phase-spinner"></div>
                        <div v-else class="phase-dot-pending"></div>
                      </div>
                      <span class="phase-label">{{ ph.label }}</span>
                    </div>
                    <div class="phase-connector" :class="{ filled: ph.status === 'done' }" v-if="ph.visible && i < buildPhases(msg).length - 1 && buildPhases(msg)[i + 1]?.visible"></div>
                  </template>
                </div>

                <!-- 实时日志（展开时显示） -->
                <TransitionGroup
                  v-if="!msg.thinkingCollapsed && msg.thinkingLogs.length > 0"
                  tag="div"
                  class="process-logs"
                  name="log-pop"
                >
                  <div class="log-entry" v-for="entry in msg.thinkingLogs" :key="entry.id">
                    <span class="log-dot"></span>
                    <span class="log-text">{{ entry.text }}</span>
                  </div>
                </TransitionGroup>
              </div>

              <!-- RAG 检索结果面板（独立于 thinking-block，始终可见） -->
              <div class="rag-results-panel" v-if="msg.ragResults && msg.ragResults.length > 0">
                <div class="rag-panel-header" @click="msg.ragResultsExpanded = !msg.ragResultsExpanded">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                  <span class="rag-panel-title">RAG 检索结果</span>
                  <span class="rag-count-badge">{{ msg.ragResults.length }} 首</span>
                  <svg class="rag-chevron" :class="{ open: msg.ragResultsExpanded }" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6,9 12,15 18,9"/></svg>
                </div>
                <div class="rag-poems-list" v-show="msg.ragResultsExpanded">
                  <div class="rag-poem-card" :class="{ expanded: poem.expanded, ['conf-' + confLevel(poem.similarity)]: true }" v-for="poem in msg.ragResults" :key="poem.index" @click="poem.expanded = !poem.expanded">
                    <div class="rag-poem-top">
                      <span class="rag-poem-title">《{{ poem.title }}》</span>
                      <span class="rag-poem-meta">{{ poem.author }} · {{ poem.dynasty }}</span>
                      <span class="rag-mode-tag" :class="poem.mode">{{ poem.mode === 'exact' ? '精准' : '语义' }}</span>
                      <svg class="rag-card-chevron" :class="{ open: poem.expanded }" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6,9 12,15 18,9"/></svg>
                    </div>
                    <!-- 可信度条 -->
                    <div class="rag-conf-row">
                      <div class="rag-conf-bar-wrap">
                        <div class="rag-conf-bar" :class="confLevel(poem.similarity)" :style="{ width: (poem.similarity * 100).toFixed(1) + '%' }"></div>
                      </div>
                      <span class="rag-sim-pct" :class="confLevel(poem.similarity)">{{ (poem.similarity * 100).toFixed(1) }}%</span>
                      <span class="rag-conf-label" :class="confLevel(poem.similarity)">{{ confLevelText(poem.similarity) }}</span>
                    </div>
                    <div class="rag-poem-body" v-show="poem.expanded">
                      <div class="rag-poem-original" v-if="poem.original">{{ poem.original }}</div>
                      <div class="rag-poem-no-content" v-else>（暂无原文）</div>
                      <div class="rag-poem-trans" v-if="poem.translation">
                        <span class="rag-trans-label">译</span>{{ poem.translation }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Pipeline Steps (only when generate_image triggered) -->
              <PipelineSteps
                v-if="msg.hasGeneration"
                :pipeline-stage="msg.pipelineStage"
                :is-streaming="msg.isStreaming"
              />

              <!-- Final Reply -->
              <div class="reply-text" v-if="msg.replyText">
                <span v-html="renderMarkdown(msg.replyText)"></span>
                <span class="cursor-blink" v-if="msg.isStreaming && !msg.hasGeneration"></span>
              </div>

              <!-- Suggestion Pills -->
              <div class="suggestion-pills" v-if="msg.suggestions && msg.suggestions.length > 0 && !msg.isStreaming">
                <span class="sugg-label">💡 你可能还想</span>
                <button
                  v-for="sugg in msg.suggestions"
                  :key="sugg"
                  class="sugg-btn"
                  @click="sendSuggestion(sugg)"
                >
                  {{ sugg }}
                </button>
              </div>

              <!-- Image Card -->
              <div class="result-card" v-if="msg.imageUrl">
                <div class="result-image-wrap">
                  <img :src="msg.imageUrl" alt="AI 意境插画" class="result-img" loading="lazy"
                    @error="(e) => (e.target as HTMLImageElement).style.display='none'"/>
                  <div class="image-overlay">
                    <a :href="msg.imageUrl" target="_blank" class="view-full-btn">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15,3 21,3 21,9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                      查看原图
                    </a>
                  </div>
                </div>
                <details class="result-details" v-if="msg.poemInfo || msg.enhancedPrompt || msg.ragText">
                  <summary class="details-summary">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    RAG 检索 · 提示词详情
                    <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6,9 12,15 18,9"/></svg>
                  </summary>
                  <div class="details-body">
                    <div class="detail-item" v-if="msg.poemInfo">
                      <div class="detail-label"><span class="label-dot rag"></span>来源诗词</div>
                      <p class="detail-text">{{ msg.poemInfo }}</p>
                    </div>
                    <div class="detail-item" v-if="msg.enhancedPrompt">
                      <div class="detail-label"><span class="label-dot prompt"></span>正向提示词</div>
                      <code class="detail-code">{{ msg.enhancedPrompt }}</code>
                    </div>
                    <div class="detail-item" v-if="msg.negativePrompt">
                      <div class="detail-label"><span class="label-dot" style="background:var(--danger)"></span>负向提示词</div>
                      <code class="detail-code">{{ msg.negativePrompt }}</code>
                    </div>
                  </div>
                </details>
              </div>

              <!-- Storyboard Shots Grid（多图分镜）：plan 事件后立即显示占位网格 -->
              <div class="storyboard-wrap" v-if="msg.storyboardPlan || (msg.storyboardShots && msg.storyboardShots.length > 0)">
                <div class="storyboard-header" v-if="msg.storyboardPlan">
                  <span class="storyboard-title">《{{ msg.storyboardPlan.poem_title }}》{{ msg.storyboardPlan.author }} · {{ msg.storyboardPlan.dynasty }}</span>
                  <span class="storyboard-count">{{ msg.storyboardShots.length }} / {{ msg.storyboardTotal || '?' }} 张</span>
                </div>
                <div class="storyboard-grid">
                  <div
                    v-for="shot in msg.storyboardShots"
                    :key="shot.shot_id"
                    class="shot-card"
                    :class="{ 'shot-error': !!shot.error, 'shot-loading': !shot.image_url && !shot.error }"
                  >
                    <!-- 图片区 -->
                    <div class="shot-img-wrap">
                      <img
                        v-if="shot.image_url"
                        :src="shot.image_url"
                        :alt="shot.shot_name"
                        class="shot-img"
                        loading="lazy"
                        @error="(e) => (e.target as HTMLImageElement).src = ''"
                      />
                      <div v-else-if="shot.error" class="shot-placeholder shot-err-placeholder">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                        生成失败
                      </div>
                      <div v-else class="shot-placeholder">
                        <div class="shot-spinner"></div>
                      </div>
                      <a v-if="shot.image_url" :href="shot.image_url" target="_blank" class="shot-fullscreen">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15,3 21,3 21,9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                      </a>
                    </div>
                    <!-- 元信息 -->
                    <div class="shot-meta">
                      <div class="shot-name">{{ shot.shot_name }}</div>
                      <div class="shot-lines" v-if="shot.poem_lines && shot.poem_lines.length">
                        {{ shot.poem_lines.join('　') }}
                      </div>
                      <div class="shot-emotion" v-if="shot.emotion">{{ shot.emotion }}</div>
                    </div>
                  </div>
                  <!-- 占位骨架（plan 已知总数，但图片还未到） -->
                  <div
                    v-for="n in pendingPlaceholders(msg)"
                    :key="'ph-' + n"
                    class="shot-card shot-loading"
                  >
                    <div class="shot-img-wrap">
                      <div class="shot-placeholder"><div class="shot-spinner"></div></div>
                    </div>
                    <div class="shot-meta"><div class="shot-name">等待生成…</div></div>
                  </div>
                </div>
              </div>

              <!-- Error -->
              <div class="error-block" v-if="msg.error">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                {{ msg.error }}
              </div>

            </div>
          </div>

        </div>
        <div style="height: 32px"></div>
      </div>
    </div>

    <!-- Input Dock -->
    <div class="input-dock">
      <div class="input-shell">
        <textarea
          v-model="inputText"
          ref="textareaRef"
          class="input-textarea"
          :placeholder="messages.length === 0 ? '输入诗句生成分镜意境图，或直接聊聊古诗词……' : '继续提问，或输入诗句生成意境图…'"
          rows="1"
          @input="autoResize"
          @keydown.enter.exact.prevent="handleSend"
          @keydown.shift.enter="appendNewline"
        ></textarea>
        <button
          class="send-btn"
          :disabled="!inputText.trim() || isSending"
          @click="handleSend"
        >
          <svg v-if="!isSending" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22,2 15,22 11,13 2,9"/>
          </svg>
          <div v-else class="send-spinner"></div>
        </button>
      </div>
      <div class="input-hint">Enter 发送 · Shift+Enter 换行 · 输入诗句自动生成分镜意境图</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { createChatSession as apiCreateSession, fetchChatStream, fetchStoryboardStream } from '../services/poetryService'
import { useAuthStore } from '../stores/auth'
import PipelineSteps from '../components/PipelineSteps.vue'

let _logIdSeq = 0
const newLogId = () => ++_logIdSeq

const authStore = useAuthStore()

// ── Types ──────────────────────────────────────────────────────────────────
interface ToolEntry {
  name: string
  display: string
  status: 'running' | 'done'
  count: number
}

interface LogEntry {
  id: number
  text: string
}

interface RagPoem {
  index: number
  title: string
  author: string
  dynasty: string
  original: string
  translation: string
  similarity: number
  expanded: boolean
  mode: 'exact' | 'semantic'
}

interface StoryboardShot {
  shot_id: number
  shot_name: string
  shot_type: string
  poem_lines: string[]
  translation_excerpt: string
  camera_angle: string
  emotion: string
  positive_prompt: string
  image_url: string | null
  error?: string
}

interface StoryboardPlanInfo {
  poem_title: string
  author: string
  dynasty: string
  global_style: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  userText: string
  isStreaming: boolean
  replyText: string
  tools: ToolEntry[]
  thinkingCollapsed: boolean
  hasGeneration: boolean
  pipelineStage: 'idle' | 'rag' | 'enhance' | 'generate' | 'done' | 'failed'
  ragText: string
  enhancedPrompt: string
  imageUrl: string
  poemInfo: string
  negativePrompt: string
  suggestions: string[]
  error: string
  statusText: string
  waitSeconds: number
  streamStartedAt: number
  lastEventAt: number
  thinkingLogs: LogEntry[]
  progressBucket: number
  thinkingQueue: string[]
  thinkingFlushTimer: number | null
  ragResults: RagPoem[]
  ragResultsExpanded: boolean
  currentPhase: 'understand' | 'retrieve' | 'think' | 'reply' | 'done'
  // 分镜多图相关
  storyboardShots: StoryboardShot[]
  storyboardPlan: StoryboardPlanInfo | null
  storyboardTotal: number
  isStoryboard: boolean
}

// ── RAG output parser ──────────────────────────────────────────────────
const parseRagOutput = (output: string): RagPoem[] => {
  if (!output || output.includes('检索失败') || output.includes('检索超时') || output.includes('未在知识库')) {
    return []
  }

  const poems: RagPoem[] = []

  // ── 语义模式（多首）：包含 "找到 N 首" 标识 ──────────────────────
  if (output.includes('找到')) {
    // 分割每个 **[N]** 条目
    const entries = output.split(/\*\*\[\d+\]\*\*/).slice(1)
    entries.forEach((entry, i) => {
      // 第一行：《诗名》 — 作者（朝代） 相似度 0.xx
      const headerLine = entry.split('\n')[0] || ''
      const headerMatch = headerLine.match(/《(.+?)》\s*[\u2014\u2013\-]+\s*(.+?)（(.+?)）\s*相似度\s*([\d.]+)/)
      if (!headerMatch) return
      const [, title, author, dynasty, simStr] = headerMatch

      const origMatch = entry.match(/原诗[\uff1a:]+\s*(.+?)(?:\n|$)/)
      const transMatch = entry.match(/译文[\uff1a:]+\s*(.+?)(?:……|\n|$)/)

      poems.push({
        index: i + 1,
        title: title.trim(),
        author: author.trim(),
        dynasty: dynasty.trim(),
        original: origMatch ? origMatch[1].trim() : '',
        translation: transMatch ? transMatch[1].trim() : '',
        similarity: parseFloat(simStr || '0'),
        expanded: false,
        mode: 'semantic',
      })
    })
    return poems
  }

  // ── 精准模式（单首） ───────────────────────────────────
  // 格式: **《title》 — author（dynasty）**
  const headerMatch = output.match(/\*\*《(.+?)》\s*[\u2014\u2013\-]+\s*(.+?)（(.+?)）\*\*/)
  if (!headerMatch) return poems
  const [, title, author, dynasty] = headerMatch

  // 原诗内容：在 **原诗：** 和 **白话译文：** 之间
  const origMatch  = output.match(/\*\*原诗[：:]\.?\*\*[\s\S]*?\n([\s\S]+?)\n\n\*\*白话/)
  // 译文内容：在 **白话译文：** 和 相似度 之间
  const transMatch = output.match(/\*\*白话译文[：:]\.?\*\*[\s\S]*?\n([\s\S]+?)\n\n相似度/)
  const simMatch   = output.match(/相似度[：:]([\d.]+)/)

  poems.push({
    index: 1,
    title: title.trim(),
    author: author.trim(),
    dynasty: dynasty.trim(),
    original: origMatch  ? origMatch[1].trim()  : '',
    translation: transMatch ? transMatch[1].trim() : '',
    similarity: simMatch ? parseFloat(simMatch[1]) : 0,
    expanded: false,
    mode: 'exact',
  })
  return poems
}

// ── State ──────────────────────────────────────────────────────────────────
const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const isSending = ref(false)
const messagesRef = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const sessionId = ref('')

const TOOL_DISPLAY: Record<string, string> = {
  search_poetry:  'RAG 检索',
  visualize_poem: '意境插画',
}

// 各阶段索引（用于比较）
const PHASE_IDX: Record<string, number> = {
  understand: 0, retrieve: 1, think: 2, reply: 3, done: 4,
}

interface PhaseItem {
  key: string
  label: string
  visible: boolean
  status: 'done' | 'active' | 'pending'
}

const buildPhases = (msg: ChatMessage): PhaseItem[] => {
  // 分镜流程专用阶段
  if (msg.isStoryboard) {
    const hasPlan = !!msg.storyboardPlan
    const hasShots = msg.storyboardShots.length > 0
    const allDone = !msg.isStreaming
    const phases: PhaseItem[] = [
      { key: 'rag',      label: 'RAG 检索', visible: true,
        status: hasPlan || hasShots || allDone ? 'done' : msg.isStreaming ? 'active' : 'pending' },
      { key: 'plan',     label: 'GLM 规划分镜', visible: true,
        status: hasPlan || hasShots || allDone ? 'done' : (msg.isStreaming && !hasPlan) ? 'pending' : 'pending' },
      { key: 'generate', label: 'CogView-4 生图', visible: true,
        status: allDone ? 'done' : hasShots ? 'active' : 'pending' },
    ]
    // 动态计算每阶段状态
    phases[0].status = hasPlan || hasShots || allDone ? 'done' : 'active'
    phases[1].status = hasPlan || hasShots || allDone ? (hasShots || allDone ? 'done' : 'active') : 'pending'
    phases[2].status = allDone ? 'done' : hasShots ? 'active' : 'pending'
    return phases
  }

  // 对话流程阶段
  const hasRetrieval = msg.tools.some(t => t.name === 'search_poetry')
  const ci = PHASE_IDX[msg.currentPhase] ?? 0
  return [
    { key: 'understand', label: '理解问题', visible: true },
    { key: 'retrieve',   label: 'RAG 检索', visible: hasRetrieval },
    { key: 'think',      label: '深度推理', visible: true },
    { key: 'reply',      label: '生成回复', visible: true },
  ].map(ph => {
    const pi = PHASE_IDX[ph.key]
    let status: 'done' | 'active' | 'pending' = 'pending'
    if (!msg.isStreaming) {
      status = 'done'
    } else if (ci > pi) {
      status = 'done'
    } else if (ci === pi) {
      status = 'active'
    }
    return { ...ph, status }
  })
}

// 可信度等级辅助函数
const confLevel = (sim: number): 'high' | 'mid' | 'low' => {
  if (sim >= 0.75) return 'high'
  if (sim >= 0.55) return 'mid'
  return 'low'
}
const confLevelText = (sim: number): string => {
  if (sim >= 0.75) return '高可信'
  if (sim >= 0.55) return '中可信'
  return '参考'
}

// 实时添加日志，无延迟队列，每条带唯一 id 保证动画稳定
const addThinkingLog = (msg: ChatMessage, text: string) => {
  const value = text.trim()
  if (!value) return
  const last = msg.thinkingLogs[msg.thinkingLogs.length - 1]
  if (last?.text === value) return
  msg.thinkingLogs.push({ id: newLogId(), text: value })
  if (msg.thinkingLogs.length > 30) msg.thinkingLogs.shift()
}

const sampleInputs = [
  { tag: '生图', text: '大漠孤烟直，长河落日圆' },
  { tag: '生图', text: '月落乌啼霜满天，江枫渔火对愁眠' },
  { tag: '问答', text: '李白最著名的几首诗是什么？' },
  { tag: '问答', text: '《静夜思》表达了什么情感？' },
  { tag: '生图', text: '春江潮水连海平，海上明月共潮生' },
]

const userInitial = computed(() => {
  const name = authStore.user?.nickname || authStore.user?.username || 'U'
  return name.slice(0, 1).toUpperCase()
})

// ── 自动意图检测：判断是否为诗词/场景可视化输入 ───────────────────────────────
// 检测规则：包含古典诗句特征（较长中文串，无明显问句词）或明确可视化关键词
const VISUALIZE_KEYWORDS = ['生成图', '画出', '可视化', '意境图', '插画', '分镜', '场景生图', '生图', '画一幅', '画成']
const POEM_PATTERN = /[\u4e00-\u9fa5，。！？；]{10,}/
const SHORT_POEM_PATTERN = /^[\u4e00-\u9fa5]{4,9}[，。！；]?([\u4e00-\u9fa5]{4,9})?$/
const QUESTION_WORDS = ['什么', '为什么', '如何', '怎么', '谁', '哪', '是不是', '吗', '呢']

const detectVisualizeIntent = (text: string): boolean => {
  const t = text.trim()
  if (VISUALIZE_KEYWORDS.some(k => t.includes(k))) return true
  if (QUESTION_WORDS.some(w => t.includes(w)) || t.endsWith('？') || t.endsWith('?')) return false
  if (POEM_PATTERN.test(t)) return true
  // 短句古诗：4-9 个汉字拼成的经典诗句（单/双句）
  if (SHORT_POEM_PATTERN.test(t)) return true
  return false
}

// 分镜占位骨架计算
const pendingPlaceholders = (msg: ChatMessage): number => {
  if (!msg.storyboardTotal) return 0
  const arrived = msg.storyboardShots.length
  const pending = msg.storyboardTotal - arrived
  return pending > 0 ? pending : 0
}

// ── Session ────────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    // Spec: specs/features/interface-communication.spec.md §5
    const newId = await apiCreateSession()
    sessionId.value = newId
  } catch {
    sessionId.value = crypto.randomUUID()
  }
})

// ── Send ────────────────────────────────────────────────────────────────────
const handleSend = async () => {
  const text = inputText.value.trim()
  if (!text || isSending.value) return
  inputText.value = ''
  if (textareaRef.value) textareaRef.value.style.height = 'auto'

  messages.value.push({
    id: crypto.randomUUID(), role: 'user', userText: text,
    isStreaming: false, replyText: '', tools: [], thinkingCollapsed: false,
    hasGeneration: false, pipelineStage: 'idle',
    ragText: '', enhancedPrompt: '', imageUrl: '', poemInfo: '', negativePrompt: '', suggestions: [], error: '',
    statusText: '', waitSeconds: 0, streamStartedAt: 0, lastEventAt: 0, thinkingLogs: [], progressBucket: -1,
    thinkingQueue: [], thinkingFlushTimer: null,
    ragResults: [], ragResultsExpanded: true,
    currentPhase: 'understand',
    storyboardShots: [], storyboardPlan: null, storyboardTotal: 0, isStoryboard: false,
  })

  const agentMsg: ChatMessage = {
    id: crypto.randomUUID(), role: 'agent', userText: '',
    isStreaming: true, replyText: '', tools: [], thinkingCollapsed: false,
    hasGeneration: false, pipelineStage: 'idle',
    ragText: '', enhancedPrompt: '', imageUrl: '', poemInfo: '', negativePrompt: '', suggestions: [], error: '',
    statusText: '正在处理…', waitSeconds: 0, streamStartedAt: 0, lastEventAt: 0, thinkingLogs: [], progressBucket: -1,
    thinkingQueue: [], thinkingFlushTimer: null,
    ragResults: [], ragResultsExpanded: true,
    currentPhase: 'understand',
    storyboardShots: [], storyboardPlan: null, storyboardTotal: 0, isStoryboard: false,
  }
  messages.value.push(agentMsg)
  isSending.value = true
  await nextTick()
  scrollToBottom()

  // 自动判断：诗词/场景可视化意图 → 分镜流程；问答对话 → agent chat
  const useStoryboard = detectVisualizeIntent(text)
  agentMsg.isStoryboard = useStoryboard

  try {
    if (useStoryboard) {
      agentMsg.statusText = 'RAG 检索中，规划分镜…'
      await streamStoryboard(text, agentMsg)
    } else {
      agentMsg.statusText = '正在理解你的问题…'
      await streamChat(text, agentMsg)
    }
  } catch (err: any) {
    agentMsg.error = err?.message || '连接失败，请重试'
  } finally {
    agentMsg.isStreaming = false
    isSending.value = false
    agentMsg.statusText = agentMsg.error ? '处理失败' : '已完成'
    if (!useStoryboard) {
      // Parse 💡 suggestion block from reply text
      const { cleanText, suggestions } = parseSuggestions(agentMsg.replyText)
      agentMsg.replyText = cleanText
      agentMsg.suggestions = suggestions
    }
    addThinkingLog(agentMsg, agentMsg.error ? '流程结束：处理失败' : '流程结束：已完成')
    if (agentMsg.thinkingFlushTimer !== null && agentMsg.thinkingQueue.length === 0) {
      window.clearInterval(agentMsg.thinkingFlushTimer)
      agentMsg.thinkingFlushTimer = null
    }
    scrollToBottom()
  }
}

// ── SSE chat stream ────────────────────────────────────────────────────────
const streamChat = async (text: string, msg: ChatMessage) => {
  const token = authStore.token
  // Spec: specs/openapi/backend.yaml §/api/v1/poetry/chat
  const response = await fetchChatStream(text, sessionId.value, token)
  if (!response.ok || !response.body) throw new Error(`请求失败 (${response.status})`)

  const startedAt = Date.now()
  msg.streamStartedAt = startedAt
  msg.lastEventAt = startedAt
  msg.waitSeconds = 0
  msg.statusText = '正在理解你的问题…'
  msg.progressBucket = -1
  msg.currentPhase = 'understand'
  addThinkingLog(msg, '开始推理：正在理解你的输入')

  const updateWaitingStatus = () => {
    if (!msg.isStreaming) return

    const now = Date.now()
    const elapsedSec = Math.floor((now - msg.streamStartedAt) / 1000)
    const idleSec = Math.floor((now - msg.lastEventAt) / 1000)
    msg.waitSeconds = elapsedSec

    const bucket = Math.floor(elapsedSec / 6)
    const shouldEmitProgress = bucket > msg.progressBucket
    if (shouldEmitProgress) {
      msg.progressBucket = bucket
    }

    const runningTool = msg.tools.find((tool) => tool.status === 'running')
    if (runningTool?.name === 'search_poetry') {
      msg.statusText = `正在检索诗词语料…（${elapsedSec}s）`
      if (shouldEmitProgress && elapsedSec >= 6) {
        addThinkingLog(msg, `检索进展：仍在匹配诗词语料（已 ${elapsedSec}s）`)
      }
      return
    }
    if (runningTool?.name === 'visualize_poem') {
      msg.statusText = `正在生成意境插画…（${elapsedSec}s）`
      if (shouldEmitProgress && elapsedSec >= 6) {
        addThinkingLog(msg, `生图处理中：正在渲染细节（已 ${elapsedSec}s）`)
      }
      return
    }

    if (msg.replyText) {
      msg.statusText = `正在组织回复…（${elapsedSec}s）`
      return
    }

    if (idleSec >= 25) {
      msg.statusText = `响应较慢，仍在处理中…（${elapsedSec}s）`
      if (shouldEmitProgress) {
        addThinkingLog(msg, `进展更新：模型仍在处理中（已 ${elapsedSec}s）`)
      }
    } else if (elapsedSec >= 12) {
      msg.statusText = `正在深入思考并规划回答…（${elapsedSec}s）`
      if (shouldEmitProgress) {
        addThinkingLog(msg, `进展更新：正在规划回复结构（已 ${elapsedSec}s）`)
      }
    } else {
      msg.statusText = `正在思考中…（${elapsedSec}s）`
    }
  }

  updateWaitingStatus()
  const statusTimer = window.setInterval(updateWaitingStatus, 1000)

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) continue
        const raw = trimmed.slice(5).trim()
        if (raw === '[DONE]') continue
        let event: Record<string, any>
        try { event = JSON.parse(raw) } catch { continue }
        msg.lastEventAt = Date.now()
        handleEvent(event, msg)
        await nextTick()
        scrollToBottom()
      }
    }
  } finally {
    window.clearInterval(statusTimer)
  }
}

// ── SSE storyboard stream（分镜多图） ────────────────────────────────────────
const streamStoryboard = async (text: string, msg: ChatMessage) => {
  const token = authStore.token
  // Spec: specs/openapi/backend.yaml §/api/v1/poetry/storyboard
  const response = await fetchStoryboardStream(text, token)
  if (!response.ok || !response.body) throw new Error(`分镜请求失败 (${response.status})`)

  msg.streamStartedAt = Date.now()
  addThinkingLog(msg, '开始分镜生成：RAG 检索 → GLM 规划 → 逐张 CogView-4')

  // 启动计时器，每秒更新流式耗时（与 streamChat 保持一致）
  const storyboardTimer = window.setInterval(() => {
    if (!msg.isStreaming) { window.clearInterval(storyboardTimer); return }
    msg.waitSeconds = Math.floor((Date.now() - msg.streamStartedAt) / 1000)
    const done = msg.storyboardShots.length
    const total = msg.storyboardTotal || '?'
    if (done > 0 && msg.isStreaming) {
      msg.statusText = `已生成 ${done}/${total} 张，继续生成中…（${msg.waitSeconds}s）`
    } else if (msg.storyboardPlan && msg.isStreaming) {
      msg.statusText = `CogView-4 生图中…（${msg.waitSeconds}s）`
    }
  }, 1000)

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) continue
        const raw = trimmed.slice(5).trim()
        if (raw === '[DONE]') continue
        let ev: Record<string, any>
        try { ev = JSON.parse(raw) } catch { continue }

        const type: string = ev.type || ''

        if (type === 'progress') {
          const message: string = ev.message || ev.stage || ''
          if (message) {
            msg.statusText = message
            addThinkingLog(msg, message)
          }
        }
        else if (type === 'plan') {
          msg.storyboardPlan = {
            poem_title: ev.poem_title || '',
            author: ev.author || '',
            dynasty: ev.dynasty || '',
            global_style: ev.global_style || '',
          }
          msg.storyboardTotal = ev.total_shots || 0
          msg.hasGeneration = true
          msg.statusText = `分镜方案已确定：${msg.storyboardTotal} 张，CogView-4 生图中…`
          addThinkingLog(msg, `📋 分镜方案确定：共 ${msg.storyboardTotal} 张，《${ev.poem_title}》${ev.author}·${ev.dynasty}`)
        }
        else if (type === 'shot_done') {
          msg.storyboardShots.push({
            shot_id: ev.shot_id,
            shot_name: ev.shot_name || '',
            shot_type: ev.shot_type || '',
            poem_lines: ev.poem_lines || [],
            translation_excerpt: ev.translation_excerpt || '',
            camera_angle: ev.camera_angle || '',
            emotion: ev.emotion || '',
            positive_prompt: ev.positive_prompt || '',
            image_url: ev.image_url || null,
          })
          const cur = ev.current || msg.storyboardShots.length
          const tot = ev.total || msg.storyboardTotal
          msg.statusText = `第 ${cur}/${tot} 张生成完成`
          addThinkingLog(msg, `🖼 「${ev.shot_name}」第 ${cur}/${tot} 张完成`)
        }
        else if (type === 'shot_error') {
          if (ev.shot_id != null) {
            msg.storyboardShots.push({
              shot_id: ev.shot_id,
              shot_name: ev.shot_name || '未知分镜',
              shot_type: '',
              poem_lines: [],
              translation_excerpt: '',
              camera_angle: '',
              emotion: '',
              positive_prompt: '',
              image_url: null,
              error: ev.message || '生成失败',
            })
          }
          addThinkingLog(msg, `⚠️ 分镜失败：${ev.message || '未知错误'}`)
        }
        else if (type === 'done') {
          msg.statusText = `全部完成，共 ${msg.storyboardShots.length} 张`
          addThinkingLog(msg, `✅ 分镜生成完成：共 ${msg.storyboardShots.length} 张`)
        }

        await nextTick()
        scrollToBottom()
      }
    }
  } finally {
    window.clearInterval(storyboardTimer)
  }
}

// ── SSE event handler ──────────────────────────────────────────────────────
const handleEvent = (event: Record<string, any>, msg: ChatMessage) => {
  const type = event.type

  if (type === 'token') {
    msg.replyText += event.content || ''
    msg.statusText = '正在输出回复…'
    if (msg.currentPhase !== 'reply' && msg.currentPhase !== 'done') msg.currentPhase = 'reply'
  }
  else if (type === 'tool') {
    const name: string = event.name || ''
    const display = TOOL_DISPLAY[name] || name
    if (name === 'visualize_poem') {
      msg.hasGeneration = true
      msg.pipelineStage = 'rag'
      msg.statusText = '正在准备生图…'
      addThinkingLog(msg, '调用工具：开始意境插画生成')
      // 模拟 RAG → 提示词增强 → 生图 三阶段进度（单工具调用内部无法细粒度推送）
      setTimeout(() => { if (msg.isStreaming && msg.pipelineStage === 'rag') msg.pipelineStage = 'enhance' }, 3500)
      setTimeout(() => { if (msg.isStreaming && msg.pipelineStage === 'enhance') msg.pipelineStage = 'generate' }, 8000)
    } else if (name === 'search_poetry') {
      if (msg.pipelineStage === 'idle') msg.pipelineStage = 'rag'
      msg.statusText = '正在检索古诗词知识库…'
      msg.currentPhase = 'retrieve'
      addThinkingLog(msg, '调用工具：开始 RAG 检索')
    }
    // 同名工具合并计数，避免多次调用产生重复 badge
    const existing = msg.tools.find(t => t.name === name)
    if (existing) {
      existing.status = 'running'
      existing.count += 1
    } else {
      msg.tools.push({ name, display, status: 'running', count: 1 })
    }
  }
  else if (type === 'tool_end') {
    const name: string = event.name || ''
    const output: string = event.output || ''
    const entry = msg.tools.find(t => t.name === name)
    if (entry) entry.status = 'done'

    if (name === 'search_poetry') {
      const lines = output.split('\n').filter((l: string) => l.trim())
      msg.ragText = lines.slice(0, 4).join(' ').replace(/\*\*/g, '').trim().slice(0, 240)
      msg.statusText = '检索完成，正在整理答案…'
      msg.currentPhase = 'think'
      // 前端直接解析 output，填充结构化 ragResults
      const parsed = parseRagOutput(output)
      if (parsed.length > 0) {
        msg.ragResults = parsed
        msg.ragResultsExpanded = true
        const first = parsed[0]
        const simPct = (first.similarity * 100).toFixed(1)
        const label = parsed.length === 1 ? '精准匹配' : `语义检索 · ${parsed.length} 首`
        addThinkingLog(msg, `📚 RAG ${label}：《${first.title}》${first.author}·${first.dynasty}（相似度 ${simPct}%）`)
      } else {
        addThinkingLog(msg, 'RAG 检索完成：已找到相关诗词证据')
      }
    } else if (name === 'visualize_poem') {
      // 解析 IMAGE_URL: / POEM: / POSITIVE_PROMPT: / NEGATIVE_PROMPT:
      const imgMatch  = output.match(/IMAGE_URL:([^\n]+)/)
      const poemMatch = output.match(/POEM:([^\n]+)/)
      const posMatch  = output.match(/POSITIVE_PROMPT:([^\n]+)/)
      const negMatch  = output.match(/NEGATIVE_PROMPT:([^\n]+)/)
      if (imgMatch)  msg.imageUrl      = imgMatch[1].trim()
      if (poemMatch) msg.poemInfo      = poemMatch[1].trim()
      if (posMatch)  msg.enhancedPrompt = posMatch[1].trim()
      if (negMatch)  msg.negativePrompt = negMatch[1].trim()
      msg.pipelineStage = 'done'
      msg.statusText = '生图完成，正在组织回复…'
      addThinkingLog(msg, '意境插画生成完成：结果已返回')
    }
  }
  else if (type === 'node_progress') {
    const label: string = event.label || ''
    const node: string = event.node || ''
    const iteration: number = event.iteration ?? 0
    if (label) {
      // 区分图标：agent 节点用「思考」图标，tools 节点用「扳手」图标
      const prefix = node === 'agent'
        ? (iteration <= 1 ? '🧠' : '📝')
        : '🔧'
      addThinkingLog(msg, `${prefix} ${label}`)
      msg.statusText = label
    }
  }
  else if (type === 'rag_result') {
    const poems: RagPoem[] = event.poems || []
    // 仅当前端 tool_end 直解析未成功时才采用后端结果
    if (poems.length > 0 && msg.ragResults.length === 0) {
      msg.ragResults = poems.map(p => ({ ...p, expanded: false, mode: (event.mode === 'exact' ? 'exact' : 'semantic') as 'exact' | 'semantic' }))
      msg.ragResultsExpanded = true
      const first = poems[0]
      const simPct = (first.similarity * 100).toFixed(1)
      const modeLabel = event.mode === 'exact' ? '精准匹配' : `语义检索 · ${poems.length} 首`
      addThinkingLog(
        msg,
        `📚 RAG ${modeLabel}：《${first.title}》${first.author}·${first.dynasty}（相似度 ${simPct}%）`,
      )
    }
  }
  else if (type === 'done') {
    if (msg.hasGeneration && msg.pipelineStage !== 'done') msg.pipelineStage = 'done'
    msg.currentPhase = 'done'
    msg.statusText = '已完成'
    addThinkingLog(msg, '推理完成：正在收尾输出')
  }
  else if (type === 'error') {
    msg.error = event.content || '生成失败'
    if (msg.hasGeneration) msg.pipelineStage = 'failed'
    msg.statusText = '处理失败'
    addThinkingLog(msg, `流程失败：${msg.error}`)
  }
}

// ── 解析 💡 建议块 ─────────────────────────────────────────────────────────
const parseSuggestions = (text: string): { cleanText: string; suggestions: string[] } => {
  const idx = text.indexOf('💡')
  if (idx === -1) return { cleanText: text.trim(), suggestions: [] }
  // 找到 💡 之前的正文，去掉末尾的分隔线
  const beforeRaw = text.slice(0, idx).replace(/[\n\s]*[-—–─]{2,}[\n\s]*$/, '').trim()
  const afterBlock = text.slice(idx)
  const suggestions = afterBlock
    .split('\n')
    .filter(l => /^[-·•]\s/.test(l.trim()))
    .map(l => l.replace(/^[-·•\s]+/, '').replace(/\s*[→>]+\s*$/, '').trim())
    .filter(l => l.length >= 4 && l.length <= 40)
  return { cleanText: beforeRaw, suggestions }
}

// ── 点击建议 → 填入输入框并发送 ──────────────────────────────────────────────
const sendSuggestion = (text: string) => {
  if (isSending.value) return
  inputText.value = text
  nextTick(() => handleSend())
}

// ── Minimal markdown renderer ──────────────────────────────────────────────
const renderMarkdown = (text: string): string => {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // blockquote
    .replace(/^&gt;\s*(.+)$/gm, '<blockquote>$1</blockquote>')
    // bold / italic / code
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // hr (---, —— etc)
    .replace(/^[-—–]{3,}\s*$/gm, '<hr>')
    // unordered list items (-  ·  •)
    .replace(/^[-·•]\s+(.+)$/gm, '<li>$1</li>')
    // newlines (after hr/blockquote, single \n becomes <br>)
    .replace(/(?<!>)\n/g, '<br>')
}

// ── Utilities ──────────────────────────────────────────────────────────────
const scrollToBottom = async () => {
  await nextTick()
  if (messagesRef.value) messagesRef.value.scrollTo({ top: messagesRef.value.scrollHeight, behavior: 'smooth' })
}
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
</script>

<style scoped>
/* ── Layout ─────────────────────────────────────────────────────────────── */
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

/* ── Process Panel ─────────────────────────────────────────────── */
.process-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  overflow: hidden;
  animation: panelSlideIn 0.35s cubic-bezier(0.22, 1, 0.36, 1) both;
  transition: border-color 0.3s;
}
.process-panel.done {
  border-color: rgba(201, 168, 76, 0.2);
}
@keyframes panelSlideIn {
  from { opacity: 0; transform: translateY(10px) scale(0.99); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* 头部 */
.process-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
  gap: 10px;
}
.process-header:hover { background: rgba(255,255,255,0.028); }
.process-header-left {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  flex: 1;
}
.process-header-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

/* 动态圆环 */
.process-ring {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1.5px solid rgba(201,168,76,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(201,168,76,0.06);
  transition: border-color 0.3s, background 0.3s;
}
.process-ring.spinning {
  border-color: var(--accent);
  border-top-color: transparent;
  animation: spin 0.75s linear infinite;
}
.process-panel.done .process-ring {
  border-color: rgba(201,168,76,0.45);
  background: rgba(201,168,76,0.1);
}

/* 状态文字 */
.process-status-text {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  letter-spacing: 0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 阶段时间线 */
.process-phases {
  display: flex;
  align-items: center;
  padding: 0 14px 11px;
  gap: 0;
  overflow-x: auto;
  scrollbar-width: none;
}
.process-phases::-webkit-scrollbar { display: none; }
.phase-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  min-width: 56px;
}
.phase-icon-wrap {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1.5px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary);
  transition: all 0.25s ease;
}
.phase-step.done .phase-icon-wrap {
  border-color: rgba(201,168,76,0.5);
  background: rgba(201,168,76,0.1);
  color: var(--accent);
}
.phase-step.active .phase-icon-wrap {
  border-color: var(--accent);
  background: rgba(201,168,76,0.08);
  animation: phasePulse 1.8s ease-in-out infinite;
}
.phase-step.pending .phase-icon-wrap {
  opacity: 0.4;
}
@keyframes phasePulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(201,168,76,0); }
  50%       { box-shadow: 0 0 0 4px rgba(201,168,76,0.15); }
}
.phase-spinner {
  width: 10px;
  height: 10px;
  border: 1.5px solid var(--accent);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.65s linear infinite;
}
.phase-dot-pending {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--border-color);
}
.phase-label {
  font-size: 10.5px;
  letter-spacing: 0.02em;
  color: var(--text-muted);
  white-space: nowrap;
  transition: color 0.2s;
}
.phase-step.done .phase-label   { color: var(--accent); opacity: 0.85; }
.phase-step.active .phase-label { color: var(--text-secondary); }
.phase-connector {
  flex: 1;
  height: 1.5px;
  background: var(--border-color);
  min-width: 16px;
  max-width: 40px;
  margin-bottom: 18px;
  transition: background 0.4s ease;
}
.phase-connector.filled { background: rgba(201,168,76,0.4); }

/* 实时日志列表 */
.process-logs {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 0 14px 12px;
  border-top: 1px solid rgba(255,255,255,0.04);
  max-height: 240px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--border-color) transparent;
  padding-top: 9px;
}
.log-entry {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 11.5px;
  color: var(--text-muted);
  line-height: 1.55;
}
.log-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
  margin-top: 5px;
  opacity: 0.7;
}
.log-text {
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── TransitionGroup 逐条弹入动画 ────────────────────────────── */
.log-pop-enter-active {
  animation: logPopIn 0.32s cubic-bezier(0.22, 1, 0.36, 1) both;
}
@keyframes logPopIn {
  from {
    opacity: 0;
    transform: translateX(-8px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
}

/* tool badge 调用次数计数 */
.badge-count {
  font-size: 10px;
  opacity: 0.75;
  letter-spacing: 0;
}

/* ── RAG 检索结果面板 ─────────────────────────────────────────── */
.rag-results-panel {
  margin-top: 8px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: rgba(255,255,255,0.018);
  overflow: hidden;
}
.rag-panel-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  padding: 9px 14px;
  letter-spacing: 0.02em;
  transition: background 0.15s;
}
.rag-panel-header:hover {
  background: rgba(255,255,255,0.03);
  color: var(--text-primary);
}
.rag-panel-title {
  font-weight: 500;
}
.rag-count-badge {
  font-size: 10.5px;
  padding: 1px 7px;
  border-radius: 8px;
  background: var(--accent-subtle);
  color: var(--accent);
  border: 1px solid rgba(201,168,76,0.2);
  margin-left: 2px;
}
.rag-chevron {
  margin-left: auto;
  transition: transform 0.2s;
  opacity: 0.5;
}
.rag-chevron.open {
  transform: rotate(180deg);
}
.rag-poems-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0 10px 10px;
}
.rag-poem-card {
  background: rgba(255,255,255,0.022);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px 12px;
  transition: border-color 0.2s, background 0.2s;
  cursor: pointer;
  user-select: none;
}
.rag-poem-card:hover {
  border-color: rgba(201,168,76,0.3);
  background: rgba(255,255,255,0.035);
}
.rag-poem-card.expanded {
  border-color: rgba(201,168,76,0.25);
  background: rgba(201,168,76,0.04);
}
.rag-poem-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 0;
  flex-wrap: wrap;
}
.rag-card-chevron {
  margin-left: auto;
  color: var(--text-muted);
  opacity: 0.5;
  transition: transform 0.2s, opacity 0.2s;
  flex-shrink: 0;
}
.rag-card-chevron.open {
  transform: rotate(180deg);
  opacity: 0.9;
}
.rag-poem-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255,255,255,0.05);
}
.rag-poem-no-content {
  font-size: 11.5px;
  color: var(--text-muted);
  font-style: italic;
}
.rag-poem-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: 0.03em;
}
.rag-poem-meta {
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.8;
}

/* 匹配模式标签 精准 / 语义 */
.rag-mode-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 5px;
  letter-spacing: 0.04em;
  white-space: nowrap;
  border: 1px solid;
}
.rag-mode-tag.exact {
  color: #7dd3c0;
  background: rgba(125, 211, 192, 0.1);
  border-color: rgba(125, 211, 192, 0.25);
}
.rag-mode-tag.semantic {
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.1);
  border-color: rgba(167, 139, 250, 0.25);
}

/* 可信度进度条行 */
.rag-conf-row {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 6px;
}
.rag-conf-bar-wrap {
  flex: 1;
  height: 4px;
  border-radius: 999px;
  background: rgba(255,255,255,0.07);
  overflow: hidden;
}
.rag-conf-bar {
  height: 100%;
  border-radius: 999px;
  transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}
.rag-conf-bar.high { background: linear-gradient(90deg, #4ade80, #22c55e); }
.rag-conf-bar.mid  { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
.rag-conf-bar.low  { background: linear-gradient(90deg, #f87171, #ef4444); }

/* 百分比数字 */
.rag-sim-pct {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  white-space: nowrap;
  min-width: 38px;
  text-align: right;
}
.rag-sim-pct.high { color: #4ade80; }
.rag-sim-pct.mid  { color: #fbbf24; }
.rag-sim-pct.low  { color: #f87171; }

/* 可信度文字标签 */
.rag-conf-label {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 5px;
  white-space: nowrap;
  border: 1px solid;
}
.rag-conf-label.high { color: #4ade80; background: rgba(74,222,128,0.08); border-color: rgba(74,222,128,0.2); }
.rag-conf-label.mid  { color: #fbbf24; background: rgba(251,191,36,0.08); border-color: rgba(251,191,36,0.2); }
.rag-conf-label.low  { color: #f87171; background: rgba(248,113,113,0.08); border-color: rgba(248,113,113,0.2); }

/* 卡片左边框颜色根据可信度着色 */
.rag-poem-card.conf-high { border-left: 2px solid rgba(74,222,128,0.35); }
.rag-poem-card.conf-mid  { border-left: 2px solid rgba(251,191,36,0.35); }
.rag-poem-card.conf-low  { border-left: 2px solid rgba(248,113,113,0.35); }

.rag-poem-original {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: pre-wrap;
  line-height: 1.65;
  font-family: 'KaiTi', 'STKaiti', '楷体', serif;
  letter-spacing: 0.06em;
}
.rag-poem-trans {
  display: flex;
  gap: 6px;
  align-items: flex-start;
  font-size: 11.5px;
  color: var(--text-muted);
  line-height: 1.55;
  margin-top: 2px;
}
.rag-trans-label {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 5px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  flex-shrink: 0;
  align-self: flex-start;
  margin-top: 1px;
}

.tool-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 2px 9px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  background: var(--bg-tertiary);
  white-space: nowrap;
  transition: all 0.2s;
}
.tool-badge.done {
  border-color: rgba(201, 168, 76, 0.25);
  color: var(--accent);
  background: var(--accent-subtle);
}
.badge-spinner {
  width: 9px;
  height: 9px;
  border: 1.2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
.collapse-chevron {
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform 0.25s ease;
  transform: rotate(-90deg);
}
.collapse-chevron.open { transform: rotate(0deg); }

.thinking-body {
  padding: 14px 18px;
  max-height: 220px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--border-color) transparent;
  border-top: 1px solid var(--border-color);
}
.thinking-text {
  font-size: 12.5px;
  line-height: 1.9;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

/* Reply text */
.reply-text {
  font-size: 15px;
  line-height: 1.85;
  color: var(--text-primary);
  word-break: break-word;
}
.reply-text :deep(strong) { color: var(--accent); font-weight: 600; }
.reply-text :deep(code) {
  font-family: 'SF Mono', monospace;
  font-size: 13px;
  background: var(--bg-tertiary);
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid var(--border-color);
}
.reply-text :deep(blockquote) {
  margin: 8px 0;
  padding: 6px 14px;
  border-left: 3px solid var(--accent);
  background: var(--accent-subtle);
  border-radius: 0 6px 6px 0;
  font-family: 'Noto Serif SC', serif;
  font-size: 14.5px;
  color: var(--text-secondary);
  line-height: 1.8;
}
.reply-text :deep(li) {
  margin-left: 18px;
  list-style: disc;
  margin-bottom: 4px;
}
.reply-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 12px 0;
}

/* Pill tag (sample category badge) */
.pill-tag {
  display: inline-block;
  font-size: 10px;
  padding: 1px 7px;
  border-radius: 8px;
  background: var(--accent-subtle);
  border: 1px solid rgba(201, 168, 76, 0.22);
  color: var(--accent);
  letter-spacing: 0.04em;
  margin-right: 6px;
  vertical-align: middle;
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

/* Suggestion pills */
.suggestion-pills {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding-top: 4px;
  animation: fadeIn 0.35s ease both;
}
.sugg-label {
  font-size: 11.5px;
  color: var(--text-muted);
  letter-spacing: 0.04em;
  white-space: nowrap;
  flex-shrink: 0;
}
.sugg-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
  letter-spacing: 0.02em;
}
.sugg-btn:hover {
  border-color: var(--accent);
  background: var(--accent-subtle);
  color: var(--accent);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px var(--accent-glow);
}
.sugg-btn:active {
  transform: translateY(0);
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

/* ── 分镜多图展示 ─────────────────────────────────────────────── */
.storyboard-wrap {
  margin-top: 14px;
  width: 100%;
}
.storyboard-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.storyboard-title {
  font-size: 13px;
  font-family: 'Noto Serif SC', serif;
  color: var(--text-primary);
  font-weight: 500;
}
.storyboard-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-hover);
  padding: 2px 8px;
  border-radius: 10px;
}
.storyboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.shot-card {
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  overflow: hidden;
  transition: transform 0.2s, box-shadow 0.2s;
}
.shot-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.25);
}
.shot-card.shot-error {
  border-color: rgba(239,68,68,0.3);
  opacity: 0.75;
}
.shot-img-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  background: var(--bg-hover);
  overflow: hidden;
}
.shot-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.shot-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 12px;
  flex-direction: column;
  gap: 8px;
}
.shot-err-placeholder {
  color: rgba(239,68,68,0.6);
  font-size: 11px;
}
.shot-spinner {
  width: 22px;
  height: 22px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}
.shot-fullscreen {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  background: rgba(0,0,0,0.55);
  border-radius: 5px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255,255,255,0.8);
  opacity: 0;
  transition: opacity 0.15s;
  text-decoration: none;
}
.shot-img-wrap:hover .shot-fullscreen {
  opacity: 1;
}
.shot-meta {
  padding: 8px 10px 10px;
}
.shot-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.shot-lines {
  font-size: 11px;
  color: var(--accent);
  font-family: 'Noto Serif SC', serif;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}
.shot-emotion {
  font-size: 10.5px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>