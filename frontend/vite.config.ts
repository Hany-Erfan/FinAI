import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: ['frontend', 'localhost', '127.0.0.1', 'app.staging.agentixbuddy.com'],
    proxy: {
      '/login': {
        target: 'http://host-agent:8000',
        changeOrigin: true,
      },
      '/chat': {
        target: 'http://host-agent:8000',
        changeOrigin: true,
      },
      '/currentUser': {
        target: 'http://host-agent:8000',
        changeOrigin: true,
      },
      '/logout': {
        target: 'http://host-agent:8000',
        changeOrigin: true,
      },
      '/admin': {
        target: 'http://host-agent:8000',
        changeOrigin: true,
      },
      '/vector_db_service': {
        target: 'http://vector-db-service:8004',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/vector_db_service/, ''),
      },
      '/guardrails_service': {
        target: 'http://guardrails-service:8005',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/guardrails_service/, ''),
      },
    },
  },
})