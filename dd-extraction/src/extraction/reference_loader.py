"""
Reference data loader.
Loads the NSS Inventory File (ground truth) to use as a template
for column mapping, carrier name resolution, and validation.
"""
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# The 60 reference columns (with trailing spaces stripped)
REFERENCE_COLUMNS = [
    "Status",
    "Inventory creation questions, concerns, or notes.",
    "*Contract Info received",
    "Invoice File Name",
    "Files Used For Inventory",
    "Billing Name",
    "Service Address 1",
    "Service Address 2",
    "City",
    "State",
    "Zip",
    "Country",
    "Carrier",
    "Master Account",
    "Carrier Account Number",
    "Sub-Account Number",
    "Sub-Account Number 2",
    "BTN",
    "Phone Number",
    "Carrier Circuit Number",
    "Additional Circuit IDs",
    "Service Type",
    "Service Type 2",
    "USOC",
    "Service or Component",
    "Component or Feature Name",
    "Monthly Recurring Cost",
    "Quanity",
    "Cost Per Unit",
    "Currency",
    "Conversion Rate",
    "Monthly Recurring Cost per Currency",
    "Charge Type",
    "# Calls",
    "LD Minutes",
    "LD Cost",
    "Rate",
    "LD Flat Rate",
    "Point to Number",
    "Port Speed",
    "Access Speed",
    "Upload Speed",
    "Z Location Name If One Given By Carrier",
    "Z Address 1",
    "Z Address 2",
    "Z City",
    "Z State",
    "Z Zip Code",
    "Z Country",
    "*Contract - Term Months",
    "*Contract - Begin Date",
    "*Contract - Expiration Date",
    "Billing Per Contract",
    "*Currently Month-to-Month",
    "Month to Month or Less Than a Year Remaining",
    "Contract File Name",
    "Contract Number",
    "2nd Contract Number",
    "*Auto Renew",
    "Auto Renewal Notes and Removal Requirements",
]


class ReferenceData:
    """Loads and provides access to reference inventory data."""

    def __init__(self, reference_path: Path, header_row: int = 2):
        self.path = reference_path
        self.header_row = header_row
        self._df: Optional[pd.DataFrame] = None
        self._carrier_names: Optional[dict] = None
        self._carrier_accounts: Optional[dict] = None

    def _load(self):
        if self._df is not None:
            return
        logger.info(f"Loading reference data from: {self.path}")
        self._df = pd.read_excel(
            self.path,
            sheet_name="Baseline",
            header=self.header_row,
        )
        # Strip column whitespace
        self._df.columns = [c.strip() for c in self._df.columns]
        logger.info(f"Reference data loaded: {len(self._df)} rows, {len(self._df.columns)} columns")

    @property
    def df(self) -> pd.DataFrame:
        self._load()
        return self._df

    @property
    def total_rows(self) -> int:
        return len(self.df)

    def get_carrier_names(self) -> dict[str, str]:
        """Return mapping of lowercase carrier key -> exact carrier name from reference."""
        if self._carrier_names is None:
            self._carrier_names = {}
            for name in self.df["Carrier"].dropna().unique():
                key = str(name).strip().lower().replace(" ", "_")
                self._carrier_names[key] = str(name).strip()
        return self._carrier_names

    def get_carrier_rows(self, carrier_name: str) -> pd.DataFrame:
        """Get all reference rows for a specific carrier."""
        return self.df[self.df["Carrier"] == carrier_name].copy()

    def get_carrier_accounts(self, carrier_name: str) -> list[str]:
        """Get unique account numbers for a carrier."""
        sub = self.get_carrier_rows(carrier_name)
        return [str(x) for x in sub["Carrier Account Number"].dropna().unique()]

    def get_carrier_service_types(self, carrier_name: str) -> list[str]:
        """Get unique service types for a carrier."""
        sub = self.get_carrier_rows(carrier_name)
        return [str(x) for x in sub["Service Type"].dropna().unique()]

    def get_scu_pattern(self, carrier_name: str) -> dict[str, int]:
        """Get S/C/U/T\\S\\OCC row count pattern for a carrier."""
        sub = self.get_carrier_rows(carrier_name)
        return sub["Service or Component"].value_counts().to_dict()

    def get_all_carriers_summary(self) -> list[dict]:
        """Get a summary of all carriers in the reference data."""
        results = []
        for carrier in self.df["Carrier"].dropna().unique():
            sub = self.df[self.df["Carrier"] == carrier]
            results.append({
                "carrier": str(carrier),
                "total_rows": len(sub),
                "accounts": sub["Carrier Account Number"].nunique(),
                "service_types": sub["Service Type"].nunique(),
                "scu_pattern": sub["Service or Component"].value_counts().to_dict(),
            })
        return sorted(results, key=lambda x: -x["total_rows"])

    def get_carrier_feature_names(self, carrier_name: str, service_type: str) -> list[str]:
        """Get unique component/feature names for a carrier and service type."""
        sub = self.get_carrier_rows(carrier_name)
        sub = sub[sub["Service Type"] == service_type]
        c_rows = sub[sub["Service or Component"] == "C"]
        return [str(x) for x in c_rows["Component or Feature Name"].dropna().unique()]

    def get_carrier_charge_types(self, carrier_name: str) -> list[str]:
        """Get unique charge types for a carrier."""
        sub = self.get_carrier_rows(carrier_name)
        return [str(x) for x in sub["Charge Type"].dropna().unique()]


def load_reference(reference_path: Path) -> ReferenceData:
    """Create and return a ReferenceData instance."""
    return ReferenceData(reference_path)
