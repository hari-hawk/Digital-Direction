"use client";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ProjectStats, CarrierSpend, ServiceTypeCount } from "@/lib/api";
import { useProjectId } from "@/hooks/useProjectId";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const COLORS = ["#3b82f6", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#ec4899", "#6366f1", "#14b8a6", "#f97316"];

function formatMoney(n: number) {
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export default function Dashboard() {
  const projectId = useProjectId();
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [spend, setSpend] = useState<CarrierSpend[]>([]);
  const [serviceTypes, setServiceTypes] = useState<ServiceTypeCount[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getStats(projectId),
      api.getSpendByCarrier(projectId),
      api.getServiceTypes(projectId),
    ]).then(([s, sp, st]) => {
      setStats(s);
      setSpend(sp);
      setServiceTypes(st);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [projectId]);

  if (loading) return <div className="text-zinc-400">Loading dashboard...</div>;
  if (!stats) return <div className="text-red-400">Failed to load. Is the backend running on port 8000?</div>;

  const isEmpty = stats.total_rows === 0 && stats.carriers === 0;
  const topSpend = spend.slice(0, 10);
  const topServices = serviceTypes.slice(0, 8);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-xs text-zinc-500 mt-1">Telecom inventory overview · {stats.carriers} carriers · {stats.total_rows?.toLocaleString() || 0} records</p>
        </div>
        <div className="flex gap-2">
          <a href="/upload" className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm">Upload Files</a>
          <a href="/extraction" className="px-3 py-1.5 bg-zinc-800 border border-zinc-700 hover:bg-zinc-700 rounded-lg text-sm">Run Extraction</a>
        </div>
      </div>

      {/* Quick Workflow Steps */}
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

      {/* Empty state for new projects */}
      {isEmpty && (
        <Card className="bg-zinc-900 border-zinc-800 mb-8">
          <CardContent className="py-12 text-center">
            <p className="text-3xl mb-3">📂</p>
            <h2 className="text-lg font-medium mb-2">No data yet</h2>
            <p className="text-sm text-zinc-400 mb-4">
              Upload documents to get started. This project has no inventory data.
            </p>
            <a href="/upload" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium inline-block">
              Upload Documents
            </a>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-zinc-400">Total Monthly Spend</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold text-blue-400">{formatMoney(stats.total_mrc)}</p></CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-zinc-400">Active Carriers</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold text-purple-400">{stats.carriers}</p></CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-zinc-400">Total Services</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold text-cyan-400">{stats.services.toLocaleString()}</p></CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-zinc-400">Documents</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold text-emerald-400">{stats.total_documents}</p></CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Spend by Carrier */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader><CardTitle className="text-sm text-zinc-400">Monthly Spend by Carrier (Top 10)</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={topSpend} layout="vertical" margin={{ left: 120 }}>
                <XAxis type="number" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} stroke="#71717a" />
                <YAxis type="category" dataKey="carrier" width={120} tick={{ fontSize: 11, fill: "#a1a1aa" }} />
                <Tooltip formatter={(v: number) => formatMoney(v)} contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }} />
                <Bar dataKey="mrc" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Service Type Distribution */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader><CardTitle className="text-sm text-zinc-400">Service Type Distribution</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={350}>
              <PieChart>
                <Pie data={topServices} dataKey="count" nameKey="service_type" cx="50%" cy="50%" outerRadius={120} label={({ service_type, count }) => `${service_type} (${count})`}>
                  {topServices.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Carrier Table */}
      <Card className="bg-zinc-900 border-zinc-800 mt-6">
        <CardHeader><CardTitle className="text-sm text-zinc-400">Carrier Summary</CardTitle></CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-400">
                <th className="text-left py-2">Carrier</th>
                <th className="text-right py-2">Monthly Spend</th>
                <th className="text-right py-2">Services</th>
                <th className="text-right py-2">Rows</th>
                <th className="text-right py-2">Avg/Service</th>
              </tr>
            </thead>
            <tbody>
              {spend.map((c) => (
                <tr key={c.carrier} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                  <td className="py-2 font-medium">{c.carrier}</td>
                  <td className="text-right py-2 text-blue-400">{formatMoney(c.mrc)}</td>
                  <td className="text-right py-2">{c.service_count}</td>
                  <td className="text-right py-2 text-zinc-400">{c.row_count}</td>
                  <td className="text-right py-2 text-zinc-400">
                    {c.service_count > 0 ? formatMoney(c.mrc / c.service_count) : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
