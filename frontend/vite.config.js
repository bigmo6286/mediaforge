import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API + file requests to the FastAPI backend so the browser only
// ever talks to one origin (the Vite dev server).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/files": "http://127.0.0.1:8000",
    },
  },
});
