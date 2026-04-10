"use client";

import { IconChevronDown as ChevronDown } from "@tabler/icons-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface MapPanelSectionProps {
  title: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

export function MapPanelSection({ title, open, onToggle, children }: MapPanelSectionProps) {
  return (
    <Collapsible open={open} onOpenChange={() => onToggle()}>
      <div className="border-b border-sidebar-border">
        <CollapsibleTrigger className="flex w-full items-center justify-between px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/80 hover:text-sidebar-foreground transition-colors">
          {title}
          <ChevronDown
            className={`h-3 w-3 text-sidebar-foreground/60 transition-transform duration-200 ${open ? "" : "-rotate-90"}`}
          />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="px-3 pb-3">{children}</div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
