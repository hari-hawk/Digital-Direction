"""File system operations: scan directories, classify documents."""
import os
from pathlib import Path
from typing import Optional

from models.schemas import DocumentInfo, CarrierDocuments

# Document type detection from folder names
DOC_TYPE_MAP = {
    "invoices": "invoice",
    "invoice": "invoice",
    "contracts": "contract",
    "contract": "contract",
    "carrier reports, portal data, etc": "carrier_report",
    "carrier reports": "carrier_report",
    "csrs": "csr",
    "csr": "csr",
}

VALID_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".msg", ".docx", ".eml", ".doc"}


def scan_project_files(input_dir: str) -> dict[str, CarrierDocuments]:
    """Scan project input directory and return files grouped by carrier."""
    input_path = Path(input_dir)
    if not input_path.exists():
        return {}

    carriers: dict[str, dict] = {}

    for root, dirs, files in os.walk(input_path):
        root_path = Path(root)
        rel = root_path.relative_to(input_path)
        parts = list(rel.parts)

        if len(parts) < 2:
            continue

        # Detect document type from path
        doc_type = None
        for part in parts:
            dt = DOC_TYPE_MAP.get(part.lower())
            if dt:
                doc_type = dt
                break

        if not doc_type:
            continue

        # Carrier is the deepest folder
        carrier = parts[-1]

        for fname in files:
            fpath = root_path / fname
            ext = fpath.suffix.lower()
            if ext not in VALID_EXTENSIONS or fname.startswith("."):
                continue

            doc = DocumentInfo(
                name=fname,
                path=str(fpath),
                carrier=carrier,
                doc_type=doc_type,
                format=ext.lstrip("."),
                size_bytes=fpath.stat().st_size,
            )

            if carrier not in carriers:
                carriers[carrier] = {
                    "carrier": carrier,
                    "invoices": [],
                    "contracts": [],
                    "carrier_reports": [],
                    "csrs": [],
                }

            type_key = {
                "invoice": "invoices",
                "contract": "contracts",
                "carrier_report": "carrier_reports",
                "csr": "csrs",
            }.get(doc_type, "invoices")

            carriers[carrier][type_key].append(doc)

    # Convert to CarrierDocuments
    result = {}
    for cname, data in sorted(carriers.items()):
        result[cname] = CarrierDocuments(**data)

    return result


def get_all_documents_flat(input_dir: str) -> list[DocumentInfo]:
    """Get flat list of all documents."""
    carriers = scan_project_files(input_dir)
    docs = []
    for cd in carriers.values():
        docs.extend(cd.invoices)
        docs.extend(cd.contracts)
        docs.extend(cd.carrier_reports)
        docs.extend(cd.csrs)
    return docs
