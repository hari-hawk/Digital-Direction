"""Documents router: file browser, upload, preview."""
import io
import mimetypes
import zipfile
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, Response

from services.persistence import save_uploaded_file

from services.file_service import scan_project_files, get_all_documents_flat

# Ensure PDF MIME type is registered
mimetypes.add_type("application/pdf", ".pdf")

router = APIRouter(tags=["documents"])


@router.get("/projects/{project_id}/documents")
async def list_documents(project_id: str, request: Request, carrier: str = None, doc_type: str = None):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    carriers = scan_project_files(proj["input_dir"])

    if carrier:
        carriers = {k: v for k, v in carriers.items() if carrier.lower() in k.lower()}

    # Build response
    result = []
    for cname, cd in carriers.items():
        entry = {
            "carrier": cname,
            "invoices": [d.dict() for d in cd.invoices],
            "contracts": [d.dict() for d in cd.contracts],
            "carrier_reports": [d.dict() for d in cd.carrier_reports],
            "csrs": [d.dict() for d in cd.csrs],
            "total_files": len(cd.invoices) + len(cd.contracts) + len(cd.carrier_reports) + len(cd.csrs),
        }

        if doc_type:
            type_map = {
                "invoice": "invoices",
                "contract": "contracts",
                "carrier_report": "carrier_reports",
                "csr": "csrs",
            }
            key = type_map.get(doc_type)
            if key:
                entry["total_files"] = len(entry[key])

        result.append(entry)

    return sorted(result, key=lambda x: x["total_files"], reverse=True)


@router.get("/projects/{project_id}/documents/carriers")
async def list_carriers(project_id: str, request: Request):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return []
    carriers = scan_project_files(proj["input_dir"])
    return [
        {
            "name": cname,
            "invoices": len(cd.invoices),
            "contracts": len(cd.contracts),
            "carrier_reports": len(cd.carrier_reports),
            "csrs": len(cd.csrs),
            "total": len(cd.invoices) + len(cd.contracts) + len(cd.carrier_reports) + len(cd.csrs),
        }
        for cname, cd in sorted(carriers.items())
    ]


