# ADR-002 — Don't code-split recharts off the home page

**Status:** Accepted
**Date:** 2026-05-08
**Context:** Wave 4 recommendation, Wave 5 follow-up.

## Decision

We keep recharts as a regular dependency of the home (`/`) and `/context` routes. We do not wrap chart components in `next/dynamic`.

## What we measured

Wave 4 added `@next/bundle-analyzer` and a `pnpm analyze` script. Running it on `main` produces:

```
Route (app)                  Size       First Load JS
/                            9.7 kB     252 kB
/about                       14.1 kB    136 kB
/context                     4.9 kB     247 kB
/map                         2.3 kB     97.9 kB
shared chunks                           87.7 kB
```

Cross-referencing with `grep -rln "recharts" app/ components/`:

- recharts is imported by `app/page.tsx`, `app/context/page.tsx`, and `components/dashboard-charts.tsx`.
- It is **not** imported by the map route, the about route, or any shared chunk.

Next.js's per-route code-splitting already keeps recharts out of every route that doesn't render a chart. The map route's First Load (97.9 kB) is the empirical proof: if recharts were leaking, it would show up there.

## Why we don't lazy-load it on `/`

The home page **is** the dashboard. Users come to `/` specifically to see charts. Wrapping each chart in `next/dynamic`:

- Doesn't reduce the route's eventual JS payload (it just defers it).
- Adds a "loading…" state to the page's primary content.
- Hurts FCP-to-meaningful-content time, which matters more than initial bundle KB on a page where the meaningful content is the chart.

The same argument applies to `/context`.

## When to revisit

If `/map`'s First Load grows past ~150 kB, run `pnpm analyze` and check whether recharts has leaked into a shared chunk via a stray import (e.g., a util file that pulls a chart helper). That would be a real regression worth fixing.

If home-page FCP becomes a complaint, consider Suspense boundaries with skeleton placeholders — that's a UX fix, not a bundle fix.

## Cross-references

- Wave 4 commit `16891af` — added `@next/bundle-analyzer`.
- `frontend/next.config.mjs` — analyzer wiring (set `ANALYZE=true` in env).
