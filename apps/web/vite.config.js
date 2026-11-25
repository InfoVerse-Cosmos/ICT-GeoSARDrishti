import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
  },
  build: {
    // Split the large third-party libraries into their own long-lived chunks so
    // app code stays small and cacheable. maplibre-gl is a single ~800 kB library
    // that cannot be split further, so the per-chunk warning limit is raised just
    // past it rather than hidden across every chunk.
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("maplibre-gl")) return "maplibre";
          if (id.includes("recharts") || id.includes("/d3-") || id.includes("victory"))
            return "charts";
          if (id.includes("/react/") || id.includes("/react-dom/") || id.includes("/scheduler/"))
            return "react-vendor";
          return "vendor";
        },
      },
    },
  },
});
