"use client";

import { IconLayoutSidebarLeftCollapse as PanelLeftClose } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { useTranslation } from "@/lib/i18n";
import { MapPanelSection } from "./map-panel-section";
import {
  SCORE_COLORS,
  TRAVEL_TIME_BANDS,
  TRAVEL_TIME_NO_DATA_COLOR,
  TRAVEL_TIME_NO_DATA_LABEL,
  SOCIAL_PAINT,
  FREQ_COLORS,
  FREQ_WINDOWS,
  RESOLUTION_LABELS,
  BASEMAP_OPTIONS,
} from "./map-panel-types";
import type { MapPanelProps } from "./map-panel-types";

const CHECKBOX_CLASS =
  "h-3.5 w-3.5 rounded border-2 border-sidebar-foreground/40 bg-transparent appearance-none cursor-pointer relative " +
  "checked:bg-sidebar-primary checked:border-sidebar-primary " +
  "after:content-[''] after:absolute after:inset-0 after:flex after:items-center after:justify-center " +
  "checked:after:content-['\\2713'] after:text-[9px] after:font-bold after:text-white after:leading-none " +
  "after:top-[1px] after:left-[1px] " +
  "hover:border-sidebar-primary/60 transition-colors";

export function MapControlPanel(props: MapPanelProps) {
  const { t } = useTranslation();
  const {
    panelOpen, setPanelOpen,
    openSections, toggleSection,
    metric, setMetric,
    timeIndex, setTimeIndex, availableTimes, departureTime, timePeriod,
    selectedPurpose, setSelectedPurpose, poiTypes, activePoi,
    socialLayer, setSocialLayer,
    baseLayers, toggleBaseLayer, fillOpacity, setFillOpacity,
    basemap, setBasemap,
    perspective, setPerspective,
    showBuildings, setShowBuildings, showTerrain, setShowTerrain,
    resolution,
    destToggles, toggleDestination,
    showRoutes, handleToggleRoutes,
    showStops, handleToggleStops,
    showFrequency, handleToggleFrequency,
    freqWindow, setFreqWindow,
    operators, setOperators,
    selectedCell, setSelectedCell,
  } = props;

  return (
    <>
      {/* ── Control Panel ── */}
      <div
        className={`absolute inset-y-0 left-0 z-10 w-[272px] bg-white border-r border-sidebar-border flex flex-col transition-transform duration-200 ${
          panelOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Panel header */}
        <div className="flex items-center justify-between px-3 h-11 border-b border-sidebar-border flex-shrink-0">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/80">
            {t("map.controls")}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setPanelOpen(false)}
            className="h-7 w-7 text-sidebar-foreground/60 hover:!text-sidebar-foreground hover:!bg-sidebar-accent"
            title={t("map.collapsePanel")}
          >
            <PanelLeftClose className="h-3.5 w-3.5" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {/* ─── PRIMARY CONTROLS (always prominent) ─── */}

          {/* Metric toggle */}
          <div className="px-3 py-3 border-b border-sidebar-border">
            <div className="flex gap-1 rounded-lg bg-sidebar-accent/40 p-0.5">
              {(["score", "travel_time"] as const).map((m) => (
                <Button
                  key={m}
                  variant="ghost"
                  size="sm"
                  onClick={() => setMetric(m)}
                  className={`flex-1 h-7 text-[11px] font-medium rounded-md transition-all ${
                    metric === m
                      ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm hover:!bg-sidebar-primary/90 hover:!text-white"
                      : "text-sidebar-foreground/70 hover:!text-sidebar-foreground hover:!bg-sidebar-accent"
                  }`}
                >
                  {m === "score" ? t("map.metricScore") : t("map.metricTravelTime")}
                </Button>
              ))}
            </div>
          </div>

          {/* Departure Time */}
          <div className="px-3 py-3 border-b border-sidebar-border space-y-2">
            <div className="flex items-baseline justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/70">
                {t("map.departureTime")}
              </span>
              <span className="text-[10px] text-sidebar-foreground/60">{timePeriod}</span>
            </div>
            <div className="text-xl font-mono font-semibold tabular-nums text-sidebar-foreground tracking-tight">
              {departureTime}
            </div>
            <Slider
              min={0}
              max={availableTimes.length - 1}
              step={1}
              value={[timeIndex]}
              onValueChange={([v]) => setTimeIndex(v)}
              className="w-full"
            />
            <div className="flex justify-between text-[9px] text-sidebar-foreground/60">
              <span>{availableTimes[0]}</span>
              <span>{availableTimes[Math.floor(availableTimes.length / 2)]}</span>
              <span>{availableTimes[availableTimes.length - 1]}</span>
            </div>
          </div>

          {/* Destination filter + legend */}
          <MapPanelSection
            title={metric === "travel_time" ? t("map.nearestDestination") : t("map.accessibility")}
            open={openSections.destination ?? true}
            onToggle={() => toggleSection("destination")}
          >
            <div className="space-y-0.5">
              {poiTypes.map((p) => (
                <Button
                  key={p.label}
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedPurpose(p.value)}
                  className={`w-full justify-start h-7 rounded-md px-2 text-[11px] font-medium transition-all ${
                    selectedPurpose === p.value
                      ? "bg-sidebar-primary text-sidebar-primary-foreground hover:!bg-sidebar-primary/90 hover:!text-white"
                      : "text-sidebar-foreground/70 hover:!text-sidebar-foreground hover:!bg-sidebar-accent"
                  }`}
                >
                  {p.value && p.color && (
                    <span
                      className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: p.color }}
                    />
                  )}
                  {p.value === null ? t("map.combined") : p.label}
                </Button>
              ))}
            </div>

            {/* Legend */}
            <div className="mt-3 pt-2.5 border-t border-sidebar-border/60">
              <p className="text-[10px] text-sidebar-foreground/60 mb-2 leading-relaxed">
                {metric === "travel_time"
                  ? selectedPurpose
                    ? `${t("map.minutesToNearest")} ${activePoi?.label?.toLowerCase() ?? "destination"} ${t("map.transit")}`
                    : t("map.avgMinToNearest")
                  : (activePoi ? t(activePoi.descKey) : t("map.weightedAvgAll")) +
                    (selectedPurpose ? ` ${t("map.publicTransport")}` : "")}
              </p>
              {metric === "travel_time" ? (
                <div className="space-y-1">
                  {TRAVEL_TIME_BANDS.map((band) => (
                    <div key={band.label} className="flex items-center gap-2">
                      <span
                        className="inline-block w-3 h-2.5 rounded-[2px] flex-shrink-0"
                        style={{ backgroundColor: band.color }}
                      />
                      <span className="text-[10px] text-sidebar-foreground/70">{band.label}</span>
                    </div>
                  ))}
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-block w-3 h-2.5 rounded-[2px] flex-shrink-0"
                      style={{ backgroundColor: TRAVEL_TIME_NO_DATA_COLOR }}
                    />
                    <span className="text-[10px] text-sidebar-foreground/70">{TRAVEL_TIME_NO_DATA_LABEL}</span>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-1.5">
                  <span className="text-[9px] text-sidebar-foreground/60">{t("map.low")}</span>
                  <div className="flex h-2.5 flex-1 rounded-sm overflow-hidden">
                    {SCORE_COLORS.map(([, color]) => (
                      <div key={color} className="flex-1" style={{ backgroundColor: color }} />
                    ))}
                  </div>
                  <span className="text-[9px] text-sidebar-foreground/60">{t("map.high")}</span>
                </div>
              )}
              {/* No-population hatch legend */}
              <div className="flex items-center gap-2 mt-2">
                <span
                  className="inline-block w-3 h-2.5 rounded-[2px] flex-shrink-0 border border-sidebar-border"
                  style={{
                    background: "repeating-linear-gradient(-45deg, transparent, transparent 2px, rgba(120,120,120,0.45) 2px, rgba(120,120,120,0.45) 3px)",
                  }}
                />
                <span className="text-[10px] text-sidebar-foreground/70">{t("map.noPopulation")}</span>
              </div>
            </div>
          </MapPanelSection>

          {/* Social Layer */}
          <MapPanelSection
            title={t("map.socialLayer")}
            open={openSections.social ?? false}
            onToggle={() => toggleSection("social")}
          >
            <div className="space-y-0.5">
              {[
                { value: null, labelKey: "map.socialNone" },
                { value: "elderly", labelKey: "map.socialElderly" },
                { value: "income", labelKey: "map.socialIncome" },
                { value: "cars", labelKey: "map.socialCars" },
                { value: "vulnerability", labelKey: "map.socialVuln" },
              ].map((opt) => (
                <Button
                  key={opt.labelKey}
                  variant="ghost"
                  size="sm"
                  onClick={() => setSocialLayer(opt.value)}
                  className={`w-full justify-start h-7 rounded-md px-2 text-[11px] font-medium transition-all ${
                    socialLayer === opt.value
                      ? "bg-sidebar-primary text-sidebar-primary-foreground hover:!bg-sidebar-primary/90 hover:!text-white"
                      : "text-sidebar-foreground/70 hover:!text-sidebar-foreground hover:!bg-sidebar-accent"
                  }`}
                >
                  {t(opt.labelKey)}
                </Button>
              ))}
            </div>
            {/* Social legend */}
            {socialLayer && SOCIAL_PAINT[socialLayer] && (
              <div className="mt-3 pt-2.5 border-t border-sidebar-border/60">
                <p className="text-[10px] text-sidebar-foreground/60 mb-2">
                  {t(`map.social${socialLayer.charAt(0).toUpperCase() + socialLayer.slice(1)}`)}
                </p>
                <div className="flex items-center gap-1.5">
                  <span className="text-[9px] text-sidebar-foreground/60">{t("map.socialLegendLow")}</span>
                  <div className="flex h-2.5 flex-1 rounded-sm overflow-hidden">
                    {SOCIAL_PAINT[socialLayer].stops.map(([, color]) => (
                      <div key={color} className="flex-1" style={{ backgroundColor: color }} />
                    ))}
                  </div>
                  <span className="text-[9px] text-sidebar-foreground/60">{t("map.socialLegendHigh")}</span>
                </div>
                <div className="flex justify-between text-[9px] text-sidebar-foreground/60 mt-1">
                  <span>{SOCIAL_PAINT[socialLayer].stops[0][0]}</span>
                  <span>{SOCIAL_PAINT[socialLayer].stops[SOCIAL_PAINT[socialLayer].stops.length - 1][0]}</span>
                </div>
              </div>
            )}
          </MapPanelSection>

          {/* Layers */}
          <MapPanelSection
            title={t("map.layers")}
            open={openSections.layers ?? false}
            onToggle={() => toggleSection("layers")}
          >
            {/* Basemap selector */}
            <div className="mb-3">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/60 mb-1.5 block">
                {t("map.basemap")}
              </span>
              <div className="grid grid-cols-2 gap-1">
                {BASEMAP_OPTIONS.map((bm) => (
                  <Button
                    key={bm.id}
                    variant="ghost"
                    size="sm"
                    onClick={() => setBasemap(bm.id)}
                    className={`h-7 text-[10px] font-medium rounded-md transition-all ${
                      basemap === bm.id
                        ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm hover:!bg-sidebar-primary/90 hover:!text-white"
                        : "text-sidebar-foreground/70 hover:!text-sidebar-foreground hover:!bg-sidebar-accent"
                    }`}
                  >
                    {t(bm.labelKey)}
                  </Button>
                ))}
              </div>
            </div>
            <Separator className="bg-sidebar-border/60 mb-3" />
            {/* Data layer toggles */}
            <div className="space-y-0.5">
              {baseLayers.map((layer) => (
                <label key={layer.id} className="flex items-center gap-2.5 text-[11px] cursor-pointer py-1 rounded-md px-1 hover:bg-sidebar-accent/40 transition-colors">
                  <input
                    type="checkbox"
                    checked={layer.visible}
                    onChange={() => toggleBaseLayer(layer.id)}
                    className={CHECKBOX_CLASS}
                  />
                  <span className="text-sidebar-foreground/70">{t(layer.labelKey)}</span>
                </label>
              ))}
            </div>
            <div className="mt-3 pt-3 border-t border-sidebar-border/60">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-sidebar-foreground/60">{t("map.gridOpacity")}</span>
                <span className="text-[10px] font-mono text-sidebar-foreground/60 tabular-nums">
                  {Math.round(fillOpacity * 100)}%
                </span>
              </div>
              <Slider
                min={5}
                max={100}
                step={1}
                value={[Math.round(fillOpacity * 100)]}
                onValueChange={([v]) => setFillOpacity(v / 100)}
                className="w-full"
              />
            </div>
          </MapPanelSection>

          {/* 3D View */}
          <MapPanelSection
            title={t("map.3dView")}
            open={openSections.threeD ?? false}
            onToggle={() => toggleSection("threeD")}
          >
            {/* Perspective toggle: 2D / 3D */}
            <div className="mb-3">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/60 mb-1.5 block">
                {t("map.perspective")}
              </span>
              <div className="flex gap-1 rounded-lg bg-sidebar-accent/40 p-0.5">
                {(["2d", "3d"] as const).map((p) => (
                  <Button
                    key={p}
                    variant="ghost"
                    size="sm"
                    onClick={() => setPerspective(p)}
                    className={`flex-1 h-7 text-[11px] font-medium rounded-md transition-all ${
                      perspective === p
                        ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm hover:!bg-sidebar-primary/90 hover:!text-white"
                        : "text-sidebar-foreground/70 hover:!text-sidebar-foreground hover:!bg-sidebar-accent"
                    }`}
                  >
                    {p === "2d" ? t("map.perspective2d") : t("map.perspective3d")}
                  </Button>
                ))}
              </div>
            </div>
            <Separator className="bg-sidebar-border/60 mb-3" />

            {/* Layer toggles */}
            <div className="space-y-0.5">
              {[
                { checked: showBuildings, onChange: () => setShowBuildings((v) => !v), label: t("map.3dBuildings") },
                { checked: showTerrain, onChange: () => setShowTerrain((v) => !v), label: t("map.3dTerrain") },
              ].map((item) => (
                <label key={item.label} className="flex items-center gap-2.5 text-[11px] cursor-pointer py-1 rounded-md px-1 hover:bg-sidebar-accent/40 transition-colors">
                  <input
                    type="checkbox"
                    checked={item.checked}
                    onChange={item.onChange}
                    className={CHECKBOX_CLASS}
                  />
                  <span className="text-sidebar-foreground/70 font-medium">{item.label}</span>
                </label>
              ))}
            </div>
          </MapPanelSection>

          {/* Destination markers */}
          <MapPanelSection
            title={t("map.destinations")}
            open={openSections.destinations ?? false}
            onToggle={() => toggleSection("destinations")}
          >
            <div className="space-y-0.5">
              {destToggles.map((dt) => (
                <label key={dt.id} className="flex items-center gap-2.5 text-[11px] cursor-pointer py-1 rounded-md px-1 hover:bg-sidebar-accent/40 transition-colors">
                  <input
                    type="checkbox"
                    checked={dt.visible}
                    onChange={() => toggleDestination(dt.id)}
                    className={CHECKBOX_CLASS}
                  />
                  <span
                    className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                    style={{ backgroundColor: dt.color }}
                  />
                  <span className="text-sidebar-foreground/70">{dt.label}</span>
                </label>
              ))}
            </div>
          </MapPanelSection>

          {/* Public Transport */}
          <MapPanelSection
            title={t("map.publicTransportSection")}
            open={openSections.transit ?? false}
            onToggle={() => toggleSection("transit")}
          >
            {/* Global toggles */}
            <div className="flex gap-1 mb-3 rounded-lg bg-sidebar-accent/40 p-0.5">
              {[
                { active: showRoutes, onClick: handleToggleRoutes, label: t("map.routes") },
                { active: showStops, onClick: handleToggleStops, label: t("map.stops") },
                { active: showFrequency, onClick: handleToggleFrequency, label: t("map.freqToggle") },
              ].map((btn) => (
                <Button
                  key={btn.label}
                  variant="ghost"
                  size="sm"
                  onClick={btn.onClick}
                  className={`flex-1 h-7 text-[10px] font-medium rounded-md transition-all ${
                    btn.active
                      ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm hover:!bg-sidebar-primary/90 hover:!text-white"
                      : "text-sidebar-foreground/70 hover:!text-sidebar-foreground hover:!bg-sidebar-accent"
                  }`}
                >
                  {btn.label}
                </Button>
              ))}
            </div>

            {/* Frequency time window */}
            {showFrequency && (
              <div className="mb-3 space-y-2">
                <span className="text-[10px] text-sidebar-foreground/60">{t("map.freqWindow")}</span>
                <div className="flex flex-wrap gap-1">
                  {FREQ_WINDOWS.map((tw) => (
                    <Button
                      key={tw}
                      variant="ghost"
                      size="sm"
                      onClick={() => setFreqWindow(tw)}
                      className={`h-5 rounded px-1.5 text-[9px] font-medium transition-all ${
                        freqWindow === tw
                          ? "bg-sidebar-primary text-sidebar-primary-foreground hover:!bg-sidebar-primary/90 hover:!text-white"
                          : "text-sidebar-foreground/60 hover:!text-sidebar-foreground hover:!bg-sidebar-accent"
                      }`}
                    >
                      {tw}
                    </Button>
                  ))}
                </div>
                {/* Frequency legend */}
                <div className="pt-2 space-y-1">
                  <p className="text-[10px] text-sidebar-foreground/60">{t("map.freqLegend")}</p>
                  {[
                    { color: FREQ_COLORS.high, label: t("map.freqHigh") },
                    { color: FREQ_COLORS.med, label: t("map.freqMed") },
                    { color: FREQ_COLORS.low, label: t("map.freqLow") },
                    { color: FREQ_COLORS.veryLow, label: t("map.freqVeryLow") },
                  ].map((b) => (
                    <div key={b.label} className="flex items-center gap-2">
                      <span className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: b.color }} />
                      <span className="text-[10px] text-sidebar-foreground/70">{b.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Per-operator checkboxes */}
            {(showRoutes || showStops) && (
              <div className="space-y-0.5">
                {operators.map((op) => (
                  <label key={op.id} className="flex items-center gap-2.5 text-[11px] cursor-pointer py-1 rounded-md px-1 hover:bg-sidebar-accent/40 transition-colors">
                    <input
                      type="checkbox"
                      checked={op.visible}
                      onChange={() =>
                        setOperators((prev) =>
                          prev.map((o) => (o.id === op.id ? { ...o, visible: !o.visible } : o)),
                        )
                      }
                      className={CHECKBOX_CLASS}
                    />
                    <span
                      className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: op.color }}
                    />
                    <span className="truncate text-sidebar-foreground/70">{op.label}</span>
                  </label>
                ))}
              </div>
            )}
          </MapPanelSection>

        </div>
      </div>

      {/* ── Cell detail card ── */}
      {selectedCell && (
        <div className="absolute bottom-4 right-4 z-10 w-60 rounded-lg border border-sidebar-border bg-white p-3.5 shadow-lg">
          <div className="flex items-start justify-between mb-3">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/80">
              {t("map.cellDetails")}
            </h3>
            <button
              onClick={() => setSelectedCell(null)}
              className="text-sidebar-foreground/50 hover:text-sidebar-foreground text-[10px] font-medium transition-colors"
            >
              {t("map.close")}
            </button>
          </div>
          <div className="space-y-1.5 text-[11px]">
            <CellRow label={t("map.code")} value={selectedCell.cell_code} />
            {selectedCell.id != null && <CellRow label={t("map.id")} value={String(selectedCell.id)} />}
            <CellRow label={t("map.resolution")} value={RESOLUTION_LABELS[resolution] ?? `${resolution} m`} />
            <CellRow label={t("map.population")} value={Number(selectedCell.population).toFixed(0)} />
            <Separator className="bg-sidebar-border/60" />
            <CellRow
              label={
                metric === "travel_time"
                  ? `${activePoi?.label ?? "Avg"} (min)`
                  : activePoi?.label ?? t("map.combined")
              }
              value={
                selectedCell.score != null
                  ? metric === "travel_time"
                    ? `${Number(selectedCell.score).toFixed(0)} min`
                    : Number(selectedCell.score).toFixed(1)
                  : "\u2014"
              }
              highlight
            />
          </div>
        </div>
      )}
    </>
  );
}

function CellRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex justify-between items-baseline">
      <span className="text-sidebar-foreground/70">{label}</span>
      <span className={`font-mono tabular-nums ${highlight ? "text-sidebar-foreground font-semibold" : "text-sidebar-foreground/80"}`}>
        {value}
      </span>
    </div>
  );
}
