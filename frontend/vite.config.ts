import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true, // reachable from a phone on the same Wi-Fi
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
