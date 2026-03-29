"use client";

import dynamic from "next/dynamic";

const ConnectivityMap = dynamic(
  () => import("@/components/connectivity-map"),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Loading map...
      </div>
    ),
  },
);

export default function MapPage() {
  return (
    <div className="h-full relative">
      <ConnectivityMap />
    </div>
  );
}
