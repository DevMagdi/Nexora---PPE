import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "vite"
import { fileURLToPath, URL } from "node:url"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // ✅ REST + WebSocket proxy
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true, // مهم جدًا للـ /api/v1/ws/...
      },
      "/frames": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
})