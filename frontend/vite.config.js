import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The proxy forwards /api and /health to FastAPI on port 8000,
// so the frontend never hits CORS issues and never hardcodes the
// backend URL. In the browser you just fetch("/api/drafts").
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
