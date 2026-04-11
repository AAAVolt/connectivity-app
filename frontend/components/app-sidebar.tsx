"use client";

import { useCallback } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  IconLayoutDashboard as LayoutDashboard,
  IconMap as Map,
  IconUsers as Users,
  IconBook as BookOpen,
  IconLanguage as Languages,
} from "@tabler/icons-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTranslation } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";
import { prefetchHeavyMapData, prefetchSocioProfiles } from "@/lib/prefetch";

// ── Navigation items ──

const NAV_ITEMS = [
  { href: "/", icon: LayoutDashboard, key: "nav.dashboard" },
  { href: "/context", icon: Users, key: "nav.context" },
  { href: "/map", icon: Map, key: "nav.map" },
  { href: "/about", icon: BookOpen, key: "nav.methodology" },
] as const;

// ── Language options ──

const LANGS: { code: Lang; flag: string | null; img?: string; label: string }[] = [
  { code: "eu", flag: null, img: "/euskera.png", label: "Euskara" },
  { code: "es", flag: "\u{1F1EA}\u{1F1F8}", label: "Espa\u00f1ol" },
  { code: "en", flag: "\u{1F1EC}\u{1F1E7}", label: "English" },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { t, lang, setLang } = useTranslation();
  const currentLang = LANGS.find((l) => l.code === lang) ?? LANGS[0];
  const queryClient = useQueryClient();

  const handleNavHover = useCallback(
    (href: string) => {
      if (href === "/map") prefetchHeavyMapData(queryClient);
      if (href === "/context") prefetchSocioProfiles(queryClient);
    },
    [queryClient],
  );

  return (
    <Sidebar collapsible="icon" variant="inset">
      {/* ── Header: Logo ── */}
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/">
                <Image
                  src="/logo.png"
                  alt="Bizkaia Connectivity"
                  width={32}
                  height={32}
                  className="size-8 rounded-lg object-contain"
                />
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">Bizkaia</span>
                  <span className="truncate text-[11px] text-sidebar-foreground/70">
                    Connectivity
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      {/* ── Navigation ── */}
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_ITEMS.map(({ href, icon: Icon, key }) => {
                const active =
                  href === "/" ? pathname === "/" : pathname.startsWith(href);
                return (
                  <SidebarMenuItem key={href}>
                    <SidebarMenuButton asChild isActive={active} tooltip={t(key)} className="text-xs">
                      <Link href={href} onMouseEnter={() => handleNavHover(href)}>
                        <Icon className="size-4" />
                        <span>{t(key)}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {/* ── Footer: Language only ── */}
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton tooltip={t("sidebar.language")} className="text-xs">
                  <Languages className="size-4" />
                  <span>{currentLang.label}</span>
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="right" align="end" className="w-40">
                {LANGS.map((l) => (
                  <DropdownMenuItem
                    key={l.code}
                    onClick={() => setLang(l.code)}
                    className={`text-xs ${lang === l.code ? "bg-accent" : ""}`}
                  >
                    <span className="mr-2 text-sm">
                      {l.img ? (
                        <Image
                          src={l.img}
                          alt={l.label}
                          width={16}
                          height={16}
                          className="h-4 w-auto inline-block"
                        />
                      ) : (
                        l.flag
                      )}
                    </span>
                    {l.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

    </Sidebar>
  );
}
