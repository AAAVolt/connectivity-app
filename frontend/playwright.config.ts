import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the Bizkaia Connectivity frontend.
 *
 * - In CI we boot `next start` against a prebuilt app: deterministic and
 *   far faster than dev mode (no on-demand compile = no 30s map timeouts).
 * - Locally we keep `next dev` for HMR. CI is detected via the CI env var.
 * - The map and dashboard talk to the live API via the `/api/backend`
 *   proxy. Tests run against the proxied API by default; override with
 *   `PLAYWRIGHT_BASE_URL` to hit a deployed environment.
 * - We skip Firefox/WebKit by default to keep CI fast; flip on when a
 *   browser-specific bug shows up.
 */
const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  workers: isCI ? 2 : undefined,
  reporter: isCI ? "github" : "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: isCI
          ? "pnpm start --hostname 0.0.0.0"
          : "pnpm dev --hostname 0.0.0.0",
        url: "http://localhost:3000",
        timeout: 180_000,
        reuseExistingServer: !isCI,
        stdout: "pipe",
        stderr: "pipe",
      },
});
