"""
54-column Dynamics inventory schema definition.
Maps columns A-BB with section areas, requirement tiers, and validation rules.
Updated to match the new sample inventory template (54 columns).
"""
from dataclasses import dataclass, field, fields, asdict
from typing import Optional


# --- Column Schema Definition ---

@dataclass
class ColumnDef:
    letter: str
    name: str
    section_area: str
    requirement_tier: str
    data_type: str = "text"


# The full 54-column schema matching the new inventory template
# Removed from old 60-col: Currency, Conversion Rate, Monthly Recurring Cost per Currency,
#   Point to Number, Z Location Name If One Given By Carrier, Billing Per Contract
# Renamed: "Service Address 1" -> "Service Address"
# Reordered contract area: Contract File Name now at index 50 (before Contract Number)
INVENTORY_SCHEMA: list[ColumnDef] = [
    # DD2 Information Area (A-C)
    ColumnDef("A", "Status", "DD2 Information Area", "Required"),
    ColumnDef("B", "Inventory creation questions, concerns, or notes.", "DD2 Information Area", "Only Used as Needed"),
    ColumnDef("C", "*Contract Info received", "DD2 Information Area", "Required"),

    # File Information Area (D-F)
    ColumnDef("D", "Invoice File Name", "File Information Area", "Required"),
    ColumnDef("E", "Files Used For Inventory", "File Information Area", ""),
    ColumnDef("F", "Billing Name", "File Information Area", "Required"),

    # Location Area (G-L)
    ColumnDef("G", "Service Address", "Location Area", "Required"),
    ColumnDef("H", "Service Address 2", "Location Area", ""),
    ColumnDef("I", "City", "Location Area", ""),
    ColumnDef("J", "State", "Location Area", ""),
    ColumnDef("K", "Zip", "Location Area", ""),
    ColumnDef("L", "Country", "Location Area", ""),

    # Carrier Information Area (M-R)
    ColumnDef("M", "Carrier", "Carrier Information Area", "Required"),
    ColumnDef("N", "Master Account", "Carrier Information Area", "Required if Applicable"),
    ColumnDef("O", "Carrier Account Number", "Carrier Information Area", "Required"),
    ColumnDef("P", "Sub-Account Number", "Carrier Information Area", ""),
    ColumnDef("Q", "Sub-Account Number 2", "Carrier Information Area", ""),
    ColumnDef("R", "BTN", "Carrier Information Area", "Required if Applicable"),

    # Service Area (S-W)
    ColumnDef("S", "Phone Number", "Service Area", "Required if Applicable"),
    ColumnDef("T", "Carrier Circuit Number", "Service Area", "Required if Applicable"),
    ColumnDef("U", "Additional Circuit IDs", "Service Area", "Only Used as Needed"),
    ColumnDef("V", "Service Type", "Service Area", "Required"),
    ColumnDef("W", "Service Type 2", "Service Area", "Only Used as Needed"),

    # Component Area (X-AD)
    ColumnDef("X", "USOC", "Component Area", "Only Used as Needed"),
    ColumnDef("Y", "Service or Component", "Component Area", "Required"),
    ColumnDef("Z", "Component or Feature Name", "Component Area", "Required"),
    ColumnDef("AA", "Monthly Recurring Cost", "Component Area", "Required", "currency"),
    ColumnDef("AB", "Quanity", "Component Area", "Required if Applicable", "number"),
    ColumnDef("AC", "Cost Per Unit", "Component Area", "Required if Applicable", "currency"),
    ColumnDef("AD", "Charge Type", "Component Area", "Required"),

    # Additional Component Area (AE-AI)
    ColumnDef("AE", "# Calls", "Additional Component Area", "List if Available", "number"),
    ColumnDef("AF", "LD Minutes", "Additional Component Area", "", "number"),
    ColumnDef("AG", "LD Cost", "Additional Component Area", "", "currency"),
    ColumnDef("AH", "Rate", "Additional Component Area", ""),
    ColumnDef("AI", "LD Flat Rate", "Additional Component Area", "", "currency"),

    # Circuit Speed Area (AJ-AL)
    ColumnDef("AJ", "Port Speed", "Circuit Speed Area", "Required if Applicable"),
    ColumnDef("AK", "Access Speed", "Circuit Speed Area", "Required if Applicable"),
    ColumnDef("AL", "Upload Speed", "Circuit Speed Area", ""),

    # Z Location Area (AM-AR)
    ColumnDef("AM", "Z Address 1", "Z Location Area", ""),
    ColumnDef("AN", "Z Address 2", "Z Location Area", ""),
    ColumnDef("AO", "Z City", "Z Location Area", ""),
    ColumnDef("AP", "Z State", "Z Location Area", ""),
    ColumnDef("AQ", "Z Zip Code", "Z Location Area", ""),
    ColumnDef("AR", "Z Country", "Z Location Area", ""),

    # Contract Area (AS-BB)
    ColumnDef("AS", "*Contract - Term Months", "CONTRACT AREA", "Required for Ticket Closure", "number"),
    ColumnDef("AT", "*Contract - Begin Date", "CONTRACT AREA", "", "date"),
    ColumnDef("AU", "*Contract - Expiration Date", "CONTRACT AREA", "", "date"),
    ColumnDef("AV", "*Currently Month-to-Month", "CONTRACT AREA", "Required for Ticket Closure"),
    ColumnDef("AW", "Month to Month or Less Than a Year Remaining", "CONTRACT AREA", "Required for Ticket Closure"),
    ColumnDef("AX", "Contract File Name", "CONTRACT AREA", "Required for Ticket Closure"),
    ColumnDef("AY", "Contract Number", "CONTRACT AREA", "Only Used as Needed"),
    ColumnDef("AZ", "2nd Contract Number", "CONTRACT AREA", "Only Used as Needed"),
    ColumnDef("BA", "*Auto Renew", "CONTRACT AREA", "Required for Ticket Closure"),
    ColumnDef("BB", "Auto Renewal Notes and Removal Requirements", "CONTRACT AREA", "Only Used as Needed"),
]

