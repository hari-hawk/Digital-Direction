"""
Address normalization utilities.
ZIP-to-state lookup, billing name mapping, and address cleanup.
"""
import re
from typing import Optional

# ZIP code prefix to state mapping (first 3 digits)
# Covers all US states - sourced from USPS ZIP code ranges
ZIP3_TO_STATE = {
    # NY: 100-149
    **{str(i).zfill(3): "NY" for i in range(100, 150)},
    # MA: 010-027
    **{str(i).zfill(3): "MA" for i in range(10, 28)},
    # CT: 060-069
    **{str(i).zfill(3): "CT" for i in range(60, 70)},
    # VT: 050-059
    **{str(i).zfill(3): "VT" for i in range(50, 60)},
    # NH: 030-038
    **{str(i).zfill(3): "NH" for i in range(30, 39)},
    # PA: 150-196
    **{str(i).zfill(3): "PA" for i in range(150, 197)},
    # NJ: 070-089
    **{str(i).zfill(3): "NJ" for i in range(70, 90)},
    # ME: 039-049
    **{str(i).zfill(3): "ME" for i in range(39, 50)},
    # RI: 028-029
    "028": "RI", "029": "RI",
    # TN: 370-385
    **{str(i).zfill(3): "TN" for i in range(370, 386)},
    # CA: 900-961
    **{str(i).zfill(3): "CA" for i in range(900, 962)},
    # TX: 750-799, 885
    **{str(i).zfill(3): "TX" for i in range(750, 800)},
    "885": "TX",
    # FL: 320-349
    **{str(i).zfill(3): "FL" for i in range(320, 350)},
    # OH: 430-459
    **{str(i).zfill(3): "OH" for i in range(430, 460)},
    # MI: 480-499
    **{str(i).zfill(3): "MI" for i in range(480, 500)},
    # IL: 600-629
    **{str(i).zfill(3): "IL" for i in range(600, 630)},
    # GA: 300-319, 398-399
    **{str(i).zfill(3): "GA" for i in range(300, 320)},
    # VA: 201, 220-246
    "201": "VA",
    **{str(i).zfill(3): "VA" for i in range(220, 247)},
    # WI: 530-549
    **{str(i).zfill(3): "WI" for i in range(530, 550)},
    # MN: 550-567
    **{str(i).zfill(3): "MN" for i in range(550, 568)},
    # IN: 460-479
    **{str(i).zfill(3): "IN" for i in range(460, 480)},
    # WV: 247-268
    **{str(i).zfill(3): "WV" for i in range(247, 269)},
    # MD: 206-219
    **{str(i).zfill(3): "MD" for i in range(206, 220)},
    # DC: 200, 202-205
    "200": "DC", "202": "DC", "203": "DC", "204": "DC", "205": "DC",
}


def state_from_zip(zip_code: Optional[str]) -> Optional[str]:
    """Derive state from ZIP code using first 3 digits."""
    if not zip_code:
        return None
    # Clean ZIP: take first 5 digits
    digits = re.sub(r"\D", "", str(zip_code))
    if len(digits) < 3:
        return None
    prefix = digits[:3]
    return ZIP3_TO_STATE.get(prefix)


# Charter-specific billing name normalization
# Maps carrier report internal names → reference billing names
CHARTER_BILLING_NAME_MAP = {
    # Most Golub sites should map to "PRICE CHOPPER" (the retail brand)
    "GOLUB": "PRICE CHOPPER",
    "GOLUB CORPORATION": "GOLUB CORPORATION",
    "GOLUB CORP": "GOLUB CORPORATION",
    # TOPS MARKETS sites
    "TOPS": "TOP MARKETS LLC",
    "TOP MARKETS": "TOP MARKETS LLC",
    "TOP MARKETS LLC": "TOP MARKETS LLC",
    # Specific billing names from reference
    "NORTHEAST GROCERY": "Northeast Grocery",
    "PRICE CHOPPER": "PRICE CHOPPER",
}


def normalize_billing_name(name: Optional[str]) -> Optional[str]:
    """Normalize Charter billing name to match reference patterns."""
    if not name:
        return name

    name_upper = name.strip().upper()

    # Direct match
    if name_upper in CHARTER_BILLING_NAME_MAP:
        return CHARTER_BILLING_NAME_MAP[name_upper]

    # Pattern match: GOLUB-NNN → PRICE CHOPPER (store sites)
    if re.match(r"GOLUB-\d+", name_upper):
        return "PRICE CHOPPER"

    # Pattern match: GOLUB-NNN-LOCATION → PRICE CHOPPER
    if name_upper.startswith("GOLUB-"):
        return "PRICE CHOPPER"

    # GOLUB with any suffix
    if name_upper.startswith("GOLUB"):
        return "PRICE CHOPPER"

    return name.strip()


def normalize_zip(zip_code: Optional[str]) -> Optional[str]:
    """Normalize ZIP code to 5-digit format."""
    if not zip_code:
        return None
    digits = re.sub(r"\D", "", str(zip_code))
    if len(digits) >= 5:
        return digits[:5]
    if len(digits) > 0:
        return digits.zfill(5)
    return None


def normalize_address(address: Optional[str]) -> Optional[str]:
    """Normalize address to title case for consistent formatting.

    Converts UPPERCASE addresses (e.g., "400 MINUTEMAN RD") to title case
    ("400 Minuteman Rd") to match reference data formatting.
    Preserves special patterns like suite/unit numbers and directional prefixes.
    """
    if not address:
        return address
    addr = address.strip()
    if not addr:
        return addr

    # Skip non-address values
    if addr.lower().startswith("service not address"):
        return addr

    # Convert to title case
    addr = addr.title()

    # Fix common abbreviations that should stay abbreviated (not fully capitalized)
    # These are already correct from .title() — e.g., "St" not "ST"
    # Fix directional abbreviations that should stay uppercase
    _DIRECTIONAL = {
        " Ne ": " NE ", " Nw ": " NW ", " Se ": " SE ", " Sw ": " SW ",
        " Ne,": " NE,", " Nw,": " NW,", " Se,": " SE,", " Sw,": " SW,",
    }
    for old, new in _DIRECTIONAL.items():
        addr = addr.replace(old, new)

    # Fix ordinal suffixes that title() mangles: "1St" → "1st", "2Nd" → "2nd"
    addr = re.sub(r'(\d)(St|Nd|Rd|Th)\b', lambda m: m.group(1) + m.group(2).lower(), addr)

    return addr


def normalize_city(city: Optional[str]) -> Optional[str]:
    """Normalize city name to title case.

    Converts UPPERCASE city names (e.g., "BUFFALO") to title case ("Buffalo")
    to match reference data formatting.
    """
    if not city:
        return city
    c = city.strip()
    if not c:
        return c
    return c.title()
