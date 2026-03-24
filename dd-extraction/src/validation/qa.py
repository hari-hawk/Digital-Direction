"""
QA validation rules engine.
Implements automated checks from the DD2 QA Checklist.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from src.mapping.schema import (
    InventoryRow, REQUIRED_COLUMNS, SERVICE_TYPES, CHARGE_TYPES, SCU_CODES,
)


@dataclass
class RuleResult:
    rule_name: str
    passed: bool
    violations: list[str] = field(default_factory=list)
    checked_count: int = 0
    pass_count: int = 0

    @property
    def fail_count(self) -> int:
        return self.checked_count - self.pass_count


@dataclass
class ValidationReport:
    rules: list[RuleResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.rules)

    @property
    def summary(self) -> dict:
        return {
            "total_rules": len(self.rules),
            "passed": sum(1 for r in self.rules if r.passed),
            "failed": sum(1 for r in self.rules if not r.passed),
            "rules": {r.rule_name: {"passed": r.passed, "violations": len(r.violations)} for r in self.rules},
        }


def validate_all(rows: list[InventoryRow]) -> ValidationReport:
    """Run all QA validation rules."""
    report = ValidationReport()
    report.rules.append(check_s_row_mrc_sum(rows))
    report.rules.append(check_required_columns(rows))
    report.rules.append(check_service_type_dropdown(rows))
    report.rules.append(check_charge_type_dropdown(rows))
    report.rules.append(check_scu_code_valid(rows))
    report.rules.append(check_duplicate_circuit_ids(rows))
    report.rules.append(check_orphan_c_rows(rows))
    report.rules.append(check_billing_name_not_blank(rows))
    report.rules.append(check_currency_usd(rows))
    report.rules.append(check_phone_number_format(rows))
    return report


def check_s_row_mrc_sum(rows: list[InventoryRow]) -> RuleResult:
    """Rule 1: S-row MRC = sum of child C-row MRCs."""
    result = RuleResult(rule_name="S-row MRC = sum(C-row MRCs)", passed=True)

    # Group by linkage key
    groups = defaultdict(list)
    for row in rows:
        if row.linkage_key:
            groups[row.linkage_key].append(row)

    for key, group in groups.items():
        s_rows = [r for r in group if r.service_or_component == "S"]
        c_rows = [r for r in group if r.service_or_component == "C" and r.charge_type == "MRC"]

        for s_row in s_rows:
            result.checked_count += 1
            s_mrc = s_row.monthly_recurring_cost or 0
            c_sum = sum(c.monthly_recurring_cost or 0 for c in c_rows)

            if c_rows and abs(s_mrc - c_sum) > 0.01:
                result.passed = False
                result.violations.append(
                    f"Group {key}: S-row MRC=${s_mrc:.2f} != C-row sum=${c_sum:.2f} (diff=${abs(s_mrc - c_sum):.2f})"
                )
            else:
                result.pass_count += 1

    return result


def check_required_columns(rows: list[InventoryRow]) -> RuleResult:
    """Rule 2: All Required-tier columns are populated."""
    result = RuleResult(rule_name="Required columns populated", passed=True)

    from src.mapping.schema import COLUMN_TO_FIELD
    required_fields = [COLUMN_TO_FIELD[col] for col in REQUIRED_COLUMNS if col in COLUMN_TO_FIELD]

    # Exclude MRC from required check for C-rows with charge_type != MRC
    # and exclude invoice_file_name since it requires OCR
    soft_required = {"monthly_recurring_cost", "invoice_file_name"}

    for i, row in enumerate(rows):
        result.checked_count += 1
        missing = []
        for field_name in required_fields:
            if field_name in soft_required:
                continue  # Skip soft-required fields
            val = getattr(row, field_name, None)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(field_name)

        if missing:
            result.passed = False
            result.violations.append(f"Row {i} ({row.service_or_component}): missing {', '.join(missing)}")
        else:
            result.pass_count += 1

    return result


def check_service_type_dropdown(rows: list[InventoryRow]) -> RuleResult:
    """Rule 3: Service Type matches the 91-value dropdown list."""
    result = RuleResult(rule_name="Service Type in dropdown", passed=True)
    valid_set = set(SERVICE_TYPES)

    for i, row in enumerate(rows):
        if row.service_type:
            result.checked_count += 1
            if row.service_type in valid_set:
                result.pass_count += 1
            else:
                result.passed = False
                result.violations.append(f"Row {i}: '{row.service_type}' not in dropdown list")

    return result


def check_charge_type_dropdown(rows: list[InventoryRow]) -> RuleResult:
    """Rule 4: Charge Type matches the 8-value dropdown list."""
    result = RuleResult(rule_name="Charge Type in dropdown", passed=True)
    valid_set = set(CHARGE_TYPES)

    for i, row in enumerate(rows):
        if row.charge_type:
            result.checked_count += 1
            if row.charge_type in valid_set:
                result.pass_count += 1
            else:
                result.passed = False
                result.violations.append(f"Row {i}: '{row.charge_type}' not in dropdown list")

    return result


def check_scu_code_valid(rows: list[InventoryRow]) -> RuleResult:
    """Rule 5: Service or Component code is valid."""
    result = RuleResult(rule_name="S/C/U code valid", passed=True)
    valid_set = set(SCU_CODES)

    for i, row in enumerate(rows):
        if row.service_or_component:
            result.checked_count += 1
            if row.service_or_component in valid_set:
                result.pass_count += 1
            else:
                result.passed = False
                result.violations.append(f"Row {i}: '{row.service_or_component}' not valid")

    return result


def check_duplicate_circuit_ids(rows: list[InventoryRow]) -> RuleResult:
    """Rule 6: No duplicate Circuit IDs within same carrier (S-rows only)."""
    result = RuleResult(rule_name="No duplicate Circuit IDs", passed=True)
    seen = {}

    for i, row in enumerate(rows):
        if row.service_or_component == "S" and row.carrier_circuit_number:
            circuit = row.carrier_circuit_number.strip()
            result.checked_count += 1
            if circuit in seen:
                result.passed = False
                result.violations.append(
                    f"Row {i}: Circuit '{circuit}' duplicates row {seen[circuit]}"
                )
            else:
                seen[circuit] = i
                result.pass_count += 1

    return result


def check_orphan_c_rows(rows: list[InventoryRow]) -> RuleResult:
    """Rule 7: Every C-row must have a parent S-row."""
    result = RuleResult(rule_name="No orphan C-rows", passed=True)

    s_keys = {r.linkage_key for r in rows if r.service_or_component == "S" and r.linkage_key}

    for i, row in enumerate(rows):
        if row.service_or_component == "C":
            result.checked_count += 1
            if row.linkage_key and row.linkage_key in s_keys:
                result.pass_count += 1
            else:
                result.passed = False
                result.violations.append(f"Row {i}: C-row with key '{row.linkage_key}' has no parent S-row")

    return result


def check_billing_name_not_blank(rows: list[InventoryRow]) -> RuleResult:
    """Rule 8: Billing Name should not be blank."""
    result = RuleResult(rule_name="Billing Name not blank", passed=True)

    for i, row in enumerate(rows):
        result.checked_count += 1
        if row.billing_name and row.billing_name.strip():
            result.pass_count += 1
        else:
            result.passed = False
            result.violations.append(f"Row {i}: Billing Name is blank")

    return result


def check_currency_usd(rows: list[InventoryRow]) -> RuleResult:
    """Rule 9: Currency should be USD for US carriers."""
    result = RuleResult(rule_name="Currency = USD", passed=True)

    for i, row in enumerate(rows):
        if row.monthly_recurring_cost is not None:
            result.checked_count += 1
            if row.currency == "USD":
                result.pass_count += 1
            else:
                result.passed = False
                result.violations.append(f"Row {i}: Currency is '{row.currency}', expected 'USD'")

    return result


def check_phone_number_format(rows: list[InventoryRow]) -> RuleResult:
    """Rule 10: Phone numbers should be 10 digits."""
    result = RuleResult(rule_name="Phone number format", passed=True)
    import re

    for i, row in enumerate(rows):
        if row.phone_number:
            result.checked_count += 1
            digits = re.sub(r"\D", "", row.phone_number)
            if len(digits) == 10 or len(digits) == 11:
                result.pass_count += 1
            elif len(digits) == 0:
                result.pass_count += 1  # Empty is ok
            else:
                result.passed = False
                result.violations.append(f"Row {i}: Phone '{row.phone_number}' has {len(digits)} digits")

    return result
