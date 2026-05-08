import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the Bizkaia Connectivity frontend.
 *
 * - `webServer` boots `next dev` on demand so `pnpm e2e` is one command.
 * - The map and dashboard talk to the live API via the `/api/backend`
 *   proxy. Tests run against the proxied API by default; override with
 *   `PLAYWRIGHT_BASE_URL` to hit a deployed environment.
 * - We skip Firefox/WebKit by default to keep CI fast; flip on when a
 *   browser-specific bug shows up.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? "github" : "list",
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
        command: "pnpm dev --hostname 0.0.0.0",
        url: "http://localhost:3000",
        timeout: 120_000,
        reuseExistingServer: !process.env.CI,
        stdout: "pipe",
        stderr: "pipe",
      },
});
