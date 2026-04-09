import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    base: env.VITE_BASE ?? '/api/preview/{{PROJECT_ID}}/proxy/',
    define: {
      'import.meta.env.VITE_AUTH_PROVIDER_URL': JSON.stringify('{{AUTH_PROVIDER_URL}}'),
      'import.meta.env.VITE_AUTH_STORAGE_KEY': JSON.stringify('{{AUTH_STORAGE_KEY}}'),
      'import.meta.env.VITE_AUTH_USE_IFRAME': JSON.stringify('{{AUTH_USE_IFRAME}}'),
    },
  }
})
