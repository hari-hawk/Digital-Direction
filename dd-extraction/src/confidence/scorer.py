"""
Per-field confidence scoring.
High = structured carrier report, Medium = OCR + validated, Low = OCR-only or missing.
"""
from typing import Literal

from src.mapping.schema import InventoryRow, REQUIRED_COLUMNS, FIELD_TO_COLUMN

ConfidenceLevel = Literal["High", "Medium", "Low"]


# Fields that are always High confidence when populated from carrier report
CARRIER_REPORT_FIELDS = {
    "carrier", "carrier_account_number", "service_address_1", "city", "state",
    "zip_code", "phone_number", "carrier_circuit_number", "billing_name",
    "master_account",
}

# Fields typically from invoices
INVOICE_FIELDS = {
    "monthly_recurring_cost", "component_or_feature_name", "charge_type",
    "quantity", "cost_per_unit",
}


def score_row_confidence(row: InventoryRow) -> dict[str, ConfidenceLevel]:
    """
    Score confidence for each field in an inventory row.
    Uses existing row.confidence as base, then fills in defaults.
    """
    confidence = dict(row.confidence)  # Start with any pre-set values

    for attr_name, col_name in FIELD_TO_COLUMN.items():
        if attr_name in confidence:
            continue  # Already scored

        value = getattr(row, attr_name, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            confidence[attr_name] = "Low"
            continue

        # Fields from carrier report are High confidence
        if attr_name in CARRIER_REPORT_FIELDS:
            confidence[attr_name] = "High"
        # Invoice-derived fields default to Medium if present
        elif attr_name in INVOICE_FIELDS:
            confidence[attr_name] = "Medium"
        # Static/derived fields
        elif attr_name in ("carrier", "country", "currency", "status"):
            confidence[attr_name] = "High"
        else:
            confidence[attr_name] = "Medium"

    return confidence


def get_confidence_summary(rows: list[InventoryRow]) -> dict:
    """Get summary statistics about confidence across all rows."""
    total_fields = 0
    high_count = 0
    medium_count = 0
    low_count = 0

    for row in rows:
        conf = score_row_confidence(row)
        for field_name, level in conf.items():
            val = getattr(row, field_name, None)
            if val is not None and (not isinstance(val, str) or val.strip()):
                total_fields += 1
                if level == "High":
                    high_count += 1
                elif level == "Medium":
                    medium_count += 1
                else:
                    low_count += 1

    return {
        "total_populated_fields": total_fields,
        "high": high_count,
        "medium": medium_count,
        "low": low_count,
        "high_pct": round(100 * high_count / max(total_fields, 1), 1),
        "medium_pct": round(100 * medium_count / max(total_fields, 1), 1),
        "low_pct": round(100 * low_count / max(total_fields, 1), 1),
    }
