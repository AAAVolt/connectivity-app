"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import DOMPurify from "dompurify";
import {
  IconInfoCircle as Info,
  IconGitBranch as GitBranch,
  IconCalculator as Calculator,
  IconMap as Map,
  IconLayoutDashboard as LayoutDashboard,
  IconUsers as Users,
  IconDatabase as Database,
  IconAlertTriangle as AlertTriangle,
  IconCode as Code,
} from "@tabler/icons-react";
import type { TablerIcon as LucideIcon } from "@tabler/icons-react";
import { useTranslation } from "@/lib/i18n";

/**
 * Render a translation string that may contain a limited set of inline
 * HTML tags (`<strong>`, `<em>`, `<sub>`, `<sup>`, `<br>`).
 *
 * Input is sanitised with DOMPurify so no script injection is possible
 * even if a locale file were compromised.
 */
function RichText({ html, className }: { html: string; className?: string }) {
  // DOMPurify v3 exports a factory in Node.js (no window) — guard for SSR.
  // Locale strings are trusted internal data, so passing raw html during SSR is safe;
  // the client re-render still sanitises.
  const clean =
    typeof DOMPurify.sanitize === "function"
      ? DOMPurify.sanitize(html, {
          ALLOWED_TAGS: ["strong", "em", "sub", "sup", "br", "b", "i"],
          ALLOWED_ATTR: [],
        })
      : html;
  return <span className={className} dangerouslySetInnerHTML={{ __html: clean }} />;
}

/* ── Score color ramp (kept in sync with connectivity-map.tsx) ── */
const SCORE_STOPS = [
  "#1a0a00", "#7f1b00", "#c4321a", "#e05a2b", "#f0892e", "#f5b731",
  "#e8d534", "#b5d935", "#6ec440", "#2da84e", "#1a8a5c", "#0e5e8c",
];

/* ── Travel time bands (kept in sync with connectivity-map.tsx) ── */
const TT_BANDS_KEYS = [
  { color: "#1a9850", key: "< 30 min" },
  { color: "#91cf60", key: "30\u201345 min" },
  { color: "#fee08b", key: "45\u201360 min" },
  { color: "#fc8d59", key: "60\u201375 min" },
  { color: "#d73027", key: "75\u201390 min" },
  { color: "#878787", key: "> 90 min" },
];

/* ── POI catalogue (matches scoring.yaml + map) ── */
const POIS = [
  { code: "aeropuerto", label: "Aeropuerto", descKey: "poi.desc.aeropuerto", color: "#6366f1" },
  { code: "bachiller", label: "Bachiller", descKey: "poi.desc.bachiller", color: "#f59e0b" },
  { code: "centro_educativo", label: "Centro Educativo", descKey: "poi.desc.centro_educativo", color: "#eab308" },
  { code: "centro_urbano", label: "Centro Urbano", descKey: "poi.desc.centro_urbano", color: "#8b5cf6" },
  { code: "consulta_general", label: "Consulta General", descKey: "poi.desc.consulta_general", color: "#ef4444" },
  { code: "hacienda", label: "Hacienda", descKey: "poi.desc.hacienda", color: "#64748b" },
  { code: "hospital", label: "Hospital", descKey: "poi.desc.hospital", color: "#dc2626" },
  { code: "osakidetza", label: "Osakidetza", descKey: "poi.desc.osakidetza", color: "#f97316" },
  { code: "residencia", label: "Residencia", descKey: "poi.desc.residencia", color: "#14b8a6" },
  { code: "universidad", label: "Universidad", descKey: "poi.desc.universidad", color: "#22c55e" },
];

