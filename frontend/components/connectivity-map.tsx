"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, PanelLeftClose, PanelLeft } from "lucide-react";
import type { Map as MaplibreMap } from "maplibre-gl";
import { useTranslation } from "@/lib/i18n";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEMO_TENANT = "00000000-0000-0000-0000-000000000001";

const DEFAULT_CENTER: [number, number] = [-2.87, 43.22];
const DEFAULT_ZOOM = 10;

// ── Time-of-day slots (every 30 min, 0–47 → "00:00"–"23:30") ──
const TIME_SLOTS: string[] = Array.from({ length: 48 }, (_, i) => {
  const h = Math.floor(i / 2);
  const m = (i % 2) * 30;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
});
const DEFAULT_TIME_INDEX = 16; // 08:00

// ── POI types (primary filter) ──
const POI_TYPES = [
  { value: null, label: "Combined", descKey: "map.allDestTypes" },
  { value: "aeropuerto", label: "Aeropuerto", descKey: "poi.aeropuerto", color: "#6366f1" },
  { value: "bachiller", label: "Bachiller", descKey: "poi.bachiller", color: "#f59e0b" },
  { value: "centro_educativo", label: "Centro Educativo", descKey: "poi.centro_educativo", color: "#eab308" },
  { value: "centro_urbano", label: "Centro Urbano", descKey: "poi.centro_urbano", color: "#8b5cf6" },
  { value: "consulta_general", label: "Consulta General", descKey: "poi.consulta_general", color: "#ef4444" },
  { value: "hacienda", label: "Hacienda", descKey: "poi.hacienda", color: "#64748b" },
  { value: "hospital", label: "Hospital", descKey: "poi.hospital", color: "#dc2626" },
  { value: "osakidetza", label: "Osakidetza", descKey: "poi.osakidetza", color: "#f97316" },
  { value: "residencia", label: "Residencia", descKey: "poi.residencia", color: "#14b8a6" },
  { value: "universidad", label: "Universidad", descKey: "poi.universidad", color: "#22c55e" },
] as const;

// ── Metrics ──
type MetricType = "score" | "travel_time";

// ── 12-stop color ramp for accessibility score (low=bad, high=good) ──
const SCORE_COLORS: [number, string][] = [
  [0, "#1a0a00"],
  [9, "#7f1b00"],
  [18, "#c4321a"],
  [27, "#e05a2b"],
  [36, "#f0892e"],
  [45, "#f5b731"],
  [54, "#e8d534"],
  [63, "#b5d935"],
  [72, "#6ec440"],
  [81, "#2da84e"],
  [90, "#1a8a5c"],
  [100, "#0e5e8c"],
];

// ── Discrete color bands for travel time to nearest destination ──
const TRAVEL_TIME_BANDS = [
  { min: 0, max: 30, color: "#1a9850", label: "< 30 min" },
  { min: 30, max: 45, color: "#91cf60", label: "30–45 min" },
  { min: 45, max: 60, color: "#fee08b", label: "45–60 min" },
  { min: 60, max: 75, color: "#fc8d59", label: "60–75 min" },
  { min: 75, max: 90, color: "#d73027", label: "75–90 min" },
] as const;
const TRAVEL_TIME_NO_DATA_COLOR = "#878787";
const TRAVEL_TIME_NO_DATA_LABEL = "> 90 min";

/** MapLibre step expression for discrete travel-time bands. */
const TRAVEL_TIME_STEP_EXPR = [
  "step",
  ["coalesce", ["get", "score"], 999],
  TRAVEL_TIME_BANDS[0].color,
  30, TRAVEL_TIME_BANDS[1].color,
  45, TRAVEL_TIME_BANDS[2].color,
  60, TRAVEL_TIME_BANDS[3].color,
  75, TRAVEL_TIME_BANDS[4].color,
  90, TRAVEL_TIME_NO_DATA_COLOR,
];

// ── Transit operators with colors ──
const OPERATORS = [
  { id: "Bizkaibus", label: "Bizkaibus", color: "#166534" },       // dark green
  { id: "Bilbobus", label: "Bilbobus", color: "#d97706" },         // amber
  { id: "MetroBilbao", label: "Metro Bilbao", color: "#dc2626" },  // red
  { id: "Euskotren", label: "Euskotren", color: "#7c3aed" },       // purple
  { id: "Renfe_Cercanias", label: "Renfe Cercanias", color: "#0369a1" }, // sky blue
  { id: "FunicularArtxanda", label: "Funicular Artxanda", color: "#a855f7" }, // violet
] as const;

