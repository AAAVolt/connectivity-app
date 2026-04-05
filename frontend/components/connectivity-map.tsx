"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, PanelLeftClose, PanelLeft } from "lucide-react";
import type { Map as MaplibreMap } from "maplibre-gl";
import { useTranslation } from "@/lib/i18n";
import { buildHeightExpr, getResolution as getGridResolution } from "@/lib/map-3d";

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

// ── Zoom → grid resolution mapping (delegates to map-3d.ts) ──
const getResolution = getGridResolution;

const RESOLUTION_LABELS: Record<number, string> = {
  250: "250 m",
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

// ── Frequency color bands ──
const FREQ_COLORS = {
  high: "#1a9850",   // 6+ /hr
  med: "#91cf60",    // 3–6 /hr
  low: "#fee08b",    // 1–3 /hr
  veryLow: "#d73027", // <1 /hr
};

const FREQ_WINDOWS = [
  "07:00-09:00", "09:00-12:00", "12:00-15:00",
  "15:00-18:00", "18:00-21:00", "06:00-22:00",
];

// Social layer color ramps — semantic direction:
//   elderly:       high % → red (more vulnerable population)
//   income:        low index → red (less purchasing power)
//   cars:          low veh/inhab → red (more transit-dependent)
//   vulnerability: high index → red (composite vulnerability)
const SOCIAL_PAINT: Record<string, { prop: string; stops: [number, string][]; label: string }> = {
  elderly: {
    prop: "pct_65_plus",
    stops: [[15, "#ffffcc"], [20, "#fed976"], [24, "#feb24c"], [28, "#fd8d3c"], [33, "#e31a1c"], [40, "#800026"]],
    label: "% 65+",
  },
  income: {
    prop: "renta_index",
    stops: [[60, "#800026"], [75, "#e31a1c"], [90, "#fd8d3c"], [100, "#ffffcc"], [110, "#addd8e"], [130, "#006837"]],
    label: "Index",
  },
  cars: {
    prop: "vehicles_per_inhab",
    stops: [[0.3, "#800026"], [0.4, "#e31a1c"], [0.5, "#fd8d3c"], [0.6, "#ffffcc"], [0.75, "#addd8e"], [1.0, "#006837"]],
    label: "Veh/inhab",
  },
  vulnerability: {
    prop: "vulnerability",
    stops: [[0.1, "#006837"], [0.25, "#addd8e"], [0.35, "#ffffcc"], [0.45, "#fd8d3c"], [0.55, "#e31a1c"], [0.7, "#800026"]],
    label: "Index",
  },
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

// ── Default extrusion height (meters) for max score ──
const DEFAULT_EXTRUSION_HEIGHT = 400;

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
  const [showFrequency, setShowFrequency] = useState(false);
  const [freqWindow, setFreqWindow] = useState("07:00-09:00");
  const [socialLayer, setSocialLayer] = useState<string | null>(null);
  const [fillOpacity, setFillOpacity] = useState(0.7);

  // 3D mode
  const [is3D, setIs3D] = useState(false);
  const [showTerrain, setShowTerrain] = useState(false);
  const [showBuildings, setShowBuildings] = useState(false);
  const [extrusionHeight, setExtrusionHeight] = useState(DEFAULT_EXTRUSION_HEIGHT);

  // Panel collapse
  const [panelOpen, setPanelOpen] = useState(true);

  // Collapsible section state
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    metric: true,
    time: true,
    destination: true,
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

    // Fetch frequency GeoJSON for the selected time window
    const controller = new AbortController();
    fetch(
      `${API_BASE}/sociodemographic/frequency/geojson?time_window=${freqWindow}&min_dph=0`,
      { headers: { "X-Tenant-ID": DEMO_TENANT }, signal: controller.signal },
    )
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
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
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError("Failed to load frequency data");
      });

    return () => controller.abort();
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
      const controller = new AbortController();
      fetch(`${API_BASE}/sociodemographic/municipalities/geojson`, {
        headers: { "X-Tenant-ID": DEMO_TENANT },
        signal: controller.signal,
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (!data) return;
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
          if (err instanceof DOMException && err.name === "AbortError") return;
          setError("Failed to load sociodemographic layer");
        });
      return () => controller.abort();
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
      .catch(() => { setError("Failed to load departure times"); });
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
        if (!res.ok) return null;
        return res.json();
      })
      .then((data) => {
        if (!data) return;
        const source = mlMap.getSource("cells");
        if (source && "setData" in source) {
          (source as { setData: (d: unknown) => void }).setData(data);
          mlMap.triggerRepaint();
        }
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
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

    // Sync 3D extrusion color + height to match the active metric
    if (map.getLayer("cells-3d")) {
      mlMap.setPaintProperty("cells-3d", "fill-extrusion-color", colorExpr);
      const heightExpr = buildHeightExpr(metric, extrusionHeight);
      mlMap.setPaintProperty("cells-3d", "fill-extrusion-height", heightExpr);
    }

    // Adjust outline width – thicker for coarse grids, still visible for 100 m
    if (map.getLayer("cells-outline")) {
      const width = resolution >= 1000 ? 1.5 : resolution >= 500 ? 0.8 : resolution >= 200 ? 0.5 : 0.3;
      mlMap.setPaintProperty("cells-outline", "line-width", width);
    }

    return () => controller.abort();
  }, [selectedPurpose, metric, departureTime, resolution, extrusionHeight, mapReady]);

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
    set("cells-3d", "fill-extrusion-opacity", fillOpacity);
  }, [fillOpacity, mapReady]);

  // ── 3D mode toggle (extrusion layers + buildings) ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    try {
      if (map.getLayer("cells-fill")) {
        map.setLayoutProperty("cells-fill", "visibility", "visible");
      }
      if (map.getLayer("cells-3d")) {
        map.setLayoutProperty("cells-3d", "visibility", is3D ? "visible" : "none");
      }
      if (map.getLayer("sky")) {
        map.setLayoutProperty("sky", "visibility", is3D ? "visible" : "none");
      }
      if (map.getLayer("3d-buildings")) {
        map.setLayoutProperty("3d-buildings", "visibility", showBuildings ? "visible" : "none");
      }
    } catch (err) {
      console.error("[3D] layer toggle failed:", err);
    }
  }, [is3D, showBuildings, mapReady]);

  // ── Terrain toggle ──
  // DEM source is in the initial style, so tiles are already loading.
  // setTerrain exists on MaplibreMap (v4.1+) — call it directly.
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
        // Auto-tilt so the user can see the elevation
        mlMap.easeTo({ pitch: 50, duration: 800 });
      } else {
        mlMap.setTerrain(null);
        if (map.getLayer("hillshade-layer")) {
          map.setLayoutProperty("hillshade-layer", "visibility", "none");
        }
        mlMap.easeTo({ pitch: 0, bearing: 0, duration: 800 });
      }
    } catch (err) {
      console.error("[terrain]", err);
    }
  }, [showTerrain, mapReady]);

  // ── 3D extrusion height sync ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !is3D) return;
    const mlMap = map as unknown as MaplibreMap;
    if (!map.getLayer("cells-3d")) return;

    const heightExpr = buildHeightExpr(metric, extrusionHeight);
    mlMap.setPaintProperty("cells-3d", "fill-extrusion-height", heightExpr);
  }, [extrusionHeight, metric, is3D, mapReady]);

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
              {
                id: "osm-tiles", type: "raster" as const, source: "osm",
                minzoom: 0, maxzoom: 19,
              },
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

        map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
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
            } catch (e) { console.warn("[map] optional layer failed:", e); }

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
            } catch (e) { console.warn("[map] optional layer failed:", e); }

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
            } catch (e) { console.warn("[map] optional layer failed:", e); }

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
            } catch (e) { console.warn("[map] optional layer failed:", e); }

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

            // 10. 3D cells extrusion layer (hidden by default, toggled via 3D mode)
            // Filter out zero/null scores to reduce GPU geometry count
            map.addLayer({
              id: "cells-3d",
              type: "fill-extrusion",
              source: "cells",
              layout: { visibility: "none" },
              filter: [">", ["coalesce", ["get", "score"], 0], 0],
              maxzoom: 13,
              paint: {
                "fill-extrusion-color": [
                  "interpolate", ["linear"],
                  ["coalesce", ["get", "score"], 0],
                  ...SCORE_COLORS.flatMap(([stop, color]) => [stop, color]),
                ] as unknown as string,
                "fill-extrusion-height": [
                  "*", ["coalesce", ["get", "score"], 0], DEFAULT_EXTRUSION_HEIGHT / 100,
                ] as unknown as number,
                "fill-extrusion-base": 0,
                "fill-extrusion-opacity": 0.75,
              },
            } as Parameters<MaplibreMap["addLayer"]>[0]);

            // 11. Sky layer (hidden by default, visible in 3D mode)
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
        map.on("click", "cells-3d", (e) => {
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
          const props = e.features[0].properties;
          const muniName = props?.name ?? "";
          const muniCode = props?.muni_code ?? "";

          // Fetch socio profile for this municipality
          fetch(`${API_BASE}/sociodemographic/profiles`, {
            headers: { "X-Tenant-ID": DEMO_TENANT },
          })
            .then((res) => (res.ok ? res.json() : []))
            .then((profiles: Array<Record<string, unknown>>) => {
              const p = profiles.find(
                (pr) => pr.muni_code === muniCode || pr.name === muniName,
              );
              new maplibregl.Popup().setLngLat(e.lngLat)
                .setHTML(buildMuniPopupHtml(muniName, p ?? null, t))
                .addTo(map);
            })
            .catch(() => {
              new maplibregl.Popup().setLngLat(e.lngLat)
                .setHTML(`<strong>${muniName}</strong>`)
                .addTo(map);
            });
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
            .setHTML(buildMuniPopupHtml(name, p ?? null, t))
            .addTo(map);
        });

        const clickable = ["cells-fill", "cells-3d", "social-fill", "transit-stops", "transit-routes", "freq-circles", "municipalities-boundary", "nucleos-fill", ...DEST_LAYERS.map((d) => d.id)];
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
      } catch (e) { console.warn("[map] optional layer failed:", e); }
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

          {/* Social Layer */}
          <Section title={t("map.socialLayer")} open={openSections.social} onToggle={() => toggleSection("social")}>
            <div className="space-y-1">
              {[
                { value: null, labelKey: "map.socialNone" },
                { value: "elderly", labelKey: "map.socialElderly" },
                { value: "income", labelKey: "map.socialIncome" },
                { value: "cars", labelKey: "map.socialCars" },
                { value: "vulnerability", labelKey: "map.socialVuln" },
              ].map((opt) => (
                <button
                  key={opt.labelKey}
                  onClick={() => setSocialLayer(opt.value)}
                  className={`w-full rounded px-2.5 py-1.5 text-left text-xs font-medium transition-colors ${
                    socialLayer === opt.value
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary/50 text-secondary-foreground hover:bg-secondary"
                  }`}
                >
                  {t(opt.labelKey)}
                </button>
              ))}
            </div>
            {/* Legend */}
            {socialLayer && SOCIAL_PAINT[socialLayer] && (
              <div className="mt-3 pt-2 border-t">
                <p className="text-[10px] text-muted-foreground mb-1.5">{t(`map.social${socialLayer.charAt(0).toUpperCase() + socialLayer.slice(1)}`)}</p>
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-muted-foreground">{t("map.socialLegendLow")}</span>
                  <div className="flex h-3 flex-1 rounded-sm overflow-hidden">
                    {SOCIAL_PAINT[socialLayer].stops.map(([, color]) => (
                      <div key={color} className="flex-1" style={{ backgroundColor: color }} />
                    ))}
                  </div>
                  <span className="text-[10px] text-muted-foreground">{t("map.socialLegendHigh")}</span>
                </div>
                <div className="flex justify-between text-[9px] text-muted-foreground mt-0.5">
                  <span>{SOCIAL_PAINT[socialLayer].stops[0][0]}</span>
                  <span>{SOCIAL_PAINT[socialLayer].stops[SOCIAL_PAINT[socialLayer].stops.length - 1][0]}</span>
                </div>
              </div>
            )}
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

          {/* 3D View */}
          <Section title={t("map.3dView")} open={openSections.threeD} onToggle={() => toggleSection("threeD")}>
            <label className="flex items-center gap-2 text-xs cursor-pointer py-0.5">
              <input
                type="checkbox"
                checked={is3D}
                onChange={() => setIs3D((v) => !v)}
                className="rounded border-input"
              />
              <span className="font-medium">{t("map.3dEnable")}</span>
            </label>

            <label className="flex items-center gap-2 text-xs cursor-pointer py-0.5">
              <input
                type="checkbox"
                checked={showBuildings}
                onChange={() => setShowBuildings((v) => !v)}
                className="rounded border-input"
              />
              <span className="font-medium">{t("map.3dBuildings")}</span>
            </label>

            <label className="flex items-center gap-2 text-xs cursor-pointer py-0.5">
              <input
                type="checkbox"
                checked={showTerrain}
                onChange={() => setShowTerrain((v) => !v)}
                className="rounded border-input"
              />
              <span className="font-medium">{t("map.3dTerrain")}</span>
            </label>

            {is3D && (
              <div className="mt-2 space-y-2.5">

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-muted-foreground">{t("map.3dHeight")}</span>
                    <span className="text-xs font-mono text-muted-foreground w-10 text-right">
                      {extrusionHeight}m
                    </span>
                  </div>
                  <input
                    type="range"
                    min={50}
                    max={1000}
                    step={50}
                    value={extrusionHeight}
                    onChange={(e) => setExtrusionHeight(Number(e.target.value))}
                    className="w-full h-1.5 bg-secondary rounded-full appearance-none cursor-pointer accent-primary"
                  />
                  <div className="flex justify-between text-[9px] text-muted-foreground mt-0.5">
                    <span>{t("map.3dFlat")}</span>
                    <span>{t("map.3dTall")}</span>
                  </div>
                </div>

                <p className="text-[10px] text-muted-foreground leading-relaxed">
                  {t("map.3dHint")}
                </p>
                {resolution <= 200 && (
                  <p className="text-[10px] text-amber-600 dark:text-amber-400 leading-relaxed">
                    {t("map.3dZoomNote")}
                  </p>
                )}
              </div>
            )}
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
            {/* Global Routes / Stops / Frequency toggle */}
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
              <button
                onClick={handleToggleFrequency}
                className={`flex-1 rounded px-2 py-1.5 text-xs font-medium transition-colors ${
                  showFrequency
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary/50 text-secondary-foreground hover:bg-secondary"
                }`}
              >
                {t("map.freqToggle")}
              </button>
            </div>

            {/* Frequency time window */}
            {showFrequency && (
              <div className="mb-2.5 space-y-1.5">
                <span className="text-[10px] text-muted-foreground">{t("map.freqWindow")}</span>
                <div className="flex flex-wrap gap-1">
                  {FREQ_WINDOWS.map((tw) => (
                    <button
                      key={tw}
                      onClick={() => setFreqWindow(tw)}
                      className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                        freqWindow === tw
                          ? "bg-primary text-primary-foreground"
                          : "bg-secondary/50 text-secondary-foreground hover:bg-secondary"
                      }`}
                    >
                      {tw}
                    </button>
                  ))}
                </div>
                {/* Frequency legend */}
                <div className="pt-1.5 space-y-0.5">
                  <p className="text-[10px] text-muted-foreground">{t("map.freqLegend")}</p>
                  {[
                    { color: FREQ_COLORS.high, label: t("map.freqHigh") },
                    { color: FREQ_COLORS.med, label: t("map.freqMed") },
                    { color: FREQ_COLORS.low, label: t("map.freqLow") },
                    { color: FREQ_COLORS.veryLow, label: t("map.freqVeryLow") },
                  ].map((b) => (
                    <div key={b.label} className="flex items-center gap-1.5">
                      <span className="inline-block w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: b.color }} />
                      <span className="text-[10px] text-muted-foreground">{b.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

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
