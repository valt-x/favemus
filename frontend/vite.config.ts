import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8091',
      '/chat': 'http://127.0.0.1:8091',
      '/auth': 'http://127.0.0.1:8091',
      '/harness': 'http://127.0.0.1:8091',
      '/saas': 'http://127.0.0.1:8091',
      '/telegram': 'http://127.0.0.1:8091',
      '/whatsapp': 'http://127.0.0.1:8091',
      '/static': 'http://127.0.0.1:8091',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
