from __future__ import annotations
"""Inventory router: read and filter inventory data with multi-sheet support."""
from pathlib import Path

import pandas as pd
import openpyxl
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from services.analytics_service import get_inventory_rows, load_inventory

router = APIRouter(tags=["inventory"])

# Cache for sheet data
_sheet_cache = {}  # type: dict


def _resolve_file(proj: dict, source: str) -> str:
    if source == "extracted":
        output_dir = Path(proj["output_dir"])
        output_files = sorted(output_dir.glob("*_inventory_output.xlsx"))
        return str(output_files[-1]) if output_files else proj["reference_file"]
    return proj["reference_file"]


def _load_all_sheets(file_path: str) -> dict:
    """Load all sheet names and metadata from Excel file."""
    if file_path in _sheet_cache:
        return _sheet_cache[file_path]

    path = Path(file_path)
    if not path.exists():
        return {"sheets": []}

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets = []
    for name in wb.sheetnames:
        ws = wb[name]
        sheets.append({
            "name": name.strip(),
            "rows": ws.max_row or 0,
            "cols": ws.max_column or 0,
        })
    wb.close()

    result = {"sheets": sheets}
    _sheet_cache[file_path] = result
    return result


def _load_sheet_data(file_path: str, sheet_name: str, header_row: int = None) -> pd.DataFrame:
    """Load specific sheet from Excel with correct header detection."""
    path = Path(file_path)
    if not path.exists():
        return pd.DataFrame()

    # Baseline uses header row 2 (0-indexed), others use 0
    if sheet_name.strip() == "Baseline":
        header_row = header_row if header_row is not None else 2
    elif sheet_name.strip() in ("Inactive Services", "Windstream Zero Cost Charge", "Migrated Accounts"):
        # These have a similar 3-row header structure
        header_row = header_row if header_row is not None else 0
    else:
        header_row = header_row if header_row is not None else 0

    df = pd.read_excel(path, sheet_name=sheet_name, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]
    return df


@router.get("/projects/{project_id}/inventory/sheets")
async def list_sheets(project_id: str, request: Request, source: str = "reference"):
    """List all sheets in the inventory file."""
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    file_path = _resolve_file(proj, source)
    return _load_all_sheets(file_path)


@router.get("/projects/{project_id}/inventory")
async def list_inventory(
    project_id: str,
    request: Request,
    carrier: str = None,
    service_type: str = None,
    charge_type: str = None,
    scu_code: str = None,
    status: str = None,
    search: str = None,
    sort_by: str = None,
    sort_dir: str = "asc",
    page: int = 1,
    page_size: int = 100,
    source: str = "reference",
    sheet: str = "Baseline",
):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    file_path = _resolve_file(proj, source)

    if sheet.strip() == "Baseline":
        return get_inventory_rows(
            file_path=file_path,
            carrier=carrier,
            service_type=service_type,
            charge_type=charge_type,
            scu_code=scu_code,
            status=status,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page=page,
            page_size=page_size,
        )

    # Generic sheet loading for non-Baseline sheets
    df = _load_sheet_data(file_path, sheet)
    if df.empty:
        return {"rows": [], "total": 0, "page": page, "page_size": page_size, "columns": []}

    # Apply search filter
    if search:
        mask = pd.Series([False] * len(df))
        for col in df.columns:
            mask |= df[col].astype(str).str.contains(search, case=False, na=False)
        df = df[mask]

    # Apply sorting
    if sort_by and sort_by in df.columns:
        ascending = sort_dir != "desc"
        df = df.sort_values(sort_by, ascending=ascending, na_position="last")

    total = len(df)
    start = (page - 1) * page_size
    end = start + page_size
    page_df = df.iloc[start:end]

    rows = []
    for idx, row in page_df.iterrows():
        row_dict = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                row_dict[col] = None
            elif hasattr(val, 'item'):
                row_dict[col] = val.item()
            elif hasattr(val, 'isoformat'):
                row_dict[col] = val.isoformat()
            else:
                row_dict[col] = val
        rows.append({"row_index": int(idx), "data": row_dict})

    return {
        "rows": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "columns": list(df.columns),
    }


@router.get("/projects/{project_id}/inventory/columns")
async def inventory_columns(project_id: str, request: Request, sheet: str = "Baseline"):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    if sheet.strip() == "Baseline":
        df = load_inventory(proj["reference_file"])
    else:
        df = _load_sheet_data(proj["reference_file"], sheet)

    if df.empty:
        return []
    return [{"name": col, "index": i} for i, col in enumerate(df.columns)]


@router.get("/projects/{project_id}/inventory/filters")
async def inventory_filters(project_id: str, request: Request, source: str = "reference"):
    """Get unique filter values for dropdowns."""
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    file_path = _resolve_file(proj, source)
    df = load_inventory(file_path)
    if df.empty:
        return {}

    def _unique_sorted(col_name):
        col = next((c for c in df.columns if c.strip().lower() == col_name.lower()), None)
        if not col:
            col = next((c for c in df.columns if col_name.lower() in c.lower()), None)
        if not col:
            return []
        vals = df[col].dropna().astype(str).str.strip().unique().tolist()
        return sorted([v for v in vals if v and v != "nan"])

    return {
        "carriers": _unique_sorted("carrier"),
        "service_types": _unique_sorted("service type"),
        "charge_types": _unique_sorted("charge type"),
        "scu_codes": _unique_sorted("service or component"),
        "statuses": _unique_sorted("status"),
    }


@router.get("/projects/{project_id}/inventory/checklist")
async def get_checklist(project_id: str, request: Request, source: str = "reference"):
    """Get the checklist sheet data."""
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    file_path = _resolve_file(proj, source)
    path = Path(file_path)
    if not path.exists():
        return {"items": []}

    # Find checklist sheet (may have leading space)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    checklist_sheet = None
    for name in wb.sheetnames:
        if "checklist" in name.lower():
            checklist_sheet = name
            break
    wb.close()

    if not checklist_sheet:
        return {"items": []}

    df = pd.read_excel(file_path, sheet_name=checklist_sheet, header=0)
    df.columns = [str(c).strip() for c in df.columns]

    items = []
    for _, row in df.iterrows():
        item = {}
        for col in df.columns:
            val = row[col]
            item[col] = None if pd.isna(val) else str(val)
        if item.get("Checklist"):  # Skip empty rows
            items.append(item)

    return {"items": items, "columns": list(df.columns)}


@router.post("/projects/{project_id}/inventory/checklist")
async def update_checklist(project_id: str, request: Request):
    """Update checklist items — persisted to disk."""
    from services.persistence import save_checklist
    data = await request.json()
    items = data.get("items", [])
    save_checklist(project_id, items)
    return {"status": "saved", "count": len(items)}


@router.get("/projects/{project_id}/inventory/export")
async def export_inventory(project_id: str, request: Request, source: str = "reference"):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    if source == "extracted":
        output_dir = Path(proj["output_dir"])
        output_files = sorted(output_dir.glob("*_inventory_output.xlsx"))
        if output_files:
            return FileResponse(output_files[-1], filename=output_files[-1].name)

    ref_path = Path(proj["reference_file"])
    if ref_path.exists():
        return FileResponse(ref_path, filename=ref_path.name)

    return {"error": "No inventory file found"}
