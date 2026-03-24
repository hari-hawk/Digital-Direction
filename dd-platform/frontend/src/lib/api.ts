const API_BASE = "http://127.0.0.1:8000/api";

async function fetchApi<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function postApi<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface ProjectStats {
  total_mrc: number;
  carriers: number;
  services: number;
  total_rows: number;
  total_documents: number;
  carrier_list: string[];
}

export interface CarrierSpend {
  carrier: string;
  mrc: number;
  row_count: number;
  service_count: number;
}

export interface ServiceTypeCount {
  service_type: string;
  count: number;
  mrc: number;
}

export interface CarrierDocs {
  carrier: string;
  invoices: DocInfo[];
  contracts: DocInfo[];
  carrier_reports: DocInfo[];
  csrs: DocInfo[];
  total_files: number;
}

export interface DocInfo {
  name: string;
  path: string;
  carrier: string;
  doc_type: string;
  format: string;
  size_bytes: number;
}

export interface CarrierSummary {
  name: string;
  invoices: number;
  contracts: number;
  carrier_reports: number;
  csrs: number;
  total: number;
}

export interface InventoryResponse {
  rows: InventoryRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface InventoryRow {
  row_index: number;
  data: Record<string, unknown>;
  service_or_component: string;
}

export interface ExtractionResult {
  status: string;
  summary: Record<string, unknown>;
  stdout: string;
  stderr: string;
}

export interface InsightFlag {
  category: string;
  severity: string;
  count: number;
  description: string;
  details: string[];
}

export interface CostBreakdown {
  carrier: string;
  mrc: number;
  row_count: number;
  service_count: number;
  avg_mrc_per_service: number;
}

export const api = {
  getStats: (projectId: string) => fetchApi<ProjectStats>(`/projects/${projectId}/stats`),
  getSpendByCarrier: (projectId: string) => fetchApi<CarrierSpend[]>(`/projects/${projectId}/spend-by-carrier`),
  getServiceTypes: (projectId: string) => fetchApi<ServiceTypeCount[]>(`/projects/${projectId}/service-types`),
  getDocuments: (projectId: string) => fetchApi<CarrierDocs[]>(`/projects/${projectId}/documents`),
  getCarriers: (projectId: string) => fetchApi<CarrierSummary[]>(`/projects/${projectId}/documents/carriers`),
  getInventory: (projectId: string, params: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString();
    return fetchApi<InventoryResponse>(`/projects/${projectId}/inventory?${qs}`);
  },
  getInventoryColumns: (projectId: string, sheet?: string) => {
    const qs = sheet ? `?sheet=${encodeURIComponent(sheet)}` : "";
    return fetchApi<{ name: string; index: number }[]>(`/projects/${projectId}/inventory/columns${qs}`);
  },
  getInventorySheets: (projectId: string, source?: string) =>
    fetchApi<{ sheets: { name: string; rows: number; cols: number }[] }>(
      `/projects/${projectId}/inventory/sheets?source=${source || "reference"}`
    ),
  getInventoryFilters: (projectId: string, source?: string) =>
    fetchApi<{
      carriers: string[];
      service_types: string[];
      charge_types: string[];
      scu_codes: string[];
      statuses: string[];
    }>(`/projects/${projectId}/inventory/filters?source=${source || "reference"}`),
  getChecklist: (projectId: string) =>
    fetchApi<{ items: Record<string, string>[]; columns: string[] }>(`/projects/${projectId}/inventory/checklist`),
  updateChecklist: (projectId: string, items: Record<string, string>[]) =>
    postApi<{ status: string }>(`/projects/${projectId}/inventory/checklist`, { items }),
  runExtraction: (projectId: string, carrierKey: string, apiKey?: string) =>
    postApi<ExtractionResult>(`/projects/${projectId}/extract`, { carrier_key: carrierKey, api_key: apiKey }),
  getExtractionStatus: (projectId: string, carrierKey: string) =>
    fetchApi<Record<string, unknown>>(`/projects/${projectId}/extraction/status?carrier_key=${carrierKey}`),
  getExtractionCarriers: (projectId: string) =>
    fetchApi<{ key: string; name: string; tier: number; status: string }[]>(`/projects/${projectId}/extraction/carriers`),
  getInsights: (projectId: string) => fetchApi<InsightFlag[]>(`/projects/${projectId}/insights`),
  getCostBreakdown: (projectId: string) => fetchApi<CostBreakdown[]>(`/projects/${projectId}/insights/cost-breakdown`),

  // Projects
  getProjects: () => fetchApi<{ id: string; name: string }[]>("/projects"),
  createProject: (id: string, name: string) => postApi<{ id: string; name: string }>("/projects", { id, name }),

  // Upload - single file
  uploadFile: async (projectId: string, file: File, carrier: string, docType: string) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("carrier", carrier);
    formData.append("doc_type", docType);
    const res = await fetch(`${API_BASE}/projects/${projectId}/documents/upload`, {
      method: "POST",
      body: formData,
    });
    return res.json();
  },

  // Upload - bulk (multiple files, zip, auto-detect)
  uploadBulk: async (projectId: string, files: File[], carrier?: string, docType?: string) => {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }
    if (carrier) formData.append("carrier", carrier);
    if (docType) formData.append("doc_type", docType);
    const res = await fetch(`${API_BASE}/projects/${projectId}/documents/upload-bulk`, {
      method: "POST",
      body: formData,
    });
    return res.json();
  },
};
