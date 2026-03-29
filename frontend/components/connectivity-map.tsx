"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEMO_TENANT = "00000000-0000-0000-0000-000000000001";

const DEFAULT_CENTER: [number, number] = [-2.87, 43.22];
const DEFAULT_ZOOM = 10;

// ── POI types (primary filter) ──
const POI_TYPES = [
  { value: null, label: "Combined", desc: "All destination types" },
  { value: "jobs", label: "Jobs", desc: "Employment zones", color: "#6366f1" },
  { value: "education", label: "Education", desc: "Schools", color: "#f59e0b" },
  { value: "health", label: "Health", desc: "Health centres & pharmacies", color: "#ef4444" },
  { value: "retail", label: "Retail", desc: "Supermarkets & shops", color: "#22c55e" },
] as const;

// ── 12-stop color ramp ──
const SCORE_COLORS: [number, string][] = [
  [0, "#1a0a00"],
  [9, "#7f1b00"],
  [18, "#c4321a"],
  [27, "#e05a2b"],
  [36, "#f0892e"],
  [45, "#f5b731"],
  [54, "#e8d534"],
  [63, "#b5d935"],
  [72, "#6ec440"],
  [81, "#2da84e"],
  [90, "#1a8a5c"],
  [100, "#0e5e8c"],
];

// ── Transit operators with colors ──
const OPERATORS = [
  { id: "Bizkaibus", label: "Bizkaibus", color: "#166534" },       // dark green
  { id: "Bilbobus", label: "Bilbobus", color: "#d97706" },         // amber
  { id: "MetroBilbao", label: "Metro Bilbao", color: "#dc2626" },  // red
  { id: "Euskotren", label: "Euskotren", color: "#7c3aed" },       // purple
  { id: "Renfe_Cercanias", label: "Renfe Cercanias", color: "#0369a1" }, // sky blue
  { id: "FunicularArtxanda", label: "Funicular Artxanda", color: "#a855f7" }, // violet
] as const;

// ── Destination marker styles ──
const DEST_LAYERS = [
  { id: "dest-schools", type: "school_primary", color: "#f59e0b", label: "Schools" },
  { id: "dest-health", type: "health_gp", color: "#ef4444", label: "Health" },
  { id: "dest-supermarkets", type: "supermarket", color: "#22c55e", label: "Supermarkets" },
  { id: "dest-jobs", type: "jobs", color: "#6366f1", label: "Jobs" },
];

interface CellProperties {
  id: number;
  cell_code: string;
  population: number;
  score: number | null;
}

interface LayerToggle {
  id: string;
  label: string;
  visible: boolean;
  color?: string;
}

interface OperatorState {
  id: string;
  label: string;
  color: string;
  lines: boolean;
  stops: boolean;
}

type MapInstance = {
  getSource: (id: string) => { setData: (data: unknown) => void } | undefined;
  getLayer: (id: string) => unknown;
  setLayoutProperty: (id: string, prop: string, val: string) => void;
  setFilter: (id: string, filter: unknown) => void;
  remove: () => void;
};

