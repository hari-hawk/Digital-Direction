"""
Row classifier: assigns S/C/U/T\\S\\OCC type and validates parent-child relationships.
This module works as a post-processing step after extraction.
"""
import logging
from collections import defaultdict

from src.mapping.schema import InventoryRow

logger = logging.getLogger(__name__)


def validate_row_classification(rows: list[InventoryRow]) -> list[str]:
    """
    Validate S/C/U/T\\S\\OCC classification rules.
    Returns a list of warning messages.
    """
    warnings = []

    # Group rows by linkage key
    groups = defaultdict(list)
    for row in rows:
        if row.linkage_key:
            groups[row.linkage_key].append(row)

    for key, group in groups.items():
        s_rows = [r for r in group if r.service_or_component == "S"]
        c_rows = [r for r in group if r.service_or_component == "C"]

        # Rule: Each group should have exactly one S-row
        if len(s_rows) == 0:
            warnings.append(f"Group {key}: No S-row found (orphan C-rows)")
        elif len(s_rows) > 1:
            warnings.append(f"Group {key}: Multiple S-rows found ({len(s_rows)})")

        # Rule: S-row should have at least one C-row (except standalone services)
        if len(s_rows) == 1 and len(c_rows) == 0:
            # This is acceptable for standalone services (e.g., EPL without breakdown)
            pass

    # Check for rows without classification
    unclassified = [r for r in rows if not r.service_or_component]
    if unclassified:
        warnings.append(f"{len(unclassified)} rows have no S/C/U/T\\S\\OCC classification")

    # Check for valid classification values
    valid_codes = {"S", "C", "U", "T\\S\\OCC"}
    for i, row in enumerate(rows):
        if row.service_or_component and row.service_or_component not in valid_codes:
            warnings.append(f"Row {i}: Invalid classification '{row.service_or_component}'")

    return warnings


def ensure_parent_child_inheritance(rows: list[InventoryRow]) -> list[InventoryRow]:
    """
    Ensure C-rows inherit key fields from their parent S-row.
    Fields inherited: carrier, account, address, circuit number.
    """
    # Build S-row lookup by linkage key
    s_row_lookup = {}
    for row in rows:
        if row.service_or_component == "S" and row.linkage_key:
            s_row_lookup[row.linkage_key] = row

    # Ensure inheritance
    for row in rows:
        if row.service_or_component in ("C", "U") and row.linkage_key:
            parent = s_row_lookup.get(row.linkage_key)
            if parent:
                # Inherit location if missing
                if not row.service_address_1:
                    row.service_address_1 = parent.service_address_1
                if not row.city:
                    row.city = parent.city
                if not row.state:
                    row.state = parent.state
                if not row.zip_code:
                    row.zip_code = parent.zip_code
                # Inherit carrier info
                if not row.carrier:
                    row.carrier = parent.carrier
                if not row.carrier_account_number:
                    row.carrier_account_number = parent.carrier_account_number
                if not row.master_account:
                    row.master_account = parent.master_account
                if not row.carrier_circuit_number:
                    row.carrier_circuit_number = parent.carrier_circuit_number
                # Inherit service type
                if not row.service_type:
                    row.service_type = parent.service_type

    return rows


def get_row_stats(rows: list[InventoryRow]) -> dict:
    """Get statistics about row classification."""
    stats = {"total": len(rows), "S": 0, "C": 0, "U": 0, "T\\S\\OCC": 0, "unclassified": 0}
    for row in rows:
        code = row.service_or_component
        if code in stats:
            stats[code] += 1
        else:
            stats["unclassified"] += 1
    return stats
