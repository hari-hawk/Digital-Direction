"""Tests for row classification."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.mapping.schema import InventoryRow
from src.classification.row_classifier import (
    validate_row_classification,
    ensure_parent_child_inheritance,
    get_row_stats,
)


def _make_row(**kwargs) -> InventoryRow:
    return InventoryRow(**kwargs)


def test_validate_classification_valid():
    rows = [
        _make_row(service_or_component="S", linkage_key="g1"),
        _make_row(service_or_component="C", linkage_key="g1"),
    ]
    warnings = validate_row_classification(rows)
    assert len(warnings) == 0


def test_validate_orphan_c_row():
    rows = [
        _make_row(service_or_component="C", linkage_key="g1"),
    ]
    warnings = validate_row_classification(rows)
    assert any("No S-row" in w for w in warnings)


def test_ensure_inheritance():
    rows = [
        _make_row(
            service_or_component="S", linkage_key="g1",
            carrier="Charter", city="Albany", state="NY",
            carrier_account_number="117931801",
        ),
        _make_row(service_or_component="C", linkage_key="g1"),
    ]
    rows = ensure_parent_child_inheritance(rows)
    assert rows[1].carrier == "Charter"
    assert rows[1].city == "Albany"
    assert rows[1].carrier_account_number == "117931801"


def test_get_row_stats():
    rows = [
        _make_row(service_or_component="S"),
        _make_row(service_or_component="C"),
        _make_row(service_or_component="C"),
        _make_row(service_or_component="T\\S\\OCC"),
    ]
    stats = get_row_stats(rows)
    assert stats["S"] == 1
    assert stats["C"] == 2
    assert stats["T\\S\\OCC"] == 1
    assert stats["total"] == 4
