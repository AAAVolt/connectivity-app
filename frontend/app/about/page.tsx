"use client";

import { useTranslation } from "@/lib/i18n";

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

/* ── Reusable pieces ── */
function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-3 text-base font-semibold text-foreground">{children}</h2>;
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

/* ════════════════════════════════════════════════════════════════════════════ */

export default function MethodologyPage() {
  const { t } = useTranslation();

  return (
    <div className="mx-auto max-w-2xl px-6 pt-16 pb-20 lg:px-8 lg:pt-20">
      <h1 className="text-2xl font-semibold">{t("method.title")}</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        {t("method.intro")}
      </p>

      <article className="mt-8 space-y-12 text-sm leading-relaxed text-muted-foreground">

        {/* ─── 1. Overview ─── */}
        <section>
          <SectionHeading>{t("method.whatIsThis")}</SectionHeading>
          <p>
            {t("method.whatIsThisP1")}{" "}
            <em>&ldquo;{t("method.whatIsThisQuestion")}&rdquo;</em>
          </p>
          <p className="mt-3" dangerouslySetInnerHTML={{ __html: t("method.whatIsThisP2") }} />
          <ul className="mt-2 ml-4 list-disc space-y-1">
            <li><strong className="text-foreground">{t("method.zoom1km").split(" \u2014 ")[0]}</strong> &mdash; {t("method.zoom1km").split(" \u2014 ")[1]}</li>
            <li><strong className="text-foreground">{t("method.zoom500m").split(" \u2014 ")[0]}</strong> &mdash; {t("method.zoom500m").split(" \u2014 ")[1]}</li>
            <li><strong className="text-foreground">{t("method.zoom250m").split(" \u2014 ")[0]}</strong> &mdash; {t("method.zoom250m").split(" \u2014 ")[1]}</li>
          </ul>
        </section>

        {/* ─── 2. Data pipeline ─── */}
        <section>
          <SectionHeading>{t("method.dataPipeline")}</SectionHeading>
          <p>{t("method.dataPipelineIntro")}</p>

          <Step n={1} title={t("method.step1Title")} />
          <p>{t("method.step1Text")}</p>

          <Step n={2} title={t("method.step2Title")} />
          <p dangerouslySetInnerHTML={{ __html: t("method.step2Text") }} />

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
          <p dangerouslySetInnerHTML={{ __html: t("method.step5Text") }} />
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
          </ul>

          <Step n={6} title={t("method.step6Title")} />
          <p>{t("method.step6Text")}</p>
        </section>

        {/* ─── 3. Scoring model ─── */}
        <section>
          <SectionHeading>{t("method.scoringModel")}</SectionHeading>

          <Step n={1} title={t("method.decay")} />
          <p>{t("method.decayP1")}</p>
          <div className="my-3 rounded-md border bg-muted/30 px-4 py-2.5 text-center font-mono text-xs">
            impedance = e<sup>&minus;&alpha; &times; t</sup>
          </div>
          <p dangerouslySetInnerHTML={{ __html: t("method.decayP2") }} />
          <p className="mt-2" dangerouslySetInnerHTML={{ __html: t("method.decayP3") }} />

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
        <section>
          <SectionHeading>{t("method.readingMap")}</SectionHeading>

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
        <section>
          <SectionHeading>{t("method.dashboardAnalytics")}</SectionHeading>
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
        <section>
          <SectionHeading>{t("method.socioTitle")}</SectionHeading>
          <p dangerouslySetInnerHTML={{ __html: t("method.socioIntro") }} />

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
                  <td className="px-3 py-2" dangerouslySetInnerHTML={{ __html: t("method.socioElderlyInterp") }} />
                </tr>
                <tr>
                  <td className="px-3 py-2 font-medium text-foreground">{t("method.socioIncome")}</td>
                  <td className="px-3 py-2">{t("method.socioIncomeSource")}</td>
                  <td className="px-3 py-2" dangerouslySetInnerHTML={{ __html: t("method.socioIncomeInterp") }} />
                </tr>
                <tr>
                  <td className="px-3 py-2 font-medium text-foreground">{t("method.socioCars")}</td>
                  <td className="px-3 py-2">{t("method.socioCarsSource")}</td>
                  <td className="px-3 py-2" dangerouslySetInnerHTML={{ __html: t("method.socioCarsInterp") }} />
                </tr>
              </tbody>
            </table>
          </div>

          <p className="mt-5 mb-2 font-medium text-foreground">{t("method.socioVulnTitle")}</p>
          <p dangerouslySetInnerHTML={{ __html: t("method.socioVulnP1") }} />
          <div className="my-3 rounded-md border bg-muted/30 px-4 py-2.5 text-center font-mono text-xs">
            V = 0.4 &times; (1 &minus; connectivity<sub>norm</sub>) + 0.2 &times; elderly<sub>norm</sub> + 0.2 &times; (1 &minus; income<sub>norm</sub>) + 0.2 &times; (1 &minus; cars<sub>norm</sub>)
          </div>
          <p dangerouslySetInnerHTML={{ __html: t("method.socioVulnP2") }} />

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
            <li dangerouslySetInnerHTML={{ __html: t("method.socioColorsElderly") }} />
            <li dangerouslySetInnerHTML={{ __html: t("method.socioColorsIncome") }} />
            <li dangerouslySetInnerHTML={{ __html: t("method.socioColorsCars") }} />
            <li dangerouslySetInnerHTML={{ __html: t("method.socioColorsVuln") }} />
          </ul>

          <p className="mt-4 mb-2 font-medium text-foreground">{t("method.socioLimTitle")}</p>
          <ul className="ml-4 list-disc space-y-1">
            <li>{t("method.socioLim1")}</li>
            <li>{t("method.socioLim2")}</li>
            <li>{t("method.socioLim3")}</li>
          </ul>
        </section>

        {/* ─── 7. Data sources ─── */}
        <section>
          <SectionHeading>{t("method.dataSources")}</SectionHeading>
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
              </tbody>
            </table>
          </div>
        </section>

        {/* ─── 8. Limitations ─── */}
        <section>
          <SectionHeading>{t("method.limitations")}</SectionHeading>
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
          </ul>
        </section>

        {/* ─── 9. Open source ─── */}
        <section>
          <SectionHeading>{t("method.openSource")}</SectionHeading>
          <p>{t("method.openSourceP1")}</p>
        </section>
      </article>
    </div>
  );
}
