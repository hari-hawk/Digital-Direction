"""
Excel output generator.
Produces Dynamics-ready inventory file with 3-tier headers, dropdowns, and formatting.
"""
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from src.mapping.schema import (
    INVENTORY_SCHEMA, SECTION_AREAS, COLUMN_NAMES,
    SERVICE_TYPES, CHARGE_TYPES, SCU_CODES, END_USE_VALUES,
    MONTH_TO_MONTH_VALUES, InventoryRow,
)

# Styling constants
HEADER_FONT = Font(bold=True, size=11)
SECTION_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
SECTION_FONT = Font(bold=True, color="FFFFFF", size=11)
TIER_FILL = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)


def generate_inventory_excel(
    rows: list[InventoryRow],
    output_path: Path,
    carrier_name: str = "Charter Communications",
) -> Path:
    """
    Generate the Dynamics-ready Excel inventory file.

    Creates:
    - Baseline sheet with 3-tier headers and data
    - Dropdowns sheet with validation lists
    - TFs/DIDs sheet (empty for Charter)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()

    # --- Baseline Sheet ---
    ws = wb.active
    ws.title = "Baseline"
    _write_baseline_sheet(ws, rows)

    # --- Dropdowns Sheet ---
    ws_dd = wb.create_sheet("Dropdowns")
    _write_dropdowns_sheet(ws_dd)

    # --- TFs/DIDs Sheet ---
    ws_tf = wb.create_sheet("TF DID")
    _write_tf_did_sheet(ws_tf)

    # --- Apply data validation ---
    _apply_data_validation(wb["Baseline"], len(rows))

    wb.save(str(output_path))
    return output_path


def _write_baseline_sheet(ws, rows: list[InventoryRow]):
    """Write the Baseline sheet with 3-tier header structure."""
    num_cols = len(INVENTORY_SCHEMA)

    # --- Row 1: Section Area headers (merged cells) ---
    for section_name, (start_letter, end_letter) in SECTION_AREAS.items():
        start_idx = _letter_to_col_idx(start_letter)
        end_idx = _letter_to_col_idx(end_letter)

        ws.merge_cells(
            start_row=1, start_column=start_idx,
            end_row=1, end_column=end_idx,
        )
        cell = ws.cell(row=1, column=start_idx, value=section_name)
        cell.font = SECTION_FONT
        cell.fill = SECTION_FILL
        cell.alignment = Alignment(horizontal="center")

    # --- Row 2: Requirement Tier flags ---
    for i, col_def in enumerate(INVENTORY_SCHEMA):
        cell = ws.cell(row=2, column=i + 1, value=col_def.requirement_tier)
        cell.font = Font(italic=True, size=9)
        cell.fill = TIER_FILL
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    # --- Row 3: Column Names ---
    for i, col_def in enumerate(INVENTORY_SCHEMA):
        cell = ws.cell(row=3, column=i + 1, value=col_def.name)
        cell.font = HEADER_FONT
        cell.border = THIN_BORDER
        cell.alignment = Alignment(wrap_text=True)

    # --- Row 4+: Data ---
    for row_idx, inv_row in enumerate(rows, start=4):
        row_dict = inv_row.to_row_dict()
        for col_idx, col_def in enumerate(INVENTORY_SCHEMA):
            value = row_dict.get(col_def.name)
            cell = ws.cell(row=row_idx, column=col_idx + 1, value=value)
            cell.border = THIN_BORDER

    # --- Formatting ---
    # Freeze panes at row 4 (below headers)
    ws.freeze_panes = "A4"

    # Auto-adjust column widths (approximate)
    for i, col_def in enumerate(INVENTORY_SCHEMA):
        col_letter = get_column_letter(i + 1)
        max_width = max(len(col_def.name), 12)
        ws.column_dimensions[col_letter].width = min(max_width + 2, 30)


def _write_dropdowns_sheet(ws):
    """Write dropdown validation lists."""
    # Column A: Service Types
    ws.cell(row=1, column=1, value="Service Type").font = HEADER_FONT
    for i, val in enumerate(SERVICE_TYPES, start=2):
        ws.cell(row=i, column=1, value=val)

    # Column B: Charge Types
    ws.cell(row=1, column=2, value="Charge Type").font = HEADER_FONT
    for i, val in enumerate(CHARGE_TYPES, start=2):
        ws.cell(row=i, column=2, value=val)

    # Column C: S/C/U Codes
    ws.cell(row=1, column=3, value="Service or Component").font = HEADER_FONT
    for i, val in enumerate(SCU_CODES, start=2):
        ws.cell(row=i, column=3, value=val)

    # Column D: End Use
    ws.cell(row=1, column=4, value="End Use").font = HEADER_FONT
    for i, val in enumerate(END_USE_VALUES, start=2):
        ws.cell(row=i, column=4, value=val)

    # Column E: Month-to-Month
    ws.cell(row=1, column=5, value="Currently Month-to-Month").font = HEADER_FONT
    for i, val in enumerate(MONTH_TO_MONTH_VALUES, start=2):
        ws.cell(row=i, column=5, value=val)

    # Adjust widths
    for col in range(1, 6):
        ws.column_dimensions[get_column_letter(col)].width = 25


def _write_tf_did_sheet(ws):
    """Write TFs/DIDs sheet (empty for Charter)."""
    headers = ["Vendor", "Account", "Subaccount", "DID", "TN"]
    for i, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=i, value=h)
        cell.font = HEADER_FONT
        cell.border = THIN_BORDER


def _apply_data_validation(ws, num_rows: int):
    """Apply dropdown data validation to the Baseline sheet."""
    if num_rows == 0:
        return

    last_row = num_rows + 3  # 3 header rows + data

    # Service Type (column V = 22)
    dv_service = DataValidation(
        type="list",
        formula1=f"Dropdowns!$A$2:$A${len(SERVICE_TYPES) + 1}",
        allow_blank=True,
    )
    dv_service.error = "Invalid Service Type"
    dv_service.errorTitle = "Service Type"
    ws.add_data_validation(dv_service)
    dv_service.add(f"V4:V{last_row}")

    # Charge Type (column AG = 33)
    dv_charge = DataValidation(
        type="list",
        formula1=f"Dropdowns!$B$2:$B${len(CHARGE_TYPES) + 1}",
        allow_blank=True,
    )
    dv_charge.error = "Invalid Charge Type"
    ws.add_data_validation(dv_charge)
    dv_charge.add(f"AG4:AG{last_row}")

    # Service or Component (column Y = 25)
    dv_scu = DataValidation(
        type="list",
        formula1=f"Dropdowns!$C$2:$C${len(SCU_CODES) + 1}",
        allow_blank=True,
    )
    ws.add_data_validation(dv_scu)
    dv_scu.add(f"Y4:Y{last_row}")

    # Month-to-Month (column BB = 54)
    dv_mtm = DataValidation(
        type="list",
        formula1="Dropdowns!$E$2:$E$3",
        allow_blank=True,
    )
    ws.add_data_validation(dv_mtm)
    dv_mtm.add(f"BB4:BB{last_row}")


def _letter_to_col_idx(letter: str) -> int:
    """Convert Excel column letter to 1-based index."""
    result = 0
    for char in letter.upper():
        result = result * 26 + (ord(char) - ord('A') + 1)
    return result
