"""Tests for QA validation rules."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.mapping.schema import InventoryRow
from src.validation.qa import (
    check_s_row_mrc_sum,
    check_service_type_dropdown,
    check_charge_type_dropdown,
    check_scu_code_valid,
    check_duplicate_circuit_ids,
    check_orphan_c_rows,
    check_billing_name_not_blank,
    validate_all,
)


def _make_row(**kwargs) -> InventoryRow:
    defaults = {
        "status": "Completed",
        "carrier": "Charter Communications",
        "service_type": "DIA",
        "service_or_component": "S",
        "charge_type": "MRC",
        "billing_name": "TEST",
        "service_address_1": "123 Main St",
        "city": "Albany",
        "state": "NY",
        "zip_code": "12345",
    }
    defaults.update(kwargs)
    return InventoryRow(**defaults)


def test_s_row_mrc_sum_pass():
    rows = [
        _make_row(service_or_component="S", monthly_recurring_cost=325.0, linkage_key="g1"),
        _make_row(service_or_component="C", monthly_recurring_cost=325.0, linkage_key="g1"),
        _make_row(service_or_component="C", monthly_recurring_cost=0.0, linkage_key="g1"),
    ]
    result = check_s_row_mrc_sum(rows)
    assert result.passed


def test_s_row_mrc_sum_fail():
    rows = [
        _make_row(service_or_component="S", monthly_recurring_cost=500.0, linkage_key="g1"),
        _make_row(service_or_component="C", monthly_recurring_cost=325.0, linkage_key="g1"),
    ]
    result = check_s_row_mrc_sum(rows)
    assert not result.passed
    assert len(result.violations) == 1


def test_service_type_valid():
    rows = [_make_row(service_type="DIA"), _make_row(service_type="POTS")]
    result = check_service_type_dropdown(rows)
    assert result.passed


def test_service_type_invalid():
    rows = [_make_row(service_type="INVALID_TYPE")]
    result = check_service_type_dropdown(rows)
    assert not result.passed


def test_charge_type_valid():
    rows = [_make_row(charge_type="MRC"), _make_row(charge_type="Taxes")]
    result = check_charge_type_dropdown(rows)
    assert result.passed


def test_scu_code_valid():
    rows = [
        _make_row(service_or_component="S"),
        _make_row(service_or_component="C"),
        _make_row(service_or_component="T\\S\\OCC"),
    ]
    result = check_scu_code_valid(rows)
    assert result.passed


def test_duplicate_circuit_ids():
    rows = [
        _make_row(service_or_component="S", carrier_circuit_number="CIRCUIT-001"),
        _make_row(service_or_component="S", carrier_circuit_number="CIRCUIT-002"),
    ]
    result = check_duplicate_circuit_ids(rows)
    assert result.passed


def test_duplicate_circuit_ids_fail():
    rows = [
        _make_row(service_or_component="S", carrier_circuit_number="CIRCUIT-001"),
        _make_row(service_or_component="S", carrier_circuit_number="CIRCUIT-001"),
    ]
    result = check_duplicate_circuit_ids(rows)
    assert not result.passed


def test_orphan_c_rows_pass():
    rows = [
        _make_row(service_or_component="S", linkage_key="g1"),
        _make_row(service_or_component="C", linkage_key="g1"),
    ]
    result = check_orphan_c_rows(rows)
    assert result.passed


def test_orphan_c_rows_fail():
    rows = [
        _make_row(service_or_component="S", linkage_key="g1"),
        _make_row(service_or_component="C", linkage_key="g2"),  # No parent
    ]
    result = check_orphan_c_rows(rows)
    assert not result.passed


def test_billing_name_not_blank():
    rows = [_make_row(billing_name="GOLUB")]
    result = check_billing_name_not_blank(rows)
    assert result.passed


def test_billing_name_blank():
    rows = [_make_row(billing_name="")]
    result = check_billing_name_not_blank(rows)
    assert not result.passed
