import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

/** Preview uses VITE_PREVIEW_BASE; publish build uses VITE_EXPORT_BASE. */
function resolveViteBase(mode: string, env: Record<string, string>): string {
  if (mode === 'production') {
    return env.VITE_EXPORT_BASE || '/'
  }
  return env.VITE_PREVIEW_BASE || '/'
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    base: resolveViteBase(mode, env),
    define: {
      'import.meta.env.VITE_AUTH_PROVIDER_URL': JSON.stringify('{{AUTH_PROVIDER_URL}}'),
      'import.meta.env.VITE_AUTH_STORAGE_KEY': JSON.stringify('{{AUTH_STORAGE_KEY}}'),
      'import.meta.env.VITE_AUTH_USE_IFRAME': JSON.stringify('{{AUTH_USE_IFRAME}}'),
    },
  }
})
