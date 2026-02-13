import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const repoRoot = path.resolve(__dirname, '..')
  const env = loadEnv(mode, repoRoot, '')
  const explicitApiUrl = env.VITE_API_URL || process.env.VITE_API_URL
  const apiPort = env.API_PORT || process.env.API_PORT
  const apiUrl = explicitApiUrl || (apiPort ? `http://localhost:${apiPort}` : '')
  if (!apiUrl) {
    throw new Error('VITE_API_URL or API_PORT is required. Set one in the root .env file.')
  }

  return {
    envDir: repoRoot,
    plugins: [react()],
    define: {
      'import.meta.env.VITE_API_URL': JSON.stringify(apiUrl)
    }
  }
})
