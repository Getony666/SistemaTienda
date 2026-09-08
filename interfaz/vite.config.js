import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base relativa para que sirva igual desde cualquier ruta del servidor local
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist", emptyOutDir: true },
});
