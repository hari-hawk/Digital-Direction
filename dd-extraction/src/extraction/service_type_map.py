"""
Centralized service type normalization map.

Maps raw carrier report values and extracted service types to the standardized
service type names used in the NSS reference file. This is the single source
of truth for service type normalization across all carriers.
"""

# ---------------------------------------------------------------------------
# Per-carrier: raw carrier report value  ->  reference service type
# ---------------------------------------------------------------------------

SERVICE_TYPE_MAP = {
    # ---------------------------------------------------------------
    # CHARTER COMMUNICATIONS
    # ---------------------------------------------------------------
    "charter": {
        # Circuit type mappings from carrier report
        "Dedicated Fiber Internet": "DIA",
        "Ethernet Access": "DIA",
        "Enterprise Fiber Internet": "DIA",
        "Access Loop": "DIA",
        "Spectrum Internet": "Business Internet",
        "Business Internet": "Business Internet",
        "Internet": "Business Internet",
        "Voice": "VOIP Line",
        "VoIP": "VOIP Line",
        "VoIP Product": "VOIP Line",
        "Video": "TV",
        "TV": "TV",
        "Ethernet": "EPL",
        "EVPL": "EVPL",
        "EPL": "EPL",
        "SD-WAN VMware Product": "SDWAN",
        "SD-WAN": "SDWAN",
        "SDWAN": "SDWAN",
        "Broadband": "Broadband",
        "Account Level": "Account Level",
        "Account Level ": "Account Level",  # trailing space variant
    },

    # ---------------------------------------------------------------
    # WINDSTREAM
    # ---------------------------------------------------------------
    "windstream": {
        # From circuit types in Customer Inventory by COMMS
        "Customer Provided Access": "UCaaS",
        "SD-WAN Management-Concierge": "SDWAN",
        "SD-WAN Management": "SDWAN",
        "SD-WAN Service License": "SDWAN",
        "sd-wan management-concierge": "SDWAN",
        "sd-wan management": "SDWAN",
        "sd-wan service license": "SDWAN",
        "sd-wan": "SDWAN",
        "sdwan": "SDWAN",
        "Cellular Broadband Internet Access": "Wireless Cellular Internet",
        "Cellular Broadband Charge": "Wireless Cellular Internet",
        "Ethernet Access": "Ethernet",
        "Internet Service": "DIA",
        "Access Loop": "UCaaS",
        "VoIP": "UCaaS",
        "VoIP Connection Number": "UCaaS",
        "Broadband": "Broadband",
        "Email": "Other",
        "Centrex": "Centrex",
        "Centrex Link": "Centrex",
        "IBN Exchange": "Centrex",
        "Billed Number": "Centrex",
        "SIP Trunk": "SIP Trunk",
        "Trunk Line - MetaSwitch": "SIP Trunk",
        "UCaaS": "UCaaS",
        "Account Level": "Account Level",
        "Wireless Cellular Internet": "Wireless Cellular Internet",
    },

    # ---------------------------------------------------------------
    # GRANITE
    # ---------------------------------------------------------------
    "granite": {
        "POTS": "POTS",
        "Account Level": "Account Level",
        "Usage": "Long Distance",
        "RCF": "RCF",
        "Centrex": "Centrex",
        "Long Distance": "Long Distance",
        "CHG": "POTS",
        "LTE": "POTS",
        "OTH": "POTS",
        "TXS": "Account Level",
        "SUR": "Account Level",
        "USG": "Long Distance",
        "CNX": "Centrex",
    },

    # ---------------------------------------------------------------
    # PEERLESS NETWORK
    # ---------------------------------------------------------------
    "peerless": {
        "SIP Trunk": "SIP Trunk",
        "DID with 911": "SIP Trunk",
        "DID Basic": "SIP Trunk",
        "DID": "DID",
    },

    # ---------------------------------------------------------------
    # CONSOLIDATED COMMUNICATIONS
    # ---------------------------------------------------------------
    "consolidated": {
        "Ethernet Virtual Connection EVC": "DIA",
        "Carrier Ethernet Service CES": "DIA",
        "Operator Virtual Circuit OVC": "DIA",
        "POTS": "POTS",
        "Centrex": "Centrex",
        "SIP Trunk": "SIP Trunk",
        "SIP": "SIP Trunk",
        "PRI": "ISDN PRI",
        "Internet": "DIA",
        "Broadband": "Broadband",
        "DIA": "DIA",
    },

    # ---------------------------------------------------------------
    # SPECTROTEL
    # ---------------------------------------------------------------
    "spectrotel": {
        "POTS": "POTS",
        "POTS - Local/Regional/LD": "POTS",
    },
}


