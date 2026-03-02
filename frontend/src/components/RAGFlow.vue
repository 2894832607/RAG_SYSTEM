<template>
  <section class="rag-shell">
    <el-card class="input-card">
      <div class="section-header">
        <h2>Poem Input</h2>
        <p>用途: 让系统理解你的诗意，后端会附带 RAG 强化提示词来驱动 Stable Diffusion。</p>
      </div>
      <el-input
        v-model="poem"
        type="textarea"
        placeholder="例：孤帆远影碧空尽，唯见长江天际流"
        :rows="5"
      ></el-input>
      <el-button type="primary" class="submit" :loading="submitting" @click="submit">
        Submit for Visualization
      </el-button>
    </el-card>

    <div class="panels">
      <el-card class="panel">
        <h3>Task Timeline</h3>
        <div v-if="tasks.length === 0" class="empty-state">等待输入后端开始生成</div>
        <el-timeline v-else>
          <el-timeline-item
            v-for="task in tasks"
            :key="task.taskId"
            :timestamp="task.status"
            :color="task.status === 'COMPLETED' ? 'success' : 'warning'"
          >
            <template #content>
              <strong>{{ task.taskId }}</strong>
              <p>{{ task.retrievedText || '尚未检索结果' }}</p>
              <small>{{ task.enhancedPrompt }}</small>
            </template>
          </el-timeline-item>
        </el-timeline>
      </el-card>

      <el-card class="panel">
        <h3>Gallery Preview</h3>
        <div class="gallery">
          <figure v-for="task in tasks" :key="task.taskId" class="preview">
            <img :src="task.resultImageUrl || placeholder" alt="生成预览" />
            <figcaption>
              <p>Status: {{ task.status }}</p>
              <p>Prompt: {{ task.enhancedPrompt || '等待生成' }}</p>
            </figcaption>
          </figure>
          <div v-if="tasks.length === 0" class="empty-state-small">等待生成结果</div>
        </div>
      </el-card>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue';
import { ElMessage } from 'element-plus';
import { submitPoemTask, fetchTaskStatus } from '../services/api';

type TaskItem = {
  taskId: string;
  status: string;
  retrievedText: string;
  enhancedPrompt: string;
  resultImageUrl: string;
};

const poem = ref('');
const submitting = ref(false);
const tasks = ref<TaskItem[]>([]);
const pollingHandles = new Map<string, number>();
const placeholder = 'https://via.placeholder.com/320x200?text=Awaiting+render';

const submit = async () => {
  if (!poem.value.trim()) {
    ElMessage.warning('请输入一段诗句来驱动可视化。');
    return;
  }
  submitting.value = true;
  try {
    const response = await submitPoemTask(poem.value.trim());
    const taskId = response.data?.data?.taskId ?? `task-${Date.now()}`;
    tasks.value = [
      {
        taskId,
        status: 'PENDING',
        retrievedText: '',
        enhancedPrompt: '',
        resultImageUrl: ''
      },
      ...(tasks.value ?? [])
    ];
    startPolling(taskId);
    ElMessage.success('任务已提交，正在准备检索层数据。');
  } catch (error) {
    ElMessage.error('任务提交失败，请检查网络或后端服务。');
  } finally {
    submitting.value = false;
  }
};

const startPolling = (taskId: string) => {
  if (pollingHandles.has(taskId)) {
    return;
  }
  const handle = window.setInterval(async () => {
    try {
      const statusResponse = await fetchTaskStatus(taskId);
      const payload = statusResponse.data?.data;
      const statusValue = payload?.taskStatus ?? payload?.task_status;
      const resolvedStatus = statusValue === 1 || statusValue === 'COMPLETED' ? 'COMPLETED' : statusValue === 2 || statusValue === 'FAILED' ? 'FAILED' : 'RUNNING';
      const taskIndex = (tasks.value ?? []).findIndex((t) => t.taskId === taskId);
      if (taskIndex === -1) {
        return;
      }
      const updatedTask = {
        ...tasks.value![taskIndex],
        status: resolvedStatus,
        retrievedText: payload?.retrievedText ?? payload?.retrieved_text ?? '',
        enhancedPrompt: payload?.enhancedPrompt ?? payload?.enhanced_prompt ?? '',
        resultImageUrl: payload?.resultImageUrl ?? payload?.result_image_url ?? ''
      };
      tasks.value = [...tasks.value!];
      tasks.value[taskIndex] = updatedTask;
      if (resolvedStatus === 'COMPLETED' || resolvedStatus === 'FAILED') {
        clearInterval(handle);
        pollingHandles.delete(taskId);
      }
    } catch (error) {
      // ignore transient polling failures
    }
  }, 3000);
  pollingHandles.set(taskId, handle);
};

onBeforeUnmount(() => {
  pollingHandles.forEach((handle) => window.clearInterval(handle));
});
</script>

<style scoped>
.rag-shell {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.input-card {
  background: rgba(255, 255, 255, 0.85);
}
.section-header h2 {
  margin: 0;
}
.submit {
  margin-top: 1rem;
}
.panels {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.5rem;
}
.panel {
  min-height: 280px;
  background: rgba(255, 255, 255, 0.9);
}
.gallery {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}
.preview {
  border-radius: 1rem;
  overflow: hidden;
  background: #fff;
  display: flex;
  flex-direction: column;
}
.preview img {
  width: 100%;
  height: 120px;
  object-fit: cover;
}
.preview figcaption {
  padding: 0.75rem;
  font-size: 0.85rem;
  background: #f6f5f2;
}
.empty-state,
.empty-state-small {
  color: #8a7f7a;
  font-style: italic;
  padding: 2rem 0;
}
.empty-state-small {
  text-align: center;
}
</style>