@router.get("/projects/{project_id}/documents/file")
async def get_file(
    project_id: str,
    file_path: str,
    request: Request,
    mode: str = "inline",  # "inline" for preview, "download" for download
):
    """Serve a file for preview (inline) or download (attachment)."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return {"error": "File not found"}

    # Security: ensure file is within allowed directories
    proj = request.app.state.projects.get(project_id)
    if proj:
        input_dir = Path(proj["input_dir"])
        # Allow files from input dir or its parent (Claude dir may have shared files)
        allowed = False
        for base in [input_dir, input_dir.parent.parent]:
            try:
                path.resolve().relative_to(base.resolve())
                allowed = True
                break
            except ValueError:
                continue
        if not allowed:
            return {"error": "Access denied"}

    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        suffix = path.suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".csv": "text/csv",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".msg": "application/vnd.ms-outlook",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        mime_type = mime_map.get(suffix, "application/octet-stream")

    # Read file and serve with correct headers
    content = path.read_bytes()

    if mode == "download":
        # Force download with attachment disposition
        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{path.name}"',
                "Content-Length": str(len(content)),
            },
        )
    else:
        # Inline display — browser renders PDF/images natively
        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'inline; filename="{path.name}"',
                "Content-Length": str(len(content)),
                "Cache-Control": "public, max-age=3600",
            },
        )


@router.post("/projects/{project_id}/documents/upload")
async def upload_file(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    carrier: str = Form(...),
    doc_type: str = Form(...),  # invoice, contract, carrier_report, csr
):
    """Upload a file to a specific carrier/type folder."""
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    # Map doc_type to folder name
    type_folder_map = {
        "invoice": "Invoices",
        "contract": "Contracts",
        "carrier_report": "Carrier Reports, Portal Data, ETC",
        "csr": "CSRs",
    }
    folder_name = type_folder_map.get(doc_type)
    if not folder_name:
        return {"error": f"Invalid doc_type: {doc_type}. Use: invoice, contract, carrier_report, csr"}

    # Create carrier subfolder
    target_dir = Path(proj["input_dir"]) / folder_name / carrier
    target_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    target_path = target_dir / file.filename
    content = await file.read()
    with open(target_path, "wb") as f:
        f.write(content)

    return {
        "status": "uploaded",
        "file": file.filename,
        "carrier": carrier,
        "doc_type": doc_type,
        "path": str(target_path),
        "size_bytes": len(content),
    }


def _detect_doc_type(file_path: str) -> tuple[str, str]:
    """Auto-detect document type and carrier from file path or name.
    Returns (doc_type_folder, carrier_name)."""

    path_lower = file_path.lower()
    name = Path(file_path).name.lower()

    # Detect type from folder path keywords
    type_keywords = {
        "Invoices": ["invoice", "bill", "_bill"],
        "Contracts": ["contract", "agreement", "signed", "quote"],
        "Carrier Reports, Portal Data, ETC": ["carrier report", "portal", "inventory by", "report", "spreadsheet", "comms"],
        "CSRs": ["csr", "customer service record"],
    }

    detected_type = "Invoices"  # default
    for folder_name, keywords in type_keywords.items():
        for kw in keywords:
            if kw in path_lower:
                detected_type = folder_name
                break

    # Detect carrier from filename patterns
    common_carriers = [
        "Charter Communications", "Windstream", "Granite", "Peerless",
        "Consolidated", "Spectrotel", "Frontier", "Verizon", "Nextiva",
        "Delhi Telephone", "Champlain", "TDS Telecom", "StateTel",
        "Directv", "BCN Telecom", "WVT Fiber", "Lumen", "AT&T",
        "Comcast", "Cox", "CenturyLink",
    ]
    detected_carrier = "Unknown"
    for carrier in common_carriers:
        if carrier.lower() in name or carrier.lower().replace(" ", "_") in name:
            detected_carrier = carrier
            break

    # Also try extracting carrier from path (folder-based organization)
    if detected_carrier == "Unknown":
        parts = Path(file_path).parts
        for part in parts:
            for carrier in common_carriers:
                if carrier.lower() in part.lower():
                    detected_carrier = carrier
                    break

    return detected_type, detected_carrier


@router.post("/projects/{project_id}/documents/upload-bulk")
async def upload_bulk(
    project_id: str,
    request: Request,
    files: List[UploadFile] = File(...),
    carrier: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
):
    """Bulk upload: multiple files, auto-detect type/carrier. Also handles zip files."""
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    type_folder_map = {
        "invoice": "Invoices",
        "contract": "Contracts",
        "carrier_report": "Carrier Reports, Portal Data, ETC",
        "csr": "CSRs",
    }

    results = []

    for file in files:
        content = await file.read()

        # Handle ZIP files
        if file.filename and file.filename.lower().endswith(".zip"):
            try:
                zf = zipfile.ZipFile(io.BytesIO(content))
                for zip_entry in zf.namelist():
                    # Skip directories and hidden files
                    if zip_entry.endswith("/") or "/." in zip_entry or zip_entry.startswith("__MACOSX"):
                        continue

                    entry_name = Path(zip_entry).name
                    if not entry_name:
                        continue

                    # Auto-detect from zip path
                    auto_type, auto_carrier = _detect_doc_type(zip_entry)
                    use_type = type_folder_map.get(doc_type, auto_type) if doc_type else auto_type
                    use_carrier = carrier if carrier else auto_carrier

                    target_dir = Path(proj["input_dir"]) / use_type / use_carrier
                    target_dir.mkdir(parents=True, exist_ok=True)
                    target_path = target_dir / entry_name

                    entry_data = zf.read(zip_entry)
                    with open(target_path, "wb") as f:
                        f.write(entry_data)

                    # Record in database
                    save_uploaded_file(project_id, use_carrier, use_type, entry_name, str(target_path), len(entry_data))

                    results.append({
                        "file": entry_name,
                        "carrier": use_carrier,
                        "doc_type": use_type,
                        "source": f"zip:{file.filename}",
                        "status": "uploaded",
                    })
                zf.close()
            except zipfile.BadZipFile:
                results.append({"file": file.filename, "status": "error", "error": "Invalid ZIP file"})
        else:
            # Regular file — auto-detect or use provided values
            auto_type, auto_carrier = _detect_doc_type(file.filename or "unknown")
            use_type = type_folder_map.get(doc_type, auto_type) if doc_type else auto_type
            use_carrier = carrier if carrier else auto_carrier

            target_dir = Path(proj["input_dir"]) / use_type / use_carrier
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / (file.filename or "unknown")

            with open(target_path, "wb") as f:
                f.write(content)

            # Record in database
            save_uploaded_file(project_id, use_carrier, use_type, file.filename or "unknown", str(target_path), len(content))

            results.append({
                "file": file.filename,
                "carrier": use_carrier,
                "doc_type": use_type,
                "size_bytes": len(content),
                "status": "uploaded",
            })

    success_count = sum(1 for r in results if r["status"] == "uploaded")
    return {
        "status": "completed",
        "total_files": len(results),
        "success": success_count,
        "errors": len(results) - success_count,
        "results": results,
    }


@router.get("/projects/{project_id}/documents/preview-excel")
async def preview_excel(project_id: str, file_path: str, request: Request):
    """Return first 100 rows of an Excel/CSV file as JSON for preview."""
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return {"error": "File not found"}

    # Security check
    if proj:
        input_dir = Path(proj["input_dir"])
        try:
            path.resolve().relative_to(input_dir.resolve())
        except ValueError:
            # Also allow files from the parent Claude directory
            pass

    try:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(path, nrows=100)
        elif suffix in (".xlsx", ".xls"):
            df = pd.read_excel(path, nrows=100)
        else:
            return {"error": f"Unsupported format: {suffix}"}

        headers = [str(c) for c in df.columns]
        rows = []
        for _, row in df.iterrows():
            rows.append([str(v) if pd.notna(v) else "" for v in row])

        return {"headers": headers, "rows": rows}
    except Exception as e:
        return {"error": f"Failed to read file: {e}"}
