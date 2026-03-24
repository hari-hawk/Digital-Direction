"use client";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, ProjectStats, CarrierSpend, ServiceTypeCount } from "@/lib/api";
import { useProjectIdWithReady } from "@/hooks/useProjectId";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const COLORS = ["#3b82f6", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#ec4899", "#6366f1", "#14b8a6", "#f97316"];

function formatMoney(n: number) {
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

interface EnhancedData {
  scu_breakdown: { carrier: string; s_rows: number; c_rows: number; t_rows: number; u_rows: number; total: number; mrc: number }[];
  contract_expiry: { category: string; count: number; color: string }[];
  month_to_month_count: number;
  data_quality: Record<string, number>;
  avg_data_quality: number;
  cost_by_service_type: { service_type: string; mrc: number; count: number; services: number }[];
  top_locations: { address: string; mrc: number }[];
  status_distribution: { status: string; count: number }[];
  health_score: number;
}

export default function Dashboard() {
  const { projectId, ready } = useProjectIdWithReady();
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [spend, setSpend] = useState<CarrierSpend[]>([]);
  const [serviceTypes, setServiceTypes] = useState<ServiceTypeCount[]>([]);
  const [enhanced, setEnhanced] = useState<EnhancedData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ready) return; // Wait for localStorage to be read
    setLoading(true);
    Promise.all([
      api.getStats(projectId),
      api.getSpendByCarrier(projectId),
      api.getServiceTypes(projectId),
      api.getEnhancedDashboard(projectId),
    ]).then(([s, sp, st, en]) => {
      setStats(s);
      setSpend(sp);
      setServiceTypes(st);
      setEnhanced(en);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [projectId, ready]);

  if (loading) return <div className="text-zinc-400 p-8">Loading dashboard...</div>;
  if (!stats) return <div className="text-red-400 p-8">Failed to load. Is the backend running on port 8000?</div>;

  const isEmpty = stats.total_rows === 0 && stats.carriers === 0;
  const topSpend = spend.slice(0, 10);
  const topServices = serviceTypes.slice(0, 8);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-xs text-zinc-500 mt-1">
            Telecom inventory overview · {stats.carriers} carriers · {stats.total_rows?.toLocaleString() || 0} records
          </p>
        </div>
        <div className="flex gap-2">
          <a href="/upload" className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm">Upload</a>
          <a href="/extraction" className="px-3 py-1.5 bg-zinc-800 border border-zinc-700 hover:bg-zinc-700 rounded-lg text-sm">Extract</a>
        </div>
      </div>

      {/* Workflow Steps */}
      <div className="grid grid-cols-5 gap-2 mb-6">
        {[
          { step: "1", label: "Upload", desc: "Drop files or ZIP", href: "/upload", color: "blue" },
          { step: "2", label: "Documents", desc: "Browse & preview", href: "/documents", color: "purple" },
          { step: "3", label: "Extract", desc: "Run AI pipeline", href: "/extraction", color: "cyan" },
          { step: "4", label: "Inventory", desc: "View & filter data", href: "/inventory", color: "emerald" },
          { step: "5", label: "Insights", desc: "Audit & analyze", href: "/insights", color: "amber" },
        ].map((item) => (
          <a key={item.step} href={item.href}
            className="p-3 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-600 transition-colors group">
            <div className="flex items-center gap-2 mb-1">
              <span className={`w-5 h-5 rounded-full bg-${item.color}-600/20 text-${item.color}-400 text-xs flex items-center justify-center`}>
                {item.step}
              </span>
              <span className="text-sm font-medium group-hover:text-white">{item.label}</span>
            </div>
            <p className="text-xs text-zinc-500">{item.desc}</p>
          </a>
        ))}
      </div>

      {/* Empty state */}
      {isEmpty && (
        <Card className="bg-zinc-900 border-zinc-800 mb-8">
          <CardContent className="py-12 text-center">
            <p className="text-3xl mb-3">📂</p>
            <h2 className="text-lg font-medium mb-2">No data yet</h2>
            <p className="text-sm text-zinc-400 mb-4">Upload documents to get started.</p>
            <a href="/upload" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium inline-block">Upload Documents</a>
          </CardContent>
        </Card>
      )}

      {/* Row 1: Stats Cards + Health Score */}
      {!isEmpty && (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2"><CardTitle className="text-xs text-zinc-400">Total Monthly Spend</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-bold text-blue-400">{formatMoney(stats.total_mrc)}</p></CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2"><CardTitle className="text-xs text-zinc-400">Carriers</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-bold text-purple-400">{stats.carriers}</p></CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2"><CardTitle className="text-xs text-zinc-400">Services (S-rows)</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-bold text-cyan-400">{stats.services.toLocaleString()}</p></CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2"><CardTitle className="text-xs text-zinc-400">Documents</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-bold text-emerald-400">{stats.total_documents}</p></CardContent>
        </Card>
        {enhanced && (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2"><CardTitle className="text-xs text-zinc-400">Data Quality Score</CardTitle></CardHeader>
            <CardContent>
              <p className={`text-xl font-bold ${
                enhanced.health_score >= 80 ? "text-emerald-400" :
                enhanced.health_score >= 60 ? "text-amber-400" : "text-red-400"
              }`}>
                {enhanced.health_score}%
              </p>
            </CardContent>
          </Card>
        )}
      </div>
      )}

      {/* Row 2: Data Quality + Contract Expiry + M2M */}
      {enhanced && !isEmpty && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          {/* Data Quality Heatmap */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400">
                Data Quality by Column
                <Badge className="ml-2 bg-zinc-800 text-zinc-300">{enhanced.avg_data_quality}% avg</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1.5">
                {Object.entries(enhanced.data_quality).map(([col, pct]) => (
                  <div key={col} className="flex items-center gap-2">
                    <span className="text-xs text-zinc-400 w-32 truncate" title={col}>{col}</span>
                    <div className="flex-1 bg-zinc-800 rounded-full h-2 overflow-hidden">
                      <div
                        className={`h-2 rounded-full ${
                          pct >= 95 ? "bg-emerald-500" : pct >= 80 ? "bg-blue-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-zinc-500 w-10 text-right">{pct}%</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Contract Expiration */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2"><CardTitle className="text-sm text-zinc-400">Contract Expiration</CardTitle></CardHeader>
            <CardContent>
              {enhanced.contract_expiry.length > 0 ? (
                <div className="space-y-3">
                  {enhanced.contract_expiry.map((item) => (
                    <div key={item.category} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                        <span className="text-sm text-zinc-300">{item.category}</span>
                      </div>
                      <span className="text-sm font-medium" style={{ color: item.color }}>{item.count}</span>
                    </div>
                  ))}
                  {enhanced.month_to_month_count > 0 && (
                    <div className="pt-2 border-t border-zinc-800 flex items-center justify-between">
                      <span className="text-sm text-zinc-400">Month-to-Month</span>
                      <Badge className="bg-amber-500/20 text-amber-300">{enhanced.month_to_month_count}</Badge>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-zinc-500 text-sm py-4">No contract dates available</p>
              )}
            </CardContent>
          </Card>

          {/* Status Distribution */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2"><CardTitle className="text-sm text-zinc-400">Status Distribution</CardTitle></CardHeader>
            <CardContent>
              {enhanced.status_distribution.length > 0 ? (
                <div className="space-y-2">
                  {enhanced.status_distribution.map((item) => {
                    const total = enhanced.status_distribution.reduce((s, i) => s + i.count, 0);
                    const pct = total > 0 ? (item.count / total) * 100 : 0;
                    return (
                      <div key={item.status}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-zinc-300">{item.status}</span>
                          <span className="text-zinc-500">{item.count.toLocaleString()} ({pct.toFixed(1)}%)</span>
                        </div>
                        <div className="w-full bg-zinc-800 rounded-full h-1.5">
                          <div
                            className={`h-1.5 rounded-full ${
                              item.status.includes("Completed") ? "bg-emerald-500" :
                              item.status.includes("Pending") ? "bg-amber-500" : "bg-blue-500"
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-zinc-500 text-sm py-4">No status data</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Row 3: Charts */}
      {!isEmpty && <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader><CardTitle className="text-sm text-zinc-400">Monthly Spend by Carrier (Top 10)</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={topSpend} layout="vertical" margin={{ left: 120 }}>
                <XAxis type="number" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} stroke="#71717a" />
                <YAxis type="category" dataKey="carrier" width={120} tick={{ fontSize: 11, fill: "#a1a1aa" }} />
                <Tooltip formatter={(v: number) => formatMoney(v)} contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }} />
                <Bar dataKey="mrc" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader><CardTitle className="text-sm text-zinc-400">Service Type Distribution</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={topServices} dataKey="count" nameKey="service_type" cx="50%" cy="50%" outerRadius={100}
                  label={({ service_type, count }) => `${service_type} (${count})`}>
                  {topServices.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>}

      {/* Row 4: Cost by Service Type + Top Locations */}
      {enhanced && !isEmpty && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Cost by Service Type */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader><CardTitle className="text-sm text-zinc-400">Cost by Service Type (Top 10)</CardTitle></CardHeader>
            <CardContent>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-500">
                    <th className="text-left py-2">Service Type</th>
                    <th className="text-right py-2">MRC</th>
                    <th className="text-right py-2">Services</th>
                    <th className="text-right py-2">Avg/Svc</th>
                  </tr>
                </thead>
                <tbody>
                  {enhanced.cost_by_service_type.map((row) => (
                    <tr key={row.service_type} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                      <td className="py-1.5 text-zinc-300">{row.service_type}</td>
                      <td className="text-right py-1.5 text-blue-400 font-mono">{formatMoney(row.mrc)}</td>
                      <td className="text-right py-1.5">{row.services}</td>
                      <td className="text-right py-1.5 text-zinc-400 font-mono">
                        {row.services > 0 ? formatMoney(row.mrc / row.services) : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          {/* Top Locations */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader><CardTitle className="text-sm text-zinc-400">Top Locations by Spend</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2">
                {enhanced.top_locations.slice(0, 10).map((loc, i) => (
                  <div key={i} className="flex items-center justify-between py-1">
                    <span className="text-xs text-zinc-300 truncate flex-1 mr-4" title={loc.address}>{loc.address}</span>
                    <span className="text-xs text-blue-400 font-mono shrink-0">{formatMoney(loc.mrc)}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Row 5: Carrier Summary Table */}
      {!isEmpty && <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader><CardTitle className="text-sm text-zinc-400">Carrier Summary</CardTitle></CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-400 text-xs">
                <th className="text-left py-2">Carrier</th>
                <th className="text-right py-2">Monthly Spend</th>
                <th className="text-right py-2">Services</th>
                <th className="text-right py-2">Rows</th>
                <th className="text-right py-2">Avg/Service</th>
                {enhanced && <th className="text-right py-2">S / C / T</th>}
              </tr>
            </thead>
            <tbody>
              {spend.map((c) => {
                const scu = enhanced?.scu_breakdown.find((s) => s.carrier === c.carrier);
                return (
                  <tr key={c.carrier} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 text-xs">
                    <td className="py-2 font-medium">{c.carrier}</td>
                    <td className="text-right py-2 text-blue-400 font-mono">{formatMoney(c.mrc)}</td>
                    <td className="text-right py-2">{c.service_count}</td>
                    <td className="text-right py-2 text-zinc-400">{c.row_count}</td>
                    <td className="text-right py-2 text-zinc-400 font-mono">
                      {c.service_count > 0 ? formatMoney(c.mrc / c.service_count) : "-"}
                    </td>
                    {enhanced && (
                      <td className="text-right py-2 text-zinc-500 font-mono text-[10px]">
                        {scu ? `${scu.s_rows}/${scu.c_rows}/${scu.t_rows}` : "-"}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>}
    </div>
  );
}