# ---------------------------------------------------------------------------
# Normalization aliases: common extracted values -> canonical reference values
# These apply AFTER carrier-specific mapping, to catch remaining mismatches.
# ---------------------------------------------------------------------------

GLOBAL_SERVICE_TYPE_ALIASES = {
    "dia": "DIA",
    "sdwan": "SDWAN",
    "sd-wan": "SDWAN",
    "ucaas": "UCaaS",
    "voip line": "VOIP Line",
    "voip": "VOIP Line",
    "pots": "POTS",
    "sip trunk": "SIP Trunk",
    "isdn pri": "ISDN PRI",
    "epl": "EPL",
    "evpl": "EVPL",
    "broadband": "Broadband",
    "centrex": "Centrex",
    "tv": "TV",
    "business internet": "Business Internet",
    "wireless cellular internet": "Wireless Cellular Internet",
    "account level": "Account Level",
    "account level ": "Account Level",  # trailing space
    "rcf": "RCF",
    "long distance": "Long Distance",
    "usage": "Usage",
    "did": "DID",
    "other": "Other",
    "mpls": "MPLS",
    "ethernet": "Ethernet",
}


def normalize_service_type(service_type: str, carrier_key: str = "") -> str:
    """
    Normalize a service type string to match reference naming conventions.

    1. Try carrier-specific map first (exact match, then case-insensitive).
    2. Fall back to global alias table.
    3. If no match, return original with consistent casing.

    Args:
        service_type: Raw service type string from extraction.
        carrier_key: Carrier key (e.g., "charter", "windstream") for
                     carrier-specific mappings.

    Returns:
        Normalized service type string matching reference conventions.
    """
    if not service_type:
        return service_type

    st = service_type.strip()

    # 1. Carrier-specific exact match
    carrier_map = SERVICE_TYPE_MAP.get(carrier_key.lower(), {})
    if st in carrier_map:
        return carrier_map[st]

    # 2. Carrier-specific case-insensitive match
    st_lower = st.lower()
    for raw, canonical in carrier_map.items():
        if raw.lower() == st_lower:
            return canonical

    # 3. Global alias (case-insensitive)
    canonical = GLOBAL_SERVICE_TYPE_ALIASES.get(st_lower)
    if canonical:
        return canonical

    # 4. Partial matching for carrier-specific patterns
    for raw, canonical in carrier_map.items():
        if raw.lower() in st_lower or st_lower in raw.lower():
            return canonical

    # 5. Return original (trimmed)
    return st


# ---------------------------------------------------------------------------
# Valid dropdown values from the DD platform template
# These are the ONLY values accepted in the Service Type column.
# ---------------------------------------------------------------------------

VALID_SERVICE_TYPES = {
    "Account Level", "Analog Circuits", "Audit", "Broadband", "Calling Card",
    "CDN", "Cellular", "Centrex", "Cloud Direct Connection", "CO Muxed T1",
    "Collocation", "Conferencing", "CPE", "DaaS", "Dark Fiber",
    "Data Voice Bundled", "DIA", "Dial Up Internet", "DID", "DID Trunks",
    "DRaaS", "DS1", "DS3", "DSL", "E911", "Electronic Fax", "Ethernet",
    "Hosted VOIP", "Integrated Circuit", "Inventory Creation", "ISDN BRI",
    "ISDN PRI", "Listing", "Local Usage", "Long Distance", "MPLS",
    "NET MGMT", "PBX/Biz Trunks", "Point to Point", "POTS", "RCF",
    "SDWAN", "SIP Trunk", "Sonet", "Telecom Management",
    "Telecom Project Management", "TF - Dedicated", "TF - Switched", "TV",
    "UCaaS", "Usage", "Virus Protection", "Voice Mail", "VOIP DID",
    "VOIP Line", "VPLS", "VPN", "VTN", "Wireless Cellular Internet",
    "Wireless DIA", "ABN", "AVTS", "Branch Office Extension (BOE)",
    "Cable Internet", "Cloud Storage", "Completelink", "DIA-Managed",
    "DIA-Unmanaged", "FIOS", "Foreign Exchange", "Hosting", "Integrated T1",
    "IP/Flex", "LD - Dedicated", "LD - Switched", "Managed Network Services",
    "MDA", "MPLS-Managed", "MPLS-Unmanaged", "P2P Interstate",
    "P2P Intrastate", "P2P Metro", "Payphone", "TEM - Enhanced", "Uverse",
    "Wireless Internet",
}

