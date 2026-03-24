"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, RowDetailResponse, ConfidenceSummary } from "@/lib/api";
import { useProjectId } from "@/hooks/useProjectId";

interface SheetInfo { name: string; rows: number; cols: number }
interface FilterState {
  carrier: string; service_type: string; charge_type: string;
  scu_code: string; status: string; search: string;
}
interface SortState { column: string; direction: "asc" | "desc" }

const PRIORITY_COLUMNS = [
  "Status", "Carrier", "Carrier Account Number", "Service Type",
  "Service or Component", "Billing Name", "Service Address 1",
  "City", "State", "Zip", "Phone Number", "Carrier Circuit Number",
  "Monthly Recurring Cost", "Charge Type", "Component or Feature Name",
  "Access Speed", "Upload Speed",
];

const EMPTY_FILTERS: FilterState = {
  carrier: "", service_type: "", charge_type: "", scu_code: "", status: "", search: "",
};

// Status badge config
const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  completed: { label: "Completed", cls: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" },
  need_review: { label: "Need Review", cls: "bg-amber-500/20 text-amber-300 border-amber-500/30" },
  critical: { label: "Critical", cls: "bg-red-500/20 text-red-300 border-red-500/30" },
  in_progress: { label: "In Progress", cls: "bg-blue-500/20 text-blue-300 border-blue-500/30" },
};

// Field grouping for the slider detail view
const FIELD_GROUPS: Record<string, string[]> = {
  "Location": ["Service Address 1", "Service Address 2", "City", "State", "Zip", "Country", "Location Code", "Building", "Floor", "Room"],
  "Service": ["Service Type", "Charge Type", "Service or Component", "Component or Feature Name", "Access Speed", "Upload Speed", "Phone Number", "Carrier Circuit Number"],
  "Billing": ["Billing Name", "Billing Address", "Monthly Recurring Cost", "Non Recurring Charges", "Usage Charges", "Total Charges"],
  "Contract": ["Contract Number", "Contract Start", "Contract End", "Term", "Contract Term", "Auto Renew"],
  "Carrier": ["Carrier", "Carrier Account Number", "Carrier Name", "Vendor"],
  "Status": ["Status"],
};

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

// ═══════════════════════════════════════════
// Required fields — empty ones get highlighted in red in the slider panel
const _REQUIRED_FIELDS_SET = new Set([
  "carrier", "carrier account number", "service type", "charge type",
  "service or component", "billing name", "service address 1", "city",
  "state", "zip", "monthly recurring cost",
]);

