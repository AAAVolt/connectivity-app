/**
 * Pure helper functions for 3D map features.
 * Extracted from connectivity-map.tsx for testability.
 */

/** Score-based extrusion height expression for MapLibre. */
export function scoreHeightExpr(maxHeight: number): unknown[] {
  return ["*", ["coalesce", ["get", "score"], 0], maxHeight / 100];
}

/** Travel-time extrusion height expression (inverted: shorter time = taller). */
export function travelTimeHeightExpr(maxHeight: number): unknown[] {
  return [
    "*",
    ["max", ["-", 90, ["coalesce", ["get", "score"], 90]], 0],
    maxHeight / 90,
  ];
}

/** Build the height expression for the active metric. */
export function buildHeightExpr(
  metric: "score" | "travel_time",
  maxHeight: number,
): unknown[] {
  return metric === "travel_time"
    ? travelTimeHeightExpr(maxHeight)
    : scoreHeightExpr(maxHeight);
}

/** Zoom → grid resolution mapping.
 *  Must stay in sync with backend ALLOWED_RESOLUTIONS (250, 500, 1000). */
export function getResolution(zoom: number): number {
  if (zoom < 9.5) return 1000;
  if (zoom < 11) return 500;
  return 250;
}

/** Whether 3D extrusion is visible at a given resolution (perf guard). */
export function is3DVisibleAtResolution(resolution: number): boolean {
  // 3D extrusion is shown at 250m and coarser to avoid performance issues.
  return resolution >= 250;
}

/** Validate landmark feature structure. */
export function isValidLandmark(feature: {
  properties?: { name?: string; height?: number; color?: string };
  geometry?: { type?: string; coordinates?: unknown };
}): boolean {
  const p = feature.properties;
  const g = feature.geometry;
  return (
    typeof p?.name === "string" &&
    typeof p?.height === "number" &&
    p.height > 0 &&
    typeof p?.color === "string" &&
    g?.type === "Polygon" &&
    Array.isArray(g?.coordinates)
  );
}
