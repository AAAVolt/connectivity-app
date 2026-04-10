import { describe, expect, it } from "vitest";
import { en } from "@/lib/locales/en";
import { es } from "@/lib/locales/es";
import { eu } from "@/lib/locales/eu";

const enKeys = Object.keys(en).sort();
const esKeys = Object.keys(es).sort();
const euKeys = Object.keys(eu).sort();

describe("locale completeness", () => {
  it("es has the same keys as en", () => {
    const missingInEs = enKeys.filter((k) => !esKeys.includes(k));
    const extraInEs = esKeys.filter((k) => !enKeys.includes(k));
    expect(missingInEs).toEqual([]);
    expect(extraInEs).toEqual([]);
  });

  it("eu has the same keys as en", () => {
    const missingInEu = enKeys.filter((k) => !euKeys.includes(k));
    const extraInEu = euKeys.filter((k) => !enKeys.includes(k));
    expect(missingInEu).toEqual([]);
    expect(extraInEu).toEqual([]);
  });

  it("no locale has empty-string values", () => {
    const emptyEn = Object.entries(en).filter(([, v]) => v === "");
    const emptyEs = Object.entries(es).filter(([, v]) => v === "");
    const emptyEu = Object.entries(eu).filter(([, v]) => v === "");
    expect(emptyEn.map(([k]) => k)).toEqual([]);
    expect(emptyEs.map(([k]) => k)).toEqual([]);
    expect(emptyEu.map(([k]) => k)).toEqual([]);
  });
});

describe("navigation keys", () => {
  const navKeys = ["nav.dashboard", "nav.map", "nav.methodology", "nav.context"];

  it("all nav keys exist in every locale", () => {
    for (const key of navKeys) {
      expect((en as Record<string, string>)[key]).toBeDefined();
      expect((es as Record<string, string>)[key]).toBeDefined();
      expect((eu as Record<string, string>)[key]).toBeDefined();
    }
  });
});
