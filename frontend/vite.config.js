import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 默认对齐 README 的后端端口；E2E 脚本可用环境变量切到托管后端。
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000'
const devPort = Number(process.env.VITE_DEV_PORT || 3000)
const strictPort = process.env.VITE_STRICT_PORT === 'true'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: devPort,
    strictPort,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/element-plus/')) {
            return 'element-plus'
          }

          return undefined
        },
      },
    },
  },
})
