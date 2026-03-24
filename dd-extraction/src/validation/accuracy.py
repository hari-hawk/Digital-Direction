"""
Accuracy comparison tool.
Compares pipeline output against the reference NSS inventory file.
Reports field-level match rates for Charter rows.
"""
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from src.mapping.schema import INVENTORY_SCHEMA, InventoryRow

logger = logging.getLogger(__name__)

# Fields to compare (skip metadata-only or non-comparable fields)
COMPARE_FIELDS = [
    ("Carrier", "carrier"),
    ("Billing Name", "billing_name"),
    ("Service Address 1", "service_address_1"),
    ("City", "city"),
    ("State", "state"),
    ("Zip", "zip_code"),
    ("Carrier Account Number", "carrier_account_number"),
    ("Sub-Account Number", "sub_account_number"),
    ("Service Type", "service_type"),
    ("Service or Component", "service_or_component"),
    ("Monthly Recurring Cost", "monthly_recurring_cost"),
    ("Charge Type", "charge_type"),
    ("Access Speed", "access_speed"),
    ("Currency", "currency"),
]

# Fields used for matching rows between output and reference
MATCH_KEYS = [
    ("Sub-Account Number", "sub_account_number"),
    ("Service Address 1", "service_address_1"),
]


def load_reference_charter_rows(reference_path: Path) -> pd.DataFrame:
    """Load Charter rows from the reference NSS inventory file."""
    ref = pd.read_excel(reference_path, sheet_name="Baseline", header=2)

    # Find the carrier column (may have trailing space)
    carrier_col = next(c for c in ref.columns if c.strip().lower() == "carrier")
    charter = ref[ref[carrier_col] == "Charter Communications"].copy()

    # Normalize column names (strip whitespace)
    charter.columns = [c.strip() for c in charter.columns]

    logger.info(f"Loaded {len(charter)} Charter reference rows")
    return charter


def load_output_rows(output_path: Path) -> pd.DataFrame:
    """Load rows from pipeline output Excel file."""
    # Output has 3 header rows; data starts at row 4 (0-indexed row 3)
    df = pd.read_excel(output_path, sheet_name="Baseline", header=2)
    logger.info(f"Loaded {len(df)} output rows")
    return df


def normalize_value(val) -> Optional[str]:
    """Normalize a value for comparison."""
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip()
    if s in ("", "nan", "None", "NaN"):
        return None
    # Normalize common patterns
    s = s.upper()
    # Remove trailing .0 from numbers read as floats
    if s.endswith(".0"):
        s = s[:-2]
    return s


def compare_field(ref_val, out_val, field_name: str) -> tuple[bool, str]:
    """Compare a single field between reference and output."""
    ref_norm = normalize_value(ref_val)
    out_norm = normalize_value(out_val)

    # Both null = match
    if ref_norm is None and out_norm is None:
        return True, "both_null"

    # One null, one not = mismatch
    if ref_norm is None or out_norm is None:
        return False, f"null_mismatch: ref={ref_norm}, out={out_norm}"

    # Numeric comparison for MRC
    if field_name in ("Monthly Recurring Cost", "monthly_recurring_cost"):
        try:
            ref_num = float(ref_val)
            out_num = float(out_val)
            if abs(ref_num - out_num) < 0.01:
                return True, "numeric_match"
            return False, f"numeric_mismatch: ref={ref_num}, out={out_num}"
        except (ValueError, TypeError):
            pass

    # String comparison
    if ref_norm == out_norm:
        return True, "exact_match"

    # Fuzzy: check containment
    if ref_norm in out_norm or out_norm in ref_norm:
        return True, "contains_match"

    return False, f"mismatch: ref='{ref_norm}', out='{out_norm}'"


