"use client";

import { usePathname } from "next/navigation";
import { AppSidebar } from "@/components/app-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

interface SidebarLayoutProps {
  children: React.ReactNode;
  defaultOpen?: boolean;
}

export function SidebarLayout({ children, defaultOpen }: SidebarLayoutProps) {
  const pathname = usePathname();
  const isMapPage = pathname === "/map";

  return (
    <SidebarProvider defaultOpen={defaultOpen}>
      <AppSidebar />
      <SidebarInset>
        {isMapPage ? (
          /* Map page: full viewport, no chrome */
          <div className="h-dvh">{children}</div>
        ) : (
          /* Content pages: fixed wrapper, only inner content scrolls */
          <div className="flex flex-col h-dvh">
            <div className="flex-1 overflow-auto" data-scroll-root>
              {children}
            </div>
          </div>
        )}
      </SidebarInset>
    </SidebarProvider>
  );
}
