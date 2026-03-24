"""
Excel/CSV parser with header detection.
Handles XLSX, XLS, and CSV files, including files without headers.
"""
import pandas as pd
from pathlib import Path
from typing import Optional


def parse_excel(
    path: Path,
    sheet_name: Optional[str] = None,
    header_row: Optional[int] = 0,
    has_headers: bool = True,
) -> pd.DataFrame:
    """
    Parse an Excel or CSV file into a DataFrame.

    Args:
        path: Path to the file
        sheet_name: Sheet name for Excel files (None = first sheet)
        header_row: Row index for headers (0-based). None = no headers.
        has_headers: If False, assigns generic column names (col_0, col_1, ...)
    """
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".csv":
        if has_headers:
            df = pd.read_csv(path, header=header_row)
        else:
            df = pd.read_csv(path, header=None)
            df.columns = [f"col_{i}" for i in range(len(df.columns))]
    elif ext in (".xlsx", ".xls"):
        kwargs = {"sheet_name": sheet_name or 0}
        if has_headers:
            kwargs["header"] = header_row
        else:
            kwargs["header"] = None
        df = pd.read_excel(path, **kwargs)
        if not has_headers:
            df.columns = [f"col_{i}" for i in range(len(df.columns))]
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    # Drop completely empty rows
    df = df.dropna(how="all").reset_index(drop=True)

    # Strip whitespace from string columns (safely handles mixed types)
    for col in df.select_dtypes(include=["object"]).columns:
        try:
            df[col] = df[col].astype(str).str.strip().replace({"nan": None, "None": None, "": None, "NaT": None})
        except Exception:
            pass  # Skip columns that can't be cleaned

    return df


def parse_excel_all_sheets(path: Path) -> dict[str, pd.DataFrame]:
    """Parse all sheets from an Excel file."""
    path = Path(path)
    return pd.read_excel(path, sheet_name=None)


def detect_header_row(path: Path, sheet_name: Optional[str] = None, max_rows: int = 10) -> int:
    """
    Auto-detect which row contains column headers.
    Heuristic: the row with the most non-null string values that look like headers.
    """
    df_raw = pd.read_excel(path, sheet_name=sheet_name or 0, header=None, nrows=max_rows)
    best_row = 0
    best_score = 0
    for i in range(min(max_rows, len(df_raw))):
        row = df_raw.iloc[i]
        # Score: count of non-null string values that are likely headers
        score = sum(
            1 for v in row
            if isinstance(v, str) and len(v) > 1 and not v.replace(".", "").replace("-", "").isdigit()
        )
        if score > best_score:
            best_score = score
            best_row = i
    return best_row
