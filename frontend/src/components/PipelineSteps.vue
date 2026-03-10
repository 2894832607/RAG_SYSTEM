<template>
  <div class="pipeline">
    <div class="pipeline-track">
      <div
        v-for="(step, i) in steps"
        :key="step.key"
        class="pipeline-step"
        :class="stepClass(i)"
      >
        <div class="step-indicator">
          <!-- Completed -->
          <svg v-if="isCompleted(i)" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2.5">
            <polyline points="20,6 9,17 4,12" />
          </svg>
          <!-- Running spinner -->
          <div v-else-if="isActive(i)" class="step-spinner"></div>
          <!-- Failed X -->
          <svg v-else-if="isFailed(i)" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="2.5">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
          <!-- Pending dot -->
          <div v-else class="step-dot"></div>
        </div>
        <span class="step-label">{{ step.label }}</span>
        <!-- Connector line -->
        <div v-if="i < steps.length - 1" class="step-connector" :class="{ filled: isCompleted(i) }"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type PipelineStage = 'idle' | 'rag' | 'enhance' | 'generate' | 'done' | 'failed'

const props = defineProps<{
  pipelineStage: PipelineStage
  isStreaming: boolean
}>()

const steps = [
  { key: 'parse',    label: '诗句解析' },
  { key: 'rag',      label: 'RAG 检索' },
  { key: 'enhance',  label: '提示词增强' },
  { key: 'generate', label: '图像生成' },
]

/**
 * 根据 pipelineStage 判断当前激活步骤的索引（-1 = 失败）
 * idle       → 0  (step 0 active — parsing started)
 * rag        → 1  (RAG retrieval active)
 * enhance    → 2  (prompt enhancement active)
 * generate   → 3  (image generation active)
 * done       → 4  (all complete)
 * failed     → -1
 */
const activeIndex = computed<number>(() => {
  switch (props.pipelineStage) {
    case 'idle':     return 0
    case 'rag':      return 1
    case 'enhance':  return 2
    case 'generate': return 3
    case 'done':     return 4
    case 'failed':   return -1
    default:         return 0
  }
})

const isCompleted = (i: number) => activeIndex.value > i && props.pipelineStage !== 'failed'
const isActive    = (i: number) => activeIndex.value === i && props.isStreaming && props.pipelineStage !== 'failed' && props.pipelineStage !== 'done'
const isFailed    = (i: number) => props.pipelineStage === 'failed' && i === activeIndex.value

const stepClass = (i: number) => ({
  completed: isCompleted(i),
  active:    isActive(i),
  failed:    isFailed(i),
})
</script>

<style scoped>
.pipeline {
  padding: 4px 0 2px;
}
.pipeline-track {
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 0;
}
.pipeline-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  flex: 1;
  max-width: 120px;
}
.step-indicator {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  border: 1.5px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  position: relative;
  z-index: 2;
}
.pipeline-step.completed .step-indicator {
  background: var(--accent-subtle);
  border-color: var(--accent);
}
.pipeline-step.active .step-indicator {
  border-color: var(--accent);
  box-shadow: 0 0 0 4px var(--accent-glow);
}
.pipeline-step.failed .step-indicator {
  border-color: var(--danger);
  background: rgba(192, 57, 43, 0.1);
}
.step-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-muted);
}
.step-spinner {
  width: 14px;
  height: 14px;
  border: 1.5px solid var(--accent);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.step-label {
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--text-muted);
  white-space: nowrap;
  transition: color 0.2s;
  letter-spacing: 0.02em;
}
.pipeline-step.completed .step-label,
.pipeline-step.active .step-label {
  color: var(--text-secondary);
}
/* Connector lines */
.step-connector {
  position: absolute;
  top: 15px;
  left: calc(50% + 18px);
  width: calc(100% - 36px);
  height: 1.5px;
  background: var(--border-color);
  z-index: 1;
  transition: background 0.4s;
}
.step-connector.filled {
  background: var(--accent);
}
</style>


<style scoped>
.pipeline {
  padding: 4px 0 2px;
}
.pipeline-track {
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 0;
}
.pipeline-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  flex: 1;
  max-width: 120px;
}
.step-indicator {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  border: 1.5px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  position: relative;
  z-index: 2;
}
.pipeline-step.completed .step-indicator {
  background: var(--accent-subtle);
  border-color: var(--accent);
}
.pipeline-step.active .step-indicator {
  border-color: var(--accent);
  box-shadow: 0 0 0 4px var(--accent-glow);
}
.pipeline-step.failed .step-indicator {
  border-color: var(--danger);
  background: rgba(192, 57, 43, 0.1);
}
.step-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-muted);
}
.step-spinner {
  width: 14px;
  height: 14px;
  border: 1.5px solid var(--accent);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.step-label {
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--text-muted);
  white-space: nowrap;
  transition: color 0.2s;
  letter-spacing: 0.02em;
}
.pipeline-step.completed .step-label,
.pipeline-step.active .step-label {
  color: var(--text-secondary);
}

/* Connector lines */
.step-connector {
  position: absolute;
  top: 15px;
  left: calc(50% + 18px);
  width: calc(100% - 36px);
  height: 1.5px;
  background: var(--border-color);
  z-index: 1;
  transition: background 0.4s;
}
.step-connector.filled {
  background: var(--accent);
}
</style>
