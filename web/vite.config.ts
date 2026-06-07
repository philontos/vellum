import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/chat": "http://localhost:18080",
      "/history": "http://localhost:18080",
      "/health": "http://localhost:18080",
      "/inspect": "http://localhost:18080",
    },
  },
  test: { environment: "node" },
});
