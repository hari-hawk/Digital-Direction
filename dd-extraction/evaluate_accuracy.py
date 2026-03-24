#!/usr/bin/env python3
"""
Accuracy evaluation harness — autoresearch-style single-metric evaluator.
Compares extracted Charter inventory against reference NSS file.

Usage:
    python evaluate_accuracy.py [--extracted outputs/charter_inventory_output.xlsx]

Returns a single overall accuracy score + per-field breakdown.
"""
import sys
import re
from pathlib import Path

import pandas as pd

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_EXTRACTED = SCRIPT_DIR / "outputs" / "charter_inventory_output.xlsx"
REFERENCE_FILE = SCRIPT_DIR.parent.parent / "Client Inputs" / "NSS POC Inputs and Output" / \
    "Digital Direction_NSS_ Inventory File_01.22.2026_WIP_v3 BF- Sent to Techjays.xlsx"


def normalize_acct(val):
    """Normalize account number for matching."""
    if pd.isna(val):
        return ""
    s = str(val).strip()
    # Remove .0 from float conversion
    if s.endswith(".0"):
        s = s[:-2]
    return s


def normalize_str(val):
    """Normalize string for comparison."""
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "null"):
        return ""
    return s


def normalize_num(val):
    """Normalize numeric for comparison."""
    if pd.isna(val) or val is None:
        return None
    try:
        n = float(val)
        return round(n, 2)
    except (ValueError, TypeError):
        return None


def load_reference():
    """Load Charter rows from reference file."""
    df = pd.read_excel(str(REFERENCE_FILE), sheet_name="Baseline", header=2)
    df.columns = [str(c).strip() for c in df.columns]
    carrier_col = next((c for c in df.columns if c.lower() == "carrier"), "Carrier")
    charter = df[df[carrier_col].astype(str).str.contains("Charter", case=False, na=False)].copy()
    return charter


def load_extracted(path):
    """Load extracted file."""
    df = pd.read_excel(str(path), sheet_name="Baseline", header=2)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def evaluate(extracted_path=None):
    """Run full accuracy evaluation. Returns dict with scores."""
    if extracted_path is None:
        extracted_path = DEFAULT_EXTRACTED

    ref = load_reference()
    ext = load_extracted(extracted_path)

    print(f"Reference: {len(ref)} Charter rows")
    print(f"Extracted: {len(ext)} rows")

    # --- Row-level metrics ---
    scu_col = next((c for c in ref.columns if "service or component" in c.lower()), "Service or Component")
    ref_scu = ref[scu_col].astype(str).str.strip().value_counts().to_dict()
    ext_scu_col = next((c for c in ext.columns if "service or component" in c.lower()), "Service or Component")
    ext_scu = ext[ext_scu_col].astype(str).str.strip().value_counts().to_dict()

    print(f"\n--- Row Type Distribution ---")
    for t in ["S", "C", "T\\S\\OCC", "U"]:
        r = ref_scu.get(t, 0)
        e = ext_scu.get(t, 0)
        match_pct = min(r, e) / max(r, 1) * 100 if r > 0 else (0 if e > 0 else 100)
        print(f"  {t:10s}: ref={r:4d}  ext={e:4d}  match={match_pct:.0f}%")

    row_count_score = 1.0 - min(abs(len(ref) - len(ext)) / len(ref), 1.0)
    print(f"\n  Row count score: {row_count_score:.2%} (closer to 1.0 = better)")

    # --- Field population rates ---
    print(f"\n--- Field Population Comparison ---")
    required_fields = [
        "Status", "Carrier", "Carrier Account Number", "Service Type",
        "Service or Component", "Billing Name", "Service Address 1",
        "City", "State", "Zip", "Country", "Monthly Recurring Cost",
        "Charge Type", "Quantity", "Cost Per Unit", "Currency",
        "Conversion Rate", "Monthly Recurring Cost per Currency",
    ]

    population_scores = {}
    for field_name in required_fields:
        ref_col = next((c for c in ref.columns if c.strip().lower() == field_name.lower()), None)
        if not ref_col:
            ref_col = next((c for c in ref.columns if field_name.lower() in c.lower()), None)
        ext_col = next((c for c in ext.columns if c.strip().lower() == field_name.lower()), None)
        if not ext_col:
            ext_col = next((c for c in ext.columns if field_name.lower() in c.lower()), None)

        if ref_col and ext_col:
            ref_pop = ref[ref_col].notna().sum() / len(ref) * 100
            ext_pop = ext[ext_col].notna().sum() / len(ext) * 100
            gap = ext_pop - ref_pop
            score = min(ext_pop, ref_pop) / max(ref_pop, 0.01)
            population_scores[field_name] = score
            flag = "✓" if abs(gap) < 10 else ("▼" if gap < 0 else "▲")
            print(f"  {flag} {field_name:35s}: ref={ref_pop:5.1f}%  ext={ext_pop:5.1f}%  gap={gap:+6.1f}%")
        else:
            print(f"  ? {field_name:35s}: column not found (ref={ref_col}, ext={ext_col})")

    avg_population_score = sum(population_scores.values()) / max(len(population_scores), 1)
    print(f"\n  Avg population match: {avg_population_score:.2%}")

    # --- Overall score ---
    # Weight: row count 30%, population match 70%
    overall = row_count_score * 0.3 + avg_population_score * 0.7
    print(f"\n{'='*60}")
    print(f"OVERALL ACCURACY SCORE: {overall:.2%}")
    print(f"  Row count component:  {row_count_score:.2%} (weight 30%)")
    print(f"  Population component: {avg_population_score:.2%} (weight 70%)")
    print(f"{'='*60}")

    return {
        "overall": round(overall * 100, 1),
        "row_count_score": round(row_count_score * 100, 1),
        "population_score": round(avg_population_score * 100, 1),
        "ref_rows": len(ref),
        "ext_rows": len(ext),
        "ref_scu": ref_scu,
        "ext_scu": ext_scu,
        "population_scores": {k: round(v * 100, 1) for k, v in population_scores.items()},
    }


if __name__ == "__main__":
    extracted = sys.argv[1] if len(sys.argv) > 1 else None
    result = evaluate(extracted)
    print(f"\nScore for tracking: {result['overall']}")
