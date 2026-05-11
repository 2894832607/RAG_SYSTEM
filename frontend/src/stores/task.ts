import { defineStore } from 'pinia'
import { ref } from 'vue'
import { submitPoemTask, fetchTaskStatus } from '../services/api'

export interface TaskItem {
  taskId: string
  originalPoem: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  retrievedText: string
  enhancedPrompt: string
  resultImageUrl: string           // 主图（第一张，向后兼容）
  resultImageUrls: string[]        // 所有生成的图片 URLs（新字段）
  errorMessage: string
  createdAt: number
}

export const useTaskStore = defineStore('task', () => {
  const tasks = ref<TaskItem[]>([])
  const currentTask = ref<TaskItem | null>(null)
  const submitting = ref(false)
  const pollingHandles = new Map<string, number>()

  /** 提交诗句生成任务 */
  const addTask = async (poemText: string) => {
    submitting.value = true
    try {
      const response = await submitPoemTask(poemText)
      const taskId = response.data?.data?.taskId
      if (!taskId) throw new Error('未获取到 taskId')

      const task: TaskItem = {
        taskId,
        originalPoem: poemText,
        status: 'PENDING',
        retrievedText: '',
        enhancedPrompt: '',
        resultImageUrl: '',
        resultImageUrls: [],
        errorMessage: '',
        createdAt: Date.now()
      }
      tasks.value.unshift(task)
      currentTask.value = task
      startPolling(taskId)
      return task
    } finally {
      submitting.value = false
    }
  }

  /** 轮询任务状态 */
  const startPolling = (taskId: string) => {
    if (pollingHandles.has(taskId)) return

    const handle = window.setInterval(async () => {
      try {
        const res = await fetchTaskStatus(taskId)
        const payload = res.data?.data
        const statusValue = payload?.taskStatus
        const resolvedStatus =
          statusValue === 1
            ? 'COMPLETED'
            : statusValue === 2
              ? 'FAILED'
              : 'RUNNING'

        const idx = tasks.value.findIndex((t) => t.taskId === taskId)
        if (idx === -1) return

        // 解析多张图片 URLs
        let imageUrls: string[] = []
        if (payload?.resultImageUrls) {
          try {
            // 如果是字符串，尝试解析 JSON
            if (typeof payload.resultImageUrls === 'string') {
              imageUrls = JSON.parse(payload.resultImageUrls)
            } else if (Array.isArray(payload.resultImageUrls)) {
              imageUrls = payload.resultImageUrls
            }
          } catch (e) {
            // 解析失败则忽略
          }
        }
        // 如果没有 resultImageUrls，但有 resultImageUrl，将其作为唯一图片
        if (imageUrls.length === 0 && payload?.resultImageUrl) {
          imageUrls = [payload.resultImageUrl]
        }

        tasks.value[idx] = {
          ...tasks.value[idx],
          status: resolvedStatus,
          retrievedText: payload?.retrievedText ?? '',
          enhancedPrompt: payload?.enhancedPrompt ?? '',
          resultImageUrl: payload?.resultImageUrl ?? '',
          resultImageUrls: imageUrls,
          errorMessage: payload?.errorMessage ?? ''
        }

        if (currentTask.value?.taskId === taskId) {
          currentTask.value = { ...tasks.value[idx] }
        }

        if (resolvedStatus === 'COMPLETED' || resolvedStatus === 'FAILED') {
          clearInterval(handle)
          pollingHandles.delete(taskId)
        }
      } catch {
        // 忽略临时轮询失败
      }
    }, 3000)
    pollingHandles.set(taskId, handle)
  }

  /** 选中某个任务 */
  const selectTask = (taskId: string) => {
    const task = tasks.value.find((t) => t.taskId === taskId)
    if (task) currentTask.value = { ...task }
  }

  /** 清理所有轮询 */
  const clearPolling = () => {
    pollingHandles.forEach((h) => clearInterval(h))
    pollingHandles.clear()
  }

  /** 清除当前选中任务（回到欢迎页） */
  const clearCurrentTask = () => {
    currentTask.value = null
  }

  return { tasks, currentTask, submitting, addTask, selectTask, clearPolling, clearCurrentTask }
})
