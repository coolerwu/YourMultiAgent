import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// 编译产物输出到 server/web/，由 FastAPI 托管
export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: path.resolve(__dirname, '../server/web'),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // 确定性命名，便于缓存
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name].[ext]',
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8080',
    },
  },
})
