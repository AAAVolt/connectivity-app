"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";

const NAV_KEYS = [
  { href: "/", key: "nav.dashboard" },
  { href: "/context", key: "nav.context" },
  { href: "/map", key: "nav.map" },
  { href: "/about", key: "nav.methodology" },
] as const;

const LANGS: { code: Lang; flag: string | null; img?: string; label: string }[] = [
  { code: "eu", flag: null, img: "/euskera.png", label: "Euskara" },
  { code: "es", flag: "🇪🇸", label: "Español" },
  { code: "en", flag: "🇬🇧", label: "English" },
];

/** Height in pixels of the invisible hover zone at the top of the viewport. */
const TRIGGER_ZONE = 12;
/** How long (ms) to keep the header visible after the mouse leaves it. */
const HIDE_DELAY = 400;

export function AppSidebar({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { t, lang, setLang } = useTranslation();
  const [visible, setVisible] = useState(false);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearHideTimer = useCallback(() => {
    if (hideTimer.current) {
      clearTimeout(hideTimer.current);
      hideTimer.current = null;
    }
  }, []);

  const scheduleHide = useCallback(() => {
    clearHideTimer();
    hideTimer.current = setTimeout(() => setVisible(false), HIDE_DELAY);
  }, [clearHideTimer]);

  // Global mousemove: show header when cursor enters the top trigger zone
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (e.clientY <= TRIGGER_ZONE) {
        clearHideTimer();
        setVisible(true);
      }
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, [clearHideTimer]);

  // Clean up timer on unmount
  useEffect(() => () => clearHideTimer(), [clearHideTimer]);

  return (
    <div className="h-screen relative">
      {/* Header — slides down on hover */}
      <header
        onMouseEnter={clearHideTimer}
        onMouseLeave={scheduleHide}
        className={cn(
          "absolute inset-x-0 top-0 z-50 h-10 border-b bg-background/95 backdrop-blur-sm flex items-center px-4 gap-6 transition-transform duration-200",
          visible ? "translate-y-0" : "-translate-y-full",
        )}
      >
        <span className="text-sm font-semibold tracking-tight mr-2">
          {t("app.title")}
        </span>
        <nav className="flex items-center gap-1">
          {NAV_KEYS.map(({ href, key }) => {
            const active =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  active
                    ? "bg-accent text-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                )}
              >
                {t(key)}
              </Link>
            );
          })}
        </nav>

        {/* Language switcher */}
        <div className="ml-auto flex items-center gap-1">
          {LANGS.map((l) => (
            <button
              key={l.code}
              onClick={() => setLang(l.code)}
              title={l.label}
              className={cn(
                "rounded px-1.5 py-0.5 text-sm transition-opacity",
                lang === l.code ? "opacity-100" : "opacity-40 hover:opacity-75",
              )}
            >
              {l.img ? (
                <img src={l.img} alt={l.label} className="h-4 w-auto inline-block" />
              ) : (
                l.flag
              )}
            </button>
          ))}
        </div>
      </header>

      {/* Content takes the full viewport — header overlays on top */}
      <main className="h-full relative">
        {children}
      </main>
    </div>
  );
}
