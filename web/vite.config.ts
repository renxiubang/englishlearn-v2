import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { mockServerPlugin } from './mock/plugin'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue(), mockServerPlugin()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      // 后端已实现接口（contacts/chats/assist）与音频静态资源；mock 中间件未命中的请求落到这里
      '/api': { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/audio': { target: 'http://127.0.0.1:8080', changeOrigin: true },
    },
  },
})
