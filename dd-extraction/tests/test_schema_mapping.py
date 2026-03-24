"""Tests for schema mapping module."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.mapping.schema import (
    INVENTORY_SCHEMA, SCHEMA_BY_LETTER, SCHEMA_BY_NAME, COLUMN_NAMES,
    REQUIRED_COLUMNS, SERVICE_TYPES, CHARGE_TYPES, SCU_CODES,
    InventoryRow, SECTION_AREAS,
)


def test_schema_has_60_columns():
    assert len(INVENTORY_SCHEMA) == 60


def test_column_letters_sequential():
    letters = [col.letter for col in INVENTORY_SCHEMA]
    assert letters[0] == "A"
    assert letters[-1] == "BH"


def test_schema_by_letter_lookup():
    assert SCHEMA_BY_LETTER["A"].name == "Status"
    assert SCHEMA_BY_LETTER["M"].name == "Carrier"
    assert SCHEMA_BY_LETTER["Y"].name == "Service or Component"
    assert SCHEMA_BY_LETTER["AA"].name == "Monthly Recurring Cost"


def test_required_columns_exist():
    assert "Status" in REQUIRED_COLUMNS
    assert "Carrier" in REQUIRED_COLUMNS
    assert "Service Type" in REQUIRED_COLUMNS
    assert "Service or Component" in REQUIRED_COLUMNS
    assert "Charge Type" in REQUIRED_COLUMNS
    assert len(REQUIRED_COLUMNS) >= 8


def test_service_types_dropdown():
    assert len(SERVICE_TYPES) >= 80  # ~83-91 depending on source
    assert "DIA" in SERVICE_TYPES
    assert "POTS" in SERVICE_TYPES
    assert "UCaaS" in SERVICE_TYPES
    assert "Business Internet" in SERVICE_TYPES


def test_charge_types_dropdown():
    assert len(CHARGE_TYPES) == 8
    assert "MRC" in CHARGE_TYPES
    assert "NRC" in CHARGE_TYPES
    assert "Taxes" in CHARGE_TYPES


def test_scu_codes():
    assert len(SCU_CODES) == 4
    assert "S" in SCU_CODES
    assert "C" in SCU_CODES
    assert "T\\S\\OCC" in SCU_CODES


def test_inventory_row_to_dict():
    row = InventoryRow(
        status="Completed",
        carrier="Charter Communications",
        service_type="DIA",
        service_or_component="S",
        charge_type="MRC",
        monthly_recurring_cost=325.00,
    )
    d = row.to_row_dict()
    assert d["Status"] == "Completed"
    assert d["Carrier"] == "Charter Communications"
    assert d["Monthly Recurring Cost"] == 325.00
    assert len(d) == 60  # All 60 columns


def test_section_areas_span_all_columns():
    covered = set()
    for section, (start, end) in SECTION_AREAS.items():
        start_idx = next(i for i, c in enumerate(INVENTORY_SCHEMA) if c.letter == start)
        end_idx = next(i for i, c in enumerate(INVENTORY_SCHEMA) if c.letter == end)
        for i in range(start_idx, end_idx + 1):
            covered.add(i)
    assert len(covered) == 60
