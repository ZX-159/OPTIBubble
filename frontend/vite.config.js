import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/app/",
  build: { outDir: "../optibubble/web/dist", emptyOutDir: true, assetsDir: "." },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:5000", "/fonts": "http://127.0.0.1:5000",
             "/assets": "http://127.0.0.1:5000" },
  },
});
