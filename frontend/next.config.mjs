/** @type {import('next').NextConfig} */

import withBundleAnalyzer from "@next/bundle-analyzer";

const isProd = process.env.NODE_ENV === "production";
const bundleAnalyzer = withBundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

// External origins the MapLibre map fetches tiles, sprites, and metadata from.
// If a new basemap is added in components/connectivity-map.tsx, add its origin here.
const TILE_ORIGINS = [
  "https://tile.openstreetmap.org",
  "https://a.basemaps.cartocdn.com",
  "https://b.basemaps.cartocdn.com",
  "https://c.basemaps.cartocdn.com",
  "https://d.basemaps.cartocdn.com",
  "https://tiles.openfreemap.org",
  "https://server.arcgisonline.com",
  "https://demotiles.maplibre.org",
  "https://s3.amazonaws.com",
];

// Next.js + React inject runtime scripts/styles. A fully nonce-based CSP would
// require middleware to thread per-request nonces through Server Components;
// that's a larger change. For now we permit 'unsafe-inline' for scripts and
// styles (still blocking inline event handlers via removed 'unsafe-eval' for
// scripts). This is stricter than no CSP and a pragmatic MVP target.
const csp = [
  "default-src 'self'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  // 'unsafe-inline' kept for Next.js hydration scripts; 'wasm-unsafe-eval' for
  // MapLibre's WebAssembly-backed renderer; 'unsafe-eval' for React DevTools
  // in non-prod only.
  `script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'${isProd ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self' data:",
  `img-src 'self' data: blob: ${TILE_ORIGINS.join(" ")}`,
  // /api/backend proxies same-origin; tile JSON endpoints must be reachable.
  `connect-src 'self' ${TILE_ORIGINS.join(" ")}`,
  "worker-src 'self' blob:",
  // Manifest, prefetch, etc.
  "manifest-src 'self'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
  { key: "X-DNS-Prefetch-Control", value: "off" },
];

if (isProd) {
  // HSTS only in prod — caching it locally would force https://localhost upgrades.
  securityHeaders.push({
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  });
}

const nextConfig = {
  ...(process.env.NEXT_OUTPUT === "standalone" ? { output: "standalone" } : {}),
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default bundleAnalyzer(nextConfig);
