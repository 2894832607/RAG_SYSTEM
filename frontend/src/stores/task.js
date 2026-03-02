import { defineStore } from 'pinia';
import { ref } from 'vue';
import { submitPoemTask, fetchTaskStatus } from '../services/api';
export const useTaskStore = defineStore('task', () => {
    const tasks = ref([]);
    const currentTask = ref(null);
    const submitting = ref(false);
    const pollingHandles = new Map();
    /** 提交诗句生成任务 */
    const addTask = async (poemText) => {
        submitting.value = true;
        try {
            const response = await submitPoemTask(poemText);
            const taskId = response.data?.data?.taskId;
            if (!taskId)
                throw new Error('未获取到 taskId');
            const task = {
                taskId,
                originalPoem: poemText,
                status: 'PENDING',
                retrievedText: '',
                enhancedPrompt: '',
                resultImageUrl: '',
                errorMessage: '',
                createdAt: Date.now()
            };
            tasks.value.unshift(task);
            currentTask.value = task;
            startPolling(taskId);
            return task;
        }
        finally {
            submitting.value = false;
        }
    };
    /** 轮询任务状态 */
    const startPolling = (taskId) => {
        if (pollingHandles.has(taskId))
            return;
        const handle = window.setInterval(async () => {
            try {
                const res = await fetchTaskStatus(taskId);
                const payload = res.data?.data;
                const statusValue = payload?.taskStatus ?? payload?.task_status;
                const resolvedStatus = statusValue === 1 || statusValue === 'COMPLETED'
                    ? 'COMPLETED'
                    : statusValue === 2 || statusValue === 'FAILED'
                        ? 'FAILED'
                        : 'RUNNING';
                const idx = tasks.value.findIndex((t) => t.taskId === taskId);
                if (idx === -1)
                    return;
                tasks.value[idx] = {
                    ...tasks.value[idx],
                    status: resolvedStatus,
                    retrievedText: payload?.retrievedText ?? payload?.retrieved_text ?? '',
                    enhancedPrompt: payload?.enhancedPrompt ?? payload?.enhanced_prompt ?? '',
                    resultImageUrl: payload?.resultImageUrl ?? payload?.result_image_url ?? '',
                    errorMessage: payload?.errorMessage ?? payload?.error_message ?? ''
                };
                if (currentTask.value?.taskId === taskId) {
                    currentTask.value = { ...tasks.value[idx] };
                }
                if (resolvedStatus === 'COMPLETED' || resolvedStatus === 'FAILED') {
                    clearInterval(handle);
                    pollingHandles.delete(taskId);
                }
            }
            catch {
                // 忽略临时轮询失败
            }
        }, 3000);
        pollingHandles.set(taskId, handle);
    };
    /** 选中某个任务 */
    const selectTask = (taskId) => {
        const task = tasks.value.find((t) => t.taskId === taskId);
        if (task)
            currentTask.value = { ...task };
    };
    /** 清理所有轮询 */
    const clearPolling = () => {
        pollingHandles.forEach((h) => clearInterval(h));
        pollingHandles.clear();
    };
    return { tasks, currentTask, submitting, addTask, selectTask, clearPolling };
});
//# sourceMappingURL=task.js.map