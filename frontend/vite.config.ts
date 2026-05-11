import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 所有业务请求经 Backend（JWT 认证网关）
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true
      },
      // 静态图片资源仍由 AI Service 提供（生产可迁至 CDN / OSS）
      '/statics': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      // 模型配置切换直接调用 AI Service（仅 /ai/api/v1/config 路径）
      '/ai/api/v1/config': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
      // 注：/ai/* 其余路径不直连，前端不直接调用 AI Service 业务接口（constitution §3.1）
    }
  }
});