# Quick lookup dictionaries
SCHEMA_BY_LETTER = {col.letter: col for col in INVENTORY_SCHEMA}
SCHEMA_BY_NAME = {col.name: col for col in INVENTORY_SCHEMA}
COLUMN_NAMES = [col.name for col in INVENTORY_SCHEMA]
COLUMN_LETTERS = [col.letter for col in INVENTORY_SCHEMA]

# Required columns (must be populated for every row)
REQUIRED_COLUMNS = [col.name for col in INVENTORY_SCHEMA if col.requirement_tier == "Required"]

# Section area spans for merged header cells
SECTION_AREAS = {
    "DD2 Information Area": ("A", "C"),
    "File Information Area": ("D", "F"),
    "Location Area": ("G", "L"),
    "Carrier Information Area": ("M", "R"),
    "Service Area": ("S", "W"),
    "Component Area": ("X", "AD"),
    "Additional Component Area": ("AE", "AI"),
    "Circuit Speed Area": ("AJ", "AL"),
    "Z Location Area": ("AM", "AR"),
    "CONTRACT AREA": ("AS", "BB"),
}


# --- Dropdown Validation Lists ---

# Status dropdown (4 values)
STATUS_VALUES = [
    "Complete",
    "Withdrawn",
    "Pending",
    "Partially Obtained",
]