# Case-insensitive lookup for fast matching
_VALID_SERVICE_TYPES_LOWER = {v.lower(): v for v in VALID_SERVICE_TYPES}

# Fuzzy mapping: non-standard values that should normalize to a valid dropdown
SERVICE_TYPE_FUZZY_MAP = {
    "business internet": "Cable Internet",
    "other": "Inventory Creation",
    "epl": "Ethernet",
    "evpl": "Ethernet",
    "wireless cellular": "Wireless Cellular Internet",
    "cellular internet": "Cellular",
    "cellular broadband": "Wireless Cellular Internet",
    "cellular broadband internet access": "Wireless Cellular Internet",
    "managed services": "Managed Network Services",
    "toll free": "TF - Switched",
    "toll free dedicated": "TF - Dedicated",
    "toll free switched": "TF - Switched",
    "hosted voip": "Hosted VOIP",
    "hosted pbx": "Hosted VOIP",
    "ip pbx": "Hosted VOIP",
    "pri": "ISDN PRI",
    "bri": "ISDN BRI",
    "point-to-point": "Point to Point",
    "p2p": "Point to Point",
    "virtual private network": "VPN",
    "sd-wan": "SDWAN",
    "sd wan": "SDWAN",
}


def validate_service_type(service_type: str) -> str:
    """Validate and normalize service type against the DD platform dropdown.

    If the value is already in the valid set, return as-is.
    If it matches case-insensitively, return the canonical casing.
    If it matches a fuzzy alias, return the mapped value.
    Otherwise return the original (it will still be flagged by QA).
    """
    if not service_type:
        return service_type

    st = service_type.strip()

    # Exact match
    if st in VALID_SERVICE_TYPES:
        return st

    # Case-insensitive match
    canonical = _VALID_SERVICE_TYPES_LOWER.get(st.lower())
    if canonical:
        return canonical

    # Fuzzy alias match
    fuzzy = SERVICE_TYPE_FUZZY_MAP.get(st.lower())
    if fuzzy:
        return fuzzy

    # Return original — QA will flag it
    return st


# ---------------------------------------------------------------------------
# Valid charge types from the DD platform template
# ---------------------------------------------------------------------------

VALID_CHARGE_TYPES = {"MRC", "NRC", "OCC", "Prorated Charges", "Surcharge", "Taxes", "Usage"}

CHARGE_TYPE_ALIASES = {
    "mrc": "MRC",
    "nrc": "NRC",
    "occ": "OCC",
    "prorated": "Prorated Charges",
    "prorated charges": "Prorated Charges",
    "prorated charge": "Prorated Charges",
    "pro-rated": "Prorated Charges",
    "surcharge": "Surcharge",
    "surcharges": "Surcharge",
    "taxes": "Taxes",
    "tax": "Taxes",
    "usage": "Usage",
    "use": "Usage",
}


def validate_charge_type(charge_type: str) -> str:
    """Validate and normalize charge type against the DD platform dropdown.

    Maps common variants (e.g., "ProRated" -> "Prorated Charges") to valid values.
    """
    if not charge_type:
        return charge_type

    ct = charge_type.strip()

    # Exact match
    if ct in VALID_CHARGE_TYPES:
        return ct

    # Case-insensitive alias match
    alias = CHARGE_TYPE_ALIASES.get(ct.lower())
    if alias:
        return alias

    # Return original
    return ct
