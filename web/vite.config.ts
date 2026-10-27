import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

// Where the app is served: "/" by default, "/litstorm/" behind host 203's
// nginx (docs/web-app-design.md, base path). Set at build time.
const base = `/${(process.env.LITSTORM_BASE_PATH ?? "").replace(/^\/+|\/+$/g, "")}/`.replace("//", "/");

export default defineConfig({
  base,
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@mra": path.resolve(__dirname, "./src/mra"),
      // MRA's report code (src/mra) links with next/link; a plain anchor here, as in MRA's offline file.
      "next/link": path.resolve(__dirname, "./src/mra/shims-link.tsx"),
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    // LITSTORM_API points a second dev server at a second API, as the
    // browser scripts' throwaway environment does.
    proxy: { "/api": process.env.LITSTORM_API ?? "http://127.0.0.1:8000" },
  },
});
