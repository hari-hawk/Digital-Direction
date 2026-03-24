"use client";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useProjectId } from "@/hooks/useProjectId";

export default function ExtractionPage() {
  const projectId = useProjectId();
  const [carriers, setCarriers] = useState<{ key: string; name: string; tier: number; status: string }[]>([]);
  const [selectedCarrier, setSelectedCarrier] = useState("charter");
  const [apiKey, setApiKey] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [logs, setLogs] = useState("");
  const [lastStatus, setLastStatus] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    api.getExtractionCarriers(projectId).then(setCarriers).catch(() => {});
    api.getExtractionStatus(projectId, "charter").then(setLastStatus).catch(() => {});
  }, [projectId]);

  async function runExtraction() {
    setRunning(true);
    setLogs("Starting extraction pipeline...\nThis may take a few seconds...\n");
    setResult(null);
    try {
      const res = await api.runExtraction(projectId, selectedCarrier, apiKey || undefined);
      setResult(res);
      setLogs(res.stderr || res.stdout || "Pipeline completed.");
      if (res.summary && Object.keys(res.summary).length > 0) {
        setLastStatus(res.summary);
      }
    } catch (e) {
      setLogs(`Error: ${e}\n\nMake sure the backend is running on port 8000.`);
    }
    setRunning(false);
  }

  const summary = (lastStatus || result?.summary || {}) as Record<string, unknown>;
  const qaSum = (summary.qa_summary || {}) as Record<string, unknown>;
  const qaRules = (qaSum.rules || {}) as Record<string, { passed: boolean; violations: number }>;
  const confidence = (summary.confidence || {}) as Record<string, unknown>;
  const rowStats = (summary.row_stats || {}) as Record<string, number>;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Extraction Pipeline</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Run Panel */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader><CardTitle className="text-sm text-zinc-400">Run Extraction</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Carrier</label>
              <select value={selectedCarrier} onChange={(e) => setSelectedCarrier(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm">
                {carriers.map((c) => (
                  <option key={c.key} value={c.key} disabled={c.status !== "ready"}>
                    {c.name} (Tier {c.tier}) {c.status !== "ready" ? "- Coming soon" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Anthropic API Key (optional, for invoice OCR)</label>
              <Input type="password" placeholder="sk-ant-..." value={apiKey}
                onChange={(e) => setApiKey(e.target.value)} className="bg-zinc-800 border-zinc-700" />
            </div>
            <button onClick={runExtraction} disabled={running}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-700 rounded-lg text-sm font-medium transition-colors">
              {running ? "Running..." : "Run Extraction"}
            </button>
          </CardContent>
        </Card>

        {/* Results */}
        <div className="lg:col-span-2 space-y-4">
          {/* Summary Cards */}
          {summary.total_rows && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-4">
                  <p className="text-xs text-zinc-400">Total Rows</p>
                  <p className="text-xl font-bold">{String(summary.total_rows)}</p>
                </CardContent>
              </Card>
              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-4">
                  <p className="text-xs text-zinc-400">S / C / T Rows</p>
                  <p className="text-sm font-bold mt-1">
                    {rowStats.S || 0} / {rowStats.C || 0} / {rowStats["T\\S\\OCC"] || 0}
                  </p>
                </CardContent>
              </Card>
              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-4">
                  <p className="text-xs text-zinc-400">Processing Time</p>
                  <p className="text-xl font-bold">{String(summary.processing_time_seconds || 0)}s</p>
                </CardContent>
              </Card>
              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-4">
                  <p className="text-xs text-zinc-400">Confidence</p>
                  <p className="text-sm mt-1">
                    <span className="text-emerald-400">{String(confidence.high_pct || 0)}% H</span>{" / "}
                    <span className="text-amber-400">{String(confidence.medium_pct || 0)}% M</span>
                  </p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* QA Rules */}
          {Object.keys(qaRules).length > 0 && (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader><CardTitle className="text-sm text-zinc-400">QA Validation Rules</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.entries(qaRules).map(([name, info]) => (
                    <div key={name} className="flex items-center justify-between py-1.5 border-b border-zinc-800/50">
                      <span className="text-sm">{name}</span>
                      <Badge className={info.passed ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"}>
                        {info.passed ? "PASS" : `FAIL (${info.violations})`}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Logs */}
          {logs && (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader><CardTitle className="text-sm text-zinc-400">Pipeline Log</CardTitle></CardHeader>
              <CardContent>
                <pre className="text-xs text-zinc-400 bg-black/30 p-4 rounded-lg overflow-x-auto max-h-64 overflow-y-auto font-mono">
                  {logs}
                </pre>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
