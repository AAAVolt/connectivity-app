"use client";

import { useMemo, useState } from "react";
import {
  IconCashBanknote as Banknote,
  IconCar as Car,
  IconClock as Clock,
  IconShieldExclamation as ShieldAlert,
  IconUsers as Users,
} from "@tabler/icons-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ScatterChart,
  Scatter,
  ZAxis,
  Legend,
} from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TabButton } from "@/components/tab-button";
import type { MunicipalitySocioProfile } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { fmt, fmtPop } from "@/components/dashboard-charts";
import { useSocioProfiles, useFrequencyData } from "@/hooks/use-context-data";
import type { FreqSummary } from "@/hooks/use-context-data";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Tab = "vulnerability" | "demographics" | "income" | "cars" | "frequency";

interface VulnProfile extends MunicipalitySocioProfile {
  vuln_score: number;
  vuln_level: "high" | "medium" | "low";
}

// ---------------------------------------------------------------------------
// Vulnerability computation
// ---------------------------------------------------------------------------

function computeVulnerability(profiles: MunicipalitySocioProfile[]): VulnProfile[] {
  // Normalize each dimension to 0-1 where 1 = most vulnerable
  const withData = profiles.filter(
    (p) =>
      p.weighted_avg_score != null &&
      p.pct_65_plus != null &&
      p.renta_index != null &&
      p.vehicles_per_inhab != null,
  );

  if (withData.length === 0) return [];

  const maxElderly = Math.max(...withData.map((p) => p.pct_65_plus ?? 0));
  const minElderly = Math.min(...withData.map((p) => p.pct_65_plus ?? 0));
  const maxIncome = Math.max(...withData.map((p) => p.renta_index ?? 0));
  const minIncome = Math.min(...withData.map((p) => p.renta_index ?? 0));
  const maxCars = Math.max(...withData.map((p) => p.vehicles_per_inhab ?? 0));
  const minCars = Math.min(...withData.map((p) => p.vehicles_per_inhab ?? 0));
  const maxScore = Math.max(...withData.map((p) => p.weighted_avg_score ?? 0));
  const minScore = Math.min(...withData.map((p) => p.weighted_avg_score ?? 0));

  const norm = (v: number, min: number, max: number) =>
    max > min ? (v - min) / (max - min) : 0;

  return withData
    .map((p) => {
      const connVuln = 1 - norm(p.weighted_avg_score ?? 0, minScore, maxScore);
      const elderlyVuln = norm(p.pct_65_plus ?? 0, minElderly, maxElderly);
      const incomeVuln = 1 - norm(p.renta_index ?? 0, minIncome, maxIncome);
      const carsVuln = 1 - norm(p.vehicles_per_inhab ?? 0, minCars, maxCars);

      // Weighted composite: connectivity 40%, elderly 20%, income 20%, cars 20%
      const vuln_score =
        connVuln * 0.4 + elderlyVuln * 0.2 + incomeVuln * 0.2 + carsVuln * 0.2;

      const vuln_level: "high" | "medium" | "low" =
        vuln_score >= 0.6 ? "high" : vuln_score >= 0.35 ? "medium" : "low";

      return { ...p, vuln_score, vuln_level };
    })
    .sort((a, b) => b.vuln_score - a.vuln_score);
}

// ---------------------------------------------------------------------------
// Tab icon map
// ---------------------------------------------------------------------------

const TAB_ICONS: Record<string, typeof ShieldAlert> = {
  vulnerability: ShieldAlert,
  demographics: Users,
  income: Banknote,
  cars: Car,
  frequency: Clock,
};

// ---------------------------------------------------------------------------
// Vulnerability Tab
// ---------------------------------------------------------------------------

