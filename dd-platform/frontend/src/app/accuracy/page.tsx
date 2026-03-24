"use client";
import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, AccuracyResponse, CarrierAccuracy, ColumnAccuracy, MismatchInfo, MissingCarrier } from "@/lib/api";
import { useProjectId } from "@/hooks/useProjectId";

function accuracyColor(pct: number): string {
  if (pct >= 95) return "text-emerald-400";
  if (pct >= 80) return "text-yellow-400";
  if (pct >= 60) return "text-orange-400";
  return "text-red-400";
}

function accuracyBg(pct: number): string {
  if (pct >= 95) return "bg-emerald-500/20 border-emerald-500/30";
  if (pct >= 80) return "bg-yellow-500/20 border-yellow-500/30";
  if (pct >= 60) return "bg-orange-500/20 border-orange-500/30";
  return "bg-red-500/20 border-red-500/30";
}

function accuracyBadge(pct: number): string {
  if (pct >= 95) return "bg-emerald-600";
  if (pct >= 80) return "bg-yellow-600";
  if (pct >= 60) return "bg-orange-600";
  return "bg-red-600";
}

function barWidth(pct: number): string {
  return `${Math.max(pct, 2)}%`;
}

function barColor(pct: number): string {
  if (pct >= 95) return "bg-emerald-500";
  if (pct >= 80) return "bg-yellow-500";
  if (pct >= 60) return "bg-orange-500";
  return "bg-red-500";
}

