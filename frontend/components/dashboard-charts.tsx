"use client";

import type { TablerIcon as LucideIcon } from "@tabler/icons-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type {
  ScoreDistributionBucket,
  PurposeBreakdown,
  ServiceCoverage,
} from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const SCORE_COLORS = [
  "#7f1b00", "#c4321a", "#e05a2b", "#f0892e", "#f5b731",
  "#e8d534", "#b5d935", "#6ec440", "#2da84e", "#0e5e8c",
];

export const TRANSIT_COLOR = "hsl(221, 83%, 53%)";

const COVERAGE_COLORS = [
  "#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function fmt(n: number | null | undefined, decimals = 1, locale = "es"): string {
  if (n == null) return "\u2014";
  return n.toLocaleString(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function fmtPop(n: number | null | undefined, locale = "es"): string {
  if (n == null) return "\u2014";
  return Math.round(n).toLocaleString(locale);
}

// ---------------------------------------------------------------------------
// KPI Card
// ---------------------------------------------------------------------------

export function KpiCard({
  title,
  value,
  subtitle,
  icon: Icon,
}: {
  title: string;
  value: string;
  subtitle?: string;
  icon?: LucideIcon;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardDescription>{title}</CardDescription>
          {Icon && <Icon className="size-4 text-muted-foreground/60" />}
        </div>
        <CardTitle className="text-2xl tabular-nums">{value}</CardTitle>
      </CardHeader>
      {subtitle && (
        <CardContent>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </CardContent>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Score Distribution
// ---------------------------------------------------------------------------

export function ScoreDistributionChart({
  data,
}: {
  data: ScoreDistributionBucket[];
}) {
  const { t } = useTranslation();
  return (
    <Card className="col-span-full lg:col-span-2">
      <CardHeader>
        <CardTitle className="text-base">
          {t("dist.scoreDistribution")}
        </CardTitle>
        <CardDescription>
          {t("dist.scoreDistributionDesc")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[260px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ left: -10, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="range_label" tick={{ fontSize: 11 }} className="fill-muted-foreground" />
              <YAxis tick={{ fontSize: 11 }} className="fill-muted-foreground" />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as ScoreDistributionBucket;
                  return (
                    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                      <p className="font-medium">{t("dist.score")} {d.range_label}</p>
                      <p>{t("dist.cells")} {d.cell_count.toLocaleString()}</p>
                      <p>{t("dist.populationLabel")} {fmtPop(d.population)}</p>
                    </div>
                  );
                }}
              />
              <Bar dataKey="cell_count" radius={[3, 3, 0, 0]}>
                {data.map((_, i) => (
                  <Cell key={i} fill={SCORE_COLORS[i] ?? SCORE_COLORS[9]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Population by Score
// ---------------------------------------------------------------------------

export function PopulationByScoreChart({
  data,
}: {
  data: ScoreDistributionBucket[];
}) {
  const { t } = useTranslation();
  return (
    <Card className="col-span-full lg:col-span-2">
      <CardHeader>
        <CardTitle className="text-base">
          {t("popScore.title")}
        </CardTitle>
        <CardDescription>
          {t("popScore.subtitle")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[260px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ left: -10, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="range_label" tick={{ fontSize: 11 }} className="fill-muted-foreground" />
              <YAxis
                tick={{ fontSize: 11 }}
                className="fill-muted-foreground"
                tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as ScoreDistributionBucket;
                  return (
                    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                      <p className="font-medium">{t("dist.score")} {d.range_label}</p>
                      <p>{t("dist.populationLabel")} {fmtPop(d.population)}</p>
                      <p>{t("dist.cells")} {d.cell_count.toLocaleString()}</p>
                    </div>
                  );
                }}
              />
              <Bar dataKey="population" radius={[3, 3, 0, 0]}>
                {data.map((_, i) => (
                  <Cell key={i} fill={SCORE_COLORS[i] ?? SCORE_COLORS[9]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Purpose Breakdown
// ---------------------------------------------------------------------------

export function PurposeBarChart({
  data,
  selectedPurpose,
  onSelect,
}: {
  data: PurposeBreakdown[];
  selectedPurpose?: string | null;
  onSelect?: (purpose: string | null) => void;
}) {
  const { t } = useTranslation();
  const chartData = data
    .map((d) => ({
      purpose: d.purpose_label,
      purposeCode: d.purpose,
      score: d.weighted_avg_score ?? 0,
      travel_time: d.avg_travel_time,
    }))
    .sort((a, b) => b.score - a.score);

  return (
    <Card className="col-span-full lg:col-span-2">
      <CardHeader>
        <CardTitle className="text-base">{t("purpose.title")}</CardTitle>
        <CardDescription>
          {t("purpose.subtitle")}
          {onSelect && ` ${t("purpose.clickToFilter")}`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ left: 100, right: 16 }}
              onClick={(e) => {
                if (!onSelect || !e?.activePayload?.[0]) return;
                const code = (e.activePayload[0].payload as { purposeCode: string }).purposeCode;
                onSelect(selectedPurpose === code ? null : code);
              }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} className="fill-muted-foreground" />
              <YAxis type="category" dataKey="purpose" tick={{ fontSize: 11 }} className="fill-muted-foreground" width={100} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as { purpose: string; score: number; travel_time: number | null };
                  return (
                    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                      <p className="font-medium">{d.purpose}</p>
                      <p>{t("charts.score")} {fmt(d.score)}</p>
                      {d.travel_time != null && <p>{t("purpose.avgTravel")} {fmt(d.travel_time)} {t("coverage.min")}</p>}
                    </div>
                  );
                }}
              />
              <Bar dataKey="score" radius={[0, 3, 3, 0]} style={{ cursor: onSelect ? "pointer" : undefined }}>
                {chartData.map((d, i) => (
                  <Cell
                    key={i}
                    fill={TRANSIT_COLOR}
                    opacity={!selectedPurpose || d.purposeCode === selectedPurpose ? 1 : 0.25}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Travel Time Chart
// ---------------------------------------------------------------------------

export function TravelTimeBarChart({
  data,
  selectedPurpose,
  onSelect,
}: {
  data: PurposeBreakdown[];
  selectedPurpose?: string | null;
  onSelect?: (purpose: string | null) => void;
}) {
  const { t } = useTranslation();
  const chartData = data
    .filter((d) => d.avg_travel_time != null)
    .map((d) => ({
      purpose: d.purpose_label,
      purposeCode: d.purpose,
      travel_time: d.avg_travel_time!,
    }))
    .sort((a, b) => b.travel_time - a.travel_time);

  return (
    <Card className="col-span-full lg:col-span-2">
      <CardHeader>
        <CardTitle className="text-base">{t("travel.title")}</CardTitle>
        <CardDescription>
          {t("travel.subtitle")}
          {onSelect && ` ${t("travel.clickToFilter")}`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ left: 100, right: 16 }}
              onClick={(e) => {
                if (!onSelect || !e?.activePayload?.[0]) return;
                const code = (e.activePayload[0].payload as { purposeCode: string }).purposeCode;
                onSelect(selectedPurpose === code ? null : code);
              }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis type="number" tick={{ fontSize: 11 }} className="fill-muted-foreground" unit=" min" />
              <YAxis type="category" dataKey="purpose" tick={{ fontSize: 11 }} className="fill-muted-foreground" width={100} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as { purpose: string; travel_time: number };
                  return (
                    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                      <p className="font-medium">{d.purpose}</p>
                      <p>{t("travel.avgTravel")} {fmt(d.travel_time)} {t("coverage.min")}</p>
                    </div>
                  );
                }}
              />
              <Bar dataKey="travel_time" radius={[0, 3, 3, 0]} style={{ cursor: onSelect ? "pointer" : undefined }}>
                {chartData.map((d, i) => (
                  <Cell
                    key={i}
                    fill="hsl(0, 84%, 60%)"
                    opacity={!selectedPurpose || d.purposeCode === selectedPurpose ? 1 : 0.25}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Area Ranking
// ---------------------------------------------------------------------------

export interface AreaRanking {
  name: string;
  code: string;
  cell_count: number;
  population: number;
  avg_score: number | null;
  weighted_avg_score: number | null;
}

export function AreaRankingChart({
  data,
  title,
  description,
  color,
  maxItems,
  onSelect,
}: {
  data: AreaRanking[];
  title: string;
  description: string;
  color: string;
  maxItems?: number;
  onSelect?: (code: string) => void;
}) {
  const { t } = useTranslation();
  const slice = maxItems ? data.slice(0, maxItems) : data;

  return (
    <Card className="col-span-full lg:col-span-2">
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div style={{ height: Math.max(200, slice.length * 28 + 40) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={slice}
              layout="vertical"
              margin={{ left: 110, right: 16 }}
              onClick={(e) => {
                if (!onSelect || !e?.activePayload?.[0]) return;
                onSelect((e.activePayload[0].payload as AreaRanking).code);
              }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} className="fill-muted-foreground" />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} className="fill-muted-foreground" width={110} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as AreaRanking;
                  return (
                    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                      <p className="font-medium">{d.name}</p>
                      <p>{t("charts.score")} {fmt(d.weighted_avg_score)}</p>
                      <p>{t("kpi.population")}: {fmtPop(d.population)}</p>
                      <p>{t("ranking.gridCells")} {d.cell_count.toLocaleString()}</p>
                    </div>
                  );
                }}
              />
              <Bar
                dataKey="weighted_avg_score"
                fill={color}
                radius={[0, 3, 3, 0]}
                style={{ cursor: onSelect ? "pointer" : undefined }}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Service Coverage
// ---------------------------------------------------------------------------

export function CoverageChart({
  data,
  selectedPurpose,
}: {
  data: ServiceCoverage[];
  selectedPurpose?: string | null;
}) {
  const { t } = useTranslation();
  const filtered = selectedPurpose
    ? data.filter((d) => d.purpose === selectedPurpose)
    : data;

  const chartData = filtered
    .map((d) => ({
      purpose: d.purpose_label,
      [t("coverage.lt15")]: d.pct_pop_15min,
      [t("coverage.15_30")]: Math.max(d.pct_pop_30min - d.pct_pop_15min, 0),
      [t("coverage.30_45")]: Math.max(d.pct_pop_45min - d.pct_pop_30min, 0),
      [t("coverage.45_60")]: Math.max(d.pct_pop_60min - d.pct_pop_45min, 0),
      [t("coverage.gt60")]: Math.max(100 - d.pct_pop_60min, 0),
      _raw: d,
    }))
    .sort((a, b) => (a._raw as ServiceCoverage).pct_pop_30min - (b._raw as ServiceCoverage).pct_pop_30min);

  if (chartData.length === 0) return null;

  return (
    <Card className="col-span-full">
      <CardHeader>
        <CardTitle className="text-base">{t("coverage.title")}</CardTitle>
        <CardDescription>
          {t("coverage.subtitle")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div style={{ height: Math.max(200, chartData.length * 32 + 60) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ left: 100, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} className="fill-muted-foreground" tickFormatter={(v: number) => `${v}%`} />
              <YAxis type="category" dataKey="purpose" tick={{ fontSize: 11 }} className="fill-muted-foreground" width={100} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = ((payload[0].payload as Record<string, unknown>)._raw) as ServiceCoverage;
                  return (
                    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                      <p className="font-medium">{d.purpose_label}</p>
                      <p>{t("coverage.within15")} {fmt(d.pct_pop_15min)}%</p>
                      <p>{t("coverage.within30")} {fmt(d.pct_pop_30min)}%</p>
                      <p>{t("coverage.within45")} {fmt(d.pct_pop_45min)}%</p>
                      <p>{t("coverage.within60")} {fmt(d.pct_pop_60min)}%</p>
                      <p>{t("coverage.avgTravel")} {fmt(d.avg_travel_time)} {t("coverage.min")}</p>
                      <p>{t("coverage.medianTravel")} {fmt(d.median_travel_time)} {t("coverage.min")}</p>
                    </div>
                  );
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey={t("coverage.lt15")} stackId="a" fill={COVERAGE_COLORS[0]} />
              <Bar dataKey={t("coverage.15_30")} stackId="a" fill={COVERAGE_COLORS[1]} />
              <Bar dataKey={t("coverage.30_45")} stackId="a" fill={COVERAGE_COLORS[2]} />
              <Bar dataKey={t("coverage.45_60")} stackId="a" fill={COVERAGE_COLORS[3]} />
              <Bar dataKey={t("coverage.gt60")} stackId="a" fill={COVERAGE_COLORS[4]} radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Purpose Filter Selector
// ---------------------------------------------------------------------------

export function PurposeFilter({
  purposes,
  selected,
  onSelect,
}: {
  purposes: { code: string; label: string }[];
  selected: string | null;
  onSelect: (code: string | null) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap gap-1.5">
      <button
        onClick={() => onSelect(null)}
        className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
          !selected
            ? "bg-primary text-primary-foreground"
            : "bg-secondary text-muted-foreground hover:text-foreground"
        }`}
      >
        {t("charts.allServices")}
      </button>
      {purposes.map((p) => (
        <button
          key={p.code}
          onClick={() => onSelect(selected === p.code ? null : p.code)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
            selected === p.code
              ? "bg-primary text-primary-foreground"
              : "bg-secondary text-muted-foreground hover:text-foreground"
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
