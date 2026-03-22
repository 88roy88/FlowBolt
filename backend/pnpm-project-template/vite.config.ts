import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const base = env.VITE_BASE ?? '/api/preview/{{SESSION_ID}}/proxy/'
  return {
    plugins: [react()],
    base,
    server: {
      hmr: {
        // HMR WebSocket goes through the same proxy path as the page,
        // so it works behind reverse proxies / ngrok without direct port access.
        path: `${base}`,
      },
    },
  }
})
