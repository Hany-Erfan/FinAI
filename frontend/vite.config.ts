import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Allow external connections
    port: 5173,
    strictPort: true,
    allowedHosts: ['frontend', 'localhost', '127.0.0.1', 'app.staging.agentixbuddy.com'],
    hmr: false, // Disable HMR WebSocket in deployed environment
  },
})
