"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useProjectIdWithReady } from "@/hooks/useProjectId";
import { toast } from "@/components/ui/toaster";

export default function ExtractionPage() {
  const { projectId, ready } = useProjectIdWithReady();
  const [carriers, setCarriers] = useState<{ key: string; name: string; tier: number; status: string }[]>([]);
  const [selectedCarrier, setSelectedCarrier] = useState("charter");
  const [apiKey, setApiKey] = useState("");
  const [running, setRunning] = useState(false);
  const [, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [currentCarrier, setCurrentCarrier] = useState("");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [logs, setLogs] = useState("");
  const [lastStatus, setLastStatus] = useState<Record<string, unknown> | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!ready) return;
    api.getExtractionCarriers(projectId).then(setCarriers).catch(() => {});
    api.getExtractionStatus(projectId, "charter").then(setLastStatus).catch(() => {});
  }, [projectId, ready]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const getCarrierName = useCallback((key: string) => {
    const c = carriers.find((c) => c.key === key);
    return c ? c.name : key;
  }, [carriers]);

  async function startExtraction() {
    setRunning(true);
    setProgress(0);
    setResult(null);
    setLogs("Starting extraction pipeline...\n");
    setTaskError(null);
    setCurrentCarrier(getCarrierName(selectedCarrier));
    setElapsedSeconds(0);

    try {
      const res = await api.startExtraction(projectId, selectedCarrier, apiKey || undefined);

      if (res.task_id) {
        setTaskId(res.task_id);
        toast.info(
          "Extraction started",
          `Starting extraction for ${getCarrierName(selectedCarrier)}...`
        );

        // Start polling
        pollRef.current = setInterval(async () => {
          try {
            const task = await api.getExtractionTaskProgress(projectId, res.task_id);
            setProgress(task.progress);
            setCurrentCarrier(task.current_carrier);
            setElapsedSeconds(task.elapsed_seconds);

            if (task.status === "completed") {
              clearInterval(pollRef.current!);
              pollRef.current = null;
              setRunning(false);
              setProgress(100);

              const summary = task.result?.summary || {};
              setResult({ status: "completed", summary });
              setLastStatus(summary);
              setLogs(task.result?.stderr || task.result?.stdout || "Pipeline completed.");

              const totalRows = summary.total_rows as number || 0;
              toast.success(
                "Extraction complete!",
                `${totalRows.toLocaleString()} rows extracted for ${task.carrier_name} in ${task.elapsed_seconds}s`
              );
            } else if (task.status === "failed" || task.status === "timeout") {
              clearInterval(pollRef.current!);
              pollRef.current = null;
              setRunning(false);
              setProgress(0);
              setTaskError(task.error || "Extraction failed");
              setLogs(task.result?.stderr || task.error || "Pipeline failed.");

              toast.error(
                "Extraction failed",
                task.error || "Check logs for details"
              );
            }
          } catch {
            // Keep polling on transient errors
          }
        }, 2000);
      }
    } catch (e) {
      setRunning(false);
      setLogs(`Error: ${e}\n\nMake sure the backend is running on port 8000.`);
      toast.error("Extraction failed", String(e));
    }
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
            <button onClick={startExtraction} disabled={running}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-700 rounded-lg text-sm font-medium transition-colors">
              {running ? "Running..." : "Run Extraction"}
            </button>

            {/* Progress Bar */}
            {running && (
              <div className="space-y-2 mt-2">
                <div className="w-full bg-zinc-800 rounded-full h-2.5 overflow-hidden">
                  <div
                    className="bg-blue-500 h-2.5 rounded-full transition-all duration-500 relative"
                    style={{ width: `${progress}%` }}
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent to-blue-400/30 animate-pulse" />
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs text-zinc-400">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                    <span>{currentCarrier}</span>
                  </div>
                  <span>{progress}%</span>
                </div>
                <div className="flex justify-between text-[10px] text-zinc-500">
                  <span>Elapsed: {elapsedSeconds}s</span>
                  {progress > 0 && progress < 100 && (
                    <span>ETA: ~{Math.round((elapsedSeconds / progress) * (100 - progress))}s</span>
                  )}
                </div>
              </div>
            )}

            {/* Task Error */}
            {taskError && !running && (
              <div className="mt-2 p-3 bg-red-900/20 border border-red-500/20 rounded-lg">
                <p className="text-xs text-red-400">{taskError}</p>
              </div>
            )}

            {/* Completion indicator */}
            {!running && progress === 100 && (
              <div className="mt-2 p-3 bg-emerald-900/20 border border-emerald-500/20 rounded-lg">
                <div className="flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 text-emerald-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="text-sm text-emerald-300 font-medium">Extraction Complete</span>
                </div>
                <p className="text-xs text-zinc-400 mt-1">
                  {String(summary.total_rows || 0)} rows in {elapsedSeconds}s
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Results */}
        <div className="lg:col-span-2 space-y-4">
          {/* Summary Cards */}
          {!!summary.total_rows && (
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