# 86 valid Service Types from the new template
SERVICE_TYPES = [
    "Account Level", "Analog Circuits", "Audit", "Broadband", "Calling Card",
    "CDN", "Cellular", "Centrex", "Cloud Direct Connection", "CO Muxed T1",
    "Collocation", "Conferencing", "CPE", "DaaS", "Dark Fiber",
    "Data Voice Bundled", "DIA", "Dial Up Internet", "DID", "DID Trunks",
    "DRaaS", "DS1", "DS3", "DSL", "E911",
    "Electronic Fax", "Ethernet", "Hosted VOIP", "Integrated Circuit",
    "Inventory Creation", "ISDN BRI", "ISDN PRI", "Listing", "Local Usage",
    "Long Distance", "MPLS", "NET MGMT", "PBX/Biz Trunks", "Point to Point",
    "POTS", "RCF", "SDWAN", "SIP Trunk", "Sonet",
    "Telecom Management", "Telecom Project Management", "TF - Dedicated",
    "TF - Switched", "TV", "UCaaS", "Usage", "Virus Protection",
    "Voice Mail", "VOIP DID", "VOIP Line", "VPLS", "VPN", "VTN",
    "Wireless Cellular Internet", "Wireless DIA",
    # Additional types
    "ABN", "AVTS", "Branch Office Extension (BOE)", "Cable Internet",
    "Cloud Storage", "Completelink", "DIA-Managed", "DIA-Unmanaged",
    "FIOS", "Foreign Exchange", "Hosting", "Integrated T1", "IP/Flex",
    "LD - Dedicated", "LD - Switched", "Managed Network Services", "MDA",
    "MPLS-Managed", "MPLS-Unmanaged", "P2P Interstate", "P2P Intrastate",
    "P2P Metro", "Payphone", "TEM - Enhanced", "Uverse", "Wireless Internet",
]

CHARGE_TYPES = [
    "MRC", "NRC", "OCC", "Prorated Charges",
    "Surcharge", "Taxes", "Usage",
]

SCU_CODES = ["S", "C", "U", "T\\S\\OCC"]

MONTH_TO_MONTH_VALUES = ["Yes", "No"]

# Kept for backward compatibility with qa.py and other consumers
END_USE_VALUES = ["Alarm", "Elevator", "Fax"]


# --- Inventory Row Dataclass ---

