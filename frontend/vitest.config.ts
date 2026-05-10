import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    // Exclude Playwright's e2e directory: vitest's default include picks
    // up `*.spec.ts` from anywhere, but those files use `@playwright/test`
    // which throws "did not expect test.describe()" under vitest.
    exclude: ["**/node_modules/**", "**/dist/**", "**/.next/**", "e2e/**"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
