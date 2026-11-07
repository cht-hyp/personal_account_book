import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发模式：Vite 提供页面，/api 代理到本地 Flask（保留 /api 前缀，前端代码不写死后端域名）。
// 代理目标可用环境变量覆盖，便于 survey 时换端口：VITE_API_PROXY_TARGET=http://127.0.0.1:5055 npm run dev
const proxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:5000'

export default defineConfig({
  plugins: [vue()],
  // 构建产物由 Flask 在站点根路径提供；用相对基址，避免部署在子路径时资源 404
  base: './',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
})
