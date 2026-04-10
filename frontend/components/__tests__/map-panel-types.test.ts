import { describe, expect, it } from "vitest";
import {
  SCORE_COLORS,
  TRAVEL_TIME_BANDS,
  TRAVEL_TIME_NO_DATA_COLOR,
  OPERATORS,
  FREQ_COLORS,
  FREQ_WINDOWS,
  SOCIAL_PAINT,
  RESOLUTION_LABELS,
  toggleClasses,
} from "../map/map-panel-types";

describe("SCORE_COLORS", () => {
  it("has 12 stops", () => {
    expect(SCORE_COLORS).toHaveLength(12);
  });

  it("covers 0 to 100 range", () => {
    expect(SCORE_COLORS[0][0]).toBe(0);
    expect(SCORE_COLORS[SCORE_COLORS.length - 1][0]).toBe(100);
  });

  it("stops are monotonically increasing", () => {
    for (let i = 1; i < SCORE_COLORS.length; i++) {
      expect(SCORE_COLORS[i][0]).toBeGreaterThan(SCORE_COLORS[i - 1][0]);
    }
  });

  it("all colors are valid hex", () => {
    for (const [, color] of SCORE_COLORS) {
      expect(color).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });
});

describe("TRAVEL_TIME_BANDS", () => {
  it("has 5 bands", () => {
    expect(TRAVEL_TIME_BANDS).toHaveLength(5);
  });

  it("bands are contiguous (each max is next min)", () => {
    for (let i = 1; i < TRAVEL_TIME_BANDS.length; i++) {
      expect(TRAVEL_TIME_BANDS[i].min).toBe(TRAVEL_TIME_BANDS[i - 1].max);
    }
  });

  it("starts at 0", () => {
    expect(TRAVEL_TIME_BANDS[0].min).toBe(0);
  });

  it("no-data color is valid hex", () => {
    expect(TRAVEL_TIME_NO_DATA_COLOR).toMatch(/^#[0-9a-fA-F]{6}$/);
  });
});

describe("OPERATORS", () => {
  it("has 6 transit operators", () => {
    expect(OPERATORS).toHaveLength(6);
  });

  it("all have unique IDs", () => {
    const ids = OPERATORS.map((o) => o.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("all have valid hex colors", () => {
    for (const op of OPERATORS) {
      expect(op.color).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });

  it("includes the main Bizkaia operators", () => {
    const ids = OPERATORS.map((o) => o.id);
    expect(ids).toContain("Bizkaibus");
    expect(ids).toContain("MetroBilbao");
  });
});

describe("FREQ_COLORS", () => {
  it("has all four frequency bands", () => {
    expect(FREQ_COLORS).toHaveProperty("high");
    expect(FREQ_COLORS).toHaveProperty("med");
    expect(FREQ_COLORS).toHaveProperty("low");
    expect(FREQ_COLORS).toHaveProperty("veryLow");
  });
});

describe("FREQ_WINDOWS", () => {
  it("has 6 time windows", () => {
    expect(FREQ_WINDOWS).toHaveLength(6);
  });

  it("all match HH:MM-HH:MM format", () => {
    for (const w of FREQ_WINDOWS) {
      expect(w).toMatch(/^\d{2}:\d{2}-\d{2}:\d{2}$/);
    }
  });

  it("includes a full-day window", () => {
    expect(FREQ_WINDOWS).toContain("06:00-22:00");
  });
});

describe("SOCIAL_PAINT", () => {
  const EXPECTED_LAYERS = ["elderly", "income", "cars", "vulnerability"];

  it("has all 4 social layers", () => {
    for (const layer of EXPECTED_LAYERS) {
      expect(SOCIAL_PAINT).toHaveProperty(layer);
    }
  });

  it("each layer has prop, stops, and label", () => {
    for (const layer of EXPECTED_LAYERS) {
      const cfg = SOCIAL_PAINT[layer];
      expect(cfg.prop).toBeTruthy();
      expect(cfg.stops.length).toBeGreaterThanOrEqual(2);
      expect(cfg.label).toBeTruthy();
    }
  });

  it("stops are monotonically increasing within each layer", () => {
    for (const layer of EXPECTED_LAYERS) {
      const stops = SOCIAL_PAINT[layer].stops;
      for (let i = 1; i < stops.length; i++) {
        expect(stops[i][0]).toBeGreaterThan(stops[i - 1][0]);
      }
    }
  });
});

describe("RESOLUTION_LABELS", () => {
  it("maps 250, 500, 1000 to human-readable labels", () => {
    expect(RESOLUTION_LABELS[250]).toBe("250 m");
    expect(RESOLUTION_LABELS[500]).toBe("500 m");
    expect(RESOLUTION_LABELS[1000]).toBe("1 km");
  });
});

describe("toggleClasses", () => {
  it("returns active classes when true", () => {
    const result = toggleClasses(true);
    expect(result).toContain("bg-sidebar-primary");
    expect(result).toContain("text-sidebar-primary-foreground");
  });

  it("returns inactive classes when false", () => {
    const result = toggleClasses(false);
    expect(result).toContain("bg-sidebar-accent");
    expect(result).toContain("hover:bg-sidebar-accent");
    expect(result).not.toContain("bg-sidebar-primary ");
  });
});