// Row Detail Slider Panel
// ═══════════════════════════════════════════
function RowDetailSlider({
  projectId,
  rowIndex,
  source,
  onClose,
  onSaved,
}: {
  projectId: string;
  rowIndex: number;
  source: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [detail, setDetail] = useState<RowDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [editedFields, setEditedFields] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("in_progress");
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.getRowDetail(projectId, rowIndex, source).then((d) => {
      setDetail(d);
      setStatus(d.status || "in_progress");
      setComment(d.comment || "");
      // Initialize editable fields
      const fields: Record<string, string> = {};
      for (const f of d.fields) {
        fields[f.field_name] = f.field_value === null || f.field_value === undefined ? "" : String(f.field_value);
      }
      setEditedFields(fields);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [projectId, rowIndex, source]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  async function handleSave() {
    setSaving(true);
    try {
      await api.updateRowStatus(projectId, rowIndex, status, comment);
      onSaved();
    } catch { /* ignore */ }
    setSaving(false);
  }

  // Group fields
  function groupFields() {
    if (!detail) return [];
    const fieldEntries = detail.fields.map((f) => ({ lower: f.field_name.toLowerCase(), original: f.field_name }));
    const assigned = new Set<string>();
    const groups: { name: string; fields: string[] }[] = [];

    for (const [groupName, patterns] of Object.entries(FIELD_GROUPS)) {
      const matched: string[] = [];
      for (const pattern of patterns) {
        for (const entry of fieldEntries) {
          if (entry.lower.includes(pattern.toLowerCase()) && !assigned.has(entry.original)) {
            matched.push(entry.original);
            assigned.add(entry.original);
          }
        }
      }
      if (matched.length > 0) groups.push({ name: groupName, fields: matched });
    }

    // Remaining ungrouped fields
    const remaining = detail.fields.filter((f) => !assigned.has(f.field_name)).map((f) => f.field_name);
    if (remaining.length > 0) groups.push({ name: "Other", fields: remaining });

    return groups;
  }

  const fieldGroups = groupFields();
  const statusCfg = STATUS_CONFIG[status] || STATUS_CONFIG.in_progress;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* Slider panel */}
      <div className="fixed top-0 right-0 z-50 h-full w-full max-w-[45vw] min-w-[400px] bg-zinc-900 border-l border-zinc-700 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold">Row #{rowIndex + 1} Detail</h2>
            {detail && (
              <div className="flex items-center gap-2 mt-1">
                <Badge className={statusCfg.cls + " text-xs border"}>{statusCfg.label}</Badge>
                <span className={`text-xs font-mono ${
                  (detail.accuracy_score ?? 0) >= 90 ? "text-emerald-400" :
                  (detail.accuracy_score ?? 0) >= 70 ? "text-amber-400" : "text-red-400"
                }`}>
                  {detail.accuracy_score}% accuracy
                </span>
              </div>
            )}
          </div>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white text-lg">
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="text-zinc-400 text-center py-12">Loading row detail...</div>
          ) : detail ? (
            <>
              {/* Status dropdown */}
              <div className="mb-4">
                <label className="text-xs text-zinc-500 block mb-1">Review Status</label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm"
                >
                  <option value="completed">Completed</option>
                  <option value="need_review">Need Review</option>
                  <option value="critical">Critical</option>
                  <option value="in_progress">In Progress</option>
                </select>
              </div>

              {/* Source Documents — Clickable pills */}
              {detail.source_documents && detail.source_documents.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Source Documents</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {detail.source_documents.map((doc, i) => {
                      const ext = doc.split(".").pop()?.toLowerCase() || "";
                      const typeInfo = ext === "pdf" ? { icon: "📄", label: "Invoice", cls: "border-blue-500/30 bg-blue-500/10 text-blue-300" }
                        : ["xlsx", "xls", "csv"].includes(ext) ? { icon: "📊", label: "Report", cls: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" }
                        : ext === "msg" ? { icon: "✉️", label: "Email", cls: "border-purple-500/30 bg-purple-500/10 text-purple-300" }
                        : { icon: "📁", label: "File", cls: "border-zinc-500/30 bg-zinc-500/10 text-zinc-300" };
                      return (
                        <button key={i} className={`flex items-center gap-1.5 px-2 py-1 rounded-full border text-[10px] hover:opacity-80 transition-opacity ${typeInfo.cls}`}
                          title={doc}>
                          <span>{typeInfo.icon}</span>
                          <span>{typeInfo.label}</span>
                          <span className="text-zinc-500 max-w-[100px] truncate">{doc.split("/").pop()}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Field groups — 2-column grid layout */}
              {fieldGroups.map((group) => (
                <div key={group.name} className="mb-4">
                  <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 border-b border-zinc-800 pb-1">
                    {group.name}
                  </h3>
                  <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
                    {group.fields.map((fieldName) => {
                      const val = editedFields[fieldName] || "";
                      const isEmpty = !val || val === "nan" || val === "None";
                      const isRequired = _REQUIRED_FIELDS_SET.has(fieldName.toLowerCase());
                      const needsReview = isRequired && isEmpty;
                      return (
                        <div key={fieldName} className={`rounded-lg px-2 py-1.5 ${needsReview ? "bg-red-950/20 border border-red-500/20" : "bg-zinc-800/30"}`}>
                          <label className={`text-[10px] block mb-0.5 truncate ${needsReview ? "text-red-400 font-semibold" : "text-zinc-500"}`} title={fieldName}>
                            {fieldName} {needsReview && "⚠"}
                          </label>
                          <input
                            type="text"
                            value={val}
                            onChange={(e) => setEditedFields((prev) => ({ ...prev, [fieldName]: e.target.value }))}
                            placeholder={needsReview ? "Required — needs input" : ""}
                            className={`w-full bg-transparent border-b text-sm py-0.5 focus:outline-none ${
                              needsReview ? "border-red-500/30 text-red-200 placeholder-red-400/40" : "border-zinc-700/50 text-zinc-200 focus:border-blue-500"
                            }`}
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}

              {/* Comment */}
              <div className="mb-4">
                <label className="text-xs text-zinc-500 block mb-1">Review Comment</label>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows={3}
                  placeholder="Add notes about this row..."
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 resize-none focus:border-blue-500 focus:outline-none"
                />
              </div>
            </>
          ) : (
            <div className="text-zinc-500 text-center py-12">Row not found.</div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-zinc-800 flex items-center justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200 rounded-lg bg-zinc-800 hover:bg-zinc-700">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </>
  );
}

// ═══════════════════════════════════════════
// Main Inventory Page
// ═══════════════════════════════════════════
export default function InventoryPage() {
  const projectId = useProjectId();
  const [sheets, setSheets] = useState<SheetInfo[]>([]);
  const [activeSheet, setActiveSheet] = useState("Baseline");
  const [source, setSource] = useState<"reference" | "extracted">("reference");
  const [rows, setRows] = useState<{ row_index: number; data: Record<string, unknown>; service_or_component?: string; accuracy?: number; status?: string; source_files?: string[] }[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [filterOptions, setFilterOptions] = useState<{
    carriers: string[]; service_types: string[]; charge_types: string[];
    scu_codes: string[]; statuses: string[];
  }>({ carriers: [], service_types: [], charge_types: [], scu_codes: [], statuses: [] });
  const [sort, setSort] = useState<SortState>({ column: "", direction: "asc" });
  const [checklistItems, setChecklistItems] = useState<Record<string, string | null>[]>([]);
  const [checklistColumns, setChecklistColumns] = useState<string[]>([]);
  const [checklistLoading, setChecklistLoading] = useState(false);
  const [showAllColumns, setShowAllColumns] = useState(false);
  const [confidence, setConfidence] = useState<ConfidenceSummary | null>(null);
  const [confidenceExpanded, setConfidenceExpanded] = useState(true);
  const [reviewFilter, setReviewFilter] = useState<string>("");

  // Slider panel state
  const [selectedRowIndex, setSelectedRowIndex] = useState<number | null>(null);

  // Debounced search
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebounce(searchInput, 300);

  // Sync debounced search into filters
  useEffect(() => {
    setFilters((prev) => {
      if (prev.search === debouncedSearch) return prev;
      return { ...prev, search: debouncedSearch };
    });
    setPage(1);
  }, [debouncedSearch]);

  // Load sheets when source changes
  useEffect(() => {
    api.getInventorySheets(projectId, source).then((d) => {
      const loadedSheets = d.sheets || [];
      setSheets(loadedSheets);
      const sheetNames = loadedSheets.map((s: SheetInfo) => s.name);
      if (!sheetNames.includes(activeSheet)) {
        setActiveSheet("Baseline");
      }
    }).catch(() => {});
    api.getInventoryFilters(projectId, source).then(setFilterOptions).catch(() => {});
    api.getConfidenceSummary(projectId, source).then(setConfidence).catch(() => {});
  }, [projectId, source]);

  // Load table data
  const loadData = useCallback(async () => {
    if (activeSheet.toLowerCase().includes("checklist")) return;

    setLoading(true);
    try {
      const params: Record<string, string> = {
        page: String(page), page_size: String(pageSize), source, sheet: activeSheet,
      };
      if (activeSheet === "Baseline") {
        if (filters.carrier) params.carrier = filters.carrier;
        if (filters.service_type) params.service_type = filters.service_type;
        if (filters.charge_type) params.charge_type = filters.charge_type;
        if (filters.scu_code) params.scu_code = filters.scu_code;
        if (filters.status) params.status = filters.status;
      }
      if (filters.search) params.search = filters.search;
      if (sort.column) { params.sort_by = sort.column; params.sort_dir = sort.direction; }
      const data = await api.getInventory(projectId, params);
      let resultRows = data.rows || [];

      // Client-side review filter (filter by accuracy-based status)
      if (reviewFilter) {
        resultRows = resultRows.filter((r: Record<string, unknown>) => {
          const rowStatus = r.status as string || "";
          if (reviewFilter === "completed") return rowStatus === "completed";
          if (reviewFilter === "need_review") return rowStatus === "need_review";
          if (reviewFilter === "critical") return rowStatus === "critical" || (r.accuracy as number || 0) < 70;
          return true;
        });
      }

      setRows(resultRows);
      setTotal(reviewFilter ? resultRows.length : (data.total || 0));
      if ((data as unknown as Record<string, unknown>).columns) {
        setColumns((data as unknown as Record<string, unknown>).columns as string[]);
      }
    } catch { setRows([]); setTotal(0); }
    setLoading(false);
  }, [projectId, activeSheet, filters, sort, page, pageSize, source, reviewFilter]);

  useEffect(() => { loadData(); }, [loadData]);

  // Load checklist when that tab is selected
  useEffect(() => {
    if (activeSheet.toLowerCase().includes("checklist")) {
      setChecklistLoading(true);
      api.getChecklist(projectId).then((d) => {
        setChecklistItems(d.items || []);
        setChecklistColumns(d.columns || []);
        setChecklistLoading(false);
      }).catch(() => setChecklistLoading(false));
    }
  }, [activeSheet, projectId]);

  // Helpers
  const getDisplayColumns = (): string[] => {
    if (showAllColumns || activeSheet !== "Baseline") return columns;
    const matched = PRIORITY_COLUMNS
      .map((p) => columns.find((c) => c.trim().toLowerCase().includes(p.toLowerCase())))
      .filter((c): c is string => !!c);
    return matched.length > 0 ? matched : columns.slice(0, 15);
  };
  const displayColumns = getDisplayColumns();

  function switchSheet(name: string) {
    setActiveSheet(name);
    setPage(1);
    setSort({ column: "", direction: "asc" });
    if (name !== "Baseline") {
      setFilters({ ...EMPTY_FILTERS, search: filters.search });
    }
  }

  function switchSource(newSource: "reference" | "extracted") {
    setSource(newSource);
    setPage(1);
    setFilters(EMPTY_FILTERS);
    setSearchInput("");
    setSort({ column: "", direction: "asc" });
  }

  function toggleSort(col: string) {
    setSort(sort.column === col
      ? { column: col, direction: sort.direction === "asc" ? "desc" : "asc" }
      : { column: col, direction: "asc" });
    setPage(1);
  }

  function updateFilter(key: keyof FilterState, value: string) {
    if (key === "search") {
      setSearchInput(value);
      return;
    }
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }

  function clearFilters() {
    setFilters(EMPTY_FILTERS);
    setSearchInput("");
    setSort({ column: "", direction: "asc" });
    setPage(1);
  }

  function updateChecklistItem(index: number, column: string, value: string) {
    const updated = [...checklistItems];
    updated[index] = { ...updated[index], [column]: value };
    setChecklistItems(updated);
  }

  async function saveChecklist() {
    await api.updateChecklist(projectId, checklistItems as Record<string, string>[]);
    alert("Checklist saved!");
  }

  const totalPages = Math.ceil(total / pageSize);
  const hasActiveFilters = Object.values(filters).some((v) => v !== "") || searchInput !== "";
  const isChecklist = activeSheet.toLowerCase().includes("checklist");

  // Accuracy helper
  function accuracyColor(acc: number): string {
    if (acc >= 90) return "text-emerald-400";
    if (acc >= 70) return "text-amber-400";
    return "text-red-400";
  }
  function accuracyBg(acc: number): string {
    if (acc >= 90) return "bg-emerald-500/10";
    if (acc >= 70) return "bg-amber-500/10";
    return "bg-red-500/10";
  }

  // === RENDER ===
  return (
    <div>
      {/* Row Detail Slider */}
      {selectedRowIndex !== null && (
        <RowDetailSlider
          projectId={projectId}
          rowIndex={selectedRowIndex}
          source={source}
          onClose={() => setSelectedRowIndex(null)}
          onSaved={() => {
            setSelectedRowIndex(null);
            loadData();
          }}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold">Inventory</h1>
          <p className="text-xs text-zinc-500 mt-1">
            {source === "reference" ? "Reference Data (NSS Inventory)" : "AI Extracted Data"}
            {!isChecklist && <> · {total.toLocaleString()} rows</>}
          </p>
        </div>
        <div className="flex gap-2 items-center">
          {/* Toggle Switch: Reference <-> Extracted */}
          <div className="flex items-center bg-zinc-800 rounded-lg border border-zinc-700 p-0.5">
            <button
              onClick={() => switchSource("reference")}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                source === "reference"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Reference
            </button>
            <button
              onClick={() => switchSource("extracted")}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                source === "extracted"
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Extracted
            </button>
          </div>
          {activeSheet === "Baseline" && !isChecklist && (
            <button
              onClick={() => setShowAllColumns(!showAllColumns)}
              className="px-3 py-1.5 bg-zinc-800 border border-zinc-700 hover:bg-zinc-700 rounded-lg text-xs"
            >
              {showAllColumns ? `Key Columns (${PRIORITY_COLUMNS.length})` : `All ${columns.length} Columns`}
            </button>
          )}
          <a
            href={`http://127.0.0.1:8000/api/projects/${projectId}/inventory/export?source=${source}`}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm"
            download
          >
            Export
          </a>
        </div>
      </div>

      {/* Data Verification Dashboard — Collapsible Accordion */}
      {confidence && confidence.total_rows > 0 && activeSheet === "Baseline" && (
        <div className="mb-4">
          {/* Accordion Header — always visible */}
          <button
            onClick={() => setConfidenceExpanded(!confidenceExpanded)}
            className="w-full flex items-center justify-between px-4 py-2.5 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-colors mb-2"
          >
            <div className="flex items-center gap-4">
              <span className="text-sm font-medium text-zinc-300">Data Verification</span>
              {/* Inline mini-stats — always visible even when collapsed */}
              <div className="flex items-center gap-3 text-xs">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-emerald-400 font-mono">{confidence.high.toLocaleString()}</span>
                  <span className="text-zinc-500">({confidence.high_pct}%)</span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  <span className="text-amber-400 font-mono">{confidence.medium.toLocaleString()}</span>
                  <span className="text-zinc-500">({confidence.medium_pct}%)</span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  <span className="text-red-400 font-mono">{confidence.needs_review.toLocaleString()}</span>
                  <span className="text-zinc-500">({confidence.needs_review_pct}%)</span>
                </span>
              </div>
            </div>
            <span className={`text-zinc-500 transition-transform ${confidenceExpanded ? "rotate-180" : ""}`}>▼</span>
          </button>

          {/* Accordion Body — collapsible */}
          {confidenceExpanded && (
            <div className="space-y-3">
              {/* Confidence Cards — compact */}
              <div className="grid grid-cols-3 gap-2">
                <button onClick={() => { setReviewFilter(reviewFilter === "completed" ? "" : "completed"); setPage(1); }}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    reviewFilter === "completed" ? "border-emerald-500/50 bg-emerald-950/30 ring-1 ring-emerald-500/20" : "border-emerald-500/20 bg-emerald-950/10 hover:border-emerald-500/30"
                  }`}>
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="w-4 h-4 rounded-full bg-emerald-500/20 flex items-center justify-center text-[9px] text-emerald-400">✓</span>
                    <span className="text-[10px] font-semibold text-emerald-400 uppercase">High (90%+)</span>
                  </div>
                  <p className="text-lg font-bold text-emerald-300">{confidence.high.toLocaleString()}</p>
                  <div className="w-full bg-emerald-900/30 rounded-full h-1 mt-1">
                    <div className="bg-emerald-500 h-1 rounded-full" style={{ width: `${confidence.high_pct}%` }} />
                  </div>
                </button>

                <button onClick={() => { setReviewFilter(reviewFilter === "need_review" ? "" : "need_review"); setPage(1); }}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    reviewFilter === "need_review" ? "border-amber-500/50 bg-amber-950/30 ring-1 ring-amber-500/20" : "border-amber-500/20 bg-amber-950/10 hover:border-amber-500/30"
                  }`}>
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="w-4 h-4 rounded-full bg-amber-500/20 flex items-center justify-center text-[9px] text-amber-400">!</span>
                    <span className="text-[10px] font-semibold text-amber-400 uppercase">Medium (70-89%)</span>
                  </div>
                  <p className="text-lg font-bold text-amber-300">{confidence.medium.toLocaleString()}</p>
                  <div className="w-full bg-amber-900/30 rounded-full h-1 mt-1">
                    <div className="bg-amber-500 h-1 rounded-full" style={{ width: `${confidence.medium_pct}%` }} />
                  </div>
                </button>

                <button onClick={() => { setReviewFilter(reviewFilter === "critical" ? "" : "critical"); setPage(1); }}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    reviewFilter === "critical" ? "border-red-500/50 bg-red-950/30 ring-1 ring-red-500/20" : "border-red-500/20 bg-red-950/10 hover:border-red-500/30"
                  }`}>
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="w-4 h-4 rounded-full bg-red-500/20 flex items-center justify-center text-[9px] text-red-400">✕</span>
                    <span className="text-[10px] font-semibold text-red-400 uppercase">Review (&lt;70%)</span>
                  </div>
                  <p className="text-lg font-bold text-red-300">{confidence.needs_review.toLocaleString()}</p>
                  <div className="w-full bg-red-900/30 rounded-full h-1 mt-1">
                    <div className="bg-red-500 h-1 rounded-full" style={{ width: `${confidence.needs_review_pct}%` }} />
                  </div>
                </button>
              </div>

              {/* Data Source Table — compact */}
              {confidence.extraction_methods.length > 0 && (
                <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-zinc-800 text-zinc-500 uppercase text-[10px]">
                        <th className="text-left py-1.5 px-3">Carrier</th>
                        <th className="text-right py-1.5 px-3">Rows</th>
                        <th className="text-right py-1.5 px-3">Spend</th>
                        <th className="text-right py-1.5 px-3">Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {confidence.extraction_methods.map((m) => (
                        <tr key={m.carrier} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                          <td className="py-1 px-3 text-zinc-300">{m.carrier}</td>
                          <td className="text-right py-1 px-3 text-zinc-400 font-mono">{m.rows.toLocaleString()}</td>
                          <td className="text-right py-1 px-3 text-zinc-400 font-mono">${m.mrc.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                          <td className="text-right py-1 px-3 font-mono">
                            <span className={m.avg_confidence >= 90 ? "text-emerald-400" : m.avg_confidence >= 70 ? "text-amber-400" : "text-red-400"}>
                              {m.avg_confidence}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Review filter indicator */}
          {reviewFilter && (
            <div className="flex items-center gap-2 mt-2">
              <span className="text-xs text-zinc-400">Filtering:</span>
              <Badge className={STATUS_CONFIG[reviewFilter]?.cls || "bg-zinc-700 text-zinc-300"}>
                {STATUS_CONFIG[reviewFilter]?.label || reviewFilter}
              </Badge>
              <button onClick={() => { setReviewFilter(""); setPage(1); }} className="text-xs text-zinc-500 hover:text-zinc-300">✕ Clear</button>
            </div>
          )}
        </div>
      )}

      {/* Sheet Tabs */}
      <div className="flex gap-1 mb-4 overflow-x-auto pb-2 border-b border-zinc-800">
        {sheets.map((s) => {
          const isActive = activeSheet === s.name;
          const isChecklistTab = s.name.toLowerCase().includes("checklist");
          return (
            <button
              key={s.name}
              onClick={() => switchSheet(s.name)}
              className={`px-3 py-1.5 text-xs rounded-t-lg whitespace-nowrap transition-colors ${
                isActive
                  ? isChecklistTab ? "bg-emerald-600 text-white" : "bg-blue-600 text-white"
                  : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
              }`}
            >
              {s.name.trim()}
              <span className="ml-1 text-[10px] opacity-60">({s.rows})</span>
            </button>
          );
        })}
      </div>

      {/* === CHECKLIST VIEW === */}
      {isChecklist && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base">QA Checklist</CardTitle>
              <p className="text-xs text-zinc-500 mt-1">{checklistItems.length} items · Set each to Yes / No / N/A</p>
            </div>
            <button
              onClick={saveChecklist}
              className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-sm font-medium"
            >
              Save Checklist
            </button>
          </CardHeader>
          <CardContent>
            {checklistLoading ? (
              <div className="text-zinc-400 text-center py-8">Loading checklist...</div>
            ) : checklistItems.length === 0 ? (
              <div className="text-zinc-500 text-center py-8">No checklist items found.</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-700">
                    <th className="text-left py-2 px-3 text-zinc-500 w-8">#</th>
                    {checklistColumns.map((col) => (
                      <th key={col} className="text-left py-2 px-3 text-zinc-400 font-medium">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {checklistItems.map((item, i) => (
                    <tr key={i} className="border-b border-zinc-800 hover:bg-zinc-800/50">
                      <td className="py-2 px-3 text-zinc-600 text-xs">{i + 1}</td>
                      {checklistColumns.map((col, j) => (
                        <td key={col} className="py-2 px-3">
                          {j === 0 ? (
                            <span className="text-zinc-200 text-sm">{item[col]}</span>
                          ) : (
                            <select
                              value={item[col] || ""}
                              onChange={(e) => updateChecklistItem(i, col, e.target.value)}
                              className={`bg-zinc-800 border rounded px-2 py-1 text-xs min-w-[70px] ${
                                item[col] === "Yes" ? "border-emerald-600 text-emerald-400" :
                                item[col] === "No" ? "border-red-600 text-red-400" :
                                item[col] === "N/A" ? "border-zinc-600 text-zinc-400" :
                                "border-zinc-700 text-zinc-300"
                              }`}
                            >
                              <option value="">--</option>
                              <option value="Yes">Yes</option>
                              <option value="No">No</option>
                              <option value="N/A">N/A</option>
                            </select>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      {/* === TABLE VIEW (non-checklist sheets) === */}
      {!isChecklist && (
        <>
          {/* Filters -- only for Baseline */}
          {activeSheet === "Baseline" && (
            <div className="mb-4">
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">Search</label>
                  <Input
                    placeholder="Search all columns..."
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    className="bg-zinc-800 border-zinc-700 text-sm h-9"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">Carrier</label>
                  <select value={filters.carrier} onChange={(e) => updateFilter("carrier", e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm h-9">
                    <option value="">All Carriers</option>
                    {filterOptions.carriers.map((v) => <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">Service Type</label>
                  <select value={filters.service_type} onChange={(e) => updateFilter("service_type", e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm h-9">
                    <option value="">All Types</option>
                    {filterOptions.service_types.map((v) => <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">Status</label>
                  <select value={filters.status} onChange={(e) => updateFilter("status", e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm h-9">
                    <option value="">All Statuses</option>
                    {filterOptions.statuses.map((v) => <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">S/C/U Type</label>
                  <select value={filters.scu_code} onChange={(e) => updateFilter("scu_code", e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm h-9">
                    <option value="">All</option>
                    {filterOptions.scu_codes.map((v) => <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">Charge Type</label>
                  <select value={filters.charge_type} onChange={(e) => updateFilter("charge_type", e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-sm h-9">
                    <option value="">All</option>
                    {filterOptions.charge_types.map((v) => <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
              </div>
              {hasActiveFilters && (
                <button onClick={clearFilters} className="mt-2 text-xs text-blue-400 hover:text-blue-300">
                  Clear all filters
                </button>
              )}
            </div>
          )}

          {/* Search for non-Baseline sheets */}
          {activeSheet !== "Baseline" && (
            <div className="mb-4 max-w-sm">
              <Input
                placeholder={`Search ${activeSheet}...`}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="bg-zinc-800 border-zinc-700 text-sm h-9"
              />
            </div>
          )}

          {/* Data Table */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-0">
              {loading ? (
                <div className="p-8 text-center text-zinc-400">Loading data...</div>
              ) : rows.length === 0 ? (
                <div className="p-12 text-center">
                  <p className="text-zinc-500 text-lg mb-2">No records found</p>
                  {hasActiveFilters && (
                    <button onClick={clearFilters} className="text-sm text-blue-400 hover:text-blue-300">
                      Clear filters
                    </button>
                  )}
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-zinc-900">
                      <tr className="border-b border-zinc-700">
                        <th className="text-left py-2 px-2 text-zinc-500 font-medium w-10">#</th>
                        {/* Accuracy column -- first visible */}
                        {activeSheet === "Baseline" && (
                          <th className="text-left py-2 px-2 text-zinc-400 font-medium whitespace-nowrap w-16">
                            Accuracy
                          </th>
                        )}
                        {/* Review Status column */}
                        {activeSheet === "Baseline" && (
                          <th className="text-left py-2 px-2 text-zinc-400 font-medium whitespace-nowrap w-24">
                            Review
                          </th>
                        )}
                        {displayColumns.map((col) => (
                          <th
                            key={col}
                            onClick={() => toggleSort(col)}
                            className="text-left py-2 px-2 text-zinc-400 font-medium cursor-pointer hover:text-white select-none whitespace-nowrap"
                          >
                            <span className="flex items-center gap-1">
                              {col.length > 22 ? col.substring(0, 20) + ".." : col}
                              {sort.column === col ? (
                                <span className="text-blue-400 text-sm">{sort.direction === "asc" ? "↑" : "↓"}</span>
                              ) : (
                                <span className="text-zinc-700 text-sm">↕</span>
                              )}
                            </span>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, i) => {
                        const scu = row.service_or_component
                          || String(row.data["Service or Component"] || row.data["Service or Component "] || "").trim();
                        const rowBg = scu === "S" ? "bg-blue-950/30 border-l-2 border-l-blue-500"
                          : scu.startsWith("T") ? "bg-amber-950/20 border-l-2 border-l-amber-500" : "";
                        const acc = row.accuracy ?? 0;
                        const rowStatus = row.status || "in_progress";
                        const sCfg = STATUS_CONFIG[rowStatus] || STATUS_CONFIG.in_progress;
                        return (
                          <tr
                            key={row.row_index}
                            onClick={() => setSelectedRowIndex(row.row_index)}
                            className={`border-b border-zinc-800/50 hover:bg-zinc-800/50 cursor-pointer ${rowBg}`}
                          >
                            <td className="py-1.5 px-2 text-zinc-600">{(page - 1) * pageSize + i + 1}</td>
                            {/* Accuracy cell */}
                            {activeSheet === "Baseline" && (
                              <td className="py-1.5 px-2">
                                <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-mono font-medium ${accuracyColor(acc)} ${accuracyBg(acc)}`}>
                                  {acc}%
                                </span>
                              </td>
                            )}
                            {/* Review Status cell */}
                            {activeSheet === "Baseline" && (
                              <td className="py-1.5 px-2">
                                <Badge className={`${sCfg.cls} text-[10px] border px-1.5 py-0.5`}>{sCfg.label}</Badge>
                              </td>
                            )}
                            {displayColumns.map((col) => {
                              const val = row.data[col];
                              const display = val === null || val === undefined ? "" : String(val);
                              let cls = "text-zinc-300";
                              if (col.toLowerCase().includes("monthly recurring") && val) {
                                const num = Number(val);
                                cls = num > 0 ? "text-emerald-400 font-mono" : num < 0 ? "text-red-400 font-mono" : "text-zinc-500 font-mono";
                              }
                              if (col.toLowerCase() === "status") {
                                cls = display.includes("Completed") ? "text-emerald-400"
                                  : display.includes("Pending") ? "text-amber-400" : "text-zinc-300";
                              }
                              return (
                                <td key={col} className={`py-1.5 px-2 ${cls} truncate max-w-[200px]`} title={display}>
                                  {display}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-800">
                  <span className="text-xs text-zinc-400">
                    {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total.toLocaleString()}
                  </span>
                  <div className="flex gap-1">
                    <button onClick={() => setPage(1)} disabled={page <= 1}
                      className="px-2 py-1 text-xs bg-zinc-800 rounded disabled:opacity-30 hover:bg-zinc-700">First</button>
                    <button onClick={() => setPage(page - 1)} disabled={page <= 1}
                      className="px-2 py-1 text-xs bg-zinc-800 rounded disabled:opacity-30 hover:bg-zinc-700">Prev</button>
                    <span className="px-3 py-1 text-xs text-zinc-400">Page {page}/{totalPages}</span>
                    <button onClick={() => setPage(page + 1)} disabled={page >= totalPages}
                      className="px-2 py-1 text-xs bg-zinc-800 rounded disabled:opacity-30 hover:bg-zinc-700">Next</button>
                    <button onClick={() => setPage(totalPages)} disabled={page >= totalPages}
                      className="px-2 py-1 text-xs bg-zinc-800 rounded disabled:opacity-30 hover:bg-zinc-700">Last</button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
