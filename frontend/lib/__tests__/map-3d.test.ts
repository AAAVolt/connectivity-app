import { describe, expect, it } from "vitest";
import {
  buildHeightExpr,
  getResolution,
  is3DVisibleAtResolution,
  isValidLandmark,
  scoreHeightExpr,
  travelTimeHeightExpr,
} from "../map-3d";

describe("scoreHeightExpr", () => {
  it("returns a MapLibre expression that scales score to height", () => {
    const expr = scoreHeightExpr(400);
    expect(expr).toEqual(["*", ["coalesce", ["get", "score"], 0], 4]);
  });

  it("scales proportionally — 200m max → factor 2", () => {
    const expr = scoreHeightExpr(200);
    expect(expr[2]).toBe(2);
  });

  it("handles zero max height", () => {
    const expr = scoreHeightExpr(0);
    expect(expr[2]).toBe(0);
  });
});

describe("travelTimeHeightExpr", () => {
  it("returns a MapLibre expression that inverts travel time", () => {
    const expr = travelTimeHeightExpr(450);
    // 450 / 90 = 5
    expect(expr).toEqual([
      "*",
      ["max", ["-", 90, ["coalesce", ["get", "score"], 90]], 0],
      5,
    ]);
  });

  it("produces zero height for 90-min travel time (worst case)", () => {
    // The expression evaluates: max(90 - 90, 0) * factor = 0
    const expr = travelTimeHeightExpr(300);
    // Conceptually: score=90 → (90-90)*factor = 0 ✓
    expect(expr[1]).toEqual(["max", ["-", 90, ["coalesce", ["get", "score"], 90]], 0]);
  });

  it("produces max height for 0-min travel time (best case)", () => {
    // score=0 → max(90-0, 0) * (300/90) = 90 * 3.33 = 300 ✓
    const factor = 300 / 90;
    const expr = travelTimeHeightExpr(300);
    expect(expr[2]).toBeCloseTo(factor);
  });
});

describe("buildHeightExpr", () => {
  it("delegates to scoreHeightExpr for score metric", () => {
    const expr = buildHeightExpr("score", 400);
    expect(expr).toEqual(scoreHeightExpr(400));
  });

  it("delegates to travelTimeHeightExpr for travel_time metric", () => {
    const expr = buildHeightExpr("travel_time", 400);
    expect(expr).toEqual(travelTimeHeightExpr(400));
  });
});

describe("getResolution", () => {
  it("returns 1000 for low zoom", () => {
    expect(getResolution(8)).toBe(1000);
    expect(getResolution(9)).toBe(1000);
    expect(getResolution(9.4)).toBe(1000);
  });

  it("returns 500 for medium zoom", () => {
    expect(getResolution(9.5)).toBe(500);
    expect(getResolution(10)).toBe(500);
    expect(getResolution(10.9)).toBe(500);
  });

  it("returns 250 for high zoom (11+)", () => {
    expect(getResolution(11)).toBe(250);
    expect(getResolution(12)).toBe(250);
    expect(getResolution(14)).toBe(250);
    expect(getResolution(18)).toBe(250);
  });

  it("is monotonically non-increasing with zoom", () => {
    const zooms = [7, 9, 9.5, 10, 10.9, 11, 12, 14, 16];
    const resolutions = zooms.map(getResolution);
    for (let i = 1; i < resolutions.length; i++) {
      expect(resolutions[i]).toBeLessThanOrEqual(resolutions[i - 1]);
    }
  });
});

describe("is3DVisibleAtResolution", () => {
  it("returns true for coarse grids (250m+)", () => {
    expect(is3DVisibleAtResolution(1000)).toBe(true);
    expect(is3DVisibleAtResolution(500)).toBe(true);
    expect(is3DVisibleAtResolution(250)).toBe(true);
  });

  it("returns false for fine grids (<250m)", () => {
    expect(is3DVisibleAtResolution(200)).toBe(false);
    expect(is3DVisibleAtResolution(100)).toBe(false);
  });
});

describe("isValidLandmark", () => {
  const validFeature = {
    properties: { name: "Guggenheim", height: 50, color: "#b8b8b8" },
    geometry: {
      type: "Polygon",
      coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    },
  };

  it("accepts a valid landmark", () => {
    expect(isValidLandmark(validFeature)).toBe(true);
  });

  it("rejects missing name", () => {
    expect(
      isValidLandmark({
        properties: { height: 50, color: "#fff" },
        geometry: validFeature.geometry,
      }),
    ).toBe(false);
  });

  it("rejects zero height", () => {
    expect(
      isValidLandmark({
        properties: { name: "X", height: 0, color: "#fff" },
        geometry: validFeature.geometry,
      }),
    ).toBe(false);
  });

  it("rejects negative height", () => {
    expect(
      isValidLandmark({
        properties: { name: "X", height: -10, color: "#fff" },
        geometry: validFeature.geometry,
      }),
    ).toBe(false);
  });

  it("rejects non-Polygon geometry", () => {
    expect(
      isValidLandmark({
        properties: validFeature.properties,
        geometry: { type: "Point", coordinates: [0, 0] },
      }),
    ).toBe(false);
  });

  it("rejects missing geometry", () => {
    expect(
      isValidLandmark({ properties: validFeature.properties }),
    ).toBe(false);
  });
});