export default function AccuracyPage() {
  const projectId = useProjectId();
  const [data, setData] = useState<AccuracyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getAccuracy(projectId);
      setData(result);
      if (result.error) {
        setError(result.error);
      }
    } catch (e) {
      setError("Failed to load accuracy data");
    }
    setLoading(false);
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-zinc-400">Loading accuracy comparison...</p>
      </div>
    );
  }

  if (error || !data?.has_data) {
    return (
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold">Accuracy Comparison</h1>
            <p className="text-xs text-zinc-500 mt-1">Reference vs Extracted Data</p>
          </div>
          <button
            onClick={loadData}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium"
          >
            Run Comparison
          </button>
        </div>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-12 text-center">
            <p className="text-zinc-400 text-lg mb-2">{error || "No data available"}</p>
            <p className="text-zinc-500 text-sm">
              Make sure both a reference file and extracted output exist for this project.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const summary = data.summary!;
  const perCarrier = data.per_carrier || [];
  const perColumn = data.per_column || [];
  const topMismatches = data.top_mismatches || [];
  const missingCarriers = data.missing_carriers || [];

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold">Accuracy Comparison</h1>
          <p className="text-xs text-zinc-500 mt-1">
            Reference vs Extracted · {summary.columns_compared} columns compared
          </p>
        </div>
        <button
          onClick={loadData}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium"
        >
          Run Comparison
        </button>
      </div>

      {/* Overall Score */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card className={`border ${accuracyBg(summary.overall_match_rate)}`}>
          <CardContent className="p-6 text-center">
            <p className="text-xs text-zinc-400 mb-1">Overall Row Match Rate</p>
            <p className={`text-5xl font-bold ${accuracyColor(summary.overall_match_rate)}`}>
              {summary.overall_match_rate}%
            </p>
            <p className="text-xs text-zinc-500 mt-2">
              {summary.matched_rows} of {summary.total_ref_rows} reference rows matched
            </p>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6 text-center">
            <p className="text-xs text-zinc-400 mb-1">Reference Rows</p>
            <p className="text-3xl font-bold text-blue-400">{summary.total_ref_rows.toLocaleString()}</p>
            <p className="text-xs text-zinc-500 mt-2">Ground truth rows</p>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6 text-center">
            <p className="text-xs text-zinc-400 mb-1">Missing Rows</p>
            <p className="text-3xl font-bold text-red-400">{summary.missing_rows.toLocaleString()}</p>
            <p className="text-xs text-zinc-500 mt-2">In reference but not extracted</p>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6 text-center">
            <p className="text-xs text-zinc-400 mb-1">Extra Rows</p>
            <p className="text-3xl font-bold text-amber-400">{summary.extra_rows.toLocaleString()}</p>
            <p className="text-xs text-zinc-500 mt-2">In extracted but not reference</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Per-Carrier Accuracy */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-base">Per-Carrier Match Rate</CardTitle>
          </CardHeader>
          <CardContent>
            {perCarrier.length === 0 ? (
              <p className="text-zinc-500 text-sm">No carrier data available</p>
            ) : (
              <div className="space-y-2 max-h-[400px] overflow-y-auto">
                <div className="grid grid-cols-[1fr_80px_80px_80px] gap-2 text-xs text-zinc-500 font-medium pb-2 border-b border-zinc-800 sticky top-0 bg-zinc-900">
                  <span>Carrier</span>
                  <span className="text-right">Ref Rows</span>
                  <span className="text-right">Matched</span>
                  <span className="text-right">Match %</span>
                </div>
                {perCarrier.map((c: CarrierAccuracy) => (
                  <div key={c.carrier} className="grid grid-cols-[1fr_80px_80px_80px] gap-2 items-center text-sm">
                    <span className="text-zinc-200 truncate" title={c.carrier}>{c.carrier}</span>
                    <span className="text-right text-zinc-400">{c.ref_rows}</span>
                    <span className="text-right text-zinc-400">{c.matched_rows}</span>
                    <span className={`text-right font-medium ${accuracyColor(c.match_rate)}`}>
                      {c.match_rate}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Missing Carriers */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-base">Missing Data</CardTitle>
          </CardHeader>
          <CardContent>
            {missingCarriers.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-emerald-400 text-lg font-medium mb-1">All carriers present</p>
                <p className="text-zinc-500 text-sm">No missing carrier data detected</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[400px] overflow-y-auto">
                <div className="grid grid-cols-[1fr_100px] gap-2 text-xs text-zinc-500 font-medium pb-2 border-b border-zinc-800 sticky top-0 bg-zinc-900">
                  <span>Carrier</span>
                  <span className="text-right">Missing Rows</span>
                </div>
                {missingCarriers.map((mc: MissingCarrier) => (
                  <div key={mc.carrier} className="grid grid-cols-[1fr_100px] gap-2 items-center text-sm">
                    <span className="text-zinc-200 truncate">{mc.carrier}</span>
                    <span className="text-right text-red-400 font-medium">{mc.missing_rows}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Per-Column Accuracy Heatmap */}
      <Card className="bg-zinc-900 border-zinc-800 mb-6">
        <CardHeader>
          <CardTitle className="text-base">Per-Column Accuracy</CardTitle>
          <p className="text-xs text-zinc-500">Field-level accuracy across {perColumn.length} columns on matched rows</p>
        </CardHeader>
        <CardContent>
          {perColumn.length === 0 ? (
            <p className="text-zinc-500 text-sm">No column data available</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {perColumn.map((col: ColumnAccuracy) => (
                <div key={col.column} className="flex items-center gap-2 text-xs">
                  <span className="text-zinc-400 truncate w-40 shrink-0" title={col.column}>
                    {col.column.length > 25 ? col.column.substring(0, 23) + ".." : col.column}
                  </span>
                  <div className="flex-1 h-4 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${barColor(col.accuracy)}`}
                      style={{ width: barWidth(col.accuracy) }}
                    />
                  </div>
                  <span className={`w-12 text-right font-mono font-medium ${accuracyColor(col.accuracy)}`}>
                    {col.accuracy}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Top Mismatches */}
      {topMismatches.length > 0 && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-base">Top Mismatches</CardTitle>
            <p className="text-xs text-zinc-500">Columns with the lowest accuracy and sample differences</p>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {topMismatches.map((m: MismatchInfo) => (
                <div key={m.column} className="border border-zinc-800 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-zinc-200">{m.column}</span>
                    <Badge className={`${accuracyBadge(m.accuracy)} text-white text-xs`}>
                      {m.accuracy}%
                    </Badge>
                  </div>
                  {m.examples.length > 0 && (
                    <div className="space-y-1">
                      {m.examples.map((ex, i) => (
                        <div key={i} className="grid grid-cols-2 gap-4 text-xs">
                          <div>
                            <span className="text-zinc-500">Ref: </span>
                            <span className="text-blue-300">{ex.ref_value || "(empty)"}</span>
                          </div>
                          <div>
                            <span className="text-zinc-500">Ext: </span>
                            <span className="text-amber-300">{ex.ext_value || "(empty)"}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
