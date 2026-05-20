import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // Proxy API calls so we don't need CORS during dev
    proxy: {
      '/api': 'http://localhost:8080',
      '/runs': 'http://localhost:8080',
      '/results': 'http://localhost:8080',
      '/health': 'http://localhost:8080',
    },
  },
})
