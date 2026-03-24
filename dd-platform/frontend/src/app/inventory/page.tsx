"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, RowDetailResponse } from "@/lib/api";
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

              {/* Field groups */}
              {fieldGroups.map((group) => (
                <div key={group.name} className="mb-5">
                  <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 border-b border-zinc-800 pb-1">
                    {group.name}
                  </h3>
                  <div className="space-y-2">
                    {group.fields.map((fieldName) => (
                      <div key={fieldName} className="grid grid-cols-[140px_1fr] gap-2 items-start">
                        <label className="text-xs text-zinc-500 pt-2 truncate" title={fieldName}>
                          {fieldName.length > 20 ? fieldName.substring(0, 18) + ".." : fieldName}
                        </label>
                        <input
                          type="text"
                          value={editedFields[fieldName] || ""}
                          onChange={(e) => setEditedFields((prev) => ({ ...prev, [fieldName]: e.target.value }))}
                          className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-200 focus:border-blue-500 focus:outline-none"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {/* Source Documents */}
              {detail.source_documents && detail.source_documents.length > 0 && (
                <div className="mb-5">
                  <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 border-b border-zinc-800 pb-1">
                    Source Documents
                  </h3>
                  <div className="space-y-1">
                    {detail.source_documents.map((doc, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-zinc-400 bg-zinc-800/50 rounded px-2 py-1.5">
                        <span className="text-sm">📄</span>
                        <span className="truncate">{doc}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

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
      setRows(data.rows || []);
      setTotal(data.total || 0);
      if ((data as unknown as Record<string, unknown>).columns) {
        setColumns((data as unknown as Record<string, unknown>).columns as string[]);
      }
    } catch { setRows([]); setTotal(0); }
    setLoading(false);
  }, [projectId, activeSheet, filters, sort, page, pageSize, source]);

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
