import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 所有业务请求经 Backend（JWT 认证网关）
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true
      },
      // 静态图片资源仍由 AI Service 提供（生产可迁至 CDN / OSS）
      '/statics': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
      // 注：/ai/* 直连通道已移除。前端不直接调用 AI Service（constitution §3.1）
    }
  }
});