function VulnerabilityTab({ data }: { data: VulnProfile[] }) {
  const { t } = useTranslation();

  const highVuln = data.filter((d) => d.vuln_level === "high");
  const highVulnPop = highVuln.reduce((s, d) => s + (d.population ?? 0), 0);
  const avgElderlyHigh =
    highVuln.length > 0
      ? highVuln.reduce((s, d) => s + (d.pct_65_plus ?? 0), 0) / highVuln.length
      : 0;
  const avgIncomeHigh =
    highVuln.length > 0
      ? highVuln.reduce((s, d) => s + (d.renta_index ?? 0), 0) / highVuln.length
      : 0;
  const avgCarsHigh =
    highVuln.length > 0
      ? highVuln.reduce((s, d) => s + (d.vehicles_per_inhab ?? 0), 0) /
        highVuln.length
      : 0;

  const avgCarsAll =
    data.length > 0
      ? data.reduce((s, d) => s + (d.vehicles_per_inhab ?? 0), 0) / data.length
      : 0;
  const avgIncomeAll =
    data.length > 0
      ? data.reduce((s, d) => s + (d.renta_index ?? 0), 0) / data.length
      : 0;
  const avgElderlyAll =
    data.length > 0
      ? data.reduce((s, d) => s + (d.pct_65_plus ?? 0), 0) / data.length
      : 0;

  const vulnColor = (level: string) =>
    level === "high" ? "#dc2626" : level === "medium" ? "#f59e0b" : "#22c55e";

  return (
    <div className="space-y-6">
      {/* Insight cards */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>{t("ctx.vuln.mostVulnerable")}</CardDescription>
            <CardTitle className="text-lg text-red-600">
              {data[0]?.name ?? "—"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              {t("ctx.vuln.score")}: {fmt(data[0]?.weighted_avg_score)}/100
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>{t("ctx.vuln.highVulnMunis")}</CardDescription>
            <CardTitle className="text-lg text-red-600">
              {highVuln.length}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              {fmtPop(highVulnPop)} {t("ctx.vuln.peopleIn")}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>{t("ctx.vuln.avgElderlyHigh")}</CardDescription>
            <CardTitle className="text-lg">
              {fmt(avgElderlyHigh)}%
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              {t("ctx.vuln.vsBizkaia")} {fmt(avgElderlyAll)}%
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>{t("ctx.vuln.avgCarsHigh")}</CardDescription>
            <CardTitle className="text-lg">
              {fmt(avgCarsHigh, 2)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              {t("ctx.vuln.vsBizkaia")} {fmt(avgCarsAll, 2)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main vulnerability table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("ctx.vuln.title")}</CardTitle>
          <CardDescription>{t("ctx.vuln.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="py-2 text-left font-medium">{t("ctx.vuln.municipality")}</th>
                  <th className="py-2 text-right font-medium">{t("ctx.vuln.population")}</th>
                  <th className="py-2 text-right font-medium">{t("ctx.vuln.score")}</th>
                  <th className="py-2 text-right font-medium">{t("ctx.vuln.elderly")}</th>
                  <th className="py-2 text-right font-medium">{t("ctx.vuln.income")}</th>
                  <th className="py-2 text-right font-medium">{t("ctx.vuln.cars")}</th>
                  <th className="py-2 text-center font-medium">{t("ctx.vuln.vulnScore")}</th>
                </tr>
              </thead>
              <tbody>
                {data.slice(0, 30).map((d) => (
                  <tr key={d.muni_code} className="border-b last:border-0">
                    <td className="py-2 font-medium">{d.name}</td>
                    <td className="py-2 text-right font-mono">{fmtPop(d.population)}</td>
                    <td className="py-2 text-right font-mono">{fmt(d.weighted_avg_score)}</td>
                    <td className="py-2 text-right font-mono">{fmt(d.pct_65_plus)}%</td>
                    <td className="py-2 text-right font-mono">{fmt(d.renta_index)}</td>
                    <td className="py-2 text-right font-mono">{fmt(d.vehicles_per_inhab, 2)}</td>
                    <td className="py-2 text-center">
                      <span
                        className="inline-block rounded px-2 py-0.5 text-xs font-bold text-white"
                        style={{ backgroundColor: vulnColor(d.vuln_level) }}
                      >
                        {t(`ctx.vuln.${d.vuln_level}`)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Vulnerability bar chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("ctx.vuln.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div style={{ height: Math.max(300, Math.min(data.length, 30) * 24 + 40) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.slice(0, 30)}
                layout="vertical"
                margin={{ left: 110, right: 16 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis type="number" domain={[0, 1]} tick={{ fontSize: 11 }} className="fill-muted-foreground" />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} className="fill-muted-foreground" width={110} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload as VulnProfile;
                    return (
                      <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                        <p className="font-medium">{d.name}</p>
                        <p>{t("ctx.vuln.score")}: {fmt(d.weighted_avg_score)}/100</p>
                        <p>{t("ctx.vuln.elderly")}: {fmt(d.pct_65_plus)}%</p>
                        <p>{t("ctx.vuln.income")}: {fmt(d.renta_index)}</p>
                        <p>{t("ctx.vuln.cars")}: {fmt(d.vehicles_per_inhab, 2)}</p>
                      </div>
                    );
                  }}
                />
                <Bar dataKey="vuln_score" radius={[0, 3, 3, 0]}>
                  {data.slice(0, 30).map((d) => (
                    <Cell key={d.muni_code} fill={vulnColor(d.vuln_level)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Demographics Tab
// ---------------------------------------------------------------------------

function DemographicsTab({ data }: { data: MunicipalitySocioProfile[] }) {
  const { t } = useTranslation();
  const [sort, setSort] = useState<"pop" | "elderly" | "youth">("elderly");

  const withDemo = data.filter((d) => d.pop_total != null && d.pop_total > 0);
  const sorted = [...withDemo].sort((a, b) => {
    if (sort === "elderly") return (b.pct_65_plus ?? 0) - (a.pct_65_plus ?? 0);
    if (sort === "youth") return (b.pct_18_25 ?? 0) - (a.pct_18_25 ?? 0);
    return (b.pop_total ?? 0) - (a.pop_total ?? 0);
  });

  const top25 = sorted.slice(0, 25);

  const chartData = top25.map((d) => ({
    name: d.name,
    [t("ctx.demo.children")]: d.pct_0_17 ?? 0,
    [t("ctx.demo.youth")]: d.pct_18_25 ?? 0,
    [t("ctx.demo.adults")]: 100 - (d.pct_0_17 ?? 0) - (d.pct_18_25 ?? 0) - (d.pct_65_plus ?? 0),
    [t("ctx.demo.elderly")]: d.pct_65_plus ?? 0,
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">{t("ctx.demo.sortBy")}:</span>
        {(["pop", "elderly", "youth"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSort(s)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
              sort === s
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-muted-foreground hover:text-foreground"
            }`}
          >
            {t(`ctx.demo.sort${s.charAt(0).toUpperCase() + s.slice(1)}`)}
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("ctx.demo.title")}</CardTitle>
          <CardDescription>{t("ctx.demo.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div style={{ height: top25.length * 28 + 60 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ left: 110, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} className="fill-muted-foreground" tickFormatter={(v: number) => `${v}%`} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} className="fill-muted-foreground" width={110} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey={t("ctx.demo.children")} stackId="a" fill="#60a5fa" />
                <Bar dataKey={t("ctx.demo.youth")} stackId="a" fill="#a78bfa" />
                <Bar dataKey={t("ctx.demo.adults")} stackId="a" fill="#94a3b8" />
                <Bar dataKey={t("ctx.demo.elderly")} stackId="a" fill="#f87171" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Income Tab
// ---------------------------------------------------------------------------

function IncomeTab({ data }: { data: MunicipalitySocioProfile[] }) {
  const { t } = useTranslation();

  const withIncome = data
    .filter((d) => d.renta_index != null)
    .sort((a, b) => (a.renta_index ?? 0) - (b.renta_index ?? 0));

  const avgIndex =
    withIncome.length > 0
      ? withIncome.reduce((s, d) => s + (d.renta_index ?? 0), 0) / withIncome.length
      : 100;

  // Scatter plot data: income index vs connectivity score
  const scatterData = data
    .filter((d) => d.renta_index != null && d.weighted_avg_score != null && d.population != null)
    .map((d) => ({
      name: d.name,
      x: d.renta_index!,
      y: d.weighted_avg_score!,
      z: d.population!,
    }));

  return (
    <div className="space-y-6">
      {/* Bar chart: income index */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("ctx.income.title")}</CardTitle>
          <CardDescription>{t("ctx.income.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div style={{ height: Math.max(300, withIncome.length * 22 + 40) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={withIncome} layout="vertical" margin={{ left: 110, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis type="number" tick={{ fontSize: 11 }} className="fill-muted-foreground" />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 9 }} className="fill-muted-foreground" width={110} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload as MunicipalitySocioProfile;
                    return (
                      <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                        <p className="font-medium">{d.name}</p>
                        <p>{t("ctx.income.index")}: {fmt(d.renta_index)}</p>
                        {d.renta_personal_media != null && (
                          <p>{t("ctx.income.personal")}: {fmtPop(d.renta_personal_media)} EUR</p>
                        )}
                        <p>{t("ctx.vuln.score")}: {fmt(d.weighted_avg_score)}/100</p>
                      </div>
                    );
                  }}
                />
                <Bar dataKey="renta_index" radius={[0, 3, 3, 0]}>
                  {withIncome.map((d) => (
                    <Cell
                      key={d.muni_code}
                      fill={(d.renta_index ?? 0) < avgIndex ? "#ef4444" : "#3b82f6"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Scatter: income vs connectivity */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("ctx.income.scatterTitle")}</CardTitle>
          <CardDescription>{t("ctx.income.scatterSubtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ left: 10, right: 20, top: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis type="number" dataKey="x" name={t("ctx.income.index")} tick={{ fontSize: 11 }} className="fill-muted-foreground" label={{ value: t("ctx.income.index"), position: "insideBottom", offset: -5, fontSize: 11 }} />
                <YAxis type="number" dataKey="y" name={t("ctx.vuln.score")} tick={{ fontSize: 11 }} className="fill-muted-foreground" label={{ value: t("ctx.vuln.score"), angle: -90, position: "insideLeft", fontSize: 11 }} />
                <ZAxis type="number" dataKey="z" range={[40, 400]} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload as { name: string; x: number; y: number; z: number };
                    return (
                      <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                        <p className="font-medium">{d.name}</p>
                        <p>{t("ctx.income.index")}: {fmt(d.x)}</p>
                        <p>{t("ctx.vuln.score")}: {fmt(d.y)}/100</p>
                        <p>{t("ctx.vuln.population")}: {fmtPop(d.z)}</p>
                      </div>
                    );
                  }}
                />
                <Scatter data={scatterData} fill="#3b82f6" fillOpacity={0.6} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Car Ownership Tab
// ---------------------------------------------------------------------------

function CarOwnershipTab({ data }: { data: MunicipalitySocioProfile[] }) {
  const { t } = useTranslation();

  const withCars = data
    .filter((d) => d.vehicles_per_inhab != null)
    .sort((a, b) => (a.vehicles_per_inhab ?? 0) - (b.vehicles_per_inhab ?? 0));

  const avgCars =
    withCars.length > 0
      ? withCars.reduce((s, d) => s + (d.vehicles_per_inhab ?? 0), 0) / withCars.length
      : 0;

  const scatterData = data
    .filter((d) => d.vehicles_per_inhab != null && d.weighted_avg_score != null && d.population != null)
    .map((d) => ({
      name: d.name,
      x: d.vehicles_per_inhab!,
      y: d.weighted_avg_score!,
      z: d.population!,
    }));

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("ctx.cars.title")}</CardTitle>
          <CardDescription>{t("ctx.cars.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div style={{ height: Math.max(300, withCars.length * 22 + 40) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={withCars} layout="vertical" margin={{ left: 110, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis type="number" tick={{ fontSize: 11 }} className="fill-muted-foreground" />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 9 }} className="fill-muted-foreground" width={110} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload as MunicipalitySocioProfile;
                    return (
                      <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                        <p className="font-medium">{d.name}</p>
                        <p>{t("ctx.cars.vehPerInhab")}: {fmt(d.vehicles_per_inhab, 2)}</p>
                        <p>{t("ctx.vuln.score")}: {fmt(d.weighted_avg_score)}/100</p>
                        <p>{t("ctx.vuln.population")}: {fmtPop(d.population)}</p>
                      </div>
                    );
                  }}
                />
                <Bar dataKey="vehicles_per_inhab" radius={[0, 3, 3, 0]}>
                  {withCars.map((d) => (
                    <Cell
                      key={d.muni_code}
                      fill={(d.vehicles_per_inhab ?? 0) < avgCars ? "#ef4444" : "#3b82f6"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Scatter: cars vs connectivity */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("ctx.cars.scatterTitle")}</CardTitle>
          <CardDescription>{t("ctx.cars.scatterSubtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ left: 10, right: 20, top: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis type="number" dataKey="x" name={t("ctx.cars.vehPerInhab")} tick={{ fontSize: 11 }} className="fill-muted-foreground" label={{ value: t("ctx.cars.vehPerInhab"), position: "insideBottom", offset: -5, fontSize: 11 }} />
                <YAxis type="number" dataKey="y" name={t("ctx.vuln.score")} tick={{ fontSize: 11 }} className="fill-muted-foreground" label={{ value: t("ctx.vuln.score"), angle: -90, position: "insideLeft", fontSize: 11 }} />
                <ZAxis type="number" dataKey="z" range={[40, 400]} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload as { name: string; x: number; y: number; z: number };
                    return (
                      <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                        <p className="font-medium">{d.name}</p>
                        <p>{t("ctx.cars.vehPerInhab")}: {fmt(d.x, 2)}</p>
                        <p>{t("ctx.vuln.score")}: {fmt(d.y)}/100</p>
                        <p>{t("ctx.vuln.population")}: {fmtPop(d.z)}</p>
                      </div>
                    );
                  }}
                />
                <Scatter data={scatterData} fill="#8b5cf6" fillOpacity={0.6} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Frequency Tab
// ---------------------------------------------------------------------------

function FrequencyTab() {
  const { t } = useTranslation();
  const [window, setWindow] = useState("07:00-09:00");
  const { data: freqData = [], isLoading: loading } = useFrequencyData(window);

  const windows = [
    "07:00-09:00",
    "09:00-12:00",
    "12:00-15:00",
    "15:00-18:00",
    "18:00-21:00",
    "06:00-22:00",
  ];

  const avgDph =
    freqData.length > 0
      ? freqData.reduce((s, d) => s + d.departures_per_hour, 0) / freqData.length
      : 0;

  const highFreq = freqData.filter((d) => d.departures_per_hour >= 6).length;
  const medFreq = freqData.filter((d) => d.departures_per_hour >= 3 && d.departures_per_hour < 6).length;
  const lowFreq = freqData.filter((d) => d.departures_per_hour >= 1 && d.departures_per_hour < 3).length;
  const veryLow = freqData.filter((d) => d.departures_per_hour < 1 && d.departures_per_hour > 0).length;

  const freqBands = [
    { label: t("ctx.freq.highFreq"), count: highFreq, color: "#1a9850", pct: freqData.length > 0 ? (highFreq / freqData.length) * 100 : 0 },
    { label: t("ctx.freq.medFreq"), count: medFreq, color: "#91cf60", pct: freqData.length > 0 ? (medFreq / freqData.length) * 100 : 0 },
    { label: t("ctx.freq.lowFreq"), count: lowFreq, color: "#fee08b", pct: freqData.length > 0 ? (lowFreq / freqData.length) * 100 : 0 },
    { label: t("ctx.freq.veryLow"), count: veryLow, color: "#d73027", pct: freqData.length > 0 ? (veryLow / freqData.length) * 100 : 0 },
  ];

  const topStops = [...freqData].sort((a, b) => b.departures_per_hour - a.departures_per_hour).slice(0, 20);

  return (
    <div className="space-y-6">
      {/* Time window selector */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">{t("ctx.freq.window")}:</span>
        {windows.map((tw) => (
          <button
            key={tw}
            onClick={() => setWindow(tw)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
              window === tw
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-muted-foreground hover:text-foreground"
            }`}
          >
            {tw}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">{t("ctx.loading")}</p>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>{t("ctx.freq.stopsAnalyzed")}</CardDescription>
                <CardTitle className="text-2xl tabular-nums">{freqData.length.toLocaleString()}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>{t("ctx.freq.avgDph")}</CardDescription>
                <CardTitle className="text-2xl tabular-nums">{fmt(avgDph, 1)}</CardTitle>
              </CardHeader>
            </Card>
            {freqBands.slice(0, 2).map((band) => (
              <Card key={band.label}>
                <CardHeader className="pb-2">
                  <CardDescription>{band.label}</CardDescription>
                  <CardTitle className="text-2xl tabular-nums">
                    {band.count} <span className="text-sm font-normal text-muted-foreground">({fmt(band.pct, 0)}%)</span>
                  </CardTitle>
                </CardHeader>
              </Card>
            ))}
          </div>

          {/* Frequency distribution bar */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("ctx.freq.summaryTitle")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {freqBands.map((band) => (
                  <div key={band.label} className="flex items-center gap-4">
                    <div className="w-32 shrink-0 text-sm font-medium">{band.label}</div>
                    <div className="flex-1">
                      <div className="h-5 bg-secondary rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-l-full flex items-center justify-end pr-1"
                          style={{
                            width: `${Math.max(band.pct, 1)}%`,
                            backgroundColor: band.color,
                          }}
                        >
                          {band.pct >= 10 && (
                            <span className="text-[10px] text-white font-medium">{fmt(band.pct, 0)}%</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="w-20 text-right text-xs font-mono text-muted-foreground">
                      {band.count} stops
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Top stops table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("ctx.freq.topStops")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-muted-foreground">
                      <th className="py-2 text-left font-medium">{t("ctx.freq.operator")}</th>
                      <th className="py-2 text-left font-medium">Stop</th>
                      <th className="py-2 text-right font-medium">{t("ctx.freq.departures")}</th>
                      <th className="py-2 text-right font-medium">{t("ctx.freq.dph")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topStops.map((s, i) => (
                      <tr key={`${s.operator}-${s.stop_id}-${i}`} className="border-b last:border-0">
                        <td className="py-2">{s.operator}</td>
                        <td className="py-2 font-medium">{s.stop_name ?? s.stop_id}</td>
                        <td className="py-2 text-right font-mono">{s.departures}</td>
                        <td className="py-2 text-right font-mono font-medium">{fmt(s.departures_per_hour, 1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ContextPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("vulnerability");
  const { data: profiles = [], isLoading, error, refetch } = useSocioProfiles();
  const vulnData = useMemo(() => computeVulnerability(profiles), [profiles]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-muted border-t-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 lg:p-8 w-full">
        <h1 className="text-lg font-semibold">{t("ctx.title")}</h1>
        <p className="mt-4 text-sm text-destructive">{error instanceof Error ? error.message : String(error)}</p>
        <Button onClick={() => refetch()} variant="outline" size="sm" className="mt-3">
          {t("ctx.retry")}
        </Button>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 w-full space-y-6">
      <div>
        <h1 className="text-lg font-semibold">{t("ctx.title")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("ctx.subtitle")}</p>
      </div>

      {/* Tabs */}
      <div className="border-b flex gap-0 overflow-x-auto">
        {(["vulnerability", "demographics", "income", "cars", "frequency"] as Tab[]).map(
          (key) => (
            <TabButton key={key} active={tab === key} onClick={() => setTab(key)} icon={TAB_ICONS[key]}>
              {t(`ctx.tab.${key}`)}
            </TabButton>
          ),
        )}
      </div>

      {tab === "vulnerability" && <VulnerabilityTab data={vulnData} />}
      {tab === "demographics" && <DemographicsTab data={profiles} />}
      {tab === "income" && <IncomeTab data={profiles} />}
      {tab === "cars" && <CarOwnershipTab data={profiles} />}
      {tab === "frequency" && <FrequencyTab />}
    </div>
  );
}
