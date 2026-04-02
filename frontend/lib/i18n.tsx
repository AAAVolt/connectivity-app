"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { Locale } from "@/lib/locales/en";
import { en } from "@/lib/locales/en";
import { es } from "@/lib/locales/es";
import { eu } from "@/lib/locales/eu";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Lang = "en" | "es" | "eu";

const LOCALES: Record<Lang, Locale> = { en, es, eu };

const STORAGE_KEY = "bizkaia-lang";

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface I18nContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue>({
  lang: "es",
  setLang: () => {},
  t: (key) => key,
});

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("es");

  // Hydrate from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "es" || stored === "eu") {
      setLangState(stored);
    }
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    localStorage.setItem(STORAGE_KEY, l);
  }, []);

  const t = useCallback(
    (key: string): string => {
      const locale = LOCALES[lang];
      return (locale as Record<string, string>)[key] ?? key;
    },
    [lang],
  );

  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useTranslation() {
  return useContext(I18nContext);
}
