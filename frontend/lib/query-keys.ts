/**
 * Centralized React Query key factories and staleTime tiers.
 *
 * Three tiers based on how often data changes:
 * - STATIC:   boundaries, transit, destinations, departure times — never changes within a session
 * - COMPUTED: dashboard stats, cells, area details — tied to departure_time but stable
 * - SESSION:  frequency, user-parameterized queries — shorter cache for interactive use
 */

export const STALE_TIMES = {
  STATIC: Infinity,
  COMPUTED: 10 * 60_000,  // 10 minutes
  SESSION: 5 * 60_000,    // 5 minutes
} as const;

export const dashboardKeys = {
  all: ["dashboard"] as const,
  combined: (departureTime: string) =>
    [...dashboardKeys.all, "combined", departureTime] as const,
  areaDetail: (areaType: string, code: string) =>
    [...dashboardKeys.all, "area-detail", areaType, code] as const,
};

export const contextKeys = {
  all: ["context"] as const,
  profiles: (departureTime?: string) =>
    [...contextKeys.all, "profiles", departureTime ?? "default"] as const,
  frequency: (timeWindow: string) =>
    [...contextKeys.all, "frequency", timeWindow] as const,
};

export const mapKeys = {
  all: ["map"] as const,
  boundaries: (type: string) => [...mapKeys.all, "boundaries", type] as const,
  cells: (params: {
    mode?: string;
    purpose?: string;
    metric?: string;
    resolution?: string;
    departureTime?: string;
  }) => [...mapKeys.all, "cells", params] as const,
  destinations: () => [...mapKeys.all, "destinations"] as const,
  destTypes: () => [...mapKeys.all, "dest-types"] as const,
  transitRoutes: () => [...mapKeys.all, "transit-routes"] as const,
  transitStops: () => [...mapKeys.all, "transit-stops"] as const,
  nucleos: () => [...mapKeys.all, "nucleos"] as const,
  departureTimes: () => [...mapKeys.all, "departure-times"] as const,
  frequency: (timeWindow: string) =>
    [...mapKeys.all, "frequency", timeWindow] as const,
  socialMunis: (departureTime?: string) =>
    [...mapKeys.all, "social-munis", departureTime ?? "default"] as const,
};
