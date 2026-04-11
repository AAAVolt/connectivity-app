"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { IconLayoutSidebar as PanelLeft } from "@tabler/icons-react";
import type { Map as MaplibreMap } from "maplibre-gl";
import { useTranslation } from "@/lib/i18n";
import { getResolution as getGridResolution } from "@/lib/map-3d";
import {
  boundaryQueryOptions,
  destTypesQueryOptions,
  destinationsQueryOptions,
  transitRoutesQueryOptions,
  transitStopsQueryOptions,
  nucleosQueryOptions,
  departureTimesQueryOptions,
  cellsQueryOptions,
  frequencyQueryOptions,
  socialMunisQueryOptions,
  socioProfilesQueryOptions,
} from "@/hooks/use-map-data";
import { MapControlPanel } from "@/components/map/map-control-panel";
import {
  SCORE_COLORS,
  TRAVEL_TIME_BANDS,
  SOCIAL_PAINT,
  OPERATORS,
  TRAVEL_TIME_NO_DATA_COLOR,
  BASEMAP_OPTIONS,
} from "@/components/map/map-panel-types";
import type {
  MetricType,
  BasemapId,
  Perspective,
  PoiType,
  DestType,
  DestLayer,
  LayerToggle,
  OperatorState,
  CellProperties,
} from "@/components/map/map-panel-types";

const DEFAULT_CENTER: [number, number] = [-2.87, 43.22];
const DEFAULT_ZOOM = 10;

// ── Time-of-day slots (every 30 min, 0–47 → "00:00"–"23:30") ──
const TIME_SLOTS: string[] = Array.from({ length: 48 }, (_, i) => {
  const h = Math.floor(i / 2);
  const m = (i % 2) * 30;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
});
const DEFAULT_TIME_INDEX = 16; // 08:00

// ── Color palette for dynamically-loaded destination types ──
const DEST_COLOR_PALETTE = [
  "#6366f1", "#f59e0b", "#eab308", "#8b5cf6", "#ef4444",
  "#64748b", "#dc2626", "#f97316", "#14b8a6", "#22c55e",
  "#0ea5e9", "#a855f7", "#ec4899", "#84cc16", "#06b6d4",
];

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


/** Basemap raster tile definitions */
const BASEMAP_TILES: Record<BasemapId, { tiles: string[]; tileSize: number; attribution: string; maxzoom: number }> = {
  osm: {
    tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
    tileSize: 256, maxzoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  },
  positron: {
    tiles: ["https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png"],
    tileSize: 256, maxzoom: 20,
    attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
  },
  dark: {
    tiles: ["https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png"],
    tileSize: 256, maxzoom: 20,
    attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
  },
  satellite: {
    tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
    tileSize: 256, maxzoom: 19,
    attribution: "&copy; Esri",
  },
};

/** Build POI_TYPES and DEST_LAYERS from API response */
function buildDestMeta(types: DestType[]): { poiTypes: PoiType[]; destLayers: DestLayer[] } {
  const poiTypes: PoiType[] = [
    { value: null, label: "Combined", descKey: "map.allDestTypes" },
  ];
  const destLayers: DestLayer[] = [];
  for (let i = 0; i < types.length; i++) {
    const dt = types[i];
    const color = DEST_COLOR_PALETTE[i % DEST_COLOR_PALETTE.length];
    poiTypes.push({
      value: dt.code,
      label: dt.label,
      descKey: `poi.${dt.code}`,
      color,
    });
    destLayers.push({
      id: `dest-${dt.code.replace(/_/g, "-")}`,
      type: dt.code,
      color,
      label: dt.label,
    });
  }
  return { poiTypes, destLayers };
}

// ── Zoom → grid resolution mapping (delegates to map-3d.ts) ──
const getResolution = getGridResolution;


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

type MapInstance = {
  getSource: (id: string) => { setData: (data: unknown) => void } | undefined;
  getLayer: (id: string) => unknown;
  setLayoutProperty: (id: string, prop: string, val: string) => void;
  setFilter: (id: string, filter: unknown) => void;
  remove: () => void;
};


function applySocialPaint(map: MaplibreMap, layer: string) {
  const cfg = SOCIAL_PAINT[layer];
  if (!cfg || !map.getLayer("social-fill")) return;

  const colorExpr: unknown[] = [
    "interpolate", ["linear"],
    ["coalesce", ["get", cfg.prop], 0],
  ];
  for (const [stop, color] of cfg.stops) {
    colorExpr.push(stop, color);
  }
  map.setPaintProperty("social-fill", "fill-color", colorExpr);
}

