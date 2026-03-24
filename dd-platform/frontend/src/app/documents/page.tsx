"use client";
import { useEffect, useState, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, CarrierSummary, CarrierDocs } from "@/lib/api";
import { useProjectIdWithReady } from "@/hooks/useProjectId";

const API_BASE = "http://127.0.0.1:8000/api";

const DOC_TYPE_COLORS: Record<string, string> = {
  invoice: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  contract: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  carrier_report: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  csr: "bg-amber-500/20 text-amber-300 border-amber-500/30",
};

const DOC_TYPE_LABELS: Record<string, string> = {
  invoice: "Invoice",
  contract: "Contract",
  carrier_report: "Report",
  csr: "CSR",
};

const FORMAT_ICONS: Record<string, string> = {
  pdf: "📄", xlsx: "📊", xls: "📊", csv: "📃", msg: "✉️", docx: "📝",
};

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

interface FileInfo {
  name: string; path: string; format: string;
  size_bytes: number; doc_type: string; type_label: string;
}

// ═══════════════════════════════════════════
// Preview Modal (unchanged, kept from before)
// ═══════════════════════════════════════════
function PreviewModal({ file, projectId, onClose }: { file: FileInfo; projectId: string; onClose: () => void }) {
  const inlineUrl = `${API_BASE}/projects/${projectId}/documents/file?file_path=${encodeURIComponent(file.path)}&mode=inline`;
  const downloadUrl = `${API_BASE}/projects/${projectId}/documents/file?file_path=${encodeURIComponent(file.path)}&mode=download`;
  const isPdf = file.format === "pdf";
  const isExcel = ["xlsx", "xls", "csv"].includes(file.format);
  const isImage = ["png", "jpg", "jpeg", "gif"].includes(file.format);

  const [excelData, setExcelData] = useState<{ headers: string[]; rows: string[][] } | null>(null);
  const [excelLoading, setExcelLoading] = useState(false);

  useEffect(() => {
    if (isExcel) {
      setExcelLoading(true);
      fetch(`${API_BASE}/projects/${projectId}/documents/preview-excel?file_path=${encodeURIComponent(file.path)}`)
        .then((r) => r.json()).then((d) => { setExcelData(d); setExcelLoading(false); })
        .catch(() => setExcelLoading(false));
    }
  }, [file.path, isExcel, projectId]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-[85vw] h-[85vh] bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-2xl">{FORMAT_ICONS[file.format] || "📄"}</span>
            <div className="min-w-0">
              <h2 className="text-lg font-semibold truncate">{file.name}</h2>
              <div className="flex items-center gap-3 mt-0.5">
                <Badge className={DOC_TYPE_COLORS[file.doc_type] || "bg-zinc-700 text-zinc-300"}>{file.type_label}</Badge>
                <span className="text-xs text-zinc-500">{formatSize(file.size_bytes)}</span>
                <span className="text-xs text-zinc-500 uppercase">{file.format}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a href={downloadUrl} download={file.name} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm">Download</a>
            <button onClick={onClose} className="w-9 h-9 flex items-center justify-center rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white text-lg">✕</button>
          </div>
        </div>
        <div className="flex-1 overflow-auto bg-zinc-950">
          {isPdf && (
            <object data={inlineUrl} type="application/pdf" className="w-full h-full" title={file.name}>
              <iframe src={inlineUrl} className="w-full h-full border-0" title={file.name} />
            </object>
          )}
          {isImage && (
            <div className="flex items-center justify-center h-full p-8">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={inlineUrl} alt={file.name} className="max-w-full max-h-full object-contain rounded" />
            </div>
          )}
          {isExcel && (
            <div className="p-4">
              {excelLoading ? <div className="text-zinc-400 text-center py-12">Loading spreadsheet preview...</div>
              : excelData ? (
                <div className="overflow-auto">
                  <table className="w-full text-xs border-collapse">
                    <thead className="sticky top-0 bg-zinc-900">
                      <tr>
                        <th className="text-left py-2 px-2 text-zinc-600 font-mono border-b border-zinc-800">#</th>
                        {excelData.headers.map((h, i) => (
                          <th key={i} className="text-left py-2 px-2 text-zinc-400 font-medium border-b border-zinc-800 whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {excelData.rows.map((row, ri) => (
                        <tr key={ri} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                          <td className="py-1 px-2 text-zinc-600 font-mono">{ri + 1}</td>
                          {row.map((cell, ci) => (
                            <td key={ci} className="py-1 px-2 text-zinc-300 max-w-[200px] truncate" title={cell}>{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="text-zinc-400 text-center py-12">Could not preview. <a href={downloadUrl} download className="text-blue-400">Download</a></div>}
            </div>
          )}
          {!isPdf && !isExcel && !isImage && (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-zinc-400">
              <span className="text-5xl">{FORMAT_ICONS[file.format] || "📄"}</span>
              <p>Preview not available for .{file.format} files</p>
              <a href={downloadUrl} download={file.name} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm text-white">Download File</a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════
// Main Documents Page — Grid + Carrier Chips + Slide Panel
// ═══════════════════════════════════════════
export default function DocumentsPage() {
  const { projectId, ready } = useProjectIdWithReady();
  const [carriers, setCarriers] = useState<CarrierSummary[]>([]);
  const [docs, setDocs] = useState<CarrierDocs[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounce(searchInput, 300);
  const [selectedCarrier, setSelectedCarrier] = useState<string | null>(null);
  const [docTypeFilter, setDocTypeFilter] = useState<string>("all");
  const [previewFile, setPreviewFile] = useState<FileInfo | null>(null);

  useEffect(() => {
    if (!ready) return;
    setLoading(true);
    Promise.all([api.getCarriers(projectId), api.getDocuments(projectId)])
      .then(([c, d]) => { setCarriers(c); setDocs(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [projectId, ready]);

  if (loading) return <div className="text-zinc-400 p-8">Loading documents...</div>;

  // Build flat file list for "All" view
  function getFilesForCarrier(carrierName: string): FileInfo[] {
    const cd = docs.find((d) => d.carrier === carrierName);
    if (!cd) return [];
    return [
      ...cd.invoices.map((f) => ({ ...f, type_label: "Invoice" } as FileInfo)),
      ...cd.contracts.map((f) => ({ ...f, type_label: "Contract" } as FileInfo)),
      ...cd.carrier_reports.map((f) => ({ ...f, type_label: "Report" } as FileInfo)),
      ...cd.csrs.map((f) => ({ ...f, type_label: "CSR" } as FileInfo)),
    ];
  }

  // Carrier filter chips
  const carrierChips = [
    { key: null as string | null, label: "All Carriers", count: carriers.reduce((s, c) => s + c.total, 0) },
    ...carriers
      .filter((c) => c.total > 0)
      .sort((a, b) => b.total - a.total)
      .map((c) => ({ key: c.name, label: c.name, count: c.total })),
  ];

  // Doc type chips
  const docTypeChips = [
    { key: "all", label: "All Types" },
    { key: "invoice", label: "Invoices" },
    { key: "contract", label: "Contracts" },
    { key: "carrier_report", label: "Reports" },
    { key: "csr", label: "CSRs" },
  ];

  // Filter carriers by search — match carrier name OR file name
  const searchLower = search.toLowerCase();
  const visibleCarriers = carriers
    .filter((c) => c.total > 0)
    .filter((c) => {
      if (!search) return true;
      // Match carrier name
      if (c.name.toLowerCase().includes(searchLower)) return true;
      // Match any file name within this carrier
      const files = getFilesForCarrier(c.name);
      return files.some((f) => f.name.toLowerCase().includes(searchLower));
    })
    .filter((c) => !selectedCarrier || c.name === selectedCarrier);

  // Get all visible files — also filter individual files by search term
  const allVisibleFiles: (FileInfo & { carrierName: string })[] = visibleCarriers.flatMap((c) =>
    getFilesForCarrier(c.name)
      .filter((f) => docTypeFilter === "all" || f.doc_type === docTypeFilter)
      .filter((f) => !search || f.name.toLowerCase().includes(searchLower) || c.name.toLowerCase().includes(searchLower))
      .map((f) => ({ ...f, carrierName: c.name }))
  );

  const totalDocs = carriers.reduce((s, c) => s + c.total, 0);

  return (
    <div>
      {previewFile && <PreviewModal file={previewFile} projectId={projectId} onClose={() => setPreviewFile(null)} />}

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold">Documents</h1>
          <p className="text-xs text-zinc-500 mt-1">{totalDocs} files across {carriers.filter((c) => c.total > 0).length} carriers</p>
        </div>
        <a href="/upload" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium">Upload Files</a>
      </div>

      {/* Carrier Filter Chips — multi-row wrap */}
      <div className="flex flex-wrap gap-2 mb-3">
        {carrierChips.map((chip) => (
          <button
            key={chip.key ?? "__all__"}
            onClick={() => setSelectedCarrier(chip.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs whitespace-nowrap border transition-colors ${
              selectedCarrier === chip.key
                ? "bg-blue-600/20 text-blue-300 border-blue-500/40"
                : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:border-zinc-600 hover:text-zinc-200"
            }`}
          >
            {chip.label}
            <span className="text-[10px] opacity-60">{chip.count}</span>
          </button>
        ))}
      </div>

      {/* Doc Type Filter + Search */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex gap-1">
          {docTypeChips.map((chip) => (
            <button
              key={chip.key}
              onClick={() => setDocTypeFilter(chip.key)}
              className={`px-2.5 py-1 rounded text-xs transition-colors ${
                docTypeFilter === chip.key
                  ? "bg-zinc-700 text-white"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {chip.label}
            </button>
          ))}
        </div>
        <div className="flex-1 max-w-xs">
          <Input
            placeholder="Search files..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="bg-zinc-900 border-zinc-700 text-sm h-8"
          />
        </div>
        <span className="text-xs text-zinc-500">{allVisibleFiles.length} files</span>
      </div>

      {/* === GRID VIEW: Carrier Cards (when All Carriers selected and no search) === */}
      {!selectedCarrier && !search && docTypeFilter === "all" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {carriers
            .filter((c) => c.total > 0)
            .sort((a, b) => b.total - a.total)
            .map((c) => (
              <button
                key={c.name}
                onClick={() => setSelectedCarrier(c.name)}
                className="text-left p-4 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-zinc-600 hover:bg-zinc-800/50 transition-all group"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-medium text-sm group-hover:text-white leading-tight">{c.name}</h3>
                  <Badge variant="secondary" className="bg-zinc-800 text-zinc-300 ml-2 shrink-0">{c.total}</Badge>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {c.invoices > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      {c.invoices} Invoice{c.invoices !== 1 ? "s" : ""}
                    </span>
                  )}
                  {c.contracts > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
                      {c.contracts} Contract{c.contracts !== 1 ? "s" : ""}
                    </span>
                  )}
                  {c.carrier_reports > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {c.carrier_reports} Report{c.carrier_reports !== 1 ? "s" : ""}
                    </span>
                  )}
                  {c.csrs > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      {c.csrs} CSR{c.csrs !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>
              </button>
            ))}
        </div>
      ) : (
        /* === FILE GRID: 3-column file cards === */
        allVisibleFiles.length === 0 ? (
          <div className="text-center py-16 text-zinc-500">
            <p className="text-lg mb-2">No files found</p>
            <button onClick={() => { setSelectedCarrier(null); setDocTypeFilter("all"); setSearchInput(""); }}
              className="text-sm text-blue-400 hover:text-blue-300">Clear filters</button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {allVisibleFiles.map((f, i) => (
              <button
                key={`${f.carrierName}-${i}`}
                onClick={() => setPreviewFile(f)}
                className="text-left p-4 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-zinc-600 hover:bg-zinc-800/50 transition-all group"
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl mt-0.5">{FORMAT_ICONS[f.format] || "📄"}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate group-hover:text-white">{f.name}</p>
                    <p className="text-xs text-zinc-500 mt-0.5">{f.carrierName}</p>
                    <div className="flex items-center gap-2 mt-2">
                      <Badge className={`text-[10px] ${DOC_TYPE_COLORS[f.doc_type] || "bg-zinc-700 text-zinc-300"}`}>
                        {f.type_label}
                      </Badge>
                      <span className="text-[10px] text-zinc-600">{formatSize(f.size_bytes)}</span>
                      <span className="text-[10px] text-zinc-600 uppercase">{f.format}</span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )
      )}
    </div>
  );
}
