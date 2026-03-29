"use client";

import dynamic from "next/dynamic";

const ConnectivityMap = dynamic(
  () => import("@/components/connectivity-map"),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Loading map...
      </div>
    ),
  },
);

export default function MapPage() {
  return (
    <div className="h-[calc(100vh-3.5rem)] relative">
      <ConnectivityMap />
    </div>
  );
}
