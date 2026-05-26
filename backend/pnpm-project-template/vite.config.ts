import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

const PKG_PATH = path.resolve(__dirname, 'package.json')

function readPkg(): { version: string; [key: string]: unknown } {
  return JSON.parse(fs.readFileSync(PKG_PATH, 'utf-8'))
}

function bumpPatchVersion(current: string): string {
  const match = /^(\d+)\.(\d+)\.(\d+)/.exec(current)
  if (!match) return '0.0.1'
  const patch = Number(match[3]) + 1
  return `${match[1]}.${match[2]}.${patch}`
}

function resolveAppVersion(command: string): string {
  const pkg = readPkg()
  if (command !== 'build') return pkg.version

  const version = bumpPatchVersion(pkg.version)
  fs.writeFileSync(PKG_PATH, `${JSON.stringify({ ...pkg, version }, null, 2)}\n`)
  return version
}

const BASE_TAG_RE = /<base\s+href=["'][^"']*["']\s*\/?>/i

function syncIndexBaseHref(appBase: string): void {
  if (!appBase) return
  const indexPath = path.resolve(__dirname, 'index.html')
  let html = fs.readFileSync(indexPath, 'utf-8')
  const tag = `<base href="${appBase}" />`
  html = BASE_TAG_RE.test(html)
    ? html.replace(BASE_TAG_RE, tag)
    : html.replace('<head>', `<head>\n    ${tag}`)
  fs.writeFileSync(indexPath, html)
}

function syncIndexBasePlugin(appBase: string): Plugin {
  return {
    name: 'flow44-sync-index-base',
    config() {
      syncIndexBaseHref(appBase)
    },
  }
}

/** Preview uses VITE_PREVIEW_BASE; publish build uses VITE_EXPORT_BASE. */
function resolveViteBase(mode: string, env: Record<string, string>): string {
  if (mode === 'production') {
    return env.VITE_EXPORT_BASE || '/'
  }
  return env.VITE_PREVIEW_BASE || '/'
}

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const base = resolveViteBase(mode, env)
  const appVersion = resolveAppVersion(command)

  return {
    plugins: [syncIndexBasePlugin(base), react()],
    base,
    define: {
      'import.meta.env.VITE_AUTH_PROVIDER_URL': JSON.stringify('{{AUTH_PROVIDER_URL}}'),
      'import.meta.env.VITE_AUTH_STORAGE_KEY': JSON.stringify('{{AUTH_STORAGE_KEY}}'),
      'import.meta.env.VITE_AUTH_USE_IFRAME': JSON.stringify('{{AUTH_USE_IFRAME}}'),
      'import.meta.env.VITE_APP_VERSION': JSON.stringify(appVersion),
      'import.meta.env.VITE_BUILD_DATE': JSON.stringify(new Date().toISOString()),
    },
  }
})
