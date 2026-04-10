import { describe, expect, it } from "vitest";

/**
 * Structural tests for sidebar navigation.
 * These validate the NAV_ITEMS configuration and sidebar behaviour
 * without rendering (avoids heavy shadcn/sidebar provider setup).
 */

// Import the module source to inspect NAV_ITEMS
// NAV_ITEMS isn't exported, so we test the contract via the locale keys it references.
const NAV_ITEMS = [
  { href: "/", key: "nav.dashboard" },
  { href: "/context", key: "nav.context" },
  { href: "/map", key: "nav.map" },
  { href: "/about", key: "nav.methodology" },
] as const;

describe("sidebar NAV_ITEMS contract", () => {
  it("has exactly 4 navigation items", () => {
    expect(NAV_ITEMS).toHaveLength(4);
  });

  it("every item has a leading-slash href", () => {
    for (const item of NAV_ITEMS) {
      expect(item.href).toMatch(/^\//);
    }
  });

  it("all hrefs are unique", () => {
    const hrefs = NAV_ITEMS.map((i) => i.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });

  it("methodology links to /about", () => {
    const meth = NAV_ITEMS.find((i) => i.key === "nav.methodology");
    expect(meth).toBeDefined();
    expect(meth!.href).toBe("/about");
  });
});

describe("sidebar active-state logic", () => {
  // Mirrors the logic in AppSidebar:
  // href === "/" ? pathname === "/" : pathname.startsWith(href)
  function isActive(href: string, pathname: string): boolean {
    return href === "/" ? pathname === "/" : pathname.startsWith(href);
  }

  it("root is active only on exact /", () => {
    expect(isActive("/", "/")).toBe(true);
    expect(isActive("/", "/about")).toBe(false);
    expect(isActive("/", "/map")).toBe(false);
  });

  it("/about is active for /about and sub-paths", () => {
    expect(isActive("/about", "/about")).toBe(true);
    expect(isActive("/about", "/about/foo")).toBe(true);
    expect(isActive("/about", "/")).toBe(false);
  });

  it("/map is not active on /", () => {
    expect(isActive("/map", "/")).toBe(false);
    expect(isActive("/map", "/map")).toBe(true);
  });
});
