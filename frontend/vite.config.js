import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API + WebSocket calls to the FastAPI backend on :8000 so the frontend
// can just call "/api/..." and "/ws" without CORS headaches in dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
});
