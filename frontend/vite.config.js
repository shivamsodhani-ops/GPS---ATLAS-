import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // In dev, the frontend and backend run as two processes; this proxy
      // means the browser only ever talks to one origin (no CORS dance
      // needed) while `npm run dev` is running. In production the backend
      // serves the built frontend directly from the same origin, so this
      // block is unused there.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
