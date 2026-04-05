"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ScatterChart,
  Scatter,
  ZAxis,
  Cell as RCell,
} from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import type {
  DashboardSummary,
  ScoreDistributionBucket,
  PurposeBreakdown,
  ServiceCoverage,
} from "@/lib/api";
import {
  KpiCard,
  ScoreDistributionChart,
  PopulationByScoreChart,
  PurposeBarChart,
  TravelTimeBarChart,
  AreaRankingChart,
  CoverageChart,
  PurposeFilter,
  fmt,
  fmtPop,
  TRANSIT_COLOR,
} from "@/components/dashboard-charts";
import type { AreaRanking } from "@/components/dashboard-charts";
import type { MunicipalitySocioProfile } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AreaDetail {
  name: string;
  code: string;
  cell_count: number;
  population: number;
  avg_score: number | null;
  weighted_avg_score: number | null;
  purpose_scores: PurposeBreakdown[];
  service_coverage: ServiceCoverage[];
}

type Tab = "overview" | "comarcas" | "municipios";

// ---------------------------------------------------------------------------
// Tab button
// ---------------------------------------------------------------------------

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
        active
          ? "border-primary text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
      }`}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Comparison Bar Chart — area score vs Bizkaia average per POI
// ---------------------------------------------------------------------------

function ComparisonChart({
  areaScores,
  regionScores,
  areaName,
}: {
  areaScores: PurposeBreakdown[];
  regionScores: PurposeBreakdown[];
  areaName: string;
}) {
  const { t } = useTranslation();
  const regionMap = new Map(
    regionScores.map((r) => [r.purpose, r.weighted_avg_score ?? 0]),
  );

  const chartData = areaScores
    .map((a) => ({
      purpose: a.purpose_label,
      area: a.weighted_avg_score ?? 0,
      bizkaia: regionMap.get(a.purpose) ?? 0,
      delta: (a.weighted_avg_score ?? 0) - (regionMap.get(a.purpose) ?? 0),
    }))
    .sort((a, b) => a.delta - b.delta);

  return (
    <Card className="col-span-full">
      <CardHeader>
        <CardTitle className="text-base">
          {areaName} {t("comparison.vsBizkaia")}
        </CardTitle>
        <CardDescription>
          {t("comparison.subtitle")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ left: 100, right: 16 }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis type="number" tick={{ fontSize: 11 }} className="fill-muted-foreground" />
              <YAxis type="category" dataKey="purpose" tick={{ fontSize: 11 }} className="fill-muted-foreground" width={100} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as { purpose: string; area: number; bizkaia: number; delta: number };
                  return (
                    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                      <p className="font-medium">{d.purpose}</p>
                      <p>{areaName}: {fmt(d.area)}</p>
                      <p>{t("comparison.bizkaiaAvg")} {fmt(d.bizkaia)}</p>
                      <p className={d.delta >= 0 ? "text-green-600" : "text-red-600"}>
                        {d.delta >= 0 ? "+" : ""}{fmt(d.delta)} {t("comparison.pts")}
                      </p>
                    </div>
                  );
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="area" name={areaName} fill={TRANSIT_COLOR} radius={[0, 3, 3, 0]} />
              <Bar dataKey="bizkaia" name={t("detailTable.bizkaiaAvg")} fill="#94a3b8" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// POI Detail Cards — population impact for each service
// ---------------------------------------------------------------------------

function PoiDetailCards({
  coverage,
  selectedPurpose,
  onSelect,
}: {
  coverage: ServiceCoverage[];
  selectedPurpose: string | null;
  onSelect: (code: string | null) => void;
}) {
  const { t } = useTranslation();
  const items = selectedPurpose
    ? coverage.filter((c) => c.purpose === selectedPurpose)
    : coverage;

  return (
    <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
      {items
        .sort((a, b) => a.pct_pop_30min - b.pct_pop_30min)
        .map((c) => {
          const notReached30 = c.total_population - c.pop_30min;
          const notReached60 = c.total_population - c.pop_60min;
          const pctBar30 = c.pct_pop_30min;

          return (
            <Card
              key={c.purpose}
              className={`cursor-pointer transition-colors ${selectedPurpose === c.purpose ? "border-primary" : "hover:border-primary/50"}`}
              onClick={() => onSelect(selectedPurpose === c.purpose ? null : c.purpose)}
            >
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">{c.purpose_label}</CardTitle>
                <CardDescription>
                  {t("poiDetail.medianTravel")} {fmt(c.median_travel_time)} {t("coverage.min")}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {/* 30-min coverage bar */}
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-muted-foreground">{t("poiDetail.within30")}</span>
                    <span className="font-mono font-medium">{fmt(c.pct_pop_30min)}%</span>
                  </div>
                  <div className="h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${pctBar30}%`,
                        backgroundColor: pctBar30 >= 80 ? "#1a9850" : pctBar30 >= 50 ? "#f5b731" : "#d73027",
                      }}
                    />
                  </div>
                </div>

                {/* 60-min coverage bar */}
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-muted-foreground">{t("poiDetail.within60")}</span>
                    <span className="font-mono font-medium">{fmt(c.pct_pop_60min)}%</span>
                  </div>
                  <div className="h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${c.pct_pop_60min}%`,
                        backgroundColor: c.pct_pop_60min >= 90 ? "#1a9850" : c.pct_pop_60min >= 60 ? "#f5b731" : "#d73027",
                      }}
                    />
                  </div>
                </div>

                {/* Population impact */}
                <div className="pt-1 border-t space-y-1">
                  {notReached30 > 50 && (
                    <p className="text-xs">
                      <span className="text-red-600 font-medium">{fmtPop(notReached30)}</span>
                      <span className="text-muted-foreground"> {t("poiDetail.peopleBeyond30")}</span>
                    </p>
                  )}
                  {notReached60 > 50 && (
                    <p className="text-xs">
                      <span className="text-red-600 font-medium">{fmtPop(notReached60)}</span>
                      <span className="text-muted-foreground"> {t("poiDetail.peopleBeyond60")}</span>
                    </p>
                  )}
                  {notReached60 <= 50 && notReached30 <= 50 && (
                    <p className="text-xs text-green-600 font-medium">
                      {t("poiDetail.fullCoverage30")}
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Key Findings — auto-generated insights
// ---------------------------------------------------------------------------

function KeyFindings({
  detail,
  areas,
  regionScores,
  regionCoverage,
}: {
  detail: AreaDetail;
  areas: AreaRanking[];
  regionScores: PurposeBreakdown[];
  regionCoverage: ServiceCoverage[];
}) {
  const { t } = useTranslation();
  const rank = areas.findIndex((a) => a.code === detail.code) + 1;
  const totalAreas = areas.length;

  const regionMap = new Map(
    regionScores.map((r) => [r.purpose, r.weighted_avg_score ?? 0]),
  );
  const regionCovMap = new Map(
    regionCoverage.map((r) => [`${r.purpose}`, r.pct_pop_30min]),
  );

  const sortedByScore = [...detail.purpose_scores].sort(
    (a, b) => (b.weighted_avg_score ?? 0) - (a.weighted_avg_score ?? 0),
  );
  const best = sortedByScore[0];
  const worst = sortedByScore[sortedByScore.length - 1];

  const aboveAvg = detail.purpose_scores.filter(
    (p) => (p.weighted_avg_score ?? 0) > (regionMap.get(p.purpose) ?? 0),
  ).length;
  const belowAvg = detail.purpose_scores.length - aboveAvg;

  const worstCoverage = [...detail.service_coverage].sort(
    (a, b) => a.pct_pop_30min - b.pct_pop_30min,
  )[0];

  const biggestGap = detail.service_coverage.reduce<{ purpose: string; label: string; gap: number } | null>(
    (worst, c) => {
      const regionPct = regionCovMap.get(c.purpose) ?? 0;
      const gap = regionPct - c.pct_pop_30min;
      if (!worst || gap > worst.gap) {
        return { purpose: c.purpose, label: c.purpose_label, gap };
      }
      return worst;
    },
    null,
  );

  const ordinalSuffix = (n: number): string => {
    if (n === 1) return t("findings.st");
    if (n === 2) return t("findings.nd");
    if (n === 3) return t("findings.rd");
    return t("findings.th");
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{t("findings.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm">
          <li>
            <span className="font-medium">{t("findings.ranking")}</span>{" "}
            <span className={rank <= Math.ceil(totalAreas / 3) ? "text-green-600" : rank > Math.ceil(totalAreas * 2 / 3) ? "text-red-600" : ""}>
              {rank}{ordinalSuffix(rank)} {t("findings.of")} {totalAreas}
            </span>{" "}
            {t("findings.withScore")} {fmt(detail.weighted_avg_score)}/100
          </li>
          <li>
            <span className="font-medium">{t("findings.bestService")}</span>{" "}
            {best?.purpose_label} ({fmt(best?.weighted_avg_score)})
          </li>
          <li>
            <span className="font-medium">{t("findings.worstService")}</span>{" "}
            <span className="text-red-600">{worst?.purpose_label}</span> ({fmt(worst?.weighted_avg_score)})
          </li>
          <li>
            <span className="font-medium">{t("findings.vsBizkaia")}</span>{" "}
            <span className={aboveAvg > belowAvg ? "text-green-600" : "text-red-600"}>
              {aboveAvg} {t("findings.above")}
            </span>, {belowAvg} {t("findings.belowAverage")}
          </li>
          {worstCoverage && worstCoverage.pct_pop_30min < 50 && (
            <li>
              <span className="font-medium">{t("findings.criticalGap")}</span>{" "}
              {t("findings.onlyPct")} <span className="text-red-600 font-medium">{fmt(worstCoverage.pct_pop_30min)}%</span> {t("findings.canReach")}{" "}
              {worstCoverage.purpose_label} {t("findings.within30min")}
              {worstCoverage.total_population - worstCoverage.pop_30min > 100 && (
                <> ({fmtPop(worstCoverage.total_population - worstCoverage.pop_30min)} {t("findings.peopleAffected")})</>
              )}
            </li>
          )}
          {biggestGap && biggestGap.gap > 5 && (
            <li>
              <span className="font-medium">{t("findings.largestLag")}</span>{" "}
              {biggestGap.label} {t("findings.is")} <span className="text-red-600 font-medium">{fmt(biggestGap.gap)} {t("comparison.pts")}</span> {t("findings.ptsBelowBizkaia")}
            </li>
          )}
        </ul>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Area Analysis Panel
// ---------------------------------------------------------------------------

function AreaAnalysisPanel({
  areaType,
  areas,
  regionScores,
  regionCoverage,
  socioProfiles,
}: {
  areaType: "comarca" | "municipality";
  areas: AreaRanking[];
  regionScores: PurposeBreakdown[];
  regionCoverage: ServiceCoverage[];
  socioProfiles: MunicipalitySocioProfile[];
}) {
  const { t } = useTranslation();
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [detail, setDetail] = useState<AreaDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [selectedPurpose, setSelectedPurpose] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const loadDetail = useCallback(
    async (code: string) => {
      setLoadingDetail(true);
      setSelectedPurpose(null);
      try {
        const result = await apiFetch<AreaDetail>(
          `/dashboard/${areaType}/${code}?departure_time=08:00`,
        );
        setDetail(result);
        setSelectedCode(code);
      } catch {
        setDetail(null);
      } finally {
        setLoadingDetail(false);
      }
    },
    [areaType],
  );

  const filtered = search
    ? areas.filter((a) => a.name.toLowerCase().includes(search.toLowerCase()))
    : areas;

  const purposeList = detail
    ? detail.purpose_scores
        .reduce<{ code: string; label: string }[]>((acc, ps) => {
          if (!acc.some((p) => p.code === ps.purpose)) {
            acc.push({ code: ps.purpose, label: ps.purpose_label });
          }
          return acc;
        }, [])
        .sort((a, b) => a.label.localeCompare(b.label))
    : [];

  return (
    <div className="space-y-6">
      {/* Area selector */}
      <div>
        {areaType === "municipality" && (
          <input
            type="text"
            placeholder={t("area.searchMunicipality")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-full max-w-xs rounded-md border bg-background px-3 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring mb-3"
          />
        )}
        <div className="grid gap-1.5 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8">
          {filtered.map((a) => {
            const sp = areaType === "municipality" ? socioProfiles.find((p) => p.muni_code === a.code || p.name === a.name) : null;
            return (
              <button
                key={a.code}
                onClick={() => loadDetail(a.code)}
                className={`rounded-md border px-3 py-2 text-left text-xs transition-colors ${
                  selectedCode === a.code
                    ? "border-primary bg-primary/5 text-foreground"
                    : "border-border text-muted-foreground hover:border-primary/50 hover:text-foreground"
                }`}
              >
                <p className="font-medium truncate">{a.name}</p>
                <p className="font-mono mt-0.5">{fmt(a.weighted_avg_score)}</p>
                {sp && (
                  <div className="flex gap-2 mt-0.5 text-[9px] text-muted-foreground">
                    {sp.pct_65_plus != null && <span className={`${(sp.pct_65_plus ?? 0) > 28 ? "text-red-500" : ""}`}>65+:{fmt(sp.pct_65_plus, 0)}%</span>}
                    {sp.renta_index != null && <span className={`${(sp.renta_index ?? 0) < 90 ? "text-red-500" : ""}`}>R:{fmt(sp.renta_index, 0)}</span>}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {loadingDetail && (
        <p className="text-sm text-muted-foreground">{t("area.loadingAnalysis")}</p>
      )}

      {detail && !loadingDetail && (
        <div className="space-y-6">
          {/* Row 1: KPIs + Key Findings */}
          <div className="grid gap-4 grid-cols-1 lg:grid-cols-3">
            <div className="lg:col-span-2 grid gap-4 grid-cols-2 lg:grid-cols-4">
              <KpiCard
                title={t("kpi.population")}
                value={fmtPop(detail.population)}
              />
              <KpiCard
                title={t("kpi.connectivityScore")}
                value={`${fmt(detail.weighted_avg_score)}/100`}
                subtitle={`${t("kpi.bizkaiaAvg")} ${fmt(
                  areas.reduce((s, a) => s + (a.weighted_avg_score ?? 0), 0) / areas.length,
                )}`}
              />
              <KpiCard
                title={t("kpi.gridCells")}
                value={detail.cell_count.toLocaleString()}
              />
              <KpiCard
                title={t("kpi.ranking")}
                value={`${areas.findIndex((a) => a.code === detail.code) + 1} / ${areas.length}`}
              />
            </div>
            <KeyFindings
              detail={detail}
              areas={areas}
              regionScores={regionScores}
              regionCoverage={regionCoverage}
            />
          </div>

          {/* Sociodemographic context for this area */}
          {areaType === "municipality" && (() => {
            const socio = socioProfiles.find((p) => p.muni_code === detail.code || p.name === detail.name);
            if (!socio) return null;
            return (
              <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
                {socio.pct_65_plus != null && (
                  <KpiCard
                    title={t("dash.socio.elderly")}
                    value={`${fmt(socio.pct_65_plus)}%`}
                    subtitle={`${fmtPop(socio.pop_65_plus)} ${t("ctx.demo.elderly").toLowerCase()}`}
                  />
                )}
                {socio.renta_index != null && (
                  <KpiCard
                    title={t("dash.socio.income")}
                    value={fmt(socio.renta_index)}
                    subtitle={socio.renta_index < 100 ? t("ctx.income.belowAvg") : t("ctx.income.aboveAvg")}
                  />
                )}
                {socio.vehicles_per_inhab != null && (
                  <KpiCard
                    title={t("dash.socio.cars")}
                    value={fmt(socio.vehicles_per_inhab, 2)}
                  />
                )}
                {socio.pop_0_17 != null && socio.pop_total != null && socio.pop_total > 0 && (
                  <KpiCard
                    title={t("ctx.demo.children")}
                    value={`${fmt(socio.pct_0_17)}%`}
                    subtitle={`${fmtPop(socio.pop_0_17)}`}
                  />
                )}
              </div>
            );
          })()}

          {/* Row 2: Comparison chart */}
          <ComparisonChart
            areaScores={detail.purpose_scores}
            regionScores={regionScores}
            areaName={detail.name}
          />

          {/* Purpose filter */}
          {purposeList.length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground mb-2">
                {t("area.selectService")}
              </p>
              <PurposeFilter
                purposes={purposeList}
                selected={selectedPurpose}
                onSelect={setSelectedPurpose}
              />
            </div>
          )}

          {/* Row 3: POI detail cards with population impact */}
          <div>
            <h3 className="text-sm font-medium mb-3">
              {selectedPurpose
                ? `${purposeList.find((p) => p.code === selectedPurpose)?.label ?? selectedPurpose} ${t("poiDetail.populationCoverage")}`
                : t("poiDetail.serviceCoverage")}
            </h3>
            <PoiDetailCards
              coverage={detail.service_coverage}
              selectedPurpose={selectedPurpose}
              onSelect={setSelectedPurpose}
            />
          </div>

          {/* Row 4: Detailed table with comparison */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("detailTable.title")}</CardTitle>
              <CardDescription>
                {t("detailTable.subtitle")}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-muted-foreground">
                      <th className="py-2 text-left font-medium">{t("detailTable.service")}</th>
                      <th className="py-2 text-right font-medium">{t("detailTable.score")}</th>
                      <th className="py-2 text-right font-medium">{t("detailTable.bizkaiaAvg")}</th>
                      <th className="py-2 text-right font-medium">{t("detailTable.delta")}</th>
                      <th className="py-2 text-right font-medium">{t("detailTable.travelMin")}</th>
                      <th className="py-2 text-right font-medium">{t("detailTable.coverage30")}</th>
                      <th className="py-2 text-right font-medium">{t("detailTable.unreached30")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...detail.purpose_scores]
                      .sort((a, b) => (b.weighted_avg_score ?? 0) - (a.weighted_avg_score ?? 0))
                      .map((s) => {
                        const regionAvg = regionScores.find((r) => r.purpose === s.purpose)?.weighted_avg_score ?? 0;
                        const delta = (s.weighted_avg_score ?? 0) - regionAvg;
                        const cov = detail.service_coverage.find((c) => c.purpose === s.purpose);
                        const unreached = cov ? cov.total_population - cov.pop_30min : 0;
                        return (
                          <tr
                            key={s.purpose}
                            className={`border-b last:border-0 cursor-pointer hover:bg-accent/50 ${selectedPurpose === s.purpose ? "bg-accent/30" : ""}`}
                            onClick={() => setSelectedPurpose(selectedPurpose === s.purpose ? null : s.purpose)}
                          >
                            <td className="py-2 font-medium">{s.purpose_label}</td>
                            <td className="py-2 text-right font-mono">{fmt(s.weighted_avg_score)}</td>
                            <td className="py-2 text-right font-mono text-muted-foreground">{fmt(regionAvg)}</td>
                            <td className={`py-2 text-right font-mono font-medium ${delta >= 0 ? "text-green-600" : "text-red-600"}`}>
                              {delta >= 0 ? "+" : ""}{fmt(delta)}
                            </td>
                            <td className="py-2 text-right font-mono">{fmt(s.avg_travel_time)}</td>
                            <td className="py-2 text-right font-mono">
                              {cov ? `${fmt(cov.pct_pop_30min)}%` : "\u2014"}
                            </td>
                            <td className="py-2 text-right font-mono">
                              {unreached > 50 ? (
                                <span className="text-red-600">{fmtPop(unreached)}</span>
                              ) : (
                                <span className="text-green-600">-</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {!detail && !loadingDetail && (
        <p className="text-sm text-muted-foreground">
          {areaType === "comarca" ? t("area.selectComarca") : t("area.selectMunicipality")}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overview Tab
// ---------------------------------------------------------------------------

function OverviewTab({
  summary: s,
  distribution,
  purposes,
  coverage,
  comarcas,
  municipalities,
  socioProfiles,
}: {
  summary: DashboardSummary;
  distribution: ScoreDistributionBucket[];
  purposes: PurposeBreakdown[];
  coverage: ServiceCoverage[];
  comarcas: AreaRanking[];
  municipalities: AreaRanking[];
  socioProfiles: MunicipalitySocioProfile[];
}) {
  const { t } = useTranslation();

  // ── Computed insights ──
  const serviceDeserts = [...coverage].sort(
    (a, b) => a.pct_pop_30min - b.pct_pop_30min,
  );

  const medianScore =
    municipalities.length > 0
      ? [...municipalities].sort(
          (a, b) => (a.weighted_avg_score ?? 0) - (b.weighted_avg_score ?? 0),
        )[Math.floor(municipalities.length / 2)]?.weighted_avg_score ?? 0
      : 0;
  const equityHotspots = municipalities
    .filter(
      (m) => m.population > 5000 && (m.weighted_avg_score ?? 0) < medianScore,
    )
    .sort(
      (a, b) =>
        b.population * (100 - (b.weighted_avg_score ?? 0)) -
        a.population * (100 - (a.weighted_avg_score ?? 0)),
    )
    .slice(0, 12);

  const totalPop = s.total_population;
  const lowScorePop = distribution
    .filter((d) => d.range_max <= 30)
    .reduce((s, d) => s + d.population, 0);

  const topComarca = comarcas[0];
  const bottomComarca = comarcas[comarcas.length - 1];
  const scoreGap =
    topComarca && bottomComarca
      ? (topComarca.weighted_avg_score ?? 0) -
        (bottomComarca.weighted_avg_score ?? 0)
      : 0;

  const topMunis = municipalities.slice(0, 15);
  const bottomMunis = [...municipalities].reverse().slice(0, 15);

  return (
    <>
      {/* KPI Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <KpiCard
          title={t("kpi.totalPopulation")}
          value={fmtPop(s.total_population)}
          subtitle={`${fmtPop(s.populated_cells)} ${t("kpi.populatedCells")}`}
        />
        <KpiCard
          title={t("kpi.weightedAvgScore")}
          value={`${fmt(s.weighted_avg_score)}/100`}
          subtitle={`${t("kpi.median")} ${fmt(s.median_score)}`}
        />
        <KpiCard
          title={t("kpi.destinationsMapped")}
          value={s.destination_count.toLocaleString()}
          subtitle={`${s.transit_route_count} ${t("kpi.transitRoutes")}`}
        />
        <KpiCard
          title={t("kpi.transitStops")}
          value={s.transit_stop_count.toLocaleString()}
          subtitle={`${s.total_cells.toLocaleString()} ${t("kpi.gridCells").toLowerCase()}`}
        />
      </div>

      {/* ── Headline Insights ── */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">{t("insights.title")}</CardTitle>
          <CardDescription>
            {t("insights.subtitle")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
            {/* Equity */}
            <div className="rounded-md border p-4 space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {t("insights.equity")}
              </p>
              <p className="text-sm">
                <span className="text-red-600 font-semibold">
                  {fmtPop(lowScorePop)}
                </span>{" "}
                ({totalPop > 0 ? fmt((lowScorePop / totalPop) * 100) : "0"}%) {t("insights.equityDesc")}
              </p>
              {scoreGap > 0 && topComarca && bottomComarca && (
                <p className="text-xs text-muted-foreground">
                  {fmt(scoreGap)}{t("insights.pointGap")} {topComarca.name} {t("insights.and")}{" "}
                  {bottomComarca.name}.
                </p>
              )}
            </div>

            {/* Worst service gap */}
            {serviceDeserts[0] && (
              <div className="rounded-md border p-4 space-y-1">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  {t("insights.worstServiceGap")}
                </p>
                <p className="text-sm">
                  <span className="font-semibold">
                    {serviceDeserts[0].purpose_label}
                  </span>
                  : {t("insights.only")}{" "}
                  <span className="text-red-600 font-semibold">
                    {fmt(serviceDeserts[0].pct_pop_30min)}%
                  </span>{" "}
                  {t("insights.ofPopWithin30")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {fmtPop(
                    serviceDeserts[0].total_population -
                      serviceDeserts[0].pop_30min,
                  )}{" "}
                  {t("insights.peopleAffected")}{" "}
                  {fmt(serviceDeserts[0].median_travel_time)} {t("insights.min")}
                </p>
              </div>
            )}

            {/* Health access */}
            {(() => {
              const hospital = coverage.find(
                (c) => c.purpose === "hospital",
              );
              if (!hospital) return null;
              const unreached = hospital.total_population - hospital.pop_30min;
              return (
                <div className="rounded-md border p-4 space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {t("insights.hospitalAccess")}
                  </p>
                  <p className="text-sm">
                    <span className="text-red-600 font-semibold">
                      {fmtPop(unreached)}
                    </span>{" "}
                    {t("insights.hospitalDesc")}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {fmt(hospital.pct_pop_60min)}% {t("insights.coveredWithin60")}{" "}
                    {fmt(hospital.median_travel_time)} {t("insights.min")}
                  </p>
                </div>
              );
            })()}

            {/* Education access */}
            {(() => {
              const edu = coverage.find(
                (c) => c.purpose === "centro_educativo",
              );
              const bach = coverage.find((c) => c.purpose === "bachiller");
              if (!edu || !bach) return null;
              return (
                <div className="rounded-md border p-4 space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {t("insights.educationAccess")}
                  </p>
                  <p className="text-sm">
                    <span className="text-green-600 font-semibold">
                      {fmt(edu.pct_pop_30min)}%
                    </span>{" "}
                    {t("insights.reachCentroEdu")}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t("insights.bachillerCoverage")}{" "}
                    {fmt(bach.pct_pop_30min)}% &mdash;{" "}
                    {fmtPop(bach.total_population - bach.pop_30min)}{" "}
                    {t("insights.studentsAffected")}
                  </p>
                </div>
              );
            })()}

            {/* Geographic disparity */}
            {topComarca && bottomComarca && (
              <div className="rounded-md border p-4 space-y-1">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  {t("insights.geographicDisparity")}
                </p>
                <p className="text-sm">
                  <span className="font-semibold">{topComarca.name}</span>{" "}
                  {t("insights.scores")}{" "}
                  <span className="text-green-600 font-semibold">
                    {fmt(topComarca.weighted_avg_score)}
                  </span>{" "}
                  {t("insights.vs")}{" "}
                  <span className="text-red-600 font-semibold">
                    {fmt(bottomComarca.weighted_avg_score)}
                  </span>{" "}
                  {t("insights.in")} {bottomComarca.name}.
                </p>
                <p className="text-xs text-muted-foreground">
                  {fmtPop(bottomComarca.population)} {t("insights.peopleLiveInLeast")}
                </p>
              </div>
            )}

            {/* Overall coverage */}
            {(() => {
              const osakidetza = coverage.find(
                (c) => c.purpose === "osakidetza",
              );
              const consulta = coverage.find(
                (c) => c.purpose === "consulta_general",
              );
              if (!osakidetza || !consulta) return null;
              return (
                <div className="rounded-md border p-4 space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {t("insights.primaryHealth")}
                  </p>
                  <p className="text-sm">
                    <span className="text-green-600 font-semibold">
                      {fmt(consulta.pct_pop_30min)}%
                    </span>{" "}
                    {t("insights.canReachConsulta")}{" "}
                    <span className="text-green-600 font-semibold">
                      {fmt(osakidetza.pct_pop_30min)}%
                    </span>{" "}
                    {t("insights.osakidetzaWithin30")}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t("insights.primaryCareWell")}
                  </p>
                </div>
              );
            })()}
          </div>
        </CardContent>
      </Card>

      {/* ── Sociodemographic Context ── */}
      {socioProfiles.length > 0 && (() => {
        const withData = socioProfiles.filter(
          (p) => p.weighted_avg_score != null && p.renta_index != null && p.vehicles_per_inhab != null && p.pct_65_plus != null,
        );
        if (withData.length === 0) return null;

        const avgScore = withData.reduce((s, p) => s + (p.weighted_avg_score ?? 0), 0) / withData.length;
        const avgIncome = withData.reduce((s, p) => s + (p.renta_index ?? 0), 0) / withData.length;
        const avgCars = withData.reduce((s, p) => s + (p.vehicles_per_inhab ?? 0), 0) / withData.length;

        // Low income + low connectivity
        const lowIncomeLowConn = withData.filter(
          (p) => (p.renta_index ?? 0) < avgIncome && (p.weighted_avg_score ?? 0) < avgScore,
        );

        // Elderly in low-connectivity areas
        const lowConnMunis = withData.filter((p) => (p.weighted_avg_score ?? 0) < avgScore);
        const elderlyInLowConn = lowConnMunis.reduce((s, p) => s + (p.pop_65_plus ?? 0), 0);

        // Car-dependent: high cars + low transit
        const carDependent = withData.filter(
          (p) => (p.vehicles_per_inhab ?? 0) > avgCars && (p.weighted_avg_score ?? 0) < avgScore,
        );

        return (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">{t("dash.socio.title")}</CardTitle>
              <CardDescription>{t("dash.socio.subtitle")}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
                {/* Low income + low connectivity */}
                <div className="rounded-md border p-4 space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {t("dash.socio.lowIncomeLowConn")}
                  </p>
                  <p className="text-sm">
                    <span className="text-red-600 font-semibold">{lowIncomeLowConn.length}</span>{" "}
                    {t("dash.socio.lowIncomeLowConnDesc")}
                  </p>
                  {lowIncomeLowConn.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      {lowIncomeLowConn
                        .sort((a, b) => (b.population ?? 0) - (a.population ?? 0))
                        .slice(0, 4)
                        .map((p) => p.name)
                        .join(", ")}
                    </p>
                  )}
                </div>

                {/* Elderly access gap */}
                <div className="rounded-md border p-4 space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {t("dash.socio.elderlyAccess")}
                  </p>
                  <p className="text-sm">
                    <span className="text-red-600 font-semibold">{fmtPop(elderlyInLowConn)}</span>{" "}
                    {t("dash.socio.elderlyAccessDesc")}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {lowConnMunis.length} / {withData.length} {t("ctx.vuln.highVulnMunis")}
                  </p>
                </div>

                {/* Car dependence */}
                <div className="rounded-md border p-4 space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {t("dash.socio.carDependence")}
                  </p>
                  <p className="text-sm">
                    <span className="text-red-600 font-semibold">{carDependent.length}</span>{" "}
                    {t("dash.socio.carDependenceDesc")}
                  </p>
                  {carDependent.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      {t("ctx.cars.bizkaia")}: {fmt(avgCars, 2)} veh/inhab
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })()}

      {/* ── Demographic Service Gaps ── */}
      {socioProfiles.length > 0 && coverage.length > 0 && (() => {
        const withData = socioProfiles.filter((p) => p.pop_total != null && p.weighted_avg_score != null);
        if (withData.length === 0) return null;

        const avgScore = withData.reduce((s, p) => s + (p.weighted_avg_score ?? 0), 0) / withData.length;
        const avgIncome = withData.filter((p) => p.renta_index != null).reduce((s, p) => s + (p.renta_index ?? 0), 0) /
          (withData.filter((p) => p.renta_index != null).length || 1);
        const avgCars = withData.filter((p) => p.vehicles_per_inhab != null).reduce((s, p) => s + (p.vehicles_per_inhab ?? 0), 0) /
          (withData.filter((p) => p.vehicles_per_inhab != null).length || 1);

        // Elderly in areas with poor hospital access (score < avg)
        const lowConnMunis = withData.filter((p) => (p.weighted_avg_score ?? 0) < avgScore);
        const elderlyInLowConn = lowConnMunis.reduce((s, p) => s + (p.pop_65_plus ?? 0), 0);

        // Children in low-connectivity areas
        const childrenInLowConn = lowConnMunis.reduce((s, p) => s + (p.pop_0_17 ?? 0), 0);

        // Youth (18-25) in low connectivity
        const youthInLowConn = lowConnMunis.reduce((s, p) => s + (p.pop_18_25 ?? 0), 0);

        // Low income + low connectivity pop
        const lowIncomeLowConn = withData.filter(
          (p) => p.renta_index != null && (p.renta_index ?? 0) < avgIncome && (p.weighted_avg_score ?? 0) < avgScore,
        );
        const lowIncPop = lowIncomeLowConn.reduce((s, p) => s + (p.population ?? 0), 0);

        // Car-poor + transit-poor
        const carlessTrapped = withData.filter(
          (p) => p.vehicles_per_inhab != null && (p.vehicles_per_inhab ?? 0) < avgCars && (p.weighted_avg_score ?? 0) < avgScore,
        );
        const carlessPop = carlessTrapped.reduce((s, p) => s + (p.population ?? 0), 0);

        return (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">{t("dash.demoGaps.title")}</CardTitle>
              <CardDescription>{t("dash.demoGaps.subtitle")}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
                <div className="rounded-md border p-4 space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {t("dash.demoGaps.elderlyHospital")}
                  </p>
                  <p className="text-sm">
                    <span className="text-red-600 font-semibold">{fmtPop(elderlyInLowConn)}</span>{" "}
                    {t("dash.demoGaps.elderlyHospitalDesc")}
                  </p>
                </div>
                <div className="rounded-md border p-4 space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {t("dash.demoGaps.childrenSchool")}
                  </p>
                  <p className="text-sm">
                    <span className="text-red-600 font-semibold">{fmtPop(childrenInLowConn)}</span>{" "}
                    {t("dash.demoGaps.childrenSchoolDesc")}
                  </p>
                </div>
                <div className="rounded-md border p-4 space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {t("dash.demoGaps.youthUni")}
                  </p>
                  <p className="text-sm">
                    <span className="text-red-600 font-semibold">{fmtPop(youthInLowConn)}</span>{" "}
                    {t("dash.demoGaps.youthUniDesc")}
                  </p>
                </div>
                <div className="rounded-md border p-4 space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {t("dash.demoGaps.lowIncomeHealth")}
                  </p>
                  <p className="text-sm">
                    <span className="text-red-600 font-semibold">{fmtPop(lowIncPop)}</span>{" "}
                    {t("dash.demoGaps.lowIncomeHealthDesc")}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {lowIncomeLowConn.slice(0, 4).map((p) => p.name).join(", ")}
                  </p>
                </div>
                <div className="rounded-md border p-4 space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {t("dash.demoGaps.carlessTrapped")}
                  </p>
                  <p className="text-sm">
                    <span className="text-red-600 font-semibold">{fmtPop(carlessPop)}</span>{" "}
                    {t("dash.demoGaps.carlessTrappedDesc")}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {carlessTrapped.slice(0, 4).map((p) => p.name).join(", ")}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })()}

      {/* ── Scatter: Connectivity vs Socio ── */}
      {socioProfiles.length > 0 && (() => {
        const withData = socioProfiles.filter(
          (p) => p.weighted_avg_score != null && p.renta_index != null && p.population != null,
        );
        if (withData.length === 0) return null;

        type ScatterDot = { name: string; x: number; y: number; z: number; elderly: number; income: number; cars: number };

        const scatterData: ScatterDot[] = withData.map((p) => ({
          name: p.name,
          x: p.renta_index ?? 0,
          y: p.weighted_avg_score ?? 0,
          z: p.population ?? 0,
          elderly: p.pct_65_plus ?? 0,
          income: p.renta_index ?? 0,
          cars: p.vehicles_per_inhab ?? 0,
        }));

        const avgScore = scatterData.reduce((s, d) => s + d.y, 0) / scatterData.length;
        const avgX = scatterData.reduce((s, d) => s + d.x, 0) / scatterData.length;

        return (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("dash.scatter.title")}</CardTitle>
              <CardDescription>{t("dash.scatter.subtitle")}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[380px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ left: 10, right: 20, top: 10, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                    <XAxis
                      type="number" dataKey="x" name={t("dash.scatter.income")}
                      tick={{ fontSize: 11 }} className="fill-muted-foreground"
                      label={{ value: t("dash.scatter.income"), position: "insideBottom", offset: -10, fontSize: 11 }}
                    />
                    <YAxis
                      type="number" dataKey="y" name={t("dash.scatter.connectivity")}
                      tick={{ fontSize: 11 }} className="fill-muted-foreground"
                      label={{ value: t("dash.scatter.connectivity"), angle: -90, position: "insideLeft", fontSize: 11 }}
                    />
                    <ZAxis type="number" dataKey="z" range={[30, 500]} />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const d = payload[0].payload as ScatterDot;
                        return (
                          <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                            <p className="font-medium">{d.name}</p>
                            <p>{t("dash.scatter.connectivity")}: {fmt(d.y)}/100</p>
                            <p>{t("dash.scatter.income")}: {fmt(d.income)}</p>
                            <p>{t("dash.scatter.elderly")}: {fmt(d.elderly)}%</p>
                            <p>{t("dash.scatter.cars")}: {fmt(d.cars, 2)}</p>
                            <p>{t("ctx.vuln.population")}: {fmtPop(d.z)}</p>
                          </div>
                        );
                      }}
                    />
                    {/* Reference lines for averages */}
                    <Scatter data={scatterData}>
                      {scatterData.map((d, i) => (
                        <RCell
                          key={i}
                          fill={
                            d.x < avgX && d.y < avgScore ? "#dc2626" :  // low income + low conn = red
                            d.x >= avgX && d.y >= avgScore ? "#22c55e" : // high both = green
                            "#94a3b8" // mixed = grey
                          }
                          fillOpacity={0.65}
                        />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
              <div className="flex gap-4 justify-center mt-2 text-[10px] text-muted-foreground">
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-red-600 inline-block" /> {t("dash.socio.lowIncomeLowConn")}</span>
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-green-600 inline-block" /> {t("ctx.income.aboveAvg")}</span>
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-slate-400 inline-block" /> {t("ctx.income.mixed")}</span>
              </div>
            </CardContent>
          </Card>
        );
      })()}

      {/* ── Service Deserts — Population Impact ── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {t("deserts.title")}
          </CardTitle>
          <CardDescription>
            {t("deserts.subtitle")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {serviceDeserts.map((c) => {
              const unreached = c.total_population - c.pop_30min;
              const pct30 = c.pct_pop_30min;
              return (
                <div key={c.purpose} className="flex items-center gap-4">
                  <div className="w-32 shrink-0 text-sm font-medium truncate">
                    {c.purpose_label}
                  </div>
                  <div className="flex-1">
                    <div className="h-5 bg-secondary rounded-full overflow-hidden flex">
                      <div
                        className="h-full rounded-l-full transition-all flex items-center justify-end pr-1"
                        style={{
                          width: `${pct30}%`,
                          backgroundColor:
                            pct30 >= 80
                              ? "#1a9850"
                              : pct30 >= 50
                                ? "#f5b731"
                                : "#d73027",
                          minWidth: pct30 > 5 ? undefined : "2px",
                        }}
                      >
                        {pct30 >= 15 && (
                          <span className="text-[10px] text-white font-medium">
                            {fmt(pct30, 0)}%
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="w-40 shrink-0 text-right">
                    {unreached > 100 ? (
                      <span className="text-xs">
                        <span className="text-red-600 font-medium">
                          {fmtPop(unreached)}
                        </span>{" "}
                        <span className="text-muted-foreground">
                          {t("deserts.unreached")}
                        </span>
                      </span>
                    ) : (
                      <span className="text-xs text-green-600 font-medium">
                        {t("deserts.fullCoverage")}
                      </span>
                    )}
                  </div>
                  <div className="w-16 shrink-0 text-right text-xs text-muted-foreground font-mono">
                    {fmt(c.median_travel_time, 0)} {t("coverage.min")}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Score Distribution + Population by Score */}
      <div className="grid gap-4 grid-cols-1 lg:grid-cols-4">
        <ScoreDistributionChart data={distribution} />
        <PopulationByScoreChart data={distribution} />
      </div>

      {/* ── Equity Hotspots ── */}
      {equityHotspots.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {t("equity.title")}
            </CardTitle>
            <CardDescription>
              {t("equity.subtitlePre")} ({fmt(medianScore)}){t("equity.subtitlePost")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="py-2 text-left font-medium">{t("equity.municipality")}</th>
                    <th className="py-2 text-right font-medium">{t("equity.population")}</th>
                    <th className="py-2 text-right font-medium">{t("equity.score")}</th>
                    <th className="py-2 text-right font-medium">
                      {t("equity.gapVsMedian")}
                    </th>
                    <th className="py-2 text-right font-medium">{t("dash.socio.elderly")}</th>
                    <th className="py-2 text-right font-medium">{t("dash.socio.income")}</th>
                    <th className="py-2 text-right font-medium">{t("dash.socio.cars")}</th>
                    <th className="py-2 text-left font-medium pl-4">
                      {t("equity.connectivityLevel")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {equityHotspots.map((m) => {
                    const gap = medianScore - (m.weighted_avg_score ?? 0);
                    const score = m.weighted_avg_score ?? 0;
                    const barWidth = Math.min(score, 100);
                    const socio = socioProfiles.find((p) => p.name === m.name || p.muni_code === m.code);
                    return (
                      <tr
                        key={m.code}
                        className="border-b last:border-0"
                      >
                        <td className="py-2 font-medium">{m.name}</td>
                        <td className="py-2 text-right font-mono">
                          {fmtPop(m.population)}
                        </td>
                        <td className="py-2 text-right font-mono">
                          {fmt(score)}
                        </td>
                        <td className="py-2 text-right font-mono text-red-600">
                          -{fmt(gap)}
                        </td>
                        <td className="py-2 text-right font-mono">
                          {socio?.pct_65_plus != null ? (
                            <span className={(socio.pct_65_plus ?? 0) > 28 ? "text-red-600 font-medium" : ""}>
                              {fmt(socio.pct_65_plus)}%
                            </span>
                          ) : "—"}
                        </td>
                        <td className="py-2 text-right font-mono">
                          {socio?.renta_index != null ? (
                            <span className={(socio.renta_index ?? 0) < 90 ? "text-red-600 font-medium" : ""}>
                              {fmt(socio.renta_index)}
                            </span>
                          ) : "—"}
                        </td>
                        <td className="py-2 text-right font-mono">
                          {socio?.vehicles_per_inhab != null ? fmt(socio.vehicles_per_inhab, 2) : "—"}
                        </td>
                        <td className="py-2 pl-4 w-40">
                          <div className="h-2 bg-secondary rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${barWidth}%`,
                                backgroundColor:
                                  score >= 40
                                    ? "#f5b731"
                                    : score >= 20
                                      ? "#fc8d59"
                                      : "#d73027",
                              }}
                            />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Purpose Breakdown + Travel Times */}
      <div className="grid gap-4 grid-cols-1 lg:grid-cols-4">
        <PurposeBarChart data={purposes} />
        <TravelTimeBarChart data={purposes} />
      </div>

      {/* Service Coverage */}
      {coverage.length > 0 && <CoverageChart data={coverage} />}

      {/* Comarca Ranking */}
      {comarcas.length > 0 && (
        <AreaRankingChart
          data={comarcas}
          title={t("ranking.comarca")}
          description={t("ranking.comarcaDesc")}
          color={TRANSIT_COLOR}
        />
      )}

      {/* Municipality Rankings */}
      {municipalities.length > 0 && (
        <div className="grid gap-4 grid-cols-1 lg:grid-cols-4">
          <AreaRankingChart
            data={topMunis}
            title={t("ranking.bestMunis")}
            description={t("ranking.bestMunisDesc")}
            color={TRANSIT_COLOR}
            maxItems={15}
          />
          <AreaRankingChart
            data={bottomMunis}
            title={t("ranking.worstMunis")}
            description={t("ranking.worstMunisDesc")}
            color="hsl(0, 84%, 60%)"
            maxItems={15}
          />
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("overview");
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [distribution, setDistribution] = useState<ScoreDistributionBucket[]>([]);
  const [purposes, setPurposes] = useState<PurposeBreakdown[]>([]);
  const [comarcas, setComarcas] = useState<AreaRanking[]>([]);
  const [municipalities, setMunicipalities] = useState<AreaRanking[]>([]);
  const [coverage, setCoverage] = useState<ServiceCoverage[]>([]);
  const [socioProfiles, setSocioProfiles] = useState<MunicipalitySocioProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, d, p, co, m, c, sp] = await Promise.all([
        apiFetch<DashboardSummary>("/dashboard/summary?departure_time=08:00"),
        apiFetch<ScoreDistributionBucket[]>("/dashboard/score-distribution?departure_time=08:00"),
        apiFetch<PurposeBreakdown[]>("/dashboard/purpose-breakdown?departure_time=08:00"),
        apiFetch<AreaRanking[]>("/dashboard/comarca-ranking?departure_time=08:00"),
        apiFetch<AreaRanking[]>("/dashboard/municipality-ranking?departure_time=08:00"),
        apiFetch<ServiceCoverage[]>("/dashboard/service-coverage?departure_time=08:00"),
        apiFetch<MunicipalitySocioProfile[]>("/sociodemographic/profiles").catch(() => [] as MunicipalitySocioProfile[]),
      ]);
      setSummary(s);
      setDistribution(d);
      setPurposes(p);
      setComarcas(co);
      setMunicipalities(m);
      setCoverage(c);
      setSocioProfiles(sp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-muted-foreground">{t("dash.loading")}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 lg:p-8 w-full">
        <h1 className="text-lg font-semibold">{t("dash.error.title")}</h1>
        <p className="mt-4 text-sm text-destructive">{error}</p>
        <Button onClick={load} variant="outline" size="sm" className="mt-3">{t("dash.retry")}</Button>
      </div>
    );
  }

  const s = summary!;

  return (
    <div className="p-6 lg:p-8 w-full space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-lg font-semibold">{t("dash.title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("dash.subtitle")}
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm">
            <Link href="/map">{t("dash.openMap")}</Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href="/about">{t("dash.methodology")}</Link>
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b flex gap-0">
        <TabButton active={tab === "overview"} onClick={() => setTab("overview")}>
          {t("dash.tab.overview")}
        </TabButton>
        <TabButton active={tab === "comarcas"} onClick={() => setTab("comarcas")}>
          {t("dash.tab.comarcas")} ({comarcas.length})
        </TabButton>
        <TabButton active={tab === "municipios"} onClick={() => setTab("municipios")}>
          {t("dash.tab.municipios")} ({municipalities.length})
        </TabButton>
      </div>

      {/* Overview Tab */}
      {tab === "overview" && (
        <OverviewTab
          summary={s}
          distribution={distribution}
          purposes={purposes}
          coverage={coverage}
          comarcas={comarcas}
          municipalities={municipalities}
          socioProfiles={socioProfiles}
        />
      )}

      {/* Comarcas Tab */}
      {tab === "comarcas" && (
        <AreaAnalysisPanel areaType="comarca" areas={comarcas} regionScores={purposes} regionCoverage={coverage} socioProfiles={socioProfiles} />
      )}

      {/* Municipios Tab */}
      {tab === "municipios" && (
        <AreaAnalysisPanel areaType="municipality" areas={municipalities} regionScores={purposes} regionCoverage={coverage} socioProfiles={socioProfiles} />
      )}
    </div>
  );
}