// ── Destination marker styles ──
const DEST_LAYERS = [
  { id: "dest-aeropuerto", type: "aeropuerto", color: "#6366f1", label: "Aeropuerto" },
  { id: "dest-bachiller", type: "bachiller", color: "#f59e0b", label: "Bachiller" },
  { id: "dest-centro-educativo", type: "centro_educativo", color: "#eab308", label: "Centro Educativo" },
  { id: "dest-centro-urbano", type: "centro_urbano", color: "#8b5cf6", label: "Centro Urbano" },
  { id: "dest-consulta-general", type: "consulta_general", color: "#ef4444", label: "Consulta General" },
  { id: "dest-hacienda", type: "hacienda", color: "#64748b", label: "Hacienda" },
  { id: "dest-hospital", type: "hospital", color: "#dc2626", label: "Hospital" },
  { id: "dest-osakidetza", type: "osakidetza", color: "#f97316", label: "Osakidetza" },
  { id: "dest-residencia", type: "residencia", color: "#14b8a6", label: "Residencia" },
  { id: "dest-universidad", type: "universidad", color: "#22c55e", label: "Universidad" },
];

// ── Zoom → grid resolution mapping ──
function getResolution(zoom: number): number {
  if (zoom < 9.5) return 1000;
  if (zoom < 11) return 500;
  if (zoom < 12.5) return 200;
  return 100;
}

const RESOLUTION_LABELS: Record<number, string> = {
  100: "100 m",
  200: "200 m",
  500: "500 m",
  1000: "1 km",
};

/** Create a small diagonal-stripe image for the "no population" hatch overlay. */
function createHatchPattern(): { width: number; height: number; data: Uint8Array } {
  const size = 10;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;

  ctx.clearRect(0, 0, size, size);

  // Light grey background so unpopulated cells are clearly distinguishable
  ctx.fillStyle = "rgba(180, 180, 180, 0.45)";
  ctx.fillRect(0, 0, size, size);

  // Diagonal line (bottom-left → top-right), repeated via tiling
  ctx.strokeStyle = "rgba(80, 80, 80, 0.6)";
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.moveTo(0, size);
  ctx.lineTo(size, 0);
  ctx.moveTo(-size, size);
  ctx.lineTo(size, -size);
  ctx.moveTo(0, size * 2);
  ctx.lineTo(size * 2, 0);
  ctx.stroke();

  const imgData = ctx.getImageData(0, 0, size, size);
  return { width: size, height: size, data: new Uint8Array(imgData.data.buffer) };
}

interface CellProperties {
  id?: number;
  cell_code: string;
  population: number;
  score: number | null;
}

interface LayerToggle {
  id: string;
  label: string;
  visible: boolean;
  color?: string;
}

interface OperatorState {
  id: string;
  label: string;
  color: string;
  visible: boolean;
}

type MapInstance = {
  getSource: (id: string) => { setData: (data: unknown) => void } | undefined;
  getLayer: (id: string) => unknown;
  setLayoutProperty: (id: string, prop: string, val: string) => void;
  setFilter: (id: string, filter: unknown) => void;
  remove: () => void;
};

const BASE_LAYER_MAPPING: Record<string, string[]> = {
  cells: ["cells-fill", "cells-hatch", "cells-outline"],
  region: ["region-boundary"],
  comarcas: ["comarcas-boundary"],
  municipalities: ["municipalities-boundary"],
  nucleos: ["nucleos-fill", "nucleos-outline"],
  labels: ["comarcas-labels", "municipalities-labels"],
};

