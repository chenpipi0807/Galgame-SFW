import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 15927,
    proxy: {
      '/api': {
        target: 'http://localhost:17832',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://localhost:17832',
        changeOrigin: true,
      },
    },
  },
})
