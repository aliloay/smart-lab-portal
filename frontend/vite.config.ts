import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    // The API is proxied so the browser talks to one origin in development.
    // `vite preview` inherits this, which is what the e2e test runs against.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws':  { target: 'ws://127.0.0.1:8000', ws: true },
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