export default function ConnectivityMap() {
  const { t } = useTranslation();
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapInstance | null>(null);
  const [selectedCell, setSelectedCell] = useState<CellProperties | null>(null);
  const [status, setStatus] = useState("map.initializingMap");
  const [error, setError] = useState<string | null>(null);
  const [mapReady, setMapReady] = useState(false);

  const [selectedPurpose, setSelectedPurpose] = useState<string | null>(null);
  const [metric, setMetric] = useState<MetricType>("score");
  const [timeIndex, setTimeIndex] = useState(DEFAULT_TIME_INDEX);
  const [availableTimes, setAvailableTimes] = useState<string[]>(TIME_SLOTS);
  const [resolution, setResolution] = useState(getResolution(DEFAULT_ZOOM));

  // Base layers — labelKey is the i18n key
  const [baseLayers, setBaseLayers] = useState<(LayerToggle & { labelKey: string })[]>([
    { id: "cells", label: "", labelKey: "map.accessibilityGrid", visible: true },
    { id: "region", label: "", labelKey: "map.bizkaiaBoundary", visible: true },
    { id: "comarcas", label: "", labelKey: "map.comarcas", visible: false },
    { id: "municipalities", label: "", labelKey: "map.municipalities", visible: false },
    { id: "nucleos", label: "", labelKey: "map.nucleos", visible: false },
    { id: "labels", label: "", labelKey: "map.labels", visible: false },
  ]);

  // Per-POI-type destination toggles
  const [destToggles, setDestToggles] = useState(
    DEST_LAYERS.map((dt) => ({ id: dt.id, label: dt.label, color: dt.color, visible: false })),
  );

  // Per-operator visibility + global route/stop toggles
  const [operators, setOperators] = useState<OperatorState[]>(
    OPERATORS.map((op) => ({ id: op.id, label: op.label, color: op.color, visible: false })),
  );
  const [showRoutes, setShowRoutes] = useState(false);
  const [showStops, setShowStops] = useState(false);
  const [fillOpacity, setFillOpacity] = useState(0.7);

  // Panel collapse
  const [panelOpen, setPanelOpen] = useState(true);

  // Collapsible section state
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    metric: true,
    time: true,
    destination: true,
    layers: false,
    destinations: false,
    transit: false,
  });
  const toggleSection = useCallback((key: string) => {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const toggleBaseLayer = useCallback(
    (groupId: string) => {
      setBaseLayers((prev) =>
        prev.map((l) => (l.id === groupId ? { ...l, visible: !l.visible } : l)),
      );
      const map = mapRef.current;
      if (!map) return;
      const layer = baseLayers.find((l) => l.id === groupId);
      if (!layer) return;
      const newVis = !layer.visible ? "visible" : "none";
      for (const lid of BASE_LAYER_MAPPING[groupId] ?? []) {
        if (map.getLayer(lid)) map.setLayoutProperty(lid, "visibility", newVis);
      }
    },
    [baseLayers],
  );

  // Reactive transit layer visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const visibleOps = operators.filter((o) => o.visible).map((o) => o.id);

    if (map.getLayer("transit-routes")) {
      if (!showRoutes || visibleOps.length === 0) {
        map.setLayoutProperty("transit-routes", "visibility", "none");
      } else {
        map.setLayoutProperty("transit-routes", "visibility", "visible");
        map.setFilter("transit-routes", ["in", ["get", "operator"], ["literal", visibleOps]]);
      }
    }
    if (map.getLayer("transit-stops")) {
      if (!showStops || visibleOps.length === 0) {
        map.setLayoutProperty("transit-stops", "visibility", "none");
      } else {
        map.setLayoutProperty("transit-stops", "visibility", "visible");
        map.setFilter("transit-stops", ["in", ["get", "operator"], ["literal", visibleOps]]);
      }
    }
  }, [operators, showRoutes, showStops, mapReady]);

  const handleToggleRoutes = useCallback(() => {
    setShowRoutes((prev) => {
      const next = !prev;
      // Auto-select all operators when enabling and none are visible
      if (next) {
        setOperators((ops) =>
          ops.every((o) => !o.visible) ? ops.map((o) => ({ ...o, visible: true })) : ops,
        );
      }
      return next;
    });
  }, []);

  const handleToggleStops = useCallback(() => {
    setShowStops((prev) => {
      const next = !prev;
      if (next) {
        setOperators((ops) =>
          ops.every((o) => !o.visible) ? ops.map((o) => ({ ...o, visible: true })) : ops,
        );
      }
      return next;
    });
  }, []);

  const toggleDestination = useCallback((layerId: string) => {
    setDestToggles((prev) => {
      const updated = prev.map((d) => d.id === layerId ? { ...d, visible: !d.visible } : d);
      const map = mapRef.current;
      if (map) {
        const target = updated.find((d) => d.id === layerId);
        if (target && map.getLayer(layerId)) {
          map.setLayoutProperty(layerId, "visibility", target.visible ? "visible" : "none");
        }
      }
      return updated;
    });
  }, []);

  // Fetch available departure times on mount
  useEffect(() => {
    fetch(`${API_BASE}/cells/departure-times`, {
      headers: { "X-Tenant-ID": DEMO_TENANT },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((times: string[] | null) => {
        if (times && times.length > 0) {
          setAvailableTimes(times);
          // Keep current index if valid, otherwise snap to nearest
          const currentTime = TIME_SLOTS[timeIndex];
          const idx = times.indexOf(currentTime);
          if (idx === -1) {
            // Find the closest available slot to 08:00
            const defaultIdx = times.indexOf("08:00");
            setTimeIndex(defaultIdx >= 0 ? defaultIdx : 0);
          } else {
            setTimeIndex(idx);
          }
        }
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const departureTime = availableTimes[timeIndex] ?? "08:00";

  // Re-fetch cells when purpose, metric, departure time, or resolution changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const controller = new AbortController();

    const params = new URLSearchParams();
    if (selectedPurpose) {
      params.set("mode", "TRANSIT");
      params.set("purpose", selectedPurpose);
    }
    if (metric === "travel_time") {
      params.set("metric", "travel_time");
    }
    params.set("departure_time", departureTime);
    if (resolution !== 100) {
      params.set("resolution", String(resolution));
    }
    const qs = params.toString();

    const url = `${API_BASE}/cells/geojson${qs ? `?${qs}` : ""}`;
    const mlMap = map as unknown as MaplibreMap;

    fetch(url, {
      headers: { "X-Tenant-ID": DEMO_TENANT },
      signal: controller.signal,
    })
      .then((res) => {
        if (!res.ok) {
          console.error(`[cells] ${res.status} ${res.statusText} – ${url}`);
          return null;
        }
        return res.json();
      })
      .then((data) => {
        if (!data) return;
        console.info(`[cells] loaded ${data.features?.length ?? 0} features (${resolution} m)`);
        const source = mlMap.getSource("cells");
        if (source && "setData" in source) {
          (source as { setData: (d: unknown) => void }).setData(data);
          mlMap.triggerRepaint();
        }
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        console.error("[cells] fetch failed:", err);
      });

    // Update the fill color expression to match the active metric
    if (map.getLayer("cells-fill")) {
      const expr = metric === "travel_time"
        ? TRAVEL_TIME_STEP_EXPR
        : [
            "interpolate", ["linear"],
            ["coalesce", ["get", "score"], 0],
            ...SCORE_COLORS.flatMap(([stop, color]) => [stop, color]),
          ];
      mlMap.setPaintProperty("cells-fill", "fill-color", expr);
    }

    // Adjust outline width – thicker for coarse grids, still visible for 100 m
    if (map.getLayer("cells-outline")) {
      const width = resolution >= 1000 ? 1.5 : resolution >= 500 ? 0.8 : resolution >= 200 ? 0.5 : 0.3;
      mlMap.setPaintProperty("cells-outline", "line-width", width);
    }

    return () => controller.abort();
  }, [selectedPurpose, metric, departureTime, resolution, mapReady]);

  // ── Opacity sync ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const set = (layer: string, prop: string, val: number) => {
      if (map.getLayer(layer)) {
        (map as unknown as { setPaintProperty: (l: string, p: string, v: number) => void })
          .setPaintProperty(layer, prop, val);
      }
    };
    set("cells-fill", "fill-opacity", fillOpacity);
    set("cells-hatch", "fill-opacity", fillOpacity);
    set("cells-outline", "line-opacity", fillOpacity);
  }, [fillOpacity, mapReady]);

  // ── Map initialisation ──
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;
    let cancelled = false;

    async function init() {
      try {
        const maplibregl = await import("maplibre-gl");
        if (cancelled) return;
        setStatus("map.creatingMap");

        const map = new maplibregl.Map({
          container: mapContainer.current!,
          style: {
            version: 8 as const,
            glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
            sources: {
              osm: {
                type: "raster" as const,
                tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                tileSize: 256,
                attribution: "&copy; OpenStreetMap contributors",
              },
            },
            layers: [{
              id: "osm-tiles", type: "raster" as const, source: "osm",
              minzoom: 0, maxzoom: 19,
            }],
          },
          center: DEFAULT_CENTER,
          zoom: DEFAULT_ZOOM,
        });

        map.addControl(new maplibregl.NavigationControl(), "top-right");
        mapRef.current = map as unknown as MapInstance;

        // Track zoom level → resolution changes
        map.on("zoomend", () => {
          setResolution(getResolution(map.getZoom()));
        });

        map.on("load", async () => {
          try {
            // 1. Grid – source starts empty; the resolution/filter effect loads data
            map.addSource("cells", {
              type: "geojson",
              data: { type: "FeatureCollection" as const, features: [] },
            });
            map.addLayer({
              id: "cells-fill", type: "fill", source: "cells",
              paint: {
                "fill-color": [
                  "interpolate", ["linear"],
                  ["coalesce", ["get", "score"], 0],
                  ...SCORE_COLORS.flatMap(([stop, color]) => [stop, color]),
                ],
                "fill-opacity": 0.7,
              },
            });

            // Diagonal hatch overlay for zero-population cells
            map.addImage("hatch-pattern", createHatchPattern(), { pixelRatio: 2 });
            map.addLayer({
              id: "cells-hatch", type: "fill", source: "cells",
              filter: ["<=", ["coalesce", ["get", "population"], 0], 0],
              paint: {
                "fill-pattern": "hatch-pattern",
                "fill-opacity": 0.85,
              },
            });

            map.addLayer({
              id: "cells-outline", type: "line", source: "cells",
              paint: { "line-color": "#555", "line-width": 0.15 },
            });

            // 2. Region
            setStatus("map.loadingLayers");
            await addGeoJsonLayer(map, `${API_BASE}/boundaries/region/geojson`,
              "region", "region-boundary", "line",
              { "line-color": "#1e293b", "line-width": 3 });

            // 3. Comarcas
            await addGeoJsonLayer(map, `${API_BASE}/boundaries/comarcas/geojson`,
              "comarcas", "comarcas-boundary", "line",
              { "line-color": "#7c3aed", "line-width": 2, "line-dasharray": [4, 2] },
              "none");
            if (map.getSource("comarcas")) {
              map.addLayer({
                id: "comarcas-labels", type: "symbol", source: "comarcas",
                layout: {
                  visibility: "none",
                  "text-field": ["get", "name"],
                  "text-size": ["interpolate", ["linear"], ["zoom"], 9, 12, 13, 15],
                  "text-anchor": "center",
                  "text-letter-spacing": 0.05,
                  "text-allow-overlap": true,
                  "text-ignore-placement": true,
                },
                paint: {
                  "text-color": "#5b21b6",
                  "text-halo-color": "#fff",
                  "text-halo-width": 2,
                },
              });
            }

            // 4. Municipalities
            await addGeoJsonLayer(map, `${API_BASE}/boundaries/municipalities/geojson`,
              "municipalities", "municipalities-boundary", "line",
              { "line-color": "#0e7490", "line-width": 1.2 }, "none");
            if (map.getSource("municipalities")) {
              map.addLayer({
                id: "municipalities-labels", type: "symbol", source: "municipalities",
                layout: {
                  visibility: "none",
                  "text-field": ["get", "name"],
                  "text-size": ["interpolate", ["linear"], ["zoom"], 9, 8, 12, 11, 15, 14],
                  "text-anchor": "center",
                },
                paint: {
                  "text-color": "#0e7490",
                  "text-halo-color": "#fff",
                  "text-halo-width": 1.5,
                },
              });
            }

            // 5. Núcleos (settlement boundaries)
            try {
              const nucleosRes = await fetch(`${API_BASE}/boundaries/nucleos/geojson`, {
                headers: { "X-Tenant-ID": DEMO_TENANT },
              });
              if (nucleosRes.ok) {
                map.addSource("nucleos", { type: "geojson", data: await nucleosRes.json() });
                map.addLayer({
                  id: "nucleos-fill", type: "fill", source: "nucleos",
                  layout: { visibility: "none" },
                  paint: {
                    "fill-color": "#f59e0b",
                    "fill-opacity": 0.15,
                  },
                });
                map.addLayer({
                  id: "nucleos-outline", type: "line", source: "nucleos",
                  layout: { visibility: "none" },
                  paint: {
                    "line-color": "#d97706",
                    "line-width": 1.5,
                  },
                });
              }
            } catch { /* optional */ }

            // 6. Destinations
            setStatus("map.loadingDestinations");
            try {
              const destRes = await fetch(`${API_BASE}/destinations/geojson`, {
                headers: { "X-Tenant-ID": DEMO_TENANT },
              });
              if (destRes.ok) {
                map.addSource("destinations", { type: "geojson", data: await destRes.json() });
                for (const dt of DEST_LAYERS) {
                  map.addLayer({
                    id: dt.id, type: "circle", source: "destinations",
                    layout: { visibility: "none" },
                    filter: ["==", ["get", "type"], dt.type],
                    paint: {
                      "circle-radius": 3, "circle-color": dt.color,
                      "circle-stroke-color": "#fff", "circle-stroke-width": 0.5,
                    },
                  });
                }
              }
            } catch { /* optional */ }

            // 7. Transit routes (all operators, filtered client-side)
            setStatus("map.loadingTransit");
            try {
              const routesRes = await fetch(`${API_BASE}/transit/routes`);
              if (routesRes.ok) {
                const routesData = await routesRes.json();
                map.addSource("transit-routes", { type: "geojson", data: routesData });

                // Build match expression for operator colors
                const colorExpr: unknown[] = ["match", ["get", "operator"]];
                for (const op of OPERATORS) {
                  colorExpr.push(op.id, op.color);
                }
                colorExpr.push("#6b7280"); // fallback

                map.addLayer({
                  id: "transit-routes", type: "line", source: "transit-routes",
                  layout: { visibility: "none" },
                  paint: {
                    "line-color": colorExpr as maplibregl.ExpressionSpecification,
                    "line-width": ["interpolate", ["linear"], ["zoom"], 9, 1.5, 12, 3, 15, 6],
                    "line-opacity": ["interpolate", ["linear"], ["zoom"], 9, 0.6, 13, 0.9],
                  },
                });
              }
            } catch { /* optional */ }

            // 8. Transit stops (all operators, filtered client-side)
            try {
              const stopsRes = await fetch(`${API_BASE}/transit/stops`);
              if (stopsRes.ok) {
                map.addSource("transit-stops", { type: "geojson", data: await stopsRes.json() });

                const stopColorExpr: unknown[] = ["match", ["get", "operator"]];
                for (const op of OPERATORS) {
                  stopColorExpr.push(op.id, op.color);
                }
                stopColorExpr.push("#6b7280");

                map.addLayer({
                  id: "transit-stops", type: "circle", source: "transit-stops",
                  layout: { visibility: "none" },
                  paint: {
                    "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 2, 12, 4, 15, 8],
                    "circle-color": stopColorExpr as maplibregl.ExpressionSpecification,
                    "circle-stroke-color": "#fff",
                    "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 9, 0.3, 13, 1],
                  },
                });
              }
            } catch { /* optional */ }

            setMapReady(true);
            setStatus("");
          } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
          }
        });

        // ── Interactions ──
        map.on("click", "cells-fill", (e) => {
          if (e.features?.[0]) setSelectedCell(e.features[0].properties as CellProperties);
        });

        for (const dt of DEST_LAYERS) {
          map.on("click", dt.id, (e) => {
            if (!e.features?.[0]) return;
            const p = e.features[0].properties;
            new maplibregl.Popup().setLngLat(e.lngLat)
              .setHTML(`<strong>${p?.name ?? ""}</strong><br/><span style="color:#666;font-size:12px">${p?.type_label ?? dt.label}</span>`)
              .addTo(map);
          });
        }

        map.on("click", "transit-stops", (e) => {
          if (!e.features?.[0]) return;
          const p = e.features[0].properties;
          new maplibregl.Popup().setLngLat(e.lngLat)
            .setHTML(`<strong>${p?.stop_name ?? "Stop"}</strong><br/><span style="color:#666;font-size:12px">${p?.operator ?? ""}</span>`)
            .addTo(map);
        });

        map.on("click", "transit-routes", (e) => {
          if (!e.features?.[0]) return;
          const p = e.features[0].properties;
          new maplibregl.Popup().setLngLat(e.lngLat)
            .setHTML(`<strong>${p?.route_name ?? p?.route_id ?? "Route"}</strong><br/><span style="color:#666;font-size:12px">${p?.operator ?? ""}</span>`)
            .addTo(map);
        });

        map.on("click", "municipalities-boundary", (e) => {
          if (!e.features?.[0]) return;
          new maplibregl.Popup().setLngLat(e.lngLat)
            .setHTML(`<strong>${e.features[0].properties?.name ?? ""}</strong>`)
            .addTo(map);
        });

        map.on("click", "nucleos-fill", (e) => {
          if (!e.features?.[0]) return;
          const p = e.features[0].properties;
          new maplibregl.Popup().setLngLat(e.lngLat)
            .setHTML(`<strong>${p?.name ?? ""}</strong><br/><span style="color:#666;font-size:12px">${p?.muni_name ?? ""}</span>`)
            .addTo(map);
        });

        const clickable = ["cells-fill", "transit-stops", "transit-routes", "municipalities-boundary", "nucleos-fill", ...DEST_LAYERS.map((d) => d.id)];
        for (const lid of clickable) {
          map.on("mouseenter", lid, () => { map.getCanvas().style.cursor = "pointer"; });
          map.on("mouseleave", lid, () => { map.getCanvas().style.cursor = ""; });
        }
      } catch (err) {
        setError(`Map init failed: ${err instanceof Error ? err.message : String(err)}`);
      }
    }

    async function addGeoJsonLayer(map: MaplibreMap, url: string, sourceId: string, layerId: string,
      layerType: "line" | "fill", paint: Record<string, unknown>, visibility: "visible" | "none" = "visible") {
      try {
        const res = await fetch(url, { headers: { "X-Tenant-ID": DEMO_TENANT } });
        if (res.ok) {
          map.addSource(sourceId, { type: "geojson", data: await res.json() });
          map.addLayer({ id: layerId, type: layerType, source: sourceId, layout: { visibility }, paint } as Parameters<MaplibreMap["addLayer"]>[0]);
        }
      } catch { /* optional */ }
    }

    init();
    return () => { cancelled = true; mapRef.current?.remove(); mapRef.current = null; };
  }, []);

  const activePoi = POI_TYPES.find((p) => p.value === selectedPurpose);

  const timePeriod = (() => {
    const h = parseInt(departureTime.split(":")[0], 10);
    if (h >= 7 && h <= 9) return t("map.amPeak");
    if (h >= 17 && h <= 19) return t("map.pmPeak");
    if (h >= 10 && h <= 16) return t("map.midday");
    if (h >= 20 && h <= 22) return t("map.evening");
    return t("map.night");
  })();

  return (
    <div className="absolute inset-0">
      <div ref={mapContainer} style={{ width: "100%", height: "100%" }} />

      {/* ── Panel toggle (visible when collapsed) ── */}
      {!panelOpen && (
        <button
          onClick={() => setPanelOpen(true)}
          className="absolute top-2 left-2 z-10 h-8 w-8 flex items-center justify-center rounded-md bg-background/90 backdrop-blur-sm border shadow-md text-muted-foreground hover:text-foreground transition-colors"
          title={t("map.openPanel")}
        >
          <PanelLeft className="h-4 w-4" />
        </button>
      )}

      {/* ── Control Panel ── */}
      <div
        className={`absolute inset-y-0 left-0 z-10 w-64 bg-background/95 backdrop-blur-sm border-r flex flex-col transition-transform duration-200 ${
          panelOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Panel header */}
        <div className="flex items-center justify-between px-3 h-10 border-b border-border/60 flex-shrink-0">
          <span className="text-xs font-semibold tracking-wide text-foreground">{t("map.controls")}</span>
          <button
            onClick={() => setPanelOpen(false)}
            className="h-6 w-6 flex items-center justify-center rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            title={t("map.collapsePanel")}
          >
            <PanelLeftClose className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">

          {/* Metric */}
          <Section title={t("map.metric")} open={openSections.metric} onToggle={() => toggleSection("metric")}>
            <div className="flex gap-1">
              {(["score", "travel_time"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMetric(m)}
                  className={`flex-1 rounded px-2 py-1.5 text-xs font-medium transition-colors ${
                    metric === m
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary/50 text-secondary-foreground hover:bg-secondary"
                  }`}
                >
                  {m === "score" ? t("map.metricScore") : t("map.metricTravelTime")}
                </button>
              ))}
            </div>
          </Section>

          {/* Departure Time */}
          <Section title={t("map.departureTime")} open={openSections.time} onToggle={() => toggleSection("time")}>
            <div className="flex items-center gap-2">
              <span className="text-lg font-mono font-semibold tabular-nums min-w-[3.5rem]">
                {departureTime}
              </span>
              <span className="text-[10px] text-muted-foreground">{timePeriod}</span>
            </div>
            <input
              type="range"
              min={0}
              max={availableTimes.length - 1}
              value={timeIndex}
              onChange={(e) => setTimeIndex(Number(e.target.value))}
              className="w-full mt-1 accent-primary"
            />
            <div className="flex justify-between text-[9px] text-muted-foreground mt-0.5">
              <span>{availableTimes[0]}</span>
              <span>{availableTimes[Math.floor(availableTimes.length / 2)]}</span>
              <span>{availableTimes[availableTimes.length - 1]}</span>
            </div>
          </Section>

          {/* Destination filter + legend */}
          <Section
            title={metric === "travel_time" ? t("map.nearestDestination") : t("map.accessibility")}
            open={openSections.destination}
            onToggle={() => toggleSection("destination")}
          >
            <div className="space-y-1">
              {POI_TYPES.map((p) => (
                <button
                  key={p.label}
                  onClick={() => setSelectedPurpose(p.value)}
                  className={`w-full rounded px-2.5 py-1.5 text-left text-xs transition-colors flex items-center gap-2 ${
                    selectedPurpose === p.value
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary/50 text-secondary-foreground hover:bg-secondary"
                  }`}
                >
                  {p.value && "color" in p && (
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: (p as { color: string }).color }}
                    />
                  )}
                  <span className="font-medium">{p.value === null ? t("map.combined") : p.label}</span>
                </button>
              ))}
            </div>

            {/* Legend */}
            <div className="mt-3 pt-2 border-t">
              <p className="text-[10px] text-muted-foreground mb-1.5">
                {metric === "travel_time"
                  ? selectedPurpose
                    ? `${t("map.minutesToNearest")} ${activePoi?.label?.toLowerCase() ?? "destination"} ${t("map.transit")}`
                    : t("map.avgMinToNearest")
                  : (activePoi ? t(activePoi.descKey) : t("map.weightedAvgAll")) +
                    (selectedPurpose ? ` ${t("map.publicTransport")}` : "")}
              </p>
              {metric === "travel_time" ? (
                <div className="space-y-0.5">
                  {TRAVEL_TIME_BANDS.map((band) => (
                    <div key={band.label} className="flex items-center gap-1.5">
                      <span
                        className="inline-block w-3 h-3 rounded-sm flex-shrink-0"
                        style={{ backgroundColor: band.color }}
                      />
                      <span className="text-[10px] text-muted-foreground">{band.label}</span>
                    </div>
                  ))}
                  <div className="flex items-center gap-1.5">
                    <span
                      className="inline-block w-3 h-3 rounded-sm flex-shrink-0"
                      style={{ backgroundColor: TRAVEL_TIME_NO_DATA_COLOR }}
                    />
                    <span className="text-[10px] text-muted-foreground">{TRAVEL_TIME_NO_DATA_LABEL}</span>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-muted-foreground">{t("map.low")}</span>
                  <div className="flex h-3 flex-1 rounded-sm overflow-hidden">
                    {SCORE_COLORS.map(([, color]) => (
                      <div key={color} className="flex-1" style={{ backgroundColor: color }} />
                    ))}
                  </div>
                  <span className="text-[10px] text-muted-foreground">{t("map.high")}</span>
                </div>
              )}
              {/* No-population hatch legend */}
              <div className="flex items-center gap-1.5 mt-1.5">
                <span
                  className="inline-block w-3 h-3 rounded-sm flex-shrink-0 border border-border/60"
                  style={{
                    background: "repeating-linear-gradient(-45deg, transparent, transparent 2px, rgba(120,120,120,0.45) 2px, rgba(120,120,120,0.45) 3px)",
                  }}
                />
                <span className="text-[10px] text-muted-foreground">{t("map.noPopulation")}</span>
              </div>
            </div>
          </Section>

          {/* Layers */}
          <Section title={t("map.layers")} open={openSections.layers} onToggle={() => toggleSection("layers")}>
            {baseLayers.map((layer) => (
              <label key={layer.id} className="flex items-center gap-2 text-xs cursor-pointer py-0.5">
                <input
                  type="checkbox"
                  checked={layer.visible}
                  onChange={() => toggleBaseLayer(layer.id)}
                  className="rounded border-input"
                />
                {t(layer.labelKey)}
              </label>
            ))}
            <div className="mt-3 pt-3 border-t">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-muted-foreground">{t("map.gridOpacity")}</span>
                <span className="text-xs font-mono text-muted-foreground w-8 text-right">
                  {Math.round(fillOpacity * 100)}%
                </span>
              </div>
              <input
                type="range"
                min={5}
                max={100}
                value={Math.round(fillOpacity * 100)}
                onChange={(e) => setFillOpacity(Number(e.target.value) / 100)}
                className="w-full h-1.5 bg-secondary rounded-full appearance-none cursor-pointer accent-primary"
              />
            </div>
          </Section>

          {/* Destination markers */}
          <Section title={t("map.destinations")} open={openSections.destinations} onToggle={() => toggleSection("destinations")}>
            {destToggles.map((dt) => (
              <label key={dt.id} className="flex items-center gap-2 text-xs cursor-pointer py-0.5">
                <input
                  type="checkbox"
                  checked={dt.visible}
                  onChange={() => toggleDestination(dt.id)}
                  className="rounded border-input"
                />
                <span
                  className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: dt.color }}
                />
                {dt.label}
              </label>
            ))}
          </Section>

          {/* Public Transport */}
          <Section title={t("map.publicTransportSection")} open={openSections.transit} onToggle={() => toggleSection("transit")}>
            {/* Global Routes / Stops toggle */}
            <div className="flex gap-1 mb-2.5">
              <button
                onClick={handleToggleRoutes}
                className={`flex-1 rounded px-2 py-1.5 text-xs font-medium transition-colors ${
                  showRoutes
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary/50 text-secondary-foreground hover:bg-secondary"
                }`}
              >
                {t("map.routes")}
              </button>
              <button
                onClick={handleToggleStops}
                className={`flex-1 rounded px-2 py-1.5 text-xs font-medium transition-colors ${
                  showStops
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary/50 text-secondary-foreground hover:bg-secondary"
                }`}
              >
                {t("map.stops")}
              </button>
            </div>

            {/* Per-operator checkboxes */}
            {(showRoutes || showStops) && (
              <div className="space-y-0.5">
                {operators.map((op) => (
                  <label key={op.id} className="flex items-center gap-2 text-xs cursor-pointer py-0.5">
                    <input
                      type="checkbox"
                      checked={op.visible}
                      onChange={() =>
                        setOperators((prev) =>
                          prev.map((o) => (o.id === op.id ? { ...o, visible: !o.visible } : o)),
                        )
                      }
                      className="rounded border-input"
                    />
                    <span
                      className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: op.color }}
                    />
                    <span className="truncate">{op.label}</span>
                  </label>
                ))}
              </div>
            )}
          </Section>

        </div>
      </div>

      {/* Status / Error */}
      {status && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 rounded-md bg-background/90 px-4 py-2 text-sm text-muted-foreground shadow">
          {t(status)}
        </div>
      )}
      {error && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 rounded-md bg-destructive/10 border border-destructive px-4 py-2 text-sm text-destructive shadow">
          {error}
        </div>
      )}

      {/* Cell detail */}
      {selectedCell && (
        <div className="absolute bottom-4 right-4 z-10 w-64 rounded-lg border bg-background p-4 shadow-lg">
          <div className="flex items-start justify-between">
            <h3 className="font-semibold text-sm">{t("map.cellDetails")}</h3>
            <button
              onClick={() => setSelectedCell(null)}
              className="text-muted-foreground hover:text-foreground text-xs"
            >
              {t("map.close")}
            </button>
          </div>
          <div className="mt-3 space-y-1.5 text-sm">
            <Row label={t("map.code")} value={selectedCell.cell_code} />
            {selectedCell.id != null && <Row label={t("map.id")} value={String(selectedCell.id)} />}
            <Row label={t("map.resolution")} value={RESOLUTION_LABELS[resolution] ?? `${resolution} m`} />
            <Row label={t("map.population")} value={Number(selectedCell.population).toFixed(0)} />
            <Row
              label={
                metric === "travel_time"
                  ? `${activePoi?.label ?? "Avg"} (min)`
                  : activePoi?.label ?? t("map.combined")
              }
              value={
                selectedCell.score != null
                  ? metric === "travel_time"
                    ? `${Number(selectedCell.score).toFixed(0)} min`
                    : Number(selectedCell.score).toFixed(1)
                  : "\u2014"
              }
            />
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Helper components ── */

function Section({
  title,
  open,
  onToggle,
  children,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-border/60">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between px-3 py-2.5 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
      >
        {title}
        <ChevronDown
          className={`h-3.5 w-3.5 transition-transform duration-150 ${open ? "" : "-rotate-90"}`}
        />
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}