/** Build consistent popup HTML for municipality clicks (both boundary & social-fill layers). */
function buildMuniPopupHtml(
  name: string,
  p: Record<string, unknown> | null,
  t: (key: string) => string,
): string {
  if (!p) return `<strong style="font-size:13px">${name}</strong>`;

  const val = (key: string, decimals: number, suffix = ""): string => {
    const v = p[key];
    return v != null ? Number(v).toFixed(decimals) + suffix : "—";
  };
  const pop = p.pop_total != null
    ? Math.round(Number(p.pop_total)).toLocaleString()
    : p.population != null
      ? Math.round(Number(p.population)).toLocaleString()
      : "—";

  return (
    `<strong style="font-size:13px">${name}</strong>` +
    `<div style="margin-top:6px;font-size:11px;line-height:1.7">` +
    `<div><b>${t("popup.population")}:</b> ${pop}</div>` +
    `<div><b>${t("popup.connectivity")}:</b> ${val("weighted_avg_score", 1)}/100</div>` +
    `<div style="border-top:1px solid #eee;margin:3px 0;padding-top:3px">` +
    `<div><b>${t("popup.elderly")}:</b> ${val("pct_65_plus", 1, "%")}</div>` +
    `<div><b>${t("popup.youth")}:</b> ${val("pct_0_17", 1, "%")}</div>` +
    `<div><b>${t("popup.youngAdults")}:</b> ${val("pct_18_25", 1, "%")}</div>` +
    `</div>` +
    `<div style="border-top:1px solid #eee;margin:3px 0;padding-top:3px">` +
    `<div><b>${t("popup.incomeIndex")}:</b> ${val("renta_index", 1)}</div>` +
    `<div><b>${t("popup.carsPerInhab")}:</b> ${val("vehicles_per_inhab", 2)}</div>` +
    `</div>` +
    `<div style="border-top:1px solid #eee;margin:3px 0;padding-top:3px">` +
    `<div><b>${t("popup.vulnerability")}:</b> ${val("vulnerability", 2)}</div>` +
    `</div>` +
    `</div>`
  );
}

const BASE_LAYER_MAPPING: Record<string, string[]> = {
  cells: ["cells-fill", "cells-hatch", "cells-outline"],
  region: ["region-boundary"],
  comarcas: ["comarcas-boundary"],
  municipalities: ["municipalities-boundary"],
  nucleos: ["nucleos-fill", "nucleos-outline"],
  labels: ["comarcas-labels", "municipalities-labels"],
  frequency: ["freq-circles"],
};