/* ── Transit operators ── */
const OPERATORS = [
  { name: "Bizkaibus", descKey: "op.bizkaibus", color: "#166534" },
  { name: "Bilbobus", descKey: "op.bilbobus", color: "#d97706" },
  { name: "Metro Bilbao", descKey: "op.metrobilbao", color: "#dc2626" },
  { name: "Euskotren", descKey: "op.euskotren", color: "#7c3aed" },
  { name: "Renfe Cercan\u00edas", descKey: "op.renfe", color: "#0369a1" },
  { name: "Funicular Artxanda", descKey: "op.funicular", color: "#a855f7" },
];

/* ── Table of contents sections ── */
const SECTIONS: { id: string; key: string; icon: LucideIcon }[] = [
  { id: "overview", key: "method.whatIsThis", icon: Info },
  { id: "pipeline", key: "method.dataPipeline", icon: GitBranch },
  { id: "scoring", key: "method.scoringModel", icon: Calculator },
  { id: "map", key: "method.readingMap", icon: Map },
  { id: "dashboard", key: "method.dashboardAnalytics", icon: LayoutDashboard },
  { id: "socio", key: "method.socioTitle", icon: Users },
  { id: "sources", key: "method.dataSources", icon: Database },
  { id: "limits", key: "method.limitations", icon: AlertTriangle },
  { id: "opensource", key: "method.openSource", icon: Code },
];

/* ── Reusable pieces ── */
function SectionHeading({ icon: Icon, children }: { icon?: LucideIcon; children: React.ReactNode }) {
  return (
    <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-foreground">
      {Icon && <Icon className="size-4 text-muted-foreground" />}
      {children}
    </h2>
  );
}
function Step({ n, title }: { n: number; title: string }) {
  return (
    <h3 className="mt-6 mb-2 flex items-baseline gap-2 text-[13px] font-medium text-foreground">
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
        {n}
      </span>
      {title}
    </h3>
  );
}

