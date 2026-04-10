import { describe, expect, it } from "vitest";

/**
 * Tests for sidebar layout routing logic.
 * The layout switches between map (full viewport) and content (scrollable) modes.
 */

// Mirror the logic from sidebar-layout.tsx
function isMapPage(pathname: string): boolean {
  return pathname === "/map";
}

describe("sidebar-layout route detection", () => {
  it("identifies /map as the map page", () => {
    expect(isMapPage("/map")).toBe(true);
  });

  it("does not match /map sub-paths", () => {
    expect(isMapPage("/map/detail")).toBe(false);
  });

  it("does not match other routes", () => {
    expect(isMapPage("/")).toBe(false);
    expect(isMapPage("/about")).toBe(false);
    expect(isMapPage("/context")).toBe(false);
  });

  it("does not match partial matches", () => {
    expect(isMapPage("/mapping")).toBe(false);
    expect(isMapPage("/maps")).toBe(false);
  });
});

describe("sidebar cookie state", () => {
  // Mirror the cookie parsing logic from layout.tsx
  function parseSidebarState(cookieValue: string | undefined): boolean {
    return cookieValue !== "false";
  }

  it("defaults to open when cookie is undefined", () => {
    expect(parseSidebarState(undefined)).toBe(true);
  });

  it("returns false when cookie is 'false'", () => {
    expect(parseSidebarState("false")).toBe(false);
  });

  it("returns true for any other value", () => {
    expect(parseSidebarState("true")).toBe(true);
    expect(parseSidebarState("")).toBe(true);
  });
});
