import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Where the API runs. Override to point a second instance elsewhere, e.g.
// VITE_API_TARGET=http://127.0.0.1:8001 npm run dev -- --port 5174
const API = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    // The API is proxied so the browser talks to one origin in development.
    // `vite preview` inherits this, which is what the e2e test runs against.
    proxy: {
      '/api': { target: API, changeOrigin: true },
      '/ws':  { target: API.replace(/^http/, 'ws'), ws: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Stable vendor chunks cache across deploys; Recharts is already
        // split out because only the lazy chart pages import it.
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          motion: ['framer-motion'],
          icons: ['lucide-react'],
        },
      },
    },
  },
})
