// ── Shared types, constants, and utilities for the map control panel ──

import type React from "react";

// ── Types ──

export type MetricType = "score" | "travel_time";
export type BasemapId = "osm" | "positron" | "dark" | "satellite";
export type Perspective = "2d" | "3d";

export type DestType = { code: string; label: string };
export type PoiType = { value: string | null; label: string; descKey: string; color?: string };
export type DestLayer = { id: string; type: string; color: string; label: string };

export interface LayerToggle {
  id: string;
  label: string;
  visible: boolean;
  color?: string;
}

export interface OperatorState {
  id: string;
  label: string;
  color: string;
  visible: boolean;
}

export interface CellProperties {
  id?: number;
  cell_code: string;
  population: number;
  score: number | null;
}

// ── Constants ──

/** 12-stop color ramp for accessibility score (low=bad, high=good) */
export const SCORE_COLORS: [number, string][] = [
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

/** Discrete color bands for travel time to nearest destination */
export const TRAVEL_TIME_BANDS = [
  { min: 0, max: 30, color: "#1a9850", label: "< 30 min" },
  { min: 30, max: 45, color: "#91cf60", label: "30-45 min" },
  { min: 45, max: 60, color: "#fee08b", label: "45-60 min" },
  { min: 60, max: 75, color: "#fc8d59", label: "60-75 min" },
  { min: 75, max: 90, color: "#d73027", label: "75-90 min" },
] as const;

export const TRAVEL_TIME_NO_DATA_COLOR = "#878787";
export const TRAVEL_TIME_NO_DATA_LABEL = "> 90 min";

/** Transit operators with colors */
export const OPERATORS = [
  { id: "Bizkaibus", label: "Bizkaibus", color: "#166534" },
  { id: "Bilbobus", label: "Bilbobus", color: "#d97706" },
  { id: "MetroBilbao", label: "Metro Bilbao", color: "#dc2626" },
  { id: "Euskotren", label: "Euskotren", color: "#7c3aed" },
  { id: "Renfe_Cercanias", label: "Renfe Cercanias", color: "#0369a1" },
  { id: "FunicularArtxanda", label: "Funicular Artxanda", color: "#a855f7" },
] as const;

/** Frequency color bands */
export const FREQ_COLORS = {
  high: "#1a9850",
  med: "#91cf60",
  low: "#fee08b",
  veryLow: "#d73027",
};

export const FREQ_WINDOWS = [
  "07:00-09:00", "09:00-12:00", "12:00-15:00",
  "15:00-18:00", "18:00-21:00", "06:00-22:00",
];

/** Social layer color ramps */
export const SOCIAL_PAINT: Record<string, { prop: string; stops: [number, string][]; label: string }> = {
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

export const RESOLUTION_LABELS: Record<number, string> = {
  250: "250 m",
  500: "500 m",
  1000: "1 km",
};

/** Available basemap styles */
export const BASEMAP_OPTIONS: { id: BasemapId; labelKey: string }[] = [
  { id: "osm", labelKey: "map.basemapStandard" },
  { id: "positron", labelKey: "map.basemapLight" },
  { id: "dark", labelKey: "map.basemapDark" },
  { id: "satellite", labelKey: "map.basemapSatellite" },
];

// ── Utilities ──

/** Toggle class helper for active/inactive button states in sidebar context */
export function toggleClasses(active: boolean): string {
  return active
    ? "bg-sidebar-primary text-sidebar-primary-foreground"
    : "bg-sidebar-accent/50 text-sidebar-foreground hover:bg-sidebar-accent";
}

// ── Panel props interface ──

export interface MapPanelProps {
  panelOpen: boolean;
  setPanelOpen: (open: boolean) => void;
  openSections: Record<string, boolean>;
  toggleSection: (key: string) => void;

  // Metric
  metric: MetricType;
  setMetric: (m: MetricType) => void;

  // Time
  timeIndex: number;
  setTimeIndex: (i: number) => void;
  availableTimes: string[];
  departureTime: string;
  timePeriod: string;

  // Destination / Accessibility
  selectedPurpose: string | null;
  setSelectedPurpose: (p: string | null) => void;
  poiTypes: PoiType[];
  activePoi: PoiType | undefined;

  // Social
  socialLayer: string | null;
  setSocialLayer: (l: string | null) => void;

  // Layers
  baseLayers: (LayerToggle & { labelKey: string })[];
  toggleBaseLayer: (id: string) => void;
  fillOpacity: number;
  setFillOpacity: (o: number) => void;

  // Basemap
  basemap: BasemapId;
  setBasemap: (id: BasemapId) => void;

  // 3D / Perspective
  perspective: Perspective;
  setPerspective: (p: Perspective) => void;
  is3D: boolean;
  setIs3D: React.Dispatch<React.SetStateAction<boolean>>;
  showBuildings: boolean;
  setShowBuildings: React.Dispatch<React.SetStateAction<boolean>>;
  showTerrain: boolean;
  setShowTerrain: React.Dispatch<React.SetStateAction<boolean>>;
  extrusionHeight: number;
  setExtrusionHeight: (h: number) => void;
  resolution: number;

  // Destinations
  destToggles: { id: string; label: string; color: string; visible: boolean }[];
  toggleDestination: (id: string) => void;

  // Transit
  showRoutes: boolean;
  handleToggleRoutes: () => void;
  showStops: boolean;
  handleToggleStops: () => void;
  showFrequency: boolean;
  handleToggleFrequency: () => void;
  freqWindow: string;
  setFreqWindow: (w: string) => void;
  operators: OperatorState[];
  setOperators: React.Dispatch<React.SetStateAction<OperatorState[]>>;

  // Cell detail
  selectedCell: CellProperties | null;
  setSelectedCell: (cell: CellProperties | null) => void;
}
