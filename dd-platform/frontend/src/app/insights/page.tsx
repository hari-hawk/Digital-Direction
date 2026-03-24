"use client";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, InsightFlag, CostBreakdown } from "@/lib/api";
import { useProjectId } from "@/hooks/useProjectId";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-500/20 text-red-300 border-red-500/30",
  warning: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  info: "bg-blue-500/20 text-blue-300 border-blue-500/30",
};

const SEVERITY_ICONS: Record<string, string> = {
  critical: "\u{1F534}",
  warning: "\u{1F7E1}",
  info: "\u{1F535}",
};

function formatMoney(n: number) {
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export default function InsightsPage() {
  const projectId = useProjectId();
  const [insights, setInsights] = useState<InsightFlag[]>([]);
  const [costData, setCostData] = useState<CostBreakdown[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([api.getInsights(projectId), api.getCostBreakdown(projectId)])
      .then(([i, c]) => { setInsights(i); setCostData(c); setLoading(false); })
      .catch(() => setLoading(false));
  }, [projectId]);

  if (loading) return <div className="text-zinc-400">Loading insights...</div>;

  const critCount = insights.filter((i) => i.severity === "critical").length;
  const warnCount = insights.filter((i) => i.severity === "warning").length;
  const infoCount = insights.filter((i) => i.severity === "info").length;
  const totalFlags = insights.reduce((sum, i) => sum + i.count, 0);

  const costChartData = costData.slice(0, 10).map((c) => ({
    carrier: c.carrier.length > 18 ? c.carrier.slice(0, 18) + "..." : c.carrier,
    avg: c.avg_mrc_per_service,
  }));

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Audit Insights</h1>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-400">Total Flags</p>
            <p className="text-2xl font-bold">{totalFlags.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900 border-red-500/20">
          <CardContent className="p-4">
            <p className="text-xs text-red-400">Critical</p>
            <p className="text-2xl font-bold text-red-400">{critCount}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900 border-amber-500/20">
          <CardContent className="p-4">
            <p className="text-xs text-amber-400">Warnings</p>
            <p className="text-2xl font-bold text-amber-400">{warnCount}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900 border-blue-500/20">
          <CardContent className="p-4">
            <p className="text-xs text-blue-400">Info</p>
            <p className="text-2xl font-bold text-blue-400">{infoCount}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Insight Flags */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold mb-3">Audit Flags</h2>
          {insights.map((flag, i) => (
            <Card key={i} className={`bg-zinc-900 border ${SEVERITY_COLORS[flag.severity]?.includes("border") ? "" : "border-zinc-800"}`}>
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <span className="text-lg">{SEVERITY_ICONS[flag.severity]}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm">{flag.category}</span>
                      <Badge className={SEVERITY_COLORS[flag.severity]}>{flag.count}</Badge>
                    </div>
                    <p className="text-xs text-zinc-400">{flag.description}</p>
                    {flag.details.length > 0 && (
                      <button
                        onClick={() => setExpanded(expanded === flag.category ? null : flag.category)}
                        className="text-xs text-blue-400 mt-2 hover:underline"
                      >
                        {expanded === flag.category ? "Hide details" : "Show details"}
                      </button>
                    )}
                    {expanded === flag.category && flag.details.length > 0 && (
                      <ul className="mt-2 space-y-1">
                        {flag.details.map((d, j) => (
                          <li key={j} className="text-xs text-zinc-500 pl-2 border-l border-zinc-700">{d}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Cost Analysis */}
        <div>
          <h2 className="text-lg font-semibold mb-3">Cost per Service by Carrier</h2>
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="pt-6">
              <ResponsiveContainer width="100%" height={350}>
                <BarChart data={costChartData} layout="vertical" margin={{ left: 100 }}>
                  <XAxis type="number" tickFormatter={(v) => `$${v}`} stroke="#71717a" />
                  <YAxis type="category" dataKey="carrier" width={100} tick={{ fontSize: 11, fill: "#a1a1aa" }} />
                  <Tooltip formatter={(v: number) => formatMoney(v)} contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }} />
                  <Bar dataKey="avg" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Cost Table */}
          <Card className="bg-zinc-900 border-zinc-800 mt-4">
            <CardHeader><CardTitle className="text-sm text-zinc-400">Carrier Cost Breakdown</CardTitle></CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-400 text-xs">
                    <th className="text-left py-2">Carrier</th>
                    <th className="text-right py-2">Total MRC</th>
                    <th className="text-right py-2">Services</th>
                    <th className="text-right py-2">Avg/Svc</th>
                  </tr>
                </thead>
                <tbody>
                  {costData.map((c) => (
                    <tr key={c.carrier} className="border-b border-zinc-800/50">
                      <td className="py-1.5 text-xs">{c.carrier}</td>
                      <td className="text-right py-1.5 text-blue-400 text-xs">{formatMoney(c.mrc)}</td>
                      <td className="text-right py-1.5 text-xs">{c.service_count}</td>
                      <td className="text-right py-1.5 text-xs text-zinc-400">{formatMoney(c.avg_mrc_per_service)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
