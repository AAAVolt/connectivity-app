/**
 * Pure helper functions for map features.
 * Extracted from connectivity-map.tsx for testability.
 */

/** Zoom → grid resolution mapping.
 *  Must stay in sync with backend ALLOWED_RESOLUTIONS (250, 500, 1000). */
export function getResolution(zoom: number): number {
  if (zoom < 9.5) return 1000;
  if (zoom < 11) return 500;
  return 250;
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