export default function ConnectivityMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapInstance | null>(null);
  const [selectedCell, setSelectedCell] = useState<CellProperties | null>(null);
  const [status, setStatus] = useState("Initializing map...");
  const [error, setError] = useState<string | null>(null);
  const [mapReady, setMapReady] = useState(false);

  const [selectedPurpose, setSelectedPurpose] = useState<string | null>(null);

  // Base layers
  const [baseLayers, setBaseLayers] = useState<LayerToggle[]>([
    { id: "cells", label: "Accessibility Grid", visible: true },
    { id: "region", label: "Bizkaia Boundary", visible: true },
    { id: "comarcas", label: "Comarcas", visible: false },
    { id: "municipalities", label: "Municipalities", visible: false },
  ]);

  // Per-POI-type destination toggles
  const [destToggles, setDestToggles] = useState(
    DEST_LAYERS.map((dt) => ({ id: dt.id, label: dt.label, color: dt.color, visible: false })),
  );

  // Per-operator transit toggles (lines + stops independently)
  const [operators, setOperators] = useState<OperatorState[]>(
    OPERATORS.map((op) => ({ id: op.id, label: op.label, color: op.color, lines: false, stops: false })),
  );

  const baseLayerMapping: Record<string, string[]> = {
    cells: ["cells-fill", "cells-outline"],
    region: ["region-boundary"],
    comarcas: ["comarcas-boundary", "comarcas-labels"],
    municipalities: ["municipalities-boundary"],
  };

  const toggleBaseLayer = useCallback(
    (groupId: string) => {
      setBaseLayers((prev) =>
        prev.map((l) => (l.id === groupId ? { ...l, visible: !l.visible } : l)),
      );
      const map = mapRef.current;
      if (!map) return;
      const layer = baseLayers.find((l) => l.id === groupId);
      if (!layer) return;
      const newVis = !layer.visible ? "visible" : "none";
      for (const lid of baseLayerMapping[groupId] ?? []) {
        if (map.getLayer(lid)) map.setLayoutProperty(lid, "visibility", newVis);
      }
    },
    [baseLayers],
  );

  // Toggle operator lines or stops independently
  const applyTransitFilters = useCallback((updated: OperatorState[]) => {
    const map = mapRef.current;
    if (!map) return;

    const linesOps = updated.filter((o) => o.lines).map((o) => o.id);
    const stopsOps = updated.filter((o) => o.stops).map((o) => o.id);

    if (map.getLayer("transit-routes")) {
      if (linesOps.length === 0) {
        map.setLayoutProperty("transit-routes", "visibility", "none");
      } else {
        map.setLayoutProperty("transit-routes", "visibility", "visible");
        map.setFilter("transit-routes", ["in", ["get", "operator"], ["literal", linesOps]]);
      }
    }
    if (map.getLayer("transit-stops")) {
      if (stopsOps.length === 0) {
        map.setLayoutProperty("transit-stops", "visibility", "none");
      } else {
        map.setLayoutProperty("transit-stops", "visibility", "visible");
        map.setFilter("transit-stops", ["in", ["get", "operator"], ["literal", stopsOps]]);
      }
    }
  }, []);

  const toggleOperatorLines = useCallback((operatorId: string) => {
    setOperators((prev) => {
      const updated = prev.map((o) => o.id === operatorId ? { ...o, lines: !o.lines } : o);
      applyTransitFilters(updated);
      return updated;
    });
  }, [applyTransitFilters]);

  const toggleOperatorStops = useCallback((operatorId: string) => {
    setOperators((prev) => {
      const updated = prev.map((o) => o.id === operatorId ? { ...o, stops: !o.stops } : o);
      applyTransitFilters(updated);
      return updated;
    });
  }, [applyTransitFilters]);

  const toggleDestination = useCallback((layerId: string) => {
    setDestToggles((prev) => {
      const updated = prev.map((d) => d.id === layerId ? { ...d, visible: !d.visible } : d);
      const map = mapRef.current;
      if (map) {
        const target = updated.find((d) => d.id === layerId);
        if (target && map.getLayer(layerId)) {
          map.setLayoutProperty(layerId, "visibility", target.visible ? "visible" : "none");
        }
      }
      return updated;
    });
  }, []);

  // Re-fetch cells when purpose filter changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const params = new URLSearchParams();
    if (selectedPurpose) {
      params.set("mode", "TRANSIT");
      params.set("purpose", selectedPurpose);
    }
    const qs = params.toString();

    fetch(`${API_BASE}/cells/geojson${qs ? `?${qs}` : ""}`, {
      headers: { "X-Tenant-ID": DEMO_TENANT },
    })
      .then((res) => res.ok ? res.json() : null)
      .then((data) => {
        if (data) {
          const source = map.getSource("cells");
          if (source) source.setData(data);
        }
      })
      .catch(() => {});
  }, [selectedPurpose, mapReady]);

  // ── Map initialisation ──
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;
    let cancelled = false;

    async function init() {
      try {
        const maplibregl = await import("maplibre-gl");
        if (cancelled) return;
        setStatus("Creating map...");

        const map = new maplibregl.Map({
          container: mapContainer.current!,
          style: {
            version: 8 as const,
            sources: {
              osm: {
                type: "raster" as const,
                tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                tileSize: 256,
                attribution: "&copy; OpenStreetMap contributors",
              },
            },
            layers: [{
              id: "osm-tiles", type: "raster" as const, source: "osm",
              minzoom: 0, maxzoom: 19,
            }],
          },
          center: DEFAULT_CENTER,
          zoom: DEFAULT_ZOOM,
        });

        map.addControl(new maplibregl.NavigationControl(), "top-right");
        mapRef.current = map as unknown as MapInstance;

        map.on("load", async () => {
          try {
            // 1. Grid
            setStatus("Loading accessibility grid...");
            const cellsRes = await fetch(`${API_BASE}/cells/geojson`, {
              headers: { "X-Tenant-ID": DEMO_TENANT },
            });
            if (cellsRes.ok) {
              map.addSource("cells", { type: "geojson", data: await cellsRes.json() });
              map.addLayer({
                id: "cells-fill", type: "fill", source: "cells",
                paint: {
                  "fill-color": [
                    "interpolate", ["linear"],
                    ["coalesce", ["get", "score"], 0],
                    ...SCORE_COLORS.flatMap(([stop, color]) => [stop, color]),
                  ],
                  "fill-opacity": 0.7,
                },
              });
              map.addLayer({
                id: "cells-outline", type: "line", source: "cells",
                paint: { "line-color": "#555", "line-width": 0.15 },
              });
            }

            // 2. Region
            setStatus("Loading boundaries...");
            await addGeoJsonLayer(map, `${API_BASE}/boundaries/region/geojson`,
              "region", "region-boundary", "line",
              { "line-color": "#1e293b", "line-width": 3 });

            // 3. Comarcas
            await addGeoJsonLayer(map, `${API_BASE}/boundaries/comarcas/geojson`,
              "comarcas", "comarcas-boundary", "line",
              { "line-color": "#7c3aed", "line-width": 2, "line-dasharray": [4, 2] },
              "none");
            if (map.getSource("comarcas")) {
              map.addLayer({
                id: "comarcas-labels", type: "symbol", source: "comarcas",
                layout: {
                  visibility: "none", "text-field": ["get", "name"],
                  "text-size": 11, "text-anchor": "center",
                },
                paint: { "text-color": "#7c3aed", "text-halo-color": "#fff", "text-halo-width": 2 },
              });
            }

            // 4. Municipalities
            await addGeoJsonLayer(map, `${API_BASE}/boundaries/municipalities/geojson`,
              "municipalities", "municipalities-boundary", "line",
              { "line-color": "#94a3b8", "line-width": 0.8 }, "none");

            // 5. Destinations
            setStatus("Loading destinations...");
            try {
              const destRes = await fetch(`${API_BASE}/destinations/geojson`, {
                headers: { "X-Tenant-ID": DEMO_TENANT },
              });
              if (destRes.ok) {
                map.addSource("destinations", { type: "geojson", data: await destRes.json() });
                for (const dt of DEST_LAYERS) {
                  map.addLayer({
                    id: dt.id, type: "circle", source: "destinations",
                    layout: { visibility: "none" },
                    filter: ["==", ["get", "type"], dt.type],
                    paint: {
                      "circle-radius": 3, "circle-color": dt.color,
                      "circle-stroke-color": "#fff", "circle-stroke-width": 0.5,
                    },
                  });
                }
              }
            } catch { /* optional */ }

            // 6. Transit routes (all operators, filtered client-side)
            setStatus("Loading transit network...");
            try {
              const routesRes = await fetch(`${API_BASE}/transit/routes`);
              if (routesRes.ok) {
                const routesData = await routesRes.json();
                map.addSource("transit-routes", { type: "geojson", data: routesData });

                // Build match expression for operator colors
                const colorExpr: unknown[] = ["match", ["get", "operator"]];
                for (const op of OPERATORS) {
                  colorExpr.push(op.id, op.color);
                }
                colorExpr.push("#6b7280"); // fallback

                map.addLayer({
                  id: "transit-routes", type: "line", source: "transit-routes",
                  layout: { visibility: "none" },
                  paint: {
                    "line-color": colorExpr as maplibregl.ExpressionSpecification,
                    "line-width": 2, "line-opacity": 0.75,
                  },
                });
              }
            } catch { /* optional */ }

            // 7. Transit stops (all operators, filtered client-side)
            try {
              const stopsRes = await fetch(`${API_BASE}/transit/stops`);
              if (stopsRes.ok) {
                map.addSource("transit-stops", { type: "geojson", data: await stopsRes.json() });

                const stopColorExpr: unknown[] = ["match", ["get", "operator"]];
                for (const op of OPERATORS) {
                  stopColorExpr.push(op.id, op.color);
                }
                stopColorExpr.push("#6b7280");

                map.addLayer({
                  id: "transit-stops", type: "circle", source: "transit-stops",
                  layout: { visibility: "none" },
                  paint: {
                    "circle-radius": 3,
                    "circle-color": stopColorExpr as maplibregl.ExpressionSpecification,
                    "circle-stroke-color": "#fff", "circle-stroke-width": 0.5,
                  },
                });
              }
            } catch { /* optional */ }

            setMapReady(true);
            setStatus("");
          } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
          }
        });

        // ── Interactions ──
        map.on("click", "cells-fill", (e) => {
          if (e.features?.[0]) setSelectedCell(e.features[0].properties as CellProperties);
        });

        for (const dt of DEST_LAYERS) {
          map.on("click", dt.id, (e) => {
            if (!e.features?.[0]) return;
            const p = e.features[0].properties;
            new maplibregl.Popup().setLngLat(e.lngLat)
              .setHTML(`<strong>${p?.name ?? ""}</strong><br/><span style="color:#666;font-size:12px">${p?.type_label ?? dt.label}</span>`)
              .addTo(map);
          });
        }

        map.on("click", "transit-stops", (e) => {
          if (!e.features?.[0]) return;
          const p = e.features[0].properties;
          new maplibregl.Popup().setLngLat(e.lngLat)
            .setHTML(`<strong>${p?.stop_name ?? "Stop"}</strong><br/><span style="color:#666;font-size:12px">${p?.operator ?? ""}</span>`)
            .addTo(map);
        });

        map.on("click", "transit-routes", (e) => {
          if (!e.features?.[0]) return;
          const p = e.features[0].properties;
          new maplibregl.Popup().setLngLat(e.lngLat)
            .setHTML(`<strong>${p?.route_name ?? p?.route_id ?? "Route"}</strong><br/><span style="color:#666;font-size:12px">${p?.operator ?? ""}</span>`)
            .addTo(map);
        });

        map.on("click", "municipalities-boundary", (e) => {
          if (!e.features?.[0]) return;
          new maplibregl.Popup().setLngLat(e.lngLat)
            .setHTML(`<strong>${e.features[0].properties?.name ?? ""}</strong>`)
            .addTo(map);
        });

        const clickable = ["cells-fill", "transit-stops", "transit-routes", "municipalities-boundary", ...DEST_LAYERS.map((d) => d.id)];
        for (const lid of clickable) {
          map.on("mouseenter", lid, () => { map.getCanvas().style.cursor = "pointer"; });
          map.on("mouseleave", lid, () => { map.getCanvas().style.cursor = ""; });
        }
      } catch (err) {
        setError(`Map init failed: ${err instanceof Error ? err.message : String(err)}`);
      }
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    async function addGeoJsonLayer(map: any, url: string, sourceId: string, layerId: string,
      layerType: "line" | "fill", paint: Record<string, unknown>, visibility = "visible") {
      try {
        const res = await fetch(url, { headers: { "X-Tenant-ID": DEMO_TENANT } });
        if (res.ok) {
          map.addSource(sourceId, { type: "geojson", data: await res.json() });
          map.addLayer({ id: layerId, type: layerType, source: sourceId, layout: { visibility }, paint });
        }
      } catch { /* optional */ }
    }

    init();
    return () => { cancelled = true; mapRef.current?.remove(); mapRef.current = null; };
  }, []);

  const activePoi = POI_TYPES.find((p) => p.value === selectedPurpose);

  return (
    <div className="absolute inset-0">
      <div ref={mapContainer} style={{ width: "100%", height: "100%" }} />

      {/* ── Control Panel ── */}
      <div className="absolute top-3 left-3 z-10 w-60 space-y-2 max-h-[calc(100vh-6rem)] overflow-y-auto">

        {/* Accessibility filter */}
        <div className="rounded-lg border bg-background p-3 shadow-lg">
          <p className="text-xs font-semibold text-muted-foreground mb-2">
            Accessibility by Destination
          </p>
          <div className="space-y-1">
            {POI_TYPES.map((p) => (
              <button
                key={p.label}
                onClick={() => setSelectedPurpose(p.value)}
                className={`w-full rounded px-2.5 py-1.5 text-left text-xs transition-colors flex items-center gap-2 ${
                  selectedPurpose === p.value
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary/50 text-secondary-foreground hover:bg-secondary"
                }`}
              >
                {p.value && "color" in p && (
                  <span className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: (p as { color: string }).color }} />
                )}
                <span className="font-medium">{p.label}</span>
              </button>
            ))}
          </div>
          <div className="mt-3 pt-2 border-t">
            <p className="text-[10px] text-muted-foreground mb-1">
              {activePoi?.desc ?? "Weighted average of all destination types"}
              {selectedPurpose ? " (public transport)" : ""}
            </p>
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-muted-foreground">Low</span>
              <div className="flex h-3 flex-1 rounded-sm overflow-hidden">
                {SCORE_COLORS.map(([, color]) => (
                  <div key={color} className="flex-1" style={{ backgroundColor: color }} />
                ))}
              </div>
              <span className="text-[10px] text-muted-foreground">High</span>
            </div>
          </div>
        </div>

        {/* Layers */}
        <div className="rounded-lg border bg-background p-3 shadow-lg">
          <p className="text-xs font-semibold text-muted-foreground mb-2">Layers</p>
          {baseLayers.map((layer) => (
            <label key={layer.id} className="flex items-center gap-2 text-xs cursor-pointer py-0.5">
              <input type="checkbox" checked={layer.visible}
                onChange={() => toggleBaseLayer(layer.id)} className="rounded border-input" />
              {layer.label}
            </label>
          ))}
        </div>

        {/* Destinations per POI type */}
        <div className="rounded-lg border bg-background p-3 shadow-lg">
          <p className="text-xs font-semibold text-muted-foreground mb-2">Destinations</p>
          {destToggles.map((dt) => (
            <label key={dt.id} className="flex items-center gap-2 text-xs cursor-pointer py-0.5">
              <input type="checkbox" checked={dt.visible}
                onChange={() => toggleDestination(dt.id)} className="rounded border-input" />
              <span className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: dt.color }} />
              {dt.label}
            </label>
          ))}
        </div>

        {/* Transit operators — lines and stops independently */}
        <div className="rounded-lg border bg-background p-3 shadow-lg">
          <p className="text-xs font-semibold text-muted-foreground mb-2">
            Public Transport
          </p>
          {/* Header row */}
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground mb-1 pl-5">
            <span className="w-12 text-center">Lines</span>
            <span className="w-12 text-center">Stops</span>
          </div>
          {operators.map((op) => (
            <div key={op.id} className="flex items-center gap-1 py-0.5">
              <span className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: op.color }} />
              <span className="text-xs flex-1 truncate">{op.label}</span>
              <label className="w-12 flex justify-center cursor-pointer">
                <input type="checkbox" checked={op.lines}
                  onChange={() => toggleOperatorLines(op.id)} className="rounded border-input" />
              </label>
              <label className="w-12 flex justify-center cursor-pointer">
                <input type="checkbox" checked={op.stops}
                  onChange={() => toggleOperatorStops(op.id)} className="rounded border-input" />
              </label>
            </div>
          ))}
        </div>

      </div>

      {/* Status / Error */}
      {status && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 rounded-md bg-background/90 px-4 py-2 text-sm text-muted-foreground shadow">
          {status}
        </div>
      )}
      {error && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 rounded-md bg-destructive/10 border border-destructive px-4 py-2 text-sm text-destructive shadow">
          {error}
        </div>
      )}

      {/* Cell detail */}
      {selectedCell && (
        <div className="absolute bottom-4 right-4 z-10 w-64 rounded-lg border bg-background p-4 shadow-lg">
          <div className="flex items-start justify-between">
            <h3 className="font-semibold text-sm">Cell Details</h3>
            <button onClick={() => setSelectedCell(null)}
              className="text-muted-foreground hover:text-foreground text-xs">Close</button>
          </div>
          <div className="mt-3 space-y-1.5 text-sm">
            <Row label="Code" value={selectedCell.cell_code} />
            <Row label="ID" value={String(selectedCell.id)} />
            <Row label="Population" value={Number(selectedCell.population).toFixed(0)} />
            <Row label={activePoi?.label ?? "Combined"}
              value={selectedCell.score != null ? Number(selectedCell.score).toFixed(1) : "\u2014"} />
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}
