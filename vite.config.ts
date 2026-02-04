import { defineConfig } from "vite";
import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [tailwindcss(), reactRouter(), tsconfigPaths()],
  server: {
    host: true, // or "0.0.0.0"
    port: 8008,
    strictPort: true,
    allowedHosts: ["vroomeee.duckdns.org"],
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
