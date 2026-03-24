from __future__ import annotations
"""Accuracy router: compare extracted data vs reference data."""
import logging
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Request

router = APIRouter(tags=["accuracy"])
logger = logging.getLogger(__name__)

# Key columns used to build composite match key
KEY_COLUMNS = ["Carrier", "Carrier Account Number", "Service Type", "Service or Component", "Service Address 1"]


def _find_col(columns: list[str], target: str) -> str | None:
    """Flexible column name matching."""
    # Exact match first
    for c in columns:
        if c.strip().lower() == target.lower():
            return c
    # Partial match
    for c in columns:
        if target.lower() in c.strip().lower():
            return c
    return None


def _build_key(row: pd.Series, col_map: dict[str, str]) -> str:
    """Build a composite key from key columns."""
    parts = []
    for key_col in KEY_COLUMNS:
        mapped = col_map.get(key_col)
        if mapped:
            val = str(row.get(mapped, "")).strip().lower()
        else:
            val = ""
        parts.append(val)
    return "|".join(parts)


def _normalize_value(val) -> str:
    """Normalize a cell value for comparison."""
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip().lower()
    # Normalize common numeric representations
    if s in ("nan", "none", "nat", "n/a", "-"):
        return ""
    return s


def _load_baseline(file_path: str, header_row: int = 2) -> pd.DataFrame:
    """Load Baseline sheet from an Excel file."""
    path = Path(file_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Baseline", header=header_row)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        logger.error(f"Failed to load Baseline from {path.name}: {e}")
        return pd.DataFrame()


def _resolve_extracted_file(proj: dict) -> str | None:
    """Find the latest extracted inventory output file."""
    output_dir = Path(proj["output_dir"])
    output_files = sorted(output_dir.glob("*_inventory_output.xlsx"))
    return str(output_files[-1]) if output_files else None


def compute_accuracy(proj: dict) -> dict:
    """Core comparison logic: reference vs extracted."""
    ref_file = proj.get("reference_file", "")
    ext_file = _resolve_extracted_file(proj)

    # Load reference data
    ref_df = _load_baseline(ref_file, header_row=2)
    if ref_df.empty:
        return {"error": "Reference file not found or empty", "has_data": False}

    # Load extracted data
    if not ext_file:
        return {"error": "No extracted output file found", "has_data": False}

    ext_df = _load_baseline(ext_file, header_row=2)
    if ext_df.empty:
        return {"error": "Extracted file is empty", "has_data": False}

    # Build column maps for flexible matching
    ref_col_map = {}
    ext_col_map = {}
    for key_col in KEY_COLUMNS:
        ref_col_map[key_col] = _find_col(list(ref_df.columns), key_col)
        ext_col_map[key_col] = _find_col(list(ext_df.columns), key_col)

    # Build composite keys
    ref_df["_key"] = ref_df.apply(lambda r: _build_key(r, ref_col_map), axis=1)
    ext_df["_key"] = ext_df.apply(lambda r: _build_key(r, ext_col_map), axis=1)

    # Deduplicate keys (take first occurrence)
    ref_keys = set(ref_df["_key"].tolist())
    ext_keys = set(ext_df["_key"].tolist())

    matched_keys = ref_keys & ext_keys
    missing_keys = ref_keys - ext_keys
    extra_keys = ext_keys - ref_keys

    # --- Row-level metrics ---
    total_ref = len(ref_keys)
    total_ext = len(ext_keys)
    total_matched = len(matched_keys)
    overall_match_rate = round(total_matched / total_ref * 100, 1) if total_ref > 0 else 0

    # --- Per-carrier metrics ---
    carrier_col_ref = ref_col_map.get("Carrier")
    carrier_col_ext = ext_col_map.get("Carrier")

    carrier_stats = {}
    if carrier_col_ref:
        for carrier in ref_df[carrier_col_ref].dropna().unique():
            carrier_str = str(carrier).strip()
            if not carrier_str or carrier_str.lower() == "nan":
                continue
            ref_carrier_rows = ref_df[ref_df[carrier_col_ref].astype(str).str.strip() == carrier_str]
            ref_carrier_keys = set(ref_carrier_rows["_key"].tolist())
            matched_carrier = ref_carrier_keys & ext_keys
            carrier_stats[carrier_str] = {
                "carrier": carrier_str,
                "ref_rows": len(ref_carrier_keys),
                "matched_rows": len(matched_carrier),
                "match_rate": round(len(matched_carrier) / len(ref_carrier_keys) * 100, 1) if len(ref_carrier_keys) > 0 else 0,
            }

    # --- Per-column accuracy (field-level comparison on matched rows) ---
    # Find common columns between ref and ext (excluding internal _key)
    compare_cols = []
    col_mapping = {}  # ref_col -> ext_col
    for ref_col in ref_df.columns:
        if ref_col == "_key":
            continue
        ext_col = _find_col([c for c in ext_df.columns if c != "_key"], ref_col)
        if ext_col:
            compare_cols.append(ref_col)
            col_mapping[ref_col] = ext_col

    # Index extracted rows by key for fast lookup
    ext_by_key = {}
    for _, row in ext_df.iterrows():
        key = row["_key"]
        if key not in ext_by_key:
            ext_by_key[key] = row

    column_accuracy = {}
    column_mismatches = {}

    if matched_keys:
        for ref_col in compare_cols:
            ext_col = col_mapping[ref_col]
            match_count = 0
            total_compared = 0
            mismatches = []

            for _, ref_row in ref_df.iterrows():
                key = ref_row["_key"]
                if key not in matched_keys or key not in ext_by_key:
                    continue

                ext_row = ext_by_key[key]
                total_compared += 1
                ref_val = _normalize_value(ref_row[ref_col])
                ext_val = _normalize_value(ext_row[ext_col])

                if ref_val == ext_val:
                    match_count += 1
                elif len(mismatches) < 3:
                    mismatches.append({
                        "ref_value": str(ref_row[ref_col]) if pd.notna(ref_row[ref_col]) else "",
                        "ext_value": str(ext_row[ext_col]) if pd.notna(ext_row[ext_col]) else "",
                    })

            if total_compared > 0:
                acc = round(match_count / total_compared * 100, 1)
                column_accuracy[ref_col] = acc
                if mismatches:
                    column_mismatches[ref_col] = mismatches

    # Sort columns by accuracy ascending (worst first) for top mismatches
    sorted_cols = sorted(column_accuracy.items(), key=lambda x: x[1])
    top_mismatches = [
        {
            "column": col,
            "accuracy": acc,
            "examples": column_mismatches.get(col, []),
        }
        for col, acc in sorted_cols[:15]
        if acc < 100
    ]

    # Per-column accuracy list sorted by column name
    per_column = [
        {"column": col, "accuracy": column_accuracy.get(col, 0)}
        for col in sorted(column_accuracy.keys())
    ]

    # Missing carriers
    missing_carriers = []
    if carrier_col_ref:
        ref_missing_rows = ref_df[ref_df["_key"].isin(missing_keys)]
        if carrier_col_ref in ref_missing_rows.columns:
            missing_carrier_counts = ref_missing_rows[carrier_col_ref].value_counts().to_dict()
            missing_carriers = [
                {"carrier": str(k), "missing_rows": int(v)}
                for k, v in missing_carrier_counts.items()
                if pd.notna(k)
            ]

    return {
        "has_data": True,
        "summary": {
            "overall_match_rate": overall_match_rate,
            "total_ref_rows": total_ref,
            "total_ext_rows": total_ext,
            "matched_rows": total_matched,
            "missing_rows": len(missing_keys),
            "extra_rows": len(extra_keys),
            "columns_compared": len(compare_cols),
        },
        "per_carrier": sorted(carrier_stats.values(), key=lambda x: x["carrier"]),
        "per_column": per_column,
        "top_mismatches": top_mismatches,
        "missing_carriers": missing_carriers,
    }


@router.get("/projects/{project_id}/accuracy")
async def project_accuracy(project_id: str, request: Request):
    """Compare extracted data vs reference data and return accuracy metrics."""
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    return compute_accuracy(proj)
