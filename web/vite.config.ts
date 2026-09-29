import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    port: 5173,
    // LITSTORM_API points a second dev server at a second API, as the
    // browser scripts' throwaway environment does.
    proxy: { "/api": process.env.LITSTORM_API ?? "http://127.0.0.1:8000" },
  },
});