@dataclass
class InventoryRow:
    """Represents a single row in the 54-column inventory output."""
    # DD2 Information Area
    status: Optional[str] = None
    notes: Optional[str] = None
    contract_info_received: Optional[str] = None

    # File Information Area
    invoice_file_name: Optional[str] = None
    files_used_for_inventory: Optional[str] = None
    billing_name: Optional[str] = None

    # Location Area  (renamed: service_address_1 -> service_address)
    service_address: Optional[str] = None
    service_address_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None

    # Carrier Information Area
    carrier: Optional[str] = None
    master_account: Optional[str] = None
    carrier_account_number: Optional[str] = None
    sub_account_number: Optional[str] = None
    sub_account_number_2: Optional[str] = None
    btn: Optional[str] = None

    # Service Area
    phone_number: Optional[str] = None
    carrier_circuit_number: Optional[str] = None
    additional_circuit_ids: Optional[str] = None
    service_type: Optional[str] = None
    service_type_2: Optional[str] = None

    # Component Area  (removed: currency, conversion_rate, mrc_per_currency)
    usoc: Optional[str] = None
    service_or_component: Optional[str] = None  # S, C, U, or T\S\OCC
    component_or_feature_name: Optional[str] = None
    monthly_recurring_cost: Optional[float] = None
    quantity: Optional[float] = None
    cost_per_unit: Optional[float] = None
    charge_type: Optional[str] = None

    # Additional Component Area
    num_calls: Optional[float] = None
    ld_minutes: Optional[float] = None
    ld_cost: Optional[float] = None
    rate: Optional[float] = None
    ld_flat_rate: Optional[float] = None

    # Circuit Speed Area  (removed: point_to_number)
    port_speed: Optional[str] = None
    access_speed: Optional[str] = None
    upload_speed: Optional[str] = None

    # Z Location Area  (removed: z_location_name)
    z_service_address_1: Optional[str] = None
    z_service_address_2: Optional[str] = None
    z_city: Optional[str] = None
    z_state: Optional[str] = None
    z_zip: Optional[str] = None
    z_country: Optional[str] = None

    # Contract Area  (removed: billing_per_contract; reordered)
    contract_term: Optional[float] = None
    contract_begin_date: Optional[str] = None
    contract_expiration_date: Optional[str] = None
    currently_month_to_month: Optional[str] = None
    month_to_month_or_less: Optional[str] = None
    contract_file_name: Optional[str] = None
    contract_number: Optional[str] = None
    second_contract_number: Optional[str] = None
    auto_renew: Optional[str] = None
    auto_renewal_notes: Optional[str] = None

    # Metadata (not output columns)
    confidence: dict = field(default_factory=dict)
    source_files: list = field(default_factory=list)
    linkage_key: Optional[str] = None  # For S-C parent-child linking

    # --- Backward-compatibility aliases for old field names ---
    # These properties allow existing extraction code that writes to the old
    # field names to keep working without modification.

    @property
    def service_address_1(self):
        return self.service_address

    @service_address_1.setter
    def service_address_1(self, value):
        self.service_address = value

    @property
    def currency(self):
        return None

    @currency.setter
    def currency(self, value):
        pass  # silently discard — column removed

    @property
    def conversion_rate(self):
        return None

    @conversion_rate.setter
    def conversion_rate(self, value):
        pass  # silently discard — column removed

    @property
    def mrc_per_currency(self):
        return None

    @mrc_per_currency.setter
    def mrc_per_currency(self, value):
        pass  # silently discard — column removed

    @property
    def point_to_number(self):
        return None

    @point_to_number.setter
    def point_to_number(self, value):
        pass  # silently discard — column removed

    @property
    def z_location_name(self):
        return None

    @z_location_name.setter
    def z_location_name(self, value):
        pass  # silently discard — column removed

    @property
    def billing_per_contract(self):
        return None

    @billing_per_contract.setter
    def billing_per_contract(self, value):
        pass  # silently discard — column removed

    # Alias old field names that were renamed/repurposed in Contract Area
    @property
    def month_to_month_since(self):
        return self.month_to_month_or_less

    @month_to_month_since.setter
    def month_to_month_since(self, value):
        self.month_to_month_or_less = value

    @property
    def month_to_month_rate(self):
        return self.contract_number

    @month_to_month_rate.setter
    def month_to_month_rate(self, value):
        self.contract_number = value

    @property
    def auto_renewal_term(self):
        return self.second_contract_number

    @auto_renewal_term.setter
    def auto_renewal_term(self, value):
        self.second_contract_number = value

    def to_row_dict(self) -> dict:
        """Convert to ordered dict matching the 54-column names for output."""
        field_to_column = {
            "status": "Status",
            "notes": "Inventory creation questions, concerns, or notes.",
            "contract_info_received": "*Contract Info received",
            "invoice_file_name": "Invoice File Name",
            "files_used_for_inventory": "Files Used For Inventory",
            "billing_name": "Billing Name",
            "service_address": "Service Address",
            "service_address_2": "Service Address 2",
            "city": "City",
            "state": "State",
            "zip_code": "Zip",
            "country": "Country",
            "carrier": "Carrier",
            "master_account": "Master Account",
            "carrier_account_number": "Carrier Account Number",
            "sub_account_number": "Sub-Account Number",
            "sub_account_number_2": "Sub-Account Number 2",
            "btn": "BTN",
            "phone_number": "Phone Number",
            "carrier_circuit_number": "Carrier Circuit Number",
            "additional_circuit_ids": "Additional Circuit IDs",
            "service_type": "Service Type",
            "service_type_2": "Service Type 2",
            "usoc": "USOC",
            "service_or_component": "Service or Component",
            "component_or_feature_name": "Component or Feature Name",
            "monthly_recurring_cost": "Monthly Recurring Cost",
            "quantity": "Quanity",
            "cost_per_unit": "Cost Per Unit",
            "charge_type": "Charge Type",
            "num_calls": "# Calls",
            "ld_minutes": "LD Minutes",
            "ld_cost": "LD Cost",
            "rate": "Rate",
            "ld_flat_rate": "LD Flat Rate",
            "port_speed": "Port Speed",
            "access_speed": "Access Speed",
            "upload_speed": "Upload Speed",
            "z_service_address_1": "Z Address 1",
            "z_service_address_2": "Z Address 2",
            "z_city": "Z City",
            "z_state": "Z State",
            "z_zip": "Z Zip Code",
            "z_country": "Z Country",
            "contract_term": "*Contract - Term Months",
            "contract_begin_date": "*Contract - Begin Date",
            "contract_expiration_date": "*Contract - Expiration Date",
            "currently_month_to_month": "*Currently Month-to-Month",
            "month_to_month_or_less": "Month to Month or Less Than a Year Remaining",
            "contract_file_name": "Contract File Name",
            "contract_number": "Contract Number",
            "second_contract_number": "2nd Contract Number",
            "auto_renew": "*Auto Renew",
            "auto_renewal_notes": "Auto Renewal Notes and Removal Requirements",
        }
        result = {}
        for attr, col_name in field_to_column.items():
            result[col_name] = getattr(self, attr)
        return result

    @classmethod
    def column_field_map(cls) -> dict[str, str]:
        """Map column names to dataclass field names."""
        return {v: k for k, v in _build_field_to_column().items()}


