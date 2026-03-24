"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useProjectId } from "@/hooks/useProjectId";

interface UploadResult {
  file: string;
  carrier: string;
  doc_type: string;
  status: string;
  source?: string;
  error?: string;
  size_bytes?: number;
}

export default function UploadPage() {
  const projectId = useProjectId();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  // Upload state
  const [files, setFiles] = useState<File[]>([]);
  const [carrier, setCarrier] = useState("");
  const [docType, setDocType] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [dragActive, setDragActive] = useState(false);

  // Handle file selection
  function handleFiles(fileList: FileList | null) {
    if (!fileList) return;
    const arr = Array.from(fileList);
    setFiles((prev) => [...prev, ...arr]);
  }

  // Handle drag & drop
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const items = e.dataTransfer.items;
    const droppedFiles: File[] = [];

    if (items) {
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === "file") {
          const file = item.getAsFile();
          if (file) droppedFiles.push(file);
        }
      }
    } else if (e.dataTransfer.files) {
      for (let i = 0; i < e.dataTransfer.files.length; i++) {
        droppedFiles.push(e.dataTransfer.files[i]);
      }
    }

    if (droppedFiles.length > 0) {
      setFiles((prev) => [...prev, ...droppedFiles]);
    }
  }, []);

  // Remove a file from the list
  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  // Clear all
  function clearAll() {
    setFiles([]);
    setResults([]);
    setCarrier("");
    setDocType("");
  }

  // Upload
  async function handleUpload() {
    if (files.length === 0) return;
    setUploading(true);
    setProgress(0);
    setResults([]);

    const allResults: UploadResult[] = [];

    // Upload files individually for better progress tracking
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setProgress(Math.round(((i) / files.length) * 100));

      try {
        const res = await api.uploadBulk(
          projectId,
          [file],
          carrier || undefined,
          docType || undefined,
        );
        if (res.results) {
          allResults.push(...res.results);
        }
      } catch (e) {
        allResults.push({
          file: file.name,
          carrier: carrier || "Unknown",
          doc_type: docType || "auto",
          status: "error",
          error: String(e),
        });
      }

      // Update results as we go
      setResults([...allResults]);
    }

    setProgress(100);
    setFiles([]);
    setUploading(false);
  }

  // File size formatter
  function fmtSize(bytes: number): string {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  const totalSize = files.reduce((s, f) => s + f.size, 0);
  const zipCount = files.filter((f) => f.name.endsWith(".zip")).length;
  const successCount = results.filter((r) => r.status === "uploaded").length;
  const errorCount = results.filter((r) => r.status === "error").length;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Upload Documents</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Drop zone + file list */}
        <div className="lg:col-span-2 space-y-4">
          {/* Drop Zone */}
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-12 text-center transition-all cursor-pointer ${
              dragActive
                ? "border-blue-500 bg-blue-500/10"
                : "border-zinc-700 hover:border-zinc-500 bg-zinc-900/50"
            }`}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="text-4xl mb-3">📤</div>
            <p className="text-lg font-medium mb-2">
              Drop files or folders here
            </p>
            <p className="text-sm text-zinc-400 mb-4">
              Supports individual files, multiple files, ZIP archives, and folders
            </p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium"
              >
                Select Files
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); folderInputRef.current?.click(); }}
                className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-sm font-medium"
              >
                Select Folder
              </button>
            </div>

            {/* Hidden inputs — no accept filter to allow all file types including zip */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => handleFiles(e.target.files)}
            />
            <input
              ref={folderInputRef}
              type="file"
              // @ts-expect-error - webkitdirectory is valid but not in types
              webkitdirectory=""
              // @ts-expect-error
              directory=""
              multiple
              className="hidden"
              onChange={(e) => handleFiles(e.target.files)}
            />
          </div>

          {/* File Queue */}
          {files.length > 0 && (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader className="flex flex-row items-center justify-between py-3">
                <CardTitle className="text-sm text-zinc-400">
                  {files.length} file{files.length !== 1 ? "s" : ""} selected
                  <span className="ml-2 text-zinc-500">({fmtSize(totalSize)})</span>
                  {zipCount > 0 && (
                    <Badge className="ml-2 bg-amber-500/20 text-amber-300">{zipCount} ZIP</Badge>
                  )}
                </CardTitle>
                <button onClick={() => setFiles([])} className="text-xs text-zinc-500 hover:text-zinc-300">
                  Clear all
                </button>
              </CardHeader>
              <CardContent className="max-h-[300px] overflow-auto space-y-1">
                {files.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded bg-zinc-800/50 text-sm">
                    <span className="text-base">
                      {f.name.endsWith(".zip") ? "📦" : f.name.endsWith(".pdf") ? "📄" : "📊"}
                    </span>
                    <span className="flex-1 truncate">{f.name}</span>
                    <span className="text-xs text-zinc-500">{fmtSize(f.size)}</span>
                    <button onClick={() => removeFile(i)} className="text-zinc-600 hover:text-red-400 text-xs">✕</button>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Results */}
          {results.length > 0 && (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader className="py-3">
                <CardTitle className="text-sm">
                  Upload Results:
                  <span className="ml-2 text-emerald-400">{successCount} uploaded</span>
                  {errorCount > 0 && <span className="ml-2 text-red-400">{errorCount} failed</span>}
                </CardTitle>
              </CardHeader>
              <CardContent className="max-h-[300px] overflow-auto space-y-1">
                {results.map((r, i) => (
                  <div key={i} className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm ${
                    r.status === "uploaded" ? "bg-emerald-900/20" : "bg-red-900/20"
                  }`}>
                    <span>{r.status === "uploaded" ? "✅" : "❌"}</span>
                    <span className="flex-1 truncate">{r.file}</span>
                    <Badge className={r.status === "uploaded"
                      ? "bg-emerald-500/20 text-emerald-300"
                      : "bg-red-500/20 text-red-300"
                    }>
                      {r.doc_type || "auto"}
                    </Badge>
                    <span className="text-xs text-zinc-400">{r.carrier}</span>
                    {r.source && <span className="text-xs text-zinc-600">{r.source}</span>}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right: Options + Upload button */}
        <div className="space-y-4">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-sm text-zinc-400">Upload Options</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">
                  Carrier Name <span className="text-zinc-600">(optional — auto-detected)</span>
                </label>
                <Input
                  placeholder="e.g. Charter Communications"
                  value={carrier}
                  onChange={(e) => setCarrier(e.target.value)}
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">
                  Document Type <span className="text-zinc-600">(optional — auto-detected)</span>
                </label>
                <select
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm"
                >
                  <option value="">Auto-detect from filename</option>
                  <option value="invoice">Invoice</option>
                  <option value="contract">Contract</option>
                  <option value="carrier_report">Carrier Report</option>
                  <option value="csr">CSR</option>
                </select>
              </div>

              <div className="pt-2 border-t border-zinc-800">
                <p className="text-xs text-zinc-500 mb-3">
                  💡 Auto-detection reads filenames to identify type and carrier.
                  ZIP files are extracted automatically.
                  Folder uploads preserve structure.
                </p>
              </div>

              <button
                onClick={handleUpload}
                disabled={files.length === 0 || uploading}
                className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-700 disabled:text-zinc-500 rounded-lg text-sm font-medium transition-colors"
              >
                {uploading ? (
                  <span>Uploading... {progress}%</span>
                ) : (
                  <span>Upload {files.length} file{files.length !== 1 ? "s" : ""}</span>
                )}
              </button>

              {/* Progress bar */}
              {uploading && (
                <div className="w-full bg-zinc-800 rounded-full h-2 mt-2 overflow-hidden">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              )}

              {files.length > 0 && (
                <button
                  onClick={clearAll}
                  className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-xs text-zinc-400"
                >
                  Clear All
                </button>
              )}
            </CardContent>
          </Card>

          {/* Quick info */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="pt-4">
              <h3 className="text-xs font-medium text-zinc-400 mb-2">Supported Formats</h3>
              <div className="grid grid-cols-2 gap-1 text-xs text-zinc-500">
                <span>📄 PDF (invoices, contracts)</span>
                <span>📊 XLSX/XLS/CSV (reports)</span>
                <span>📦 ZIP (bulk upload)</span>
                <span>📁 Folders (drag or select)</span>
                <span>📧 MSG (emails)</span>
                <span>📝 DOCX (documents)</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
