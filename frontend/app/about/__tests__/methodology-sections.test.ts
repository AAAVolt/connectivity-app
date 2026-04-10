import { describe, expect, it } from "vitest";
import { en } from "@/lib/locales/en";
import { es } from "@/lib/locales/es";
import { eu } from "@/lib/locales/eu";

/**
 * Validates the methodology page sections configuration and
 * ensures all required i18n keys exist in every locale.
 */

// Mirror SECTIONS from about/page.tsx
const SECTIONS = [
  { id: "overview", key: "method.whatIsThis" },
  { id: "pipeline", key: "method.dataPipeline" },
  { id: "scoring", key: "method.scoringModel" },
  { id: "map", key: "method.readingMap" },
  { id: "dashboard", key: "method.dashboardAnalytics" },
  { id: "socio", key: "method.socioTitle" },
  { id: "sources", key: "method.dataSources" },
  { id: "limits", key: "method.limitations" },
  { id: "opensource", key: "method.openSource" },
] as const;

const locales = { en, es, eu } as Record<string, Record<string, string>>;

describe("methodology page sections", () => {
  it("has exactly 9 sections", () => {
    expect(SECTIONS).toHaveLength(9);
  });

  it("all section IDs are unique", () => {
    const ids = SECTIONS.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("all section title keys exist in every locale", () => {
    for (const section of SECTIONS) {
      for (const [locale, strings] of Object.entries(locales)) {
        expect(
          strings[section.key],
          `Missing "${section.key}" in ${locale}`,
        ).toBeDefined();
        expect(
          strings[section.key],
          `Empty "${section.key}" in ${locale}`,
        ).not.toBe("");
      }
    }
  });
});

// All i18n keys used on the methodology page that must exist
const METHODOLOGY_KEYS = [
  // Page chrome
  "method.title",
  "method.intro",
  "method.toc",
  // Overview section
  "method.whatIsThis",
  "method.whatIsThisP1",
  "method.whatIsThisQuestion",
  "method.whatIsThisP2",
  "method.zoom1km",
  "method.zoom500m",
  "method.zoom250m",
  // Data pipeline
  "method.dataPipeline",
  "method.dataPipelineIntro",
  "method.step1Title",
  "method.step1Text",
  "method.step2Title",
  "method.step2Text",
  "method.step3Title",
  "method.step3Text",
  "method.step3Category",
  "method.step3Description",
  "method.step3Toggle",
  "method.step4Title",
  "method.step4Text",
  "method.step4Foot",
  "method.step5Title",
  "method.step5Text",
  "method.step5Mode",
  "method.step5ModeVal",
  "method.step5Cutoff",
  "method.step5CutoffVal",
  "method.step5Slots",
  "method.step5SlotsVal",
  "method.step6Title",
  "method.step6Text",
  // Scoring model
  "method.scoringModel",
  "method.decay",
  "method.decayP1",
  "method.decayP2",
  "method.decayP3",
  "method.diminishing",
  "method.diminishingP1",
  "method.diminishingP2",
  "method.normalisation",
  "method.normalisationP1",
  "method.combined",
  "method.combinedP1",
  "method.combinedCategory",
  "method.combinedWeight",
  "method.combinedTotal",
  "method.combinedP2",
  // Reading the map
  "method.readingMap",
  "method.accessScore",
  "method.accessScoreP1",
  "method.scorePoor",
  "method.scoreMid",
  "method.scoreExcellent",
  "method.travelTimeNearest",
  "method.travelTimeP1",
  "method.zeroPop",
  "method.zeroPopP1",
  "method.mapControls",
  // Dashboard
  "method.dashboardAnalytics",
  "method.dashboardP1",
  "method.dashboardOverview",
  "method.dashboardOverviewDesc",
  "method.dashboardComarcas",
  "method.dashboardComarcasDesc",
  "method.dashboardMunicipios",
  "method.dashboardMunicipiosDesc",
  "method.dashboardP2",
  // Sociodemographic
  "method.socioTitle",
  "method.socioIntro",
  "method.socioIndicators",
  "method.socioIndicator",
  "method.socioSource",
  "method.socioInterpretation",
  "method.socioVulnTitle",
  "method.socioVulnP1",
  "method.socioVulnP2",
  // Data sources
  "method.dataSources",
  "method.dsLayer",
  "method.dsSource",
  // Limitations
  "method.limitations",
  // Open source
  "method.openSource",
  "method.openSourceP1",
];

describe("methodology i18n key completeness", () => {
  for (const [locale, strings] of Object.entries(locales)) {
    it(`all methodology keys exist in ${locale}`, () => {
      const missing = METHODOLOGY_KEYS.filter((k) => !(k in strings));
      expect(missing, `Missing keys in ${locale}`).toEqual([]);
    });
  }
});

// POI description keys used in the methodology page tables
const POI_DESC_KEYS = [
  "poi.desc.aeropuerto",
  "poi.desc.bachiller",
  "poi.desc.centro_educativo",
  "poi.desc.centro_urbano",
  "poi.desc.consulta_general",
  "poi.desc.hacienda",
  "poi.desc.hospital",
  "poi.desc.osakidetza",
  "poi.desc.residencia",
  "poi.desc.universidad",
];

describe("POI description keys", () => {
  for (const [locale, strings] of Object.entries(locales)) {
    it(`all POI desc keys exist in ${locale}`, () => {
      const missing = POI_DESC_KEYS.filter((k) => !(k in strings));
      expect(missing, `Missing POI keys in ${locale}`).toEqual([]);
    });
  }
});

// Operator description keys
const OPERATOR_DESC_KEYS = [
  "op.bizkaibus",
  "op.bilbobus",
  "op.metrobilbao",
  "op.euskotren",
  "op.renfe",
  "op.funicular",
];

describe("operator description keys", () => {
  for (const [locale, strings] of Object.entries(locales)) {
    it(`all operator keys exist in ${locale}`, () => {
      const missing = OPERATOR_DESC_KEYS.filter((k) => !(k in strings));
      expect(missing, `Missing operator keys in ${locale}`).toEqual([]);
    });
  }
});
