import { test, expect } from "@playwright/test";

/**
 * Golden-path smoke tests — the user-visible flows that, if they break,
 * mean the app is effectively down regardless of what the unit tests say.
 *
 * Keep these tight. Anything testing branching logic belongs in vitest.
 */

test.describe("Bizkaia Connectivity frontend", () => {
  test("home page loads and shows the dashboard chrome", async ({ page }) => {
    await page.goto("/");
    // The home is the dashboard. We can't assert on chart contents
    // (recharts sets opacity transitions etc.) but we can assert on the
    // tab navigation chrome that gates everything.
    await expect(page.getByRole("button", { name: /overview|comarcas|municip/i }).first()).toBeVisible({
      timeout: 30_000,
    });
  });

  test("map page mounts a maplibre canvas", async ({ page }) => {
    await page.goto("/map");
    // MapLibre creates a <canvas class="maplibregl-canvas"> once the map
    // initialises. Asserting on the canvas catches the most common
    // regression class: the dynamic import failing or the proxy returning
    // 5xx so no tiles ever load. We give it a generous timeout because the
    // first run also pays the in-component `await import("maplibre-gl")`.
    await expect(page.locator(".maplibregl-canvas")).toBeVisible({
      timeout: 30_000,
    });
  });

  test("about page renders methodology content", async ({ page }) => {
    await page.goto("/about");
    // The about page is largely static and translated; if the i18n
    // dictionary breaks or rich-text sanitization throws, this catches it.
    // The string used here should match a key that exists in both en/es.
    await expect(page.locator("main")).toContainText(/methodolog|metodolog/i);
  });

  test("readiness probe via the proxy returns 200", async ({ request }) => {
    // The proxy is a server-side route handler; a broken proxy is the
    // most common cause of "the app loads but everything is empty".
    const res = await request.get("/api/backend/readiness");
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ready");
  });
});
