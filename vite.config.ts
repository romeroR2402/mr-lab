import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "tailwindcss";
import autoprefixer from "autoprefixer";
import { resolve } from "node:path";

export default defineConfig({
  root: resolve(__dirname, "src/renderer"),
  base: "./",
  plugins: [react()],
  css: { postcss: { plugins: [tailwind(resolve(__dirname, "tailwind.config.js")), autoprefixer()] } },
  server: { port: 5173, strictPort: true },
  build: { outDir: resolve(__dirname, "dist/renderer"), emptyOutDir: true },
});
