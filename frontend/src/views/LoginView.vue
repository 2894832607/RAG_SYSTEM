<template>
  <div class="login-page">
    <div class="login-card">
      <h1>{{ isRegisterMode ? '注册 Poetry RAG 账号' : '登录 Poetry RAG' }}</h1>
      <p class="sub">{{ isRegisterMode ? '创建账号后即可进入生成工作台' : '使用系统账号登录后继续使用生成工作台' }}</p>

      <div class="mode-switch">
        <button :class="{ active: !isRegisterMode }" @click="switchMode(false)">登录</button>
        <button :class="{ active: isRegisterMode }" @click="switchMode(true)">注册</button>
      </div>

      <div class="form-group" v-if="isRegisterMode">
        <label>昵称</label>
        <input v-model="nickname" placeholder="请输入昵称" @keyup.enter="handleSubmit" />
      </div>

      <div class="form-group">
        <label>用户名</label>
        <input v-model="username" placeholder="请输入用户名，如 admin" @keyup.enter="handleSubmit" />
      </div>

      <div class="form-group">
        <label>密码</label>
        <input v-model="password" type="password" placeholder="请输入密码" @keyup.enter="handleSubmit" />
      </div>

      <div class="form-group" v-if="isRegisterMode">
        <label>确认密码</label>
        <input v-model="confirmPassword" type="password" placeholder="请再次输入密码" @keyup.enter="handleSubmit" />
      </div>

      <button class="login-btn" :disabled="loading" @click="handleSubmit">
        {{ loading ? (isRegisterMode ? '注册中...' : '登录中...') : (isRegisterMode ? '注册并进入' : '登录') }}
      </button>

      <div class="tips" v-if="!isRegisterMode">
        测试账号：admin / 123456
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { AxiosError } from 'axios'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const isRegisterMode = ref(false)
const nickname = ref('')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)

const switchMode = (registerMode: boolean) => {
  isRegisterMode.value = registerMode
  confirmPassword.value = ''
}

const getErrorMessage = (error: unknown): string => {
  const axiosError = error as AxiosError<{ message?: string }>
  return axiosError.response?.data?.message || '请求失败，请稍后重试'
}

const handleSubmit = async () => {
  const trimmedUsername = username.value.trim()
  const trimmedNickname = nickname.value.trim()

  if (!username.value.trim() || !password.value.trim()) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (isRegisterMode.value && !trimmedNickname) {
    ElMessage.warning('请输入昵称')
    return
  }
  if (isRegisterMode.value && password.value !== confirmPassword.value) {
    ElMessage.warning('两次密码输入不一致')
    return
  }

  loading.value = true
  try {
    if (isRegisterMode.value) {
      await authStore.register(trimmedUsername, password.value, trimmedNickname)
      ElMessage.success('注册成功，已自动登录')
    } else {
      await authStore.login(trimmedUsername, password.value)
      ElMessage.success('登录成功')
    }
    const redirect = typeof route.query.redirect === 'string' ? decodeURIComponent(route.query.redirect) : '/'
    router.push(redirect || '/')
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-main);
  padding: 24px;
}
.login-card {
  width: 100%;
  max-width: 420px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 28px;
}
h1 {
  margin: 0;
  color: var(--text-primary);
  font-size: 24px;
}
.sub {
  margin: 8px 0 20px;
  color: var(--text-secondary);
  font-size: 13px;
}
.mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 14px;
}
.mode-switch button {
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border-radius: 10px;
  padding: 8px 0;
  cursor: pointer;
}
.mode-switch button.active {
  border-color: var(--accent);
  color: var(--text-primary);
  background: var(--accent-subtle);
}
.form-group {
  margin-bottom: 14px;
}
label {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
  margin-bottom: 6px;
}
input {
  width: 100%;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  border-radius: 10px;
  padding: 10px 12px;
  outline: none;
}
input:focus {
  border-color: var(--accent);
}
.login-btn {
  width: 100%;
  margin-top: 6px;
  border: none;
  border-radius: 10px;
  padding: 11px 12px;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
}
.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.tips {
  margin-top: 14px;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
