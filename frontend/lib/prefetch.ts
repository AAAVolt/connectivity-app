import type { QueryClient } from "@tanstack/react-query";
import {
  boundaryQueryOptions,
  destTypesQueryOptions,
  departureTimesQueryOptions,
  destinationsQueryOptions,
  transitRoutesQueryOptions,
  transitStopsQueryOptions,
  nucleosQueryOptions,
  cellsQueryOptions,
  socioProfilesQueryOptions,
} from "@/hooks/use-map-data";

/**
 * Prefetch lightweight static data used by map init.
 * Call from dashboard on load — these are small and cache forever.
 */
export function prefetchStaticMapData(qc: QueryClient) {
  qc.prefetchQuery(boundaryQueryOptions("region"));
  qc.prefetchQuery(boundaryQueryOptions("comarcas"));
  qc.prefetchQuery(boundaryQueryOptions("municipalities"));
  qc.prefetchQuery(destTypesQueryOptions());
  qc.prefetchQuery(departureTimesQueryOptions());
}

/**
 * Prefetch heavier map data (destinations, transit, nucleos).
 * Call on hover of the Map nav link.
 */
export function prefetchHeavyMapData(qc: QueryClient) {
  qc.prefetchQuery(destinationsQueryOptions());
  qc.prefetchQuery(transitRoutesQueryOptions());
  qc.prefetchQuery(transitStopsQueryOptions());
  qc.prefetchQuery(nucleosQueryOptions());
}

/**
 * Prefetch the default cells GeoJSON (combined score, 08:00, 250m).
 * This is the heaviest payload — prefetch after dashboard loads.
 */
export function prefetchDefaultCells(qc: QueryClient) {
  qc.prefetchQuery(cellsQueryOptions({
    metric: "score",
    departureTime: "08:00",
    resolution: 250,
  }));
}

/**
 * Prefetch sociodemographic profiles (used by context page + map popups).
 */
export function prefetchSocioProfiles(qc: QueryClient) {
  qc.prefetchQuery(socioProfilesQueryOptions());
}
