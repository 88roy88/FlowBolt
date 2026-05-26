import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const base = env.VITE_PUBLIC_BASE_PATH || '/'
  return {
    plugins: [react()],
    base,
    define: {
      'import.meta.env.VITE_AUTH_PROVIDER_URL': JSON.stringify('{{AUTH_PROVIDER_URL}}'),
      'import.meta.env.VITE_AUTH_STORAGE_KEY': JSON.stringify('{{AUTH_STORAGE_KEY}}'),
      'import.meta.env.VITE_AUTH_USE_IFRAME': JSON.stringify('{{AUTH_USE_IFRAME}}'),
    },
  }
})
