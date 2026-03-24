"""
Abstract base class for carrier-specific extractors.
Each carrier implements this interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.mapping.schema import InventoryRow


@dataclass
class ExtractionResult:
    """Result of a carrier extraction run."""
    carrier_key: str
    carrier_name: str
    rows: list[InventoryRow]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


class CarrierExtractor(ABC):
    """
    Abstract base for carrier-specific extraction.
    Each carrier implements extract() which returns InventoryRows.
    """

    @property
    @abstractmethod
    def carrier_key(self) -> str:
        """Unique carrier identifier (e.g., 'charter')."""
        ...

    @property
    @abstractmethod
    def carrier_name(self) -> str:
        """Display name (e.g., 'Charter Communications')."""
        ...

    @abstractmethod
    def extract(
        self,
        invoice_dir: Optional[Path],
        report_dir: Optional[Path],
        contract_dir: Optional[Path],
        api_key: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Run extraction for this carrier.

        Args:
            invoice_dir: Directory containing invoice PDFs
            report_dir: Directory containing carrier reports (XLSX/CSV)
            contract_dir: Directory containing contract files
            api_key: Optional API key for OCR services
        """
        ...