export default function ConnectivityMap() {
  const { t } = useTranslation();
  const tRef = useRef(t);
  tRef.current = t;
  const queryClient = useQueryClient();
  const queryClientRef = useRef(queryClient);
  queryClientRef.current = queryClient;
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

  // Dynamic destination types from API
  const [poiTypes, setPoiTypes] = useState<PoiType[]>([
    { value: null, label: "Combined", descKey: "map.allDestTypes" },
  ]);
  const [destLayers, setDestLayers] = useState<DestLayer[]>([]);

  // Per-POI-type destination toggles (initialised once destLayers are fetched)
  const [destToggles, setDestToggles] = useState<{ id: string; label: string; color: string; visible: boolean }[]>([]);

  // Per-operator visibility + global route/stop toggles
  const [operators, setOperators] = useState<OperatorState[]>(
    OPERATORS.map((op) => ({ id: op.id, label: op.label, color: op.color, visible: false })),
  );
  const [showRoutes, setShowRoutes] = useState(false);
  const [showStops, setShowStops] = useState(false);
  const [showFrequency, setShowFrequency] = useState(false);
  const [freqWindow, setFreqWindow] = useState("07:00-09:00");
  const [socialLayer, setSocialLayer] = useState<string | null>(null);
  const [fillOpacity, setFillOpacity] = useState(0.7);

  // Basemap
  const [basemap, setBasemap] = useState<BasemapId>("osm");

  // 3D mode / perspective
  const [perspective, setPerspective] = useState<Perspective>("2d");
  const [showTerrain, setShowTerrain] = useState(false);
  const [showBuildings, setShowBuildings] = useState(false);

  // Panel collapse
  const [panelOpen, setPanelOpen] = useState(true);

  // Collapsible section state
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    metric: false,
    time: false,
    destination: false,
    social: false,
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

  // Reactive frequency layer
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    if (!showFrequency) {
      if (map.getLayer("freq-circles")) {
        map.setLayoutProperty("freq-circles", "visibility", "none");
      }
      return;
    }

    let cancelled = false;
    queryClientRef.current.fetchQuery(frequencyQueryOptions(freqWindow))
      .then((data) => {
        if (cancelled || !data) return;
        const mlMap = map as unknown as MaplibreMap;
        const source = mlMap.getSource("frequency");
        if (source && "setData" in source) {
          (source as { setData: (d: unknown) => void }).setData(data);
        }
        if (map.getLayer("freq-circles")) {
          map.setLayoutProperty("freq-circles", "visibility", "visible");
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setError("Failed to load frequency data");
      });

    return () => { cancelled = true; };
  }, [showFrequency, freqWindow, mapReady]);

  // Social choropleth layer reactivity
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const mlMap = map as unknown as MaplibreMap;

    if (!socialLayer) {
      if (map.getLayer("social-fill")) map.setLayoutProperty("social-fill", "visibility", "none");
      if (map.getLayer("social-outline")) map.setLayoutProperty("social-outline", "visibility", "none");
      return;
    }

    // Load data if source doesn't exist yet
    const source = mlMap.getSource("social-munis");
    if (!source) {
      let cancelled = false;
      queryClientRef.current.ensureQueryData(socialMunisQueryOptions())
        .then((data) => {
          if (cancelled || !data) return;
          mlMap.addSource("social-munis", { type: "geojson", data });
          mlMap.addLayer({
            id: "social-fill", type: "fill", source: "social-munis",
            paint: { "fill-color": "#888", "fill-opacity": 0.55 },
          }, "cells-fill");
          mlMap.addLayer({
            id: "social-outline", type: "line", source: "social-munis",
            paint: { "line-color": "#333", "line-width": 1 },
          }, "cells-fill");
          applySocialPaint(mlMap, socialLayer);
        })
        .catch((err) => {
          if (cancelled) return;
          setError("Failed to load sociodemographic layer");
        });
      return () => { cancelled = true; };
    } else {
      if (map.getLayer("social-fill")) {
        map.setLayoutProperty("social-fill", "visibility", "visible");
        map.setLayoutProperty("social-outline", "visibility", "visible");
        applySocialPaint(mlMap, socialLayer);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [socialLayer, mapReady]);

  const handleToggleFrequency = useCallback(() => {
    setShowFrequency((prev) => {
      const next = !prev;
      if (next) {
        // Auto-select all operators when enabling
        setOperators((ops) =>
          ops.every((o) => !o.visible) ? ops.map((o) => ({ ...o, visible: true })) : ops,
        );
      }
      return next;
    });
  }, []);

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

  // Fetch available departure times on mount (via React Query cache)
  useEffect(() => {
    queryClientRef.current.ensureQueryData(departureTimesQueryOptions())
      .then((times: string[]) => {
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
      .catch(() => { setError("Failed to load departure times"); });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const departureTime = availableTimes[timeIndex] ?? "08:00";

  // Re-fetch cells when purpose, metric, departure time, or resolution changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    let cancelled = false;
    const mlMap = map as unknown as MaplibreMap;

    queryClientRef.current.fetchQuery(cellsQueryOptions({
      mode: selectedPurpose ? "TRANSIT" : undefined,
      purpose: selectedPurpose ?? undefined,
      metric,
      resolution,
      departureTime,
    }))
      .then((data) => {
        if (cancelled || !data) return;
        const source = mlMap.getSource("cells");
        if (source && "setData" in source) {
          (source as { setData: (d: unknown) => void }).setData(data);
          mlMap.triggerRepaint();
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setError("Failed to load grid cells");
      });

    // Update the fill color expression to match the active metric
    const colorExpr = metric === "travel_time"
      ? TRAVEL_TIME_STEP_EXPR
      : [
          "interpolate", ["linear"],
          ["coalesce", ["get", "score"], 0],
          ...SCORE_COLORS.flatMap(([stop, color]) => [stop, color]),
        ];

    if (map.getLayer("cells-fill")) {
      mlMap.setPaintProperty("cells-fill", "fill-color", colorExpr);
    }

    // Adjust outline width – thicker for coarse grids, still visible for 100 m
    if (map.getLayer("cells-outline")) {
      const width = resolution >= 1000 ? 1.5 : resolution >= 500 ? 0.8 : resolution >= 200 ? 0.5 : 0.3;
      mlMap.setPaintProperty("cells-outline", "line-width", width);
    }

    return () => { cancelled = true; };
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

  // ── Buildings + sky visibility ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    try {
      if (map.getLayer("3d-buildings")) {
        map.setLayoutProperty("3d-buildings", "visibility", showBuildings ? "visible" : "none");
      }
      if (map.getLayer("sky")) {
        map.setLayoutProperty("sky", "visibility", perspective === "3d" ? "visible" : "none");
      }
    } catch (err) {
      console.error("[3D] layer toggle failed:", err);
    }
  }, [showBuildings, perspective, mapReady]);

  // ── Terrain toggle ──
  // DEM source is in the initial style, so tiles are already loading.
  // setTerrain exists on MaplibreMap (v4.1+) — call it directly.
  // Camera pitch is handled separately by the perspective toggle.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const mlMap = map as unknown as MaplibreMap;

    try {
      if (showTerrain) {
        mlMap.setTerrain({ source: "terrain-dem", exaggeration: 1.5 });
        if (map.getLayer("hillshade-layer")) {
          map.setLayoutProperty("hillshade-layer", "visibility", "visible");
        }
      } else {
        mlMap.setTerrain(null);
        if (map.getLayer("hillshade-layer")) {
          map.setLayoutProperty("hillshade-layer", "visibility", "none");
        }
      }
    } catch (err) {
      console.error("[terrain]", err);
    }
  }, [showTerrain, mapReady]);

  // ── Perspective toggle (2D ↔ 3D camera) ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const mlMap = map as unknown as MaplibreMap;

    if (perspective === "3d") {
      mlMap.easeTo({ pitch: 50, duration: 800 });
    } else {
      mlMap.easeTo({ pitch: 0, bearing: 0, duration: 800 });
    }
  }, [perspective, mapReady]);

  // ── Basemap switching ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    for (const bm of BASEMAP_OPTIONS) {
      const layerId = `${bm.id}-tiles`;
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, "visibility", bm.id === basemap ? "visible" : "none");
      }
    }

    // Adjust label halo color for dark/satellite basemaps so text stays readable
    const isDark = basemap === "dark" || basemap === "satellite";
    const mlMap = map as unknown as MaplibreMap;
    for (const lid of ["comarcas-labels", "municipalities-labels"]) {
      if (map.getLayer(lid)) {
        mlMap.setPaintProperty(lid, "text-halo-color", isDark ? "#1a1a1a" : "#fff");
      }
    }
  }, [basemap, mapReady]);



  // ── Map initialisation ──
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;
    let cancelled = false;

    async function init() {
      try {
        const maplibregl = await import("maplibre-gl");
        if (cancelled) return;
        setStatus("map.creatingMap");

        // Build basemap sources dynamically
        const basemapSources: Record<string, { type: "raster"; tiles: string[]; tileSize: number; attribution: string; maxzoom: number }> = {};
        for (const [id, def] of Object.entries(BASEMAP_TILES)) {
          basemapSources[id] = { type: "raster" as const, ...def };
        }

        // Build basemap layers (only "osm" visible by default)
        const basemapLayers = Object.keys(BASEMAP_TILES).map((id) => ({
          id: `${id}-tiles`,
          type: "raster" as const,
          source: id,
          minzoom: 0,
          maxzoom: BASEMAP_TILES[id as BasemapId].maxzoom,
          ...(id !== "osm" ? { layout: { visibility: "none" as const } } : {}),
        }));

        const map = new maplibregl.Map({
          container: mapContainer.current!,
          style: {
            version: 8 as const,
            glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
            sources: {
              ...basemapSources,
              "terrain-dem": {
                type: "raster-dem" as const,
                tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
                encoding: "terrarium" as const,
                tileSize: 256,
                maxzoom: 15,
              },
              "hillshade-dem": {
                type: "raster-dem" as const,
                tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
                encoding: "terrarium" as const,
                tileSize: 256,
                maxzoom: 15,
              },
              "openfree": {
                type: "vector" as const,
                url: "https://tiles.openfreemap.org/planet",
              },
            },
            layers: [
              ...basemapLayers,
              {
                id: "hillshade-layer", type: "hillshade" as const, source: "hillshade-dem",
                layout: { visibility: "none" as const },
                paint: {
                  "hillshade-shadow-color": "#473B24",
                  "hillshade-illumination-anchor": "map" as const,
                  "hillshade-exaggeration": 0.25,
                },
              },
              {
                id: "3d-buildings", type: "fill-extrusion" as const, source: "openfree",
                "source-layer": "building",
                layout: { visibility: "none" as const },
                minzoom: 14,
                filter: ["!=", ["get", "hide_3d"], true],
                paint: {
                  "fill-extrusion-color": [
                    "interpolate", ["linear"], ["get", "render_height"],
                    0, "#e8e0d8",
                    20, "#d4c8b8",
                    50, "#bfb09a",
                    100, "#a89880",
                  ],
                  "fill-extrusion-height": ["coalesce", ["get", "render_height"], 5],
                  "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
                  "fill-extrusion-opacity": 0.7,
                },
              },
            ],
          },
          center: DEFAULT_CENTER,
          zoom: DEFAULT_ZOOM,
          maxPitch: 85,
        });

        // Navigation controls
        map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
        map.addControl(new maplibregl.GeolocateControl({
          positionOptions: { enableHighAccuracy: true },
          trackUserLocation: false,
        }), "top-right");
        map.addControl(new maplibregl.FullscreenControl(), "top-right");
        map.addControl(new maplibregl.ScaleControl({ maxWidth: 200 }), "bottom-right");
        mapRef.current = map as unknown as MapInstance;

        // Track zoom level → resolution changes
        map.on("zoomend", () => {
          setResolution(getResolution(map.getZoom()));
        });

        // Destination layers (populated during load from API)
        let dl: DestLayer[] = [];

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

            // ── Tier 1: Boundary layers (parallel, via React Query cache) ──
            setStatus("map.loadingLayers");
            const qc = queryClientRef.current;

            const addCachedGeoJsonLayer = async (
              queryOpts: { queryKey: readonly unknown[]; queryFn: () => Promise<unknown>; staleTime: number },
              sourceId: string, layerId: string, layerType: "line" | "fill",
              paint: Record<string, unknown>, visibility: "visible" | "none" = "visible",
            ) => {
              try {
                const data = await qc.ensureQueryData(queryOpts);
                if (data) {
                  map.addSource(sourceId, { type: "geojson", data: data as GeoJSON.FeatureCollection });
                  map.addLayer({ id: layerId, type: layerType, source: sourceId, layout: { visibility }, paint } as Parameters<MaplibreMap["addLayer"]>[0]);
                }
              } catch (e) { console.warn("[map] optional layer failed:", e); }
            };

            await Promise.allSettled([
              addCachedGeoJsonLayer(boundaryQueryOptions("region"),
                "region", "region-boundary", "line",
                { "line-color": "#1e293b", "line-width": 3 }),
              addCachedGeoJsonLayer(boundaryQueryOptions("comarcas"),
                "comarcas", "comarcas-boundary", "line",
                { "line-color": "#7c3aed", "line-width": 2, "line-dasharray": [4, 2] },
                "none"),
              addCachedGeoJsonLayer(boundaryQueryOptions("municipalities"),
                "municipalities", "municipalities-boundary", "line",
                { "line-color": "#0e7490", "line-width": 1.2 }, "none"),
            ]);

            // Add label layers (synchronous, sources must exist)
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

            // ── Tier 2: Data layers (parallel, via React Query cache) ──
            setStatus("map.loadingDestinations");

            const loadNucleos = async () => {
              try {
                const data = await qc.ensureQueryData(nucleosQueryOptions());
                if (data) {
                  map.addSource("nucleos", { type: "geojson", data });
                  map.addLayer({
                    id: "nucleos-fill", type: "fill", source: "nucleos",
                    layout: { visibility: "none" },
                    paint: { "fill-color": "#f59e0b", "fill-opacity": 0.15 },
                  });
                  map.addLayer({
                    id: "nucleos-outline", type: "line", source: "nucleos",
                    layout: { visibility: "none" },
                    paint: { "line-color": "#d97706", "line-width": 1.5 },
                  });
                }
              } catch (e) { console.warn("[map] optional layer failed:", e); }
            };

            const loadDestinations = async () => {
              try {
                const [fetchedTypes, destData] = await Promise.all([
                  qc.ensureQueryData(destTypesQueryOptions()),
                  qc.ensureQueryData(destinationsQueryOptions()),
                ]);
                const meta = buildDestMeta(fetchedTypes ?? []);
                dl = meta.destLayers;
                setPoiTypes(meta.poiTypes);
                setDestLayers(dl);
                setDestToggles(dl.map((d) => ({ id: d.id, label: d.label, color: d.color, visible: false })));

                if (destData) {
                  map.addSource("destinations", { type: "geojson", data: destData });
                  for (const dt of dl) {
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
              } catch (e) { console.warn("[map] optional layer failed:", e); }
            };

            const loadTransitRoutes = async () => {
              try {
                const routesData = await qc.ensureQueryData(transitRoutesQueryOptions());
                if (routesData) {
                  map.addSource("transit-routes", { type: "geojson", data: routesData });

                  const colorExpr: unknown[] = ["match", ["get", "operator"]];
                  for (const op of OPERATORS) {
                    colorExpr.push(op.id, op.color);
                  }
                  colorExpr.push("#6b7280");

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
              } catch (e) { console.warn("[map] optional layer failed:", e); }
            };

            const loadTransitStops = async () => {
              try {
                const stopsData = await qc.ensureQueryData(transitStopsQueryOptions());
                if (stopsData) {
                  map.addSource("transit-stops", { type: "geojson", data: stopsData });

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
              } catch (e) { console.warn("[map] optional layer failed:", e); }
            };

            await Promise.allSettled([
              loadNucleos(),
              loadDestinations(),
              loadTransitRoutes(),
              loadTransitStops(),
            ]);

            // 9. Frequency layer (starts empty, loaded on demand)
            map.addSource("frequency", {
              type: "geojson",
              data: { type: "FeatureCollection" as const, features: [] },
            });
            map.addLayer({
              id: "freq-circles", type: "circle", source: "frequency",
              layout: { visibility: "none" },
              paint: {
                "circle-radius": [
                  "interpolate", ["linear"],
                  ["coalesce", ["get", "departures_per_hour"], 0],
                  0, 3, 3, 5, 6, 8, 15, 14, 30, 20,
                ],
                "circle-color": [
                  "step",
                  ["coalesce", ["get", "departures_per_hour"], 0],
                  "#d73027",    // <1
                  1, "#fee08b", // 1-3
                  3, "#91cf60", // 3-6
                  6, "#1a9850", // 6+
                ],
                "circle-opacity": 0.8,
                "circle-stroke-color": "#fff",
                "circle-stroke-width": 0.5,
              },
            });

            // 10. Sky layer (hidden by default, visible in 3D perspective)
            try {
              map.addLayer({
                id: "sky",
                type: "sky",
                layout: { visibility: "none" },
                paint: {
                  "sky-type": "atmosphere",
                  "sky-atmosphere-sun": [0.0, 90.0],
                  "sky-atmosphere-sun-intensity": 15,
                },
              } as unknown as Parameters<MaplibreMap["addLayer"]>[0]);
            } catch { /* sky layer optional — may not be supported in all builds */ }

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

        // Destination click handlers use the `dl` array captured during init
        for (const dt of dl) {
          map.on("click", dt.id, (e) => {
            if (!e.features?.[0]) return;
            const p = e.features[0].properties;
            new maplibregl.Popup().setLngLat(e.lngLat)
              .setHTML(`<strong>${p?.name ?? ""}</strong><br/><span style="color:#666;font-size:12px">${p?.type_label ?? dt.label}</span>`)
              .addTo(map);
          });
          map.on("mouseenter", dt.id, () => { map.getCanvas().style.cursor = "pointer"; });
          map.on("mouseleave", dt.id, () => { map.getCanvas().style.cursor = ""; });
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

        map.on("click", "municipalities-boundary", async (e) => {
          if (!e.features?.[0]) return;
          const props = e.features[0].properties;
          const muniName = props?.name ?? "";
          const muniCode = props?.muni_code ?? "";

          try {
            const profiles = await queryClientRef.current.ensureQueryData(socioProfilesQueryOptions());
            const p = (profiles ?? []).find(
              (pr: Record<string, unknown>) => pr.muni_code === muniCode || pr.name === muniName,
            );
            new maplibregl.Popup().setLngLat(e.lngLat)
              .setHTML(buildMuniPopupHtml(muniName, p ?? null, tRef.current))
              .addTo(map);
          } catch {
            new maplibregl.Popup().setLngLat(e.lngLat)
              .setHTML(`<strong>${muniName}</strong>`)
              .addTo(map);
          }
        });

        map.on("click", "nucleos-fill", (e) => {
          if (!e.features?.[0]) return;
          const p = e.features[0].properties;
          new maplibregl.Popup().setLngLat(e.lngLat)
            .setHTML(`<strong>${p?.name ?? ""}</strong><br/><span style="color:#666;font-size:12px">${p?.muni_name ?? ""}</span>`)
            .addTo(map);
        });

        map.on("click", "freq-circles", (e) => {
          if (!e.features?.[0]) return;
          const p = e.features[0].properties;
          const dph = Number(p?.departures_per_hour ?? 0).toFixed(1);
          new maplibregl.Popup().setLngLat(e.lngLat)
            .setHTML(
              `<strong>${p?.stop_name ?? "Stop"}</strong><br/>` +
              `<span style="color:#666;font-size:12px">${p?.operator ?? ""}</span><br/>` +
              `<span style="font-size:12px"><b>${dph}</b> dep/hr &middot; ${p?.departures ?? 0} departures</span>`,
            )
            .addTo(map);
        });

        // Social municipality fill click — show full socio profile
        map.on("click", "social-fill", (e) => {
          if (!e.features?.[0]) return;
          const p = e.features[0].properties;
          const name = p?.name ?? "";
          new maplibregl.Popup().setLngLat(e.lngLat)
            .setHTML(buildMuniPopupHtml(name, p ?? null, tRef.current))
            .addTo(map);
        });

        const clickable = ["cells-fill", "social-fill", "transit-stops", "transit-routes", "freq-circles", "municipalities-boundary", "nucleos-fill"];
        for (const lid of clickable) {
          map.on("mouseenter", lid, () => { map.getCanvas().style.cursor = "pointer"; });
          map.on("mouseleave", lid, () => { map.getCanvas().style.cursor = ""; });
        }
      } catch (err) {
        setError(`Map init failed: ${err instanceof Error ? err.message : String(err)}`);
      }
    }

    init();
    return () => { cancelled = true; mapRef.current?.remove(); mapRef.current = null; };
  // Map init runs once. Translation accessed via tRef to avoid re-creating the map.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const activePoi = poiTypes.find((p) => p.value === selectedPurpose);

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
          className="absolute top-2.5 left-2.5 z-10 h-8 w-8 flex items-center justify-center rounded-lg bg-sidebar/95 backdrop-blur-md border border-sidebar-border shadow-md text-sidebar-foreground/50 hover:text-sidebar-foreground transition-colors"
          title={t("map.openPanel")}
        >
          <PanelLeft className="h-4 w-4" />
        </button>
      )}

      <MapControlPanel
        panelOpen={panelOpen}
        setPanelOpen={setPanelOpen}
        openSections={openSections}
        toggleSection={toggleSection}
        metric={metric}
        setMetric={setMetric}
        timeIndex={timeIndex}
        setTimeIndex={setTimeIndex}
        availableTimes={availableTimes}
        departureTime={departureTime}
        timePeriod={timePeriod}
        selectedPurpose={selectedPurpose}
        setSelectedPurpose={setSelectedPurpose}
        poiTypes={poiTypes}
        activePoi={activePoi}
        socialLayer={socialLayer}
        setSocialLayer={setSocialLayer}
        baseLayers={baseLayers}
        toggleBaseLayer={toggleBaseLayer}
        fillOpacity={fillOpacity}
        setFillOpacity={setFillOpacity}
        basemap={basemap}
        setBasemap={setBasemap}
        perspective={perspective}
        setPerspective={setPerspective}
        showBuildings={showBuildings}
        setShowBuildings={setShowBuildings}
        showTerrain={showTerrain}
        setShowTerrain={setShowTerrain}
        resolution={resolution}
        destToggles={destToggles}
        toggleDestination={toggleDestination}
        showRoutes={showRoutes}
        handleToggleRoutes={handleToggleRoutes}
        showStops={showStops}
        handleToggleStops={handleToggleStops}
        showFrequency={showFrequency}
        handleToggleFrequency={handleToggleFrequency}
        freqWindow={freqWindow}
        setFreqWindow={setFreqWindow}
        operators={operators}
        setOperators={setOperators}
        selectedCell={selectedCell}
        setSelectedCell={setSelectedCell}
      />

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
    </div>
  );
}
