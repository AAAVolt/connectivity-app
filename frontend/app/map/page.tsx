"use client";

import dynamic from "next/dynamic";

function MapLoading() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-muted border-t-primary" />
    </div>
  );
}

const ConnectivityMap = dynamic(
  () => import("@/components/connectivity-map"),
  {
    ssr: false,
    loading: () => <MapLoading />,
  },
);

export default function MapPage() {
  return (
    <div className="h-full relative">
      <ConnectivityMap />
    </div>
  );
}