def run_accuracy_comparison(
    output_path: Path,
    reference_path: Path,
    carrier_name: str = "Charter Communications",
) -> dict:
    """
    Compare pipeline output against reference and report field-level accuracy.

    Strategy: Match S-rows by Sub-Account Number + Service Address, then
    compare all comparable fields.
    """
    ref_df = load_reference_charter_rows(reference_path)
    out_df = load_output_rows(output_path)

    # Normalize column name for S/C/U code
    scu_ref_col = next((c for c in ref_df.columns if "service or component" in c.lower()), None)
    scu_out_col = next((c for c in out_df.columns if "service or component" in c.lower()), None)

    if not scu_ref_col or not scu_out_col:
        return {"error": "Could not find Service or Component column"}

    # Split into S-rows for matching
    ref_s = ref_df[ref_df[scu_ref_col].str.strip() == "S"].copy()
    out_s = out_df[out_df[scu_out_col].str.strip() == "S"].copy()

    ref_c = ref_df[ref_df[scu_ref_col].str.strip() == "C"].copy()
    out_c = out_df[out_df[scu_out_col].str.strip() == "C"].copy()

    logger.info(f"Reference: {len(ref_s)} S-rows, {len(ref_c)} C-rows")
    logger.info(f"Output:    {len(out_s)} S-rows, {len(out_c)} C-rows")

    # --- Match S-rows by address ---
    # Build lookup for output S-rows by normalized address
    out_s_by_addr = {}
    addr_col_out = next((c for c in out_df.columns if c.strip().lower() == "service address 1"), None)
    subacct_col_out = next((c for c in out_df.columns if "sub-account" in c.lower()), None)

    if addr_col_out:
        for idx, row in out_s.iterrows():
            addr = normalize_value(row.get(addr_col_out))
            subacct = normalize_value(row.get(subacct_col_out)) if subacct_col_out else None
            if addr:
                key = f"{subacct}:{addr}" if subacct else addr
                out_s_by_addr[key] = row

    # Match reference S-rows to output S-rows
    addr_col_ref = next((c for c in ref_df.columns if c.strip().lower() == "service address 1"), None)
    subacct_col_ref = next((c for c in ref_df.columns if "sub-account" in c.lower()), "Sub-Account Number")

    matched_pairs = []
    unmatched_ref = []

    for idx, ref_row in ref_s.iterrows():
        ref_addr = normalize_value(ref_row.get(addr_col_ref))
        ref_subacct = normalize_value(ref_row.get(subacct_col_ref))

        # Try exact key match
        key = f"{ref_subacct}:{ref_addr}" if ref_subacct else (ref_addr or "")
        if key in out_s_by_addr:
            matched_pairs.append((ref_row, out_s_by_addr[key]))
            continue

        # Try address-only match
        if ref_addr:
            for out_key, out_row in out_s_by_addr.items():
                if ref_addr in out_key:
                    matched_pairs.append((ref_row, out_row))
                    break
            else:
                unmatched_ref.append(ref_row)
        else:
            unmatched_ref.append(ref_row)

    logger.info(f"Matched {len(matched_pairs)} S-row pairs, {len(unmatched_ref)} unmatched reference rows")

    # --- Compare fields for matched pairs ---
    field_stats = {}
    field_mismatches = {}

    for ref_col_name, _ in COMPARE_FIELDS:
        field_stats[ref_col_name] = {"total": 0, "match": 0, "mismatch": 0}
        field_mismatches[ref_col_name] = []

    for ref_row, out_row in matched_pairs:
        for ref_col_name, _ in COMPARE_FIELDS:
            # Find column in both dataframes
            ref_col = next((c for c in ref_df.columns if c.strip() == ref_col_name), None)
            out_col = next((c for c in out_df.columns if c.strip() == ref_col_name), None)

            if not ref_col or not out_col:
                continue

            ref_val = ref_row.get(ref_col)
            out_val = out_row.get(out_col)

            # Skip if reference is null (nothing to compare)
            if pd.isna(ref_val):
                continue

            field_stats[ref_col_name]["total"] += 1
            matched, reason = compare_field(ref_val, out_val, ref_col_name)

            if matched:
                field_stats[ref_col_name]["match"] += 1
            else:
                field_stats[ref_col_name]["mismatch"] += 1
                if len(field_mismatches[ref_col_name]) < 5:
                    field_mismatches[ref_col_name].append(reason)

    # --- Calculate overall accuracy ---
    total_compared = sum(s["total"] for s in field_stats.values())
    total_matched = sum(s["match"] for s in field_stats.values())
    overall_accuracy = round(100 * total_matched / max(total_compared, 1), 1)

    # Per-field accuracy
    per_field = {}
    for field_name, stats in field_stats.items():
        if stats["total"] > 0:
            pct = round(100 * stats["match"] / stats["total"], 1)
            per_field[field_name] = {
                "accuracy": pct,
                "matched": stats["match"],
                "total": stats["total"],
                "sample_mismatches": field_mismatches.get(field_name, []),
            }

    result = {
        "overall_accuracy_pct": overall_accuracy,
        "total_fields_compared": total_compared,
        "total_fields_matched": total_matched,
        "s_row_match_rate": f"{len(matched_pairs)}/{len(ref_s)} ({round(100*len(matched_pairs)/max(len(ref_s),1),1)}%)",
        "reference_s_rows": len(ref_s),
        "output_s_rows": len(out_s),
        "matched_pairs": len(matched_pairs),
        "unmatched_reference": len(unmatched_ref),
        "per_field_accuracy": per_field,
    }

    # Print report
    print("\n" + "=" * 70)
    print("ACCURACY COMPARISON REPORT")
    print("=" * 70)
    print(f"Overall field-level accuracy: {overall_accuracy}%")
    print(f"S-row match rate: {result['s_row_match_rate']}")
    print(f"Fields compared: {total_compared}, matched: {total_matched}")
    print()
    print(f"{'Field':<30} {'Accuracy':>10} {'Matched':>10} {'Total':>10}")
    print("-" * 70)
    for field_name, info in sorted(per_field.items(), key=lambda x: x[1]["accuracy"]):
        print(f"{field_name:<30} {info['accuracy']:>9.1f}% {info['matched']:>10} {info['total']:>10}")
        for mismatch in info["sample_mismatches"][:2]:
            print(f"  {'':30} -> {mismatch}")
    print("=" * 70)

    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from config import NSS_REFERENCE_FILE, OUTPUT_DIR

    output_file = OUTPUT_DIR / "charter_inventory_output.xlsx"
    result = run_accuracy_comparison(output_file, NSS_REFERENCE_FILE)
