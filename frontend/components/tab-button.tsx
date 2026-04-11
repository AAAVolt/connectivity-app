"use client";

import type { TablerIcon as LucideIcon } from "@tabler/icons-react";

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon?: LucideIcon;
  children: React.ReactNode;
}

export function TabButton({ active, onClick, icon: Icon, children }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors whitespace-nowrap ${
        active
          ? "border-primary text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
      }`}
    >
      {Icon && <Icon className="size-3.5" />}
      {children}
    </button>
  );
}
