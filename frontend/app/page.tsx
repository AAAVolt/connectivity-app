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
    <div className="p-6 lg:p-8 max-w-4xl">
      <h1 className="text-lg font-semibold">Dashboard</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Transport connectivity analysis for Bizkaia.
      </p>

      <div className="mt-6 flex gap-3">
        <Button asChild variant="outline" size="sm">
          <Link href="/map">Open Map</Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href="/about">Methodology</Link>
        </Button>
      </div>

      {/* Cell lookup */}
      <div className="mt-8">
        <h2 className="text-sm font-medium">Cell Lookup</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Enter a grid cell ID to view its connectivity scores.
        </p>

        <div className="mt-3 flex gap-2">
          <input
            type="number"
            placeholder="Cell ID"
            value={cellId}
            onChange={(e) => setCellId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchCell()}
            className="h-9 w-36 rounded-md border bg-background px-3 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <Button onClick={fetchCell} disabled={loading} size="sm">
            {loading ? "Loading\u2026" : "Fetch"}
          </Button>
        </div>

        {error && (
          <p className="mt-3 text-sm text-destructive">{error}</p>
        )}

        {cellData && (
          <div className="mt-6 space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Cell Code</p>
                <p className="mt-0.5 font-mono text-sm">{cellData.cell_code}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Population</p>
                <p className="mt-0.5 font-mono text-sm">
                  {cellData.population.toFixed(0)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Combined Score</p>
                <p className="mt-0.5 font-mono text-sm">
                  {cellData.combined_score_normalized != null
                    ? cellData.combined_score_normalized.toFixed(1)
                    : "\u2014"}
                </p>
              </div>
            </div>

            {cellData.scores.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-muted-foreground">
                      <th className="py-2 text-left font-medium">Mode</th>
                      <th className="py-2 text-left font-medium">Purpose</th>
                      <th className="py-2 text-right font-medium">Raw</th>
                      <th className="py-2 text-right font-medium">
                        Normalized
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {cellData.scores.map((s, i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td className="py-2">{s.mode}</td>
                        <td className="py-2 capitalize">{s.purpose}</td>
                        <td className="py-2 text-right font-mono text-muted-foreground">
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
                No scores computed yet.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
