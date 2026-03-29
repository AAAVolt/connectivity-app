"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/map", label: "Map" },
  { href: "/about", label: "About" },
] as const;

/** Height in pixels of the invisible hover zone at the top of the viewport. */
const TRIGGER_ZONE = 12;
/** How long (ms) to keep the header visible after the mouse leaves it. */
const HIDE_DELAY = 400;

export function AppSidebar({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
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
          Bizkaia Connectivity
        </span>
        <nav className="flex items-center gap-1">
          {NAV.map(({ href, label }) => {
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
                {label}
              </Link>
            );
          })}
        </nav>
      </header>

      {/* Content takes the full viewport — header overlays on top */}
      <main className="h-full relative">
        {children}
      </main>
    </div>
  );
}
