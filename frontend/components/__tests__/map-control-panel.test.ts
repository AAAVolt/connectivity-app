import { describe, expect, it } from "vitest";
import { en } from "@/lib/locales/en";
import { es } from "@/lib/locales/es";
import { eu } from "@/lib/locales/eu";

/**
 * Validates that all i18n keys used by the map control panel exist in every locale.
 * This prevents runtime "missing translation" issues where raw keys display.
 */

const locales = { en, es, eu } as Record<string, Record<string, string>>;

// All i18n keys referenced in map-control-panel.tsx
const MAP_PANEL_KEYS = [
  // Panel chrome
  "map.controls",
  "map.collapsePanel",
  "map.openPanel",

  // Metric section
  "map.metricScore",
  "map.metricTravelTime",

  // Departure time
  "map.departureTime",
  "map.amPeak",
  "map.pmPeak",
  "map.midday",
  "map.evening",
  "map.night",

  // Destination / Accessibility
  "map.nearestDestination",
  "map.accessibility",
  "map.combined",
  "map.allDestTypes",
  "map.minutesToNearest",
  "map.transit",
  "map.avgMinToNearest",
  "map.weightedAvgAll",
  "map.publicTransport",
  "map.low",
  "map.high",
  "map.noPopulation",

  // Social layer
  "map.socialLayer",
  "map.socialNone",
  "map.socialElderly",
  "map.socialIncome",
  "map.socialCars",
  "map.socialVuln",
  "map.socialLegendLow",
  "map.socialLegendHigh",

  // Layers
  "map.layers",
  "map.accessibilityGrid",
  "map.bizkaiaBoundary",
  "map.comarcas",
  "map.municipalities",
  "map.nucleos",
  "map.labels",
  "map.gridOpacity",

  // 3D
  "map.3dView",
  "map.3dEnable",
  "map.3dBuildings",
  "map.3dTerrain",
  "map.3dHeight",
  "map.3dFlat",
  "map.3dTall",
  "map.3dHint",
  "map.3dZoomNote",

  // Destinations
  "map.destinations",

  // Transit
  "map.publicTransportSection",
  "map.routes",
  "map.stops",
  "map.freqToggle",
  "map.freqWindow",
  "map.freqLegend",
  "map.freqHigh",
  "map.freqMed",
  "map.freqLow",
  "map.freqVeryLow",

  // Cell detail
  "map.cellDetails",
  "map.close",
  "map.code",
  "map.id",
  "map.resolution",
  "map.population",
];

describe("map control panel i18n keys", () => {
  for (const [locale, strings] of Object.entries(locales)) {
    it(`all panel keys exist in ${locale}`, () => {
      const missing = MAP_PANEL_KEYS.filter((k) => !(k in strings));
      expect(missing, `Missing keys in ${locale}`).toEqual([]);
    });
  }

  it("no panel keys are empty strings in en", () => {
    const empty = MAP_PANEL_KEYS.filter(
      (k) => (en as Record<string, string>)[k] === "",
    );
    expect(empty).toEqual([]);
  });
});

describe("map panel base layer keys", () => {
  const BASE_LAYER_KEYS = [
    "map.accessibilityGrid",
    "map.bizkaiaBoundary",
    "map.comarcas",
    "map.municipalities",
    "map.nucleos",
    "map.labels",
  ];

  it("all base layer keys are defined and non-empty in en", () => {
    for (const key of BASE_LAYER_KEYS) {
      const val = (en as Record<string, string>)[key];
      expect(val, `"${key}" should be defined`).toBeDefined();
      expect(val, `"${key}" should not be empty`).not.toBe("");
    }
  });
});
