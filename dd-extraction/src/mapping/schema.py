"""
60-column Dynamics inventory schema definition.
Maps columns A-BH with section areas, requirement tiers, and validation rules.
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


# The full 60-column schema matching the NSS Inventory File
INVENTORY_SCHEMA: list[ColumnDef] = [
    # DD2 Information Area (A-C)
    ColumnDef("A", "Status", "DD2 Information Area", "Required"),
    ColumnDef("B", "Inventory creation questions, concerns, or notes.", "DD2 Information Area", "Only Used as Needed"),
    ColumnDef("C", "*Contract Info received", "DD2 Information Area", "Required if Applicable"),

    # File Information Area (D-F)
    ColumnDef("D", "Invoice File Name", "File Information Area", "Required"),
    ColumnDef("E", "Files Used For Inventory", "File Information Area", "Required if Applicable"),
    ColumnDef("F", "Billing Name", "File Information Area", "Required"),

    # Location Area (G-L)
    ColumnDef("G", "Service Address 1", "Location Area", "Required"),
    ColumnDef("H", "Service Address 2", "Location Area", "Only Used as Needed"),
    ColumnDef("I", "City", "Location Area", "Required"),
    ColumnDef("J", "State", "Location Area", "Required"),
    ColumnDef("K", "Zip", "Location Area", "Required"),
    ColumnDef("L", "Country", "Location Area", "Required if Applicable"),

    # Carrier Information Area (M-R)
    ColumnDef("M", "Carrier", "Carrier Information Area", "Required"),
    ColumnDef("N", "Master Account", "Carrier Information Area", "Required if Applicable"),
    ColumnDef("O", "Carrier Account Number", "Carrier Information Area", "Required"),
    ColumnDef("P", "Sub-Account Number", "Carrier Information Area", "Required if Applicable"),
    ColumnDef("Q", "Sub-Account Number 2", "Carrier Information Area", "Only Used as Needed"),
    ColumnDef("R", "BTN", "Carrier Information Area", "Required if Applicable"),

    # Service Area (S-W)
    ColumnDef("S", "Phone Number", "Service Area", "Required if Applicable"),
    ColumnDef("T", "Carrier Circuit Number", "Service Area", "Required if Applicable"),
    ColumnDef("U", "Additional Circuit IDs", "Service Area", "Only Used as Needed"),
    ColumnDef("V", "Service Type", "Service Area", "Required"),
    ColumnDef("W", "Service Type 2", "Service Area", "Only Used as Needed"),

    # Component Area (X-AG)
    ColumnDef("X", "USOC", "Component Area", "Required if Applicable"),
    ColumnDef("Y", "Service or Component", "Component Area", "Required"),
    ColumnDef("Z", "Component or Feature Name", "Component Area", "Required if Applicable"),
    ColumnDef("AA", "Monthly Recurring Cost", "Component Area", "Required", "currency"),
    ColumnDef("AB", "Quanity", "Component Area", "Required if Applicable", "number"),
    ColumnDef("AC", "Cost Per Unit", "Component Area", "Required if Applicable", "currency"),
    ColumnDef("AD", "Currency", "Component Area", "Required if Applicable"),
    ColumnDef("AE", "Conversion Rate", "Component Area", "Only Used as Needed", "number"),
    ColumnDef("AF", "Monthly Recurring Cost per Currency", "Component Area", "Only Used as Needed", "currency"),
    ColumnDef("AG", "Charge Type", "Component Area", "Required"),

    # Additional Component Area (AH-AL)
    ColumnDef("AH", "# Calls", "Additional Component Area", "List if Available", "number"),
    ColumnDef("AI", "LD Minutes", "Additional Component Area", "List if Available", "number"),
    ColumnDef("AJ", "LD Cost", "Additional Component Area", "List if Available", "currency"),
    ColumnDef("AK", "Rate", "Additional Component Area", "List if Available", "number"),
    ColumnDef("AL", "LD Flat Rate", "Additional Component Area", "List if Available", "currency"),

    # Circuit Speed Area (AM-AP)
    ColumnDef("AM", "Point to Number", "Circuit Speed Area", "Only Used as Needed"),
    ColumnDef("AN", "Port Speed", "Circuit Speed Area", "Required if Applicable"),
    ColumnDef("AO", "Access Speed", "Circuit Speed Area", "Required if Applicable"),
    ColumnDef("AP", "Upload Speed", "Circuit Speed Area", "Only Used as Needed"),

    # Z Location Area (AQ-AW)
    ColumnDef("AQ", "Z Address 1", "Z Location Area", "Required for Ticket Closure"),
    ColumnDef("AR", "Z Address 2", "Z Location Area", "Only Used as Needed"),
    ColumnDef("AS", "Z City", "Z Location Area", "Required for Ticket Closure"),
    ColumnDef("AT", "Z State", "Z Location Area", "Required for Ticket Closure"),
    ColumnDef("AU", "Z Zip Code", "Z Location Area", "Required for Ticket Closure"),
    ColumnDef("AV", "Z Country", "Z Location Area", "Only Used as Needed"),
    ColumnDef("AW", "Z Location Name If One Given By Carrier", "Z Location Area", "Only Used as Needed"),

    # Contract Area (AX-BH)
    ColumnDef("AX", "*Contract - Term Months", "Contract Area", "Required for Ticket Closure", "number"),
    ColumnDef("AY", "*Contract - Begin Date", "Contract Area", "Required for Ticket Closure", "date"),
    ColumnDef("AZ", "*Contract - Expiration Date", "Contract Area", "Required for Ticket Closure", "date"),
    ColumnDef("BA", "Billing Per Contract", "Contract Area", "Required for Ticket Closure", "currency"),
    ColumnDef("BB", "*Currently Month-to-Month", "Contract Area", "Required for Ticket Closure"),
    ColumnDef("BC", "Month to Month or Less Than a Year Remaining", "Contract Area", "Only Used as Needed", "date"),
    ColumnDef("BD", "Contract Number", "Contract Area", "Only Used as Needed"),
    ColumnDef("BE", "Contract File Name", "Contract Area", "Required if Applicable"),
    ColumnDef("BF", "2nd Contract Number", "Contract Area", "Only Used as Needed"),
    ColumnDef("BG", "*Auto Renew", "Contract Area", "Required for Ticket Closure"),
    ColumnDef("BH", "Auto Renewal Notes and Removal Requirements", "Contract Area", "Only Used as Needed"),
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
    "Component Area": ("X", "AG"),
    "Additional Component Area": ("AH", "AL"),
    "Circuit Speed Area": ("AM", "AP"),
    "Z Location Area": ("AQ", "AW"),
    "Contract Area": ("AX", "BH"),
}


# --- Dropdown Validation Lists ---

SERVICE_TYPES = [
    "Account Level", "Analog Circuits", "Broadband", "Business Internet",
    "Call Path", "Cellular", "Centrex", "Cloud Services", "Conference Bridge",
    "Dark Fiber", "DIA", "Digital Phone Line", "DS0", "DS1", "DS3",
    "E-Line", "Email Services", "EPL", "Ethernet", "EVPL",
    "Fax", "Fiber Optic", "Frame Relay", "Hosted PBX", "Hosted VoIP",
    "HPBX", "Hunt Group", "Internet", "ISDN BRI", "ISDN PRI",
    "IT Services", "IVR", "Leased Line", "Long Distance",
    "Managed Firewall", "Managed Network", "Managed Router",
    "Managed Security", "Managed Services", "Managed WiFi",
    "Metro Ethernet", "MLPPP", "MPLS", "Multicast",
    "Network Management", "OC-12", "OC-192", "OC-3", "OC-48",
    "Other", "PBX", "Point to Point", "POTS", "Private Line",
    "Ring", "SD-WAN", "SDWAN", "SIP", "SIP Trunk",
    "Smart Jack", "SONET", "Switches", "T1", "T3",
    "Toll Free", "Trunk", "TV", "UCaaS",
    "UPS", "Video", "Virtual Private Line", "VOIP",
    "VOIP Line", "VoIP Trunk", "VPN", "VPLS",
    "WAN", "Wavelength", "Web Hosting", "Wide Area Network",
    "Wireless", "Wireless Backup", "Wireless Internet",
]

CHARGE_TYPES = [
    "MRC", "NRC", "OCC", "ProRated", "Prorated Charges",
    "Surcharge", "Taxes", "Usage",
]

SCU_CODES = ["S", "C", "U", "T\\S\\OCC"]

END_USE_VALUES = ["Alarm", "Elevator", "Fax"]

MONTH_TO_MONTH_VALUES = ["Yes", "No"]


# --- Inventory Row Dataclass ---

@dataclass
class InventoryRow:
    """Represents a single row in the inventory output."""
    # DD2 Information Area
    status: Optional[str] = None
    notes: Optional[str] = None
    contract_info_received: Optional[str] = None

    # File Information Area
    invoice_file_name: Optional[str] = None
    files_used_for_inventory: Optional[str] = None
    billing_name: Optional[str] = None

    # Location Area
    service_address_1: Optional[str] = None
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

    # Component Area
    usoc: Optional[str] = None
    service_or_component: Optional[str] = None  # S, C, U, or T\S\OCC
    component_or_feature_name: Optional[str] = None
    monthly_recurring_cost: Optional[float] = None
    quantity: Optional[float] = None
    cost_per_unit: Optional[float] = None
    currency: Optional[str] = None
    conversion_rate: Optional[float] = None
    mrc_per_currency: Optional[float] = None
    charge_type: Optional[str] = None

    # Additional Component Area
    num_calls: Optional[float] = None
    ld_minutes: Optional[float] = None
    ld_cost: Optional[float] = None
    rate: Optional[float] = None
    ld_flat_rate: Optional[float] = None

    # Circuit Speed Area
    point_to_number: Optional[str] = None
    port_speed: Optional[str] = None
    access_speed: Optional[str] = None
    upload_speed: Optional[str] = None

    # Z Location Area
    z_service_address_1: Optional[str] = None
    z_service_address_2: Optional[str] = None
    z_city: Optional[str] = None
    z_state: Optional[str] = None
    z_zip: Optional[str] = None
    z_country: Optional[str] = None
    z_location_name: Optional[str] = None

    # Contract Area
    contract_term: Optional[float] = None
    contract_begin_date: Optional[str] = None
    contract_expiration_date: Optional[str] = None
    billing_per_contract: Optional[float] = None
    currently_month_to_month: Optional[str] = None
    month_to_month_since: Optional[str] = None
    month_to_month_rate: Optional[float] = None
    contract_file_name: Optional[str] = None
    auto_renew: Optional[str] = None
    auto_renewal_term: Optional[str] = None
    auto_renewal_notes: Optional[str] = None

    # Metadata (not output columns)
    confidence: dict = field(default_factory=dict)
    source_files: list = field(default_factory=list)
    linkage_key: Optional[str] = None  # For S-C parent-child linking

    def to_row_dict(self) -> dict:
        """Convert to ordered dict matching column names for output."""
        field_to_column = {
            "status": "Status",
            "notes": "Inventory creation questions, concerns, or notes.",
            "contract_info_received": "*Contract Info received",
            # Note: quantity uses the misspelled name from the reference file
            "invoice_file_name": "Invoice File Name",
            "files_used_for_inventory": "Files Used For Inventory",
            "billing_name": "Billing Name",
            "service_address_1": "Service Address 1",
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
            "currency": "Currency",
            "conversion_rate": "Conversion Rate",
            "mrc_per_currency": "Monthly Recurring Cost per Currency",
            "charge_type": "Charge Type",
            "num_calls": "# Calls",
            "ld_minutes": "LD Minutes",
            "ld_cost": "LD Cost",
            "rate": "Rate",
            "ld_flat_rate": "LD Flat Rate",
            "point_to_number": "Point to Number",
            "port_speed": "Port Speed",
            "access_speed": "Access Speed",
            "upload_speed": "Upload Speed",
            "z_service_address_1": "Z Address 1",
            "z_service_address_2": "Z Address 2",
            "z_city": "Z City",
            "z_state": "Z State",
            "z_zip": "Z Zip Code",
            "z_country": "Z Country",
            "z_location_name": "Z Location Name If One Given By Carrier",
            "contract_term": "*Contract - Term Months",
            "contract_begin_date": "*Contract - Begin Date",
            "contract_expiration_date": "*Contract - Expiration Date",
            "billing_per_contract": "Billing Per Contract",
            "currently_month_to_month": "*Currently Month-to-Month",
            "month_to_month_since": "Month to Month or Less Than a Year Remaining",
            "month_to_month_rate": "Contract Number",
            "contract_file_name": "Contract File Name",
            "auto_renew": "*Auto Renew",
            "auto_renewal_term": "2nd Contract Number",
            "auto_renewal_notes": "Auto Renewal Notes and Removal Requirements",
        }
        result = {}
        for attr, col_name in field_to_column.items():
            result[col_name] = getattr(self, attr)
        return result

    @classmethod
    def column_field_map(cls) -> dict[str, str]:
        """Map column names to dataclass field names."""
        row = cls()
        row_dict = row.to_row_dict()
        inv = {}
        for f in fields(cls):
            if f.name in ("confidence", "source_files", "linkage_key"):
                continue
            val_in_dict = {col: attr for attr, col in _build_field_to_column().items()}
        return val_in_dict


def _build_field_to_column() -> dict[str, str]:
    """Internal helper to build field→column mapping."""
    return {
        "status": "Status",
        "notes": "Notes",
        "contract_info_received": "Contract Info received",
        "invoice_file_name": "Invoice File Name",
        "files_used_for_inventory": "Files Used For Inventory",
        "billing_name": "Billing Name",
        "service_address_1": "Service Address 1",
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
        "quantity": "Quantity",
        "cost_per_unit": "Cost Per Unit",
        "currency": "Currency",
        "conversion_rate": "Conversion Rate",
        "mrc_per_currency": "MRC per Currency",
        "charge_type": "Charge Type",
        "num_calls": "# Calls",
        "ld_minutes": "LD Minutes",
        "ld_cost": "LD Cost",
        "rate": "Rate",
        "ld_flat_rate": "LD Flat Rate",
        "point_to_number": "Point to Number",
        "port_speed": "Port Speed",
        "access_speed": "Access Speed",
        "upload_speed": "Upload Speed",
        "z_service_address_1": "Z Service Address 1",
        "z_service_address_2": "Z Service Address 2",
        "z_city": "Z City",
        "z_state": "Z State",
        "z_zip": "Z Zip",
        "z_country": "Z Country",
        "z_location_name": "Z Location Name",
        "contract_term": "Contract Term",
        "contract_begin_date": "Contract Begin Date",
        "contract_expiration_date": "Contract Expiration Date",
        "billing_per_contract": "Billing Per Contract",
        "currently_month_to_month": "Currently Month-to-Month",
        "month_to_month_since": "Month-to-Month Since",
        "month_to_month_rate": "Month-to-Month Rate",
        "contract_file_name": "Contract File Name",
        "auto_renew": "Auto Renew",
        "auto_renewal_term": "Auto Renewal Term",
        "auto_renewal_notes": "Auto Renewal Notes",
    }


# Column name → field name reverse mapping
COLUMN_TO_FIELD = {v: k for k, v in _build_field_to_column().items()}
FIELD_TO_COLUMN = _build_field_to_column()