/* ── Table of Contents sidebar ── */
function TableOfContents({
  activeId,
  className,
}: {
  activeId: string;
  className?: string;
}) {
  const { t } = useTranslation();
  return (
    <nav className={className}>
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {t("method.toc")}
      </p>
      <ul className="space-y-0.5">
        {SECTIONS.map((s) => {
          const Icon = s.icon;
          const isActive = activeId === s.id;
          return (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                onClick={(e) => {
                  e.preventDefault();
                  document.getElementById(s.id)?.scrollIntoView({ behavior: "smooth" });
                }}
                className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors ${
                  isActive
                    ? "bg-accent text-foreground font-medium"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                }`}
              >
                <Icon className="size-3 shrink-0" />
                <span className="truncate">{t(s.key)}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/* ════════════════════════════════════════════════════════════════════════════ */

export default function MethodologyPage() {
  const { t } = useTranslation();
  const [activeSection, setActiveSection] = useState("overview");
  const observerRef = useRef<IntersectionObserver | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  // Track which section is in view with IntersectionObserver.
  // The scroll container is the .overflow-auto ancestor from sidebar-layout,
  // so we find it and pass it as the observer root for correct intersection detection.
  const setupObserver = useCallback(() => {
    observerRef.current?.disconnect();

    // Find the nearest scrollable ancestor (the sidebar layout's overflow-auto div)
    const scrollRoot = contentRef.current?.closest("[data-scroll-root]") as HTMLElement | null
      ?? contentRef.current?.closest(".overflow-auto") as HTMLElement | null
      ?? null;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { root: scrollRoot, rootMargin: "-24px 0px -70% 0px", threshold: 0 },
    );
    for (const s of SECTIONS) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }
    observerRef.current = observer;
    return observer;
  }, []);

  useEffect(() => {
    const observer = setupObserver();
    return () => observer.disconnect();
  }, [setupObserver]);

  return (
    <div ref={contentRef} className="p-6 lg:p-8 w-full space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-lg font-semibold">{t("method.title")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("method.intro")}
        </p>
      </div>

      {/* Mobile TOC -- horizontal scroll */}
      <div className="lg:hidden overflow-x-auto pb-2">
        <div className="flex gap-1">
          {SECTIONS.map((s) => {
            const Icon = s.icon;
            return (
              <a
                key={s.id}
                href={`#${s.id}`}
                onClick={(e) => {
                  e.preventDefault();
                  document.getElementById(s.id)?.scrollIntoView({ behavior: "smooth" });
                }}
                className={`flex items-center gap-1.5 whitespace-nowrap rounded-md border px-2.5 py-1.5 text-xs transition-colors ${
                  activeSection === s.id
                    ? "border-primary bg-primary/5 text-foreground font-medium"
                    : "border-border text-muted-foreground hover:bg-accent/50"
                }`}
              >
                <Icon className="size-3" />
                {t(s.key)}
              </a>
            );
          })}
        </div>
      </div>

      {/* Two-column layout: content + sticky TOC */}
      <div className="max-w-5xl lg:grid lg:grid-cols-[1fr_190px] lg:gap-8">
        {/* Main article */}
        <article className="space-y-12 pb-20 text-sm leading-relaxed text-muted-foreground">

          {/* ─── 1. Overview ─── */}
          <section id="overview">
            <SectionHeading icon={Info}>{t("method.whatIsThis")}</SectionHeading>
            <p>
              {t("method.whatIsThisP1")}{" "}
              <em>&ldquo;{t("method.whatIsThisQuestion")}&rdquo;</em>
            </p>
            <p className="mt-3"><RichText html={t("method.whatIsThisP2")} /></p>
            <ul className="mt-2 ml-4 list-disc space-y-1">
              <li><strong className="text-foreground">{t("method.zoom1km").split(" \u2014 ")[0]}</strong> &mdash; {t("method.zoom1km").split(" \u2014 ")[1]}</li>
              <li><strong className="text-foreground">{t("method.zoom500m").split(" \u2014 ")[0]}</strong> &mdash; {t("method.zoom500m").split(" \u2014 ")[1]}</li>
              <li><strong className="text-foreground">{t("method.zoom250m").split(" \u2014 ")[0]}</strong> &mdash; {t("method.zoom250m").split(" \u2014 ")[1]}</li>
            </ul>
          </section>

          {/* ─── 2. Data pipeline ─── */}
          <section id="pipeline">
            <SectionHeading icon={GitBranch}>{t("method.dataPipeline")}</SectionHeading>
            <p>{t("method.dataPipelineIntro")}</p>

            <Step n={1} title={t("method.step1Title")} />
            <p>{t("method.step1Text")}</p>

            <Step n={2} title={t("method.step2Title")} />
            <p><RichText html={t("method.step2Text")} /></p>

            <Step n={3} title={t("method.step3Title")} />
            <p>{t("method.step3Text")}</p>
            <div className="mt-3 overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/40">
                    <th className="w-8 px-3 py-2" />
                    <th className="px-3 py-2 text-left font-medium text-foreground">{t("method.step3Category")}</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">{t("method.step3Description")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {POIS.map((p) => (
                    <tr key={p.code}>
                      <td className="px-3 py-2">
                        <span
                          className="inline-block h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: p.color }}
                        />
                      </td>
                      <td className="px-3 py-2 font-medium text-foreground">{p.label}</td>
                      <td className="px-3 py-2">{t(p.descKey)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs">{t("method.step3Toggle")}</p>

            <Step n={4} title={t("method.step4Title")} />
            <p>{t("method.step4Text")}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {OPERATORS.map((op) => (
                <span
                  key={op.name}
                  className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs"
                >
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: op.color }}
                  />
                  <span className="font-medium text-foreground">{op.name}</span>
                  <span className="text-muted-foreground">{t(op.descKey)}</span>
                </span>
              ))}
            </div>
            <p className="mt-3">{t("method.step4Foot")}</p>

            <Step n={5} title={t("method.step5Title")} />
            <p><RichText html={t("method.step5Text")} /></p>
            <ul className="mt-2 ml-4 list-disc space-y-1">
              <li>
                <strong className="text-foreground">{t("method.step5Mode")}</strong> {t("method.step5ModeVal")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.step5Cutoff")}</strong> {t("method.step5CutoffVal")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.step5Slots")}</strong> {t("method.step5SlotsVal")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.step5Walk")}</strong> {t("method.step5WalkVal")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.step5MaxWalk")}</strong> {t("method.step5MaxWalkVal")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.step5Percentile")}</strong> {t("method.step5PercentileVal")}
              </li>
            </ul>

            <Step n={6} title={t("method.step6Title")} />
            <p>{t("method.step6Text")}</p>
          </section>

          {/* ─── 3. Scoring model ─── */}
          <section id="scoring">
            <SectionHeading icon={Calculator}>{t("method.scoringModel")}</SectionHeading>

            <Step n={1} title={t("method.decay")} />
            <p>{t("method.decayP1")}</p>
            <div className="my-3 rounded-md border bg-muted/30 px-4 py-2.5 text-center font-mono text-xs">
              impedance = e<sup>&minus;&alpha; &times; t</sup>
            </div>
            <p><RichText html={t("method.decayP2")} /></p>
            <p className="mt-2"><RichText html={t("method.decayP3")} /></p>

            <Step n={2} title={t("method.diminishing")} />
            <p>{t("method.diminishingP1")}</p>
            <div className="my-3 rounded-md border bg-muted/30 px-4 py-2.5 text-center font-mono text-xs">
              adjusted = raw<sup>0.7</sup>
            </div>
            <p>{t("method.diminishingP2")}</p>

            <Step n={3} title={t("method.normalisation")} />
            <p>{t("method.normalisationP1")}</p>

            <Step n={4} title={t("method.combined")} />
            <p>{t("method.combinedP1")}</p>
            <div className="mt-2 overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/40">
                    <th className="px-3 py-2 text-left font-medium text-foreground">{t("method.combinedCategory")}</th>
                    <th className="px-3 py-2 text-right font-medium text-foreground">{t("method.combinedWeight")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {POIS.map((p) => (
                    <tr key={p.code}>
                      <td className="px-3 py-2 font-medium text-foreground">{p.label}</td>
                      <td className="px-3 py-2 text-right font-mono">10%</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t bg-muted/20">
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.combinedTotal")}</td>
                    <td className="px-3 py-2 text-right font-mono font-semibold">100%</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <p className="mt-3">{t("method.combinedP2")}</p>
          </section>

          {/* ─── 4. Reading the map ─── */}
          <section id="map">
            <SectionHeading icon={Map}>{t("method.readingMap")}</SectionHeading>

            <p className="mb-3 font-medium text-foreground">{t("method.accessScore")}</p>
            <p>{t("method.accessScoreP1")}</p>
            <div className="mt-3">
              <div
                className="h-3 w-full rounded-sm"
                style={{
                  background: `linear-gradient(to right, ${SCORE_STOPS.join(", ")})`,
                }}
              />
              <div className="mt-1 flex justify-between text-xs">
                <span>{t("method.scorePoor")}</span>
                <span>{t("method.scoreMid")}</span>
                <span>{t("method.scoreExcellent")}</span>
              </div>
            </div>

            <p className="mt-5 mb-3 font-medium text-foreground">{t("method.travelTimeNearest")}</p>
            <p>{t("method.travelTimeP1")}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {TT_BANDS_KEYS.map((b) => (
                <span
                  key={b.key}
                  className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs"
                >
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-sm"
                    style={{ backgroundColor: b.color }}
                  />
                  {b.key}
                </span>
              ))}
            </div>

            <p className="mt-5 mb-3 font-medium text-foreground">{t("method.zeroPop")}</p>
            <p>{t("method.zeroPopP1")}</p>

            <p className="mt-5 mb-3 font-medium text-foreground">{t("method.mapControls")}</p>
            <ul className="ml-4 list-disc space-y-1.5">
              <li>
                <strong className="text-foreground">{t("method.controlMetricToggle")}</strong> &mdash;{" "}
                {t("method.controlMetricToggleDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.controlDepartureSlider")}</strong> &mdash;{" "}
                {t("method.controlDepartureSliderDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.controlPoiCategory")}</strong> &mdash;{" "}
                {t("method.controlPoiCategoryDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.controlLayers")}</strong> &mdash;{" "}
                {t("method.controlLayersDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.controlDestinations")}</strong> &mdash;{" "}
                {t("method.controlDestinationsDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.controlTransit")}</strong> &mdash;{" "}
                {t("method.controlTransitDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.controlClick")}</strong>{" "}
                {t("method.controlClickDesc")}
              </li>
            </ul>
          </section>

          {/* ─── 5. Dashboard ─── */}
          <section id="dashboard">
            <SectionHeading icon={LayoutDashboard}>{t("method.dashboardAnalytics")}</SectionHeading>
            <p>{t("method.dashboardP1")}</p>
            <ul className="mt-2 ml-4 list-disc space-y-1.5">
              <li>
                <strong className="text-foreground">{t("method.dashboardOverview")}</strong> &mdash;{" "}
                {t("method.dashboardOverviewDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.dashboardComarcas")}</strong> &mdash;{" "}
                {t("method.dashboardComarcasDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.dashboardMunicipios")}</strong> &mdash;{" "}
                {t("method.dashboardMunicipiosDesc")}
              </li>
            </ul>
            <p className="mt-3">{t("method.dashboardP2")}</p>
          </section>

          {/* ─── 6. Sociodemographic layer ─── */}
          <section id="socio">
            <SectionHeading icon={Users}>{t("method.socioTitle")}</SectionHeading>
            <p><RichText html={t("method.socioIntro")} /></p>

            <p className="mt-4 mb-2 font-medium text-foreground">{t("method.socioIndicators")}</p>
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/40">
                    <th className="px-3 py-2 text-left font-medium text-foreground">{t("method.socioIndicator")}</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">{t("method.socioSource")}</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">{t("method.socioInterpretation")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.socioElderly")}</td>
                    <td className="px-3 py-2">{t("method.socioElderlySource")}</td>
                    <td className="px-3 py-2"><RichText html={t("method.socioElderlyInterp")} /></td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.socioIncome")}</td>
                    <td className="px-3 py-2">{t("method.socioIncomeSource")}</td>
                    <td className="px-3 py-2"><RichText html={t("method.socioIncomeInterp")} /></td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.socioCars")}</td>
                    <td className="px-3 py-2">{t("method.socioCarsSource")}</td>
                    <td className="px-3 py-2"><RichText html={t("method.socioCarsInterp")} /></td>
                  </tr>
                </tbody>
              </table>
            </div>

            <p className="mt-5 mb-2 font-medium text-foreground">{t("method.socioVulnTitle")}</p>
            <p><RichText html={t("method.socioVulnP1")} /></p>
            <div className="my-3 rounded-md border bg-muted/30 px-4 py-2.5 text-center font-mono text-xs">
              V = 0.4 &times; (1 &minus; connectivity<sub>norm</sub>) + 0.2 &times; elderly<sub>norm</sub> + 0.2 &times; (1 &minus; income<sub>norm</sub>) + 0.2 &times; (1 &minus; cars<sub>norm</sub>)
            </div>
            <p><RichText html={t("method.socioVulnP2")} /></p>

            <div className="mt-3 overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/40">
                    <th className="px-3 py-2 text-left font-medium text-foreground">{t("method.socioVulnDimension")}</th>
                    <th className="px-3 py-2 text-right font-medium text-foreground">{t("method.combinedWeight")}</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">{t("method.socioVulnDirection")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.socioVulnConn")}</td>
                    <td className="px-3 py-2 text-right font-mono">40%</td>
                    <td className="px-3 py-2">{t("method.socioVulnConnDir")}</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.socioVulnElderly")}</td>
                    <td className="px-3 py-2 text-right font-mono">20%</td>
                    <td className="px-3 py-2">{t("method.socioVulnElderlyDir")}</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.socioVulnIncome")}</td>
                    <td className="px-3 py-2 text-right font-mono">20%</td>
                    <td className="px-3 py-2">{t("method.socioVulnIncomeDir")}</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.socioVulnCars")}</td>
                    <td className="px-3 py-2 text-right font-mono">20%</td>
                    <td className="px-3 py-2">{t("method.socioVulnCarsDir")}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <p className="mt-4 mb-2 font-medium text-foreground">{t("method.socioColors")}</p>
            <p>{t("method.socioColorsP1")}</p>
            <ul className="mt-2 ml-4 list-disc space-y-1">
              <li><RichText html={t("method.socioColorsElderly")} /></li>
              <li><RichText html={t("method.socioColorsIncome")} /></li>
              <li><RichText html={t("method.socioColorsCars")} /></li>
              <li><RichText html={t("method.socioColorsVuln")} /></li>
            </ul>

            <p className="mt-4 mb-2 font-medium text-foreground">{t("method.socioLimTitle")}</p>
            <ul className="ml-4 list-disc space-y-1">
              <li>{t("method.socioLim1")}</li>
              <li>{t("method.socioLim2")}</li>
              <li>{t("method.socioLim3")}</li>
            </ul>
          </section>

          {/* ─── 7. Data sources ─── */}
          <section id="sources">
            <SectionHeading icon={Database}>{t("method.dataSources")}</SectionHeading>
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/40">
                    <th className="px-3 py-2 text-left font-medium text-foreground">{t("method.dsLayer")}</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">{t("method.dsSource")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.dsStreet")}</td>
                    <td className="px-3 py-2">{t("method.dsStreetVal")}</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.dsTransit")}</td>
                    <td className="px-3 py-2">{t("method.dsTransitVal")}</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.dsPop")}</td>
                    <td className="px-3 py-2">{t("method.dsPopVal")}</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.dsDest")}</td>
                    <td className="px-3 py-2">{t("method.dsDestVal")}</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.dsBound")}</td>
                    <td className="px-3 py-2">{t("method.dsBoundVal")}</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-medium text-foreground">{t("method.dsSocio")}</td>
                    <td className="px-3 py-2">{t("method.dsSocioVal")}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* ─── 8. Limitations ─── */}
          <section id="limits">
            <SectionHeading icon={AlertTriangle}>{t("method.limitations")}</SectionHeading>
            <ul className="ml-4 list-disc space-y-2">
              <li>
                <strong className="text-foreground">{t("method.limModes")}</strong>{" "}
                {t("method.limModesDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.limTimetables")}</strong>{" "}
                {t("method.limTimetablesDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.limCompleteness")}</strong>{" "}
                {t("method.limCompletenessDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.limParams")}</strong>{" "}
                {t("method.limParamsDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.limPopModel")}</strong>{" "}
                {t("method.limPopModelDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.limResolution")}</strong>{" "}
                {t("method.limResolutionDesc")}
              </li>
              <li>
                <strong className="text-foreground">{t("method.limTimePeriod")}</strong>{" "}
                {t("method.limTimePeriodDesc")}
              </li>
            </ul>
          </section>

          {/* ─── 9. Open source ─── */}
          <section id="opensource">
            <SectionHeading icon={Code}>{t("method.openSource")}</SectionHeading>
            <p>{t("method.openSourceP1")}</p>
          </section>
        </article>

        {/* Desktop TOC -- sticky sidebar */}
        <TableOfContents
          activeId={activeSection}
          className="hidden lg:block sticky top-6 self-start"
        />
      </div>
    </div>
  );
}