def _build_field_to_column() -> dict[str, str]:
    """Internal helper to build field->column mapping (54 columns)."""
    return {
        "status": "Status",
        "notes": "Inventory creation questions, concerns, or notes.",
        "contract_info_received": "*Contract Info received",
        "invoice_file_name": "Invoice File Name",
        "files_used_for_inventory": "Files Used For Inventory",
        "billing_name": "Billing Name",
        "service_address": "Service Address",
        "service_address_2": "Service Address 2",
        "city": "City",
        "state": "State",
        "zip_code": "Zip",
        "country": "Country",
        "carrier": "Carrier",
        "master_account": "Master Account",
        "carrier_account_number": "Carrier Account Number",
        "sub_account_number": "Sub-Account Number",
        "sub_account_number_2": "Sub-Account Number 2",
        "btn": "BTN",
        "phone_number": "Phone Number",
        "carrier_circuit_number": "Carrier Circuit Number",
        "additional_circuit_ids": "Additional Circuit IDs",
        "service_type": "Service Type",
        "service_type_2": "Service Type 2",
        "usoc": "USOC",
        "service_or_component": "Service or Component",
        "component_or_feature_name": "Component or Feature Name",
        "monthly_recurring_cost": "Monthly Recurring Cost",
        "quantity": "Quanity",
        "cost_per_unit": "Cost Per Unit",
        "charge_type": "Charge Type",
        "num_calls": "# Calls",
        "ld_minutes": "LD Minutes",
        "ld_cost": "LD Cost",
        "rate": "Rate",
        "ld_flat_rate": "LD Flat Rate",
        "port_speed": "Port Speed",
        "access_speed": "Access Speed",
        "upload_speed": "Upload Speed",
        "z_service_address_1": "Z Address 1",
        "z_service_address_2": "Z Address 2",
        "z_city": "Z City",
        "z_state": "Z State",
        "z_zip": "Z Zip Code",
        "z_country": "Z Country",
        "contract_term": "*Contract - Term Months",
        "contract_begin_date": "*Contract - Begin Date",
        "contract_expiration_date": "*Contract - Expiration Date",
        "currently_month_to_month": "*Currently Month-to-Month",
        "month_to_month_or_less": "Month to Month or Less Than a Year Remaining",
        "contract_file_name": "Contract File Name",
        "contract_number": "Contract Number",
        "second_contract_number": "2nd Contract Number",
        "auto_renew": "*Auto Renew",
        "auto_renewal_notes": "Auto Renewal Notes and Removal Requirements",
    }


# Column name -> field name reverse mapping
COLUMN_TO_FIELD = {v: k for k, v in _build_field_to_column().items()}
FIELD_TO_COLUMN = _build_field_to_column()
