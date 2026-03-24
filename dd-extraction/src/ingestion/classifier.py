"""
File classifier: detects file type (invoice/contract/report) and carrier.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import CARRIER_REGISTRY


@dataclass
class FileInfo:
    path: Path
    file_type: str  # "invoice", "carrier_report", "contract", "unknown"
    carrier_key: Optional[str]  # key into CARRIER_REGISTRY
    carrier_name: Optional[str]  # display name
    format: str  # "pdf", "xlsx", "xls", "csv", "msg", "docx", "eml", "unknown"


# Known folder name patterns for detection
_TYPE_FOLDER_PATTERNS = {
    "invoice": ["Invoices", "Invoice"],
    "carrier_report": ["Carrier Reports", "Portal Data"],
    "contract": ["Contracts", "Contract"],
    "csr": ["CSRs", "CSR"],
}

# Map folder names to carrier keys
_FOLDER_TO_CARRIER: dict[str, str] = {}
for key, info in CARRIER_REGISTRY.items():
    for folder_field in ["invoice_folder", "report_folder", "contract_folder"]:
        folder_name = info[folder_field]
        _FOLDER_TO_CARRIER[folder_name.lower()] = key


def _detect_format(path: Path) -> str:
    """Detect file format from extension."""
    ext = path.suffix.lower()
    format_map = {
        ".pdf": "pdf",
        ".xlsx": "xlsx",
        ".xls": "xls",
        ".csv": "csv",
        ".msg": "msg",
        ".docx": "docx",
        ".eml": "eml",
        ".doc": "doc",
    }
    return format_map.get(ext, "unknown")


def _detect_file_type(path: Path) -> str:
    """Detect file type from directory structure."""
    parts = [p.lower() for p in path.parts]
    for file_type, patterns in _TYPE_FOLDER_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in parts:
                return file_type
    return "unknown"


def _detect_carrier(path: Path) -> tuple[Optional[str], Optional[str]]:
    """Detect carrier from parent folder names."""
    # Walk up the directory tree looking for carrier folder matches
    for parent in path.parents:
        folder_lower = parent.name.lower()
        if folder_lower in _FOLDER_TO_CARRIER:
            key = _FOLDER_TO_CARRIER[folder_lower]
            return key, CARRIER_REGISTRY[key]["display_name"]

    # Fallback: check filename for carrier names
    fname_lower = path.stem.lower()
    for key, info in CARRIER_REGISTRY.items():
        if key in fname_lower or info["display_name"].lower() in fname_lower:
            return key, info["display_name"]

    return None, None


def classify_file(path: Path) -> FileInfo:
    """Classify a single file by type, carrier, and format."""
    path = Path(path)
    return FileInfo(
        path=path,
        file_type=_detect_file_type(path),
        carrier_key=_detect_carrier(path)[0],
        carrier_name=_detect_carrier(path)[1],
        format=_detect_format(path),
    )


def classify_directory(directory: Path, carrier_key: Optional[str] = None) -> list[FileInfo]:
    """Classify all files in a directory tree, optionally filtered by carrier."""
    results = []
    directory = Path(directory)
    for path in sorted(directory.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            info = classify_file(path)
            if carrier_key is None or info.carrier_key == carrier_key:
                results.append(info)
    return results


def get_carrier_files(input_dir: Path, carrier_key: str) -> dict[str, list[FileInfo]]:
    """Get all files for a specific carrier, grouped by file type."""
    all_files = classify_directory(input_dir, carrier_key=carrier_key)
    grouped = {"invoice": [], "carrier_report": [], "contract": [], "csr": [], "unknown": []}
    for f in all_files:
        grouped.setdefault(f.file_type, []).append(f)
    return grouped
