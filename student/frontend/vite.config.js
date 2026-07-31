import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        timeout: 120000
      }
    },
    watch: {
      // 避免 Windows 下不必要的文件变动触发 HMR
      ignored: ['**/node_modules/**', '**/dist/**', '**/__pycache__/**', '**/*.db', '**/*.db-journal']
    }
  }
})
