import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // relative asset paths so index.html works from file:// (Electron shell)
  base: "./",
  server: { port: 5173 },
});
