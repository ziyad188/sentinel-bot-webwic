import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8080,
    hmr: {
      overlay: false,
    },
    proxy: {
      "/api": "http://localhost:8000",
      "/auth": "http://localhost:8000",
      "/list": "http://localhost:8000",
      "/projects": "http://localhost:8000",
      "/runs": "http://localhost:8000",
      "/issues": "http://localhost:8000",
      "/evidence": "http://localhost:8000",
      "/users": "http://localhost:8000",
      "/widgets": "http://localhost:8000",
    },
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
