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
