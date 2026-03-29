"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

interface ScoreDetail {
  mode: string;
  purpose: string;
  score: number;
  score_normalized: number | null;
}

interface CellData {
  id: number;
  cell_code: string;
  population: number;
  combined_score: number | null;
  combined_score_normalized: number | null;
  scores: ScoreDetail[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function DashboardPage() {
  const [cellId, setCellId] = useState("");
  const [cellData, setCellData] = useState<CellData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchCell = async () => {
    const trimmed = cellId.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/cells/${trimmed}`);
      if (!res.ok) {
        throw new Error(
          res.status === 404
            ? `Cell ${trimmed} not found`
            : `API error: ${res.status}`,
        );
      }
      const data: CellData = await res.json();
      setCellData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setCellData(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container py-8">
      <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
      <p className="mt-2 text-muted-foreground">
        Transport connectivity analysis for Bizkaia.
      </p>

      <div className="mt-6 flex gap-3">
        <Button asChild variant="outline">
          <Link href="/map">Connectivity Map</Link>
        </Button>
      </div>

      {/* ── Cell lookup ── */}
      <div className="mt-8 rounded-lg border p-6">
        <h3 className="font-semibold">Cell Lookup</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Enter a grid cell ID to view its connectivity scores.
        </p>

        <div className="mt-4 flex gap-2">
          <input
            type="number"
            placeholder="Cell ID"
            value={cellId}
            onChange={(e) => setCellId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchCell()}
            className="flex h-10 w-40 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <Button onClick={fetchCell} disabled={loading}>
            {loading ? "Loading\u2026" : "Fetch"}
          </Button>
        </div>

        {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

        {cellData && (
          <div className="mt-6 space-y-4">
            {/* Summary cards */}
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Cell Code</p>
                <p className="mt-1 font-mono text-sm">{cellData.cell_code}</p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Population</p>
                <p className="mt-1 font-mono text-sm">
                  {cellData.population.toFixed(0)}
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Combined Score</p>
                <p className="mt-1 font-mono text-sm">
                  {cellData.combined_score_normalized != null
                    ? cellData.combined_score_normalized.toFixed(1)
                    : "\u2014"}
                </p>
              </div>
            </div>

            {/* Scores table */}
            {cellData.scores.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-muted-foreground">
                      <th className="py-2 text-left font-medium">Mode</th>
                      <th className="py-2 text-left font-medium">Purpose</th>
                      <th className="py-2 text-right font-medium">Raw</th>
                      <th className="py-2 text-right font-medium">
                        Normalized (0–100)
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {cellData.scores.map((s, i) => (
                      <tr key={i} className="border-b">
                        <td className="py-2">{s.mode}</td>
                        <td className="py-2 capitalize">{s.purpose}</td>
                        <td className="py-2 text-right font-mono">
                          {s.score.toFixed(4)}
                        </td>
                        <td className="py-2 text-right font-mono">
                          {s.score_normalized != null
                            ? s.score_normalized.toFixed(1)
                            : "\u2014"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {cellData.scores.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No scores computed yet. Run the scoring pipeline first.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
