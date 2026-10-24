import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "vite"
import { fileURLToPath, URL } from "node:url"

const proxyTarget = process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    chunkSizeWarningLimit: 1000,
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: false,
        ws: true,
      },
      "/frames": {
        target: proxyTarget,
        changeOrigin: false,
      },
    },
  },
})
