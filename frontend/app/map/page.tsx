"use client";

import dynamic from "next/dynamic";
import { useTranslation } from "@/lib/i18n";

function MapLoading() {
  const { t } = useTranslation();
  return (
    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
      {t("map.loading")}
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
