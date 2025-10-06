import { defineConfig } from "vite";

export default defineConfig({
  server: {
    open: true // Automatically open the browser on project run
  },
  build: {
    outDir: "dist"
  },
  plugins: []
});