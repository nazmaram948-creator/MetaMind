/* global process */
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The app calls /api on its own origin. In dev, Vite forwards it to the backend
// (VITE_API_TARGET, default http://localhost:8000); in production FastAPI serves
// the built files and the API from one port.
const target = process.env.VITE_API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': target,
      '/health': target,
    },
  },
})
