<template>
  <div class="pipeline" v-if="visible">
    <div class="pipeline-track">
      <div
        v-for="(step, i) in steps"
        :key="step.key"
        class="pipeline-step"
        :class="stepClass(i)"
      >
        <div class="step-indicator">
          <!-- Completed -->
          <svg v-if="isCompleted(i)" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2.5">
            <polyline points="20,6 9,17 4,12" />
          </svg>
          <!-- Running spinner -->
          <div v-else-if="isActive(i)" class="step-spinner"></div>
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

const props = defineProps<{
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  retrievedText: string
  enhancedPrompt: string
  resultImageUrl: string
}>()

const visible = computed(() => props.status !== undefined)

const steps = [
  { key: 'parse', label: '诗句解析' },
  { key: 'retrieve', label: 'RAG 检索' },
  { key: 'enhance', label: '提示词增强' },
  { key: 'generate', label: '图像生成' }
]

/** 根据实际数据判断当前到达了哪一步 */
const currentStep = computed(() => {
  if (props.status === 'COMPLETED') return 4
  if (props.status === 'FAILED') return -1
  if (props.resultImageUrl) return 4
  if (props.enhancedPrompt) return 3
  if (props.retrievedText) return 2
  if (props.status === 'RUNNING') return 1
  return 0
})

const isCompleted = (i: number) => i < currentStep.value
const isActive = (i: number) => i === currentStep.value && props.status !== 'COMPLETED' && props.status !== 'FAILED'
const stepClass = (i: number) => ({
  completed: isCompleted(i),
  active: isActive(i),
  failed: props.status === 'FAILED' && i === currentStep.value
})
</script>

<style scoped>
.pipeline {
  padding: 24px 0 8px;
}
.pipeline-track {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 0;
}
.pipeline-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  flex: 1;
  max-width: 160px;
}
.step-indicator {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  border: 2px solid var(--border-color);
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
  background: rgba(239, 68, 68, 0.1);
}
.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
}
.step-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--accent);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.step-label {
  margin-top: 10px;
  font-size: 12.5px;
  color: var(--text-muted);
  white-space: nowrap;
  transition: color 0.2s;
}
.pipeline-step.completed .step-label,
.pipeline-step.active .step-label {
  color: var(--text-primary);
}

/* Connector lines between steps */
.step-connector {
  position: absolute;
  top: 18px;
  left: calc(50% + 22px);
  width: calc(100% - 44px);
  height: 2px;
  background: var(--border-color);
  z-index: 1;
  transition: background 0.3s;
}
.step-connector.filled {
  background: var(--accent);
}
</style>
