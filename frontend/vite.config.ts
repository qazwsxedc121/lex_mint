import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const repoRoot = path.resolve(__dirname, '..')
  const env = loadEnv(mode, repoRoot, '')
  const apiPort = env.API_PORT
  if (!apiPort) {
    throw new Error('API_PORT is required. Set it in the root .env file.')
  }
  const apiUrl = `http://localhost:${apiPort}`

  return {
    envDir: repoRoot,
    plugins: [react()],
    define: {
      'import.meta.env.VITE_API_URL': JSON.stringify(apiUrl)
    }
  }
})
