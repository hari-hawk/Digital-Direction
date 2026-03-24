"""ZIP code → State lookup utility.

Uses uszipcode for comprehensive US ZIP→State mapping with a fallback
static dictionary for the most common ZIPs in the NSS dataset.
"""
import logging
import re

logger = logging.getLogger(__name__)

# Static fallback for the most common ZIPs in the dataset (fast, no DB needed)
_STATIC_ZIP_STATE = {
    # New York
    "12010": "NY", "12020": "NY", "12043": "NY", "12054": "NY", "12065": "NY",
    "12077": "NY", "12084": "NY", "12110": "NY", "12144": "NY", "12180": "NY",
    "12203": "NY", "12205": "NY", "12206": "NY", "12208": "NY", "12211": "NY",
    "12302": "NY", "12303": "NY", "12304": "NY", "12305": "NY", "12306": "NY",
    "12309": "NY", "12345": "NY", "12401": "NY", "12446": "NY", "12477": "NY",
    "12534": "NY", "12538": "NY", "12550": "NY", "12561": "NY", "12601": "NY",
    "12801": "NY", "12828": "NY", "12901": "NY", "12946": "NY", "13027": "NY",
    "13057": "NY", "13066": "NY", "13088": "NY", "13104": "NY", "13126": "NY",
    "13148": "NY", "13202": "NY", "13204": "NY", "13206": "NY", "13208": "NY",
    "13210": "NY", "13212": "NY", "13214": "NY", "13219": "NY", "13224": "NY",
    "13244": "NY", "13301": "NY", "13320": "NY", "13350": "NY", "13413": "NY",
    "13440": "NY", "13502": "NY", "13601": "NY", "13617": "NY", "13676": "NY",
    "13760": "NY", "13790": "NY", "13801": "NY", "13820": "NY", "13850": "NY",
    "14001": "NY", "14020": "NY", "14032": "NY", "14043": "NY", "14051": "NY",
    "14068": "NY", "14086": "NY", "14094": "NY", "14120": "NY", "14127": "NY",
    "14150": "NY", "14201": "NY", "14202": "NY", "14203": "NY", "14204": "NY",
    "14206": "NY", "14207": "NY", "14209": "NY", "14210": "NY", "14211": "NY",
    "14213": "NY", "14214": "NY", "14215": "NY", "14216": "NY", "14217": "NY",
    "14218": "NY", "14220": "NY", "14221": "NY", "14222": "NY", "14224": "NY",
    "14225": "NY", "14226": "NY", "14228": "NY", "14261": "NY", "14301": "NY",
    "14304": "NY", "14305": "NY", "14580": "NY", "14606": "NY", "14609": "NY",
    "14615": "NY", "14620": "NY", "14623": "NY", "14624": "NY", "14625": "NY",
    "14626": "NY", "14627": "NY", "14850": "NY", "14882": "NY", "14901": "NY",
    # Vermont
    "05401": "VT", "05452": "VT", "05455": "VT", "05468": "VT", "05478": "VT",
    "05495": "VT", "05602": "VT", "05641": "VT", "05701": "VT", "05753": "VT",
    "05819": "VT", "05855": "VT",
    # Massachusetts
    "01001": "MA", "01002": "MA", "01040": "MA", "01060": "MA", "01103": "MA",
    "01201": "MA", "01301": "MA", "01420": "MA", "01453": "MA", "01501": "MA",
    "01602": "MA", "01701": "MA", "01801": "MA", "01810": "MA", "01845": "MA",
    "02101": "MA", "02108": "MA", "02115": "MA", "02138": "MA", "02139": "MA",
    "02142": "MA", "02210": "MA",
    # Connecticut
    "06001": "CT", "06010": "CT", "06040": "CT", "06103": "CT", "06106": "CT",
    "06117": "CT", "06320": "CT", "06401": "CT", "06492": "CT", "06510": "CT",
    "06604": "CT", "06702": "CT", "06830": "CT", "06901": "CT",
    # New Jersey
    "07001": "NJ", "07030": "NJ", "07087": "NJ", "07102": "NJ", "07302": "NJ",
    "07601": "NJ", "07901": "NJ", "08540": "NJ", "08901": "NJ",
    # Pennsylvania
    "15001": "PA", "15201": "PA", "15213": "PA", "15237": "PA", "16001": "PA",
    "16501": "PA", "17011": "PA", "17101": "PA", "17601": "PA", "18015": "PA",
    "18101": "PA", "18201": "PA", "18301": "PA", "18505": "PA", "18702": "PA",
    "18901": "PA", "19001": "PA", "19019": "PA", "19102": "PA", "19103": "PA",
    "19104": "PA", "19106": "PA", "19122": "PA", "19146": "PA", "19148": "PA",
}

# Cache for uszipcode lookups
_zip_cache: dict[str, str] = {}
_search_engine = None


def _get_search():
    """Lazy-load the uszipcode search engine."""
    global _search_engine
    if _search_engine is None:
        try:
            from uszipcode import SearchEngine
            _search_engine = SearchEngine()
        except Exception as e:
            logger.warning(f"Failed to initialize uszipcode: {e}")
            _search_engine = False  # Mark as unavailable
    return _search_engine


def clean_zip(raw_zip: str) -> str:
    """Normalize a ZIP code to 5 digits."""
    if not raw_zip:
        return ""
    z = str(raw_zip).strip()
    # Remove .0 from float conversion
    if z.endswith(".0"):
        z = z[:-2]
    # Extract first 5 digits
    digits = re.sub(r"[^0-9]", "", z)
    if len(digits) >= 5:
        return digits[:5]
    if len(digits) > 0:
        return digits.zfill(5)
    return ""


def zip_to_state(raw_zip: str) -> str:
    """Convert a ZIP code to its 2-letter state abbreviation.

    Returns empty string if ZIP is invalid or not found.
    """
    z = clean_zip(raw_zip)
    if not z or len(z) < 5:
        return ""

    # Check cache
    if z in _zip_cache:
        return _zip_cache[z]

    # Check static dictionary first (fast)
    if z in _STATIC_ZIP_STATE:
        _zip_cache[z] = _STATIC_ZIP_STATE[z]
        return _STATIC_ZIP_STATE[z]

    # Try uszipcode
    engine = _get_search()
    if engine and engine is not False:
        try:
            result = engine.by_zipcode(z)
            if result and result.state:
                _zip_cache[z] = result.state
                return result.state
        except Exception:
            pass

    # Last resort: infer from first 3 digits (prefix ranges)
    prefix = int(z[:3])
    state = _prefix_to_state(prefix)
    if state:
        _zip_cache[z] = state
    return state


def _prefix_to_state(prefix: int) -> str:
    """Rough ZIP prefix → state mapping for common ranges."""
    ranges = [
        (100, 149, "NY"), (150, 196, "PA"), (197, 199, "DE"),
        (200, 205, "DC"), (206, 219, "MD"), (220, 246, "VA"),
        (247, 268, "NC"), (270, 289, "NC"), (290, 299, "SC"),
        (300, 319, "GA"), (320, 349, "FL"), (350, 369, "AL"),
        (370, 385, "TN"), (386, 397, "MS"), (400, 427, "KY"),
        (430, 459, "OH"), (460, 479, "IN"), (480, 499, "MI"),
        (500, 528, "IA"), (530, 549, "WI"), (550, 567, "MN"),
        (570, 577, "SD"), (580, 588, "ND"), (590, 599, "MT"),
        (600, 629, "IL"), (630, 658, "MO"), (660, 679, "KS"),
        (680, 693, "NE"), (700, 714, "LA"), (716, 729, "AR"),
        (730, 749, "OK"), (750, 799, "TX"), (800, 816, "CO"),
        (820, 831, "WY"), (832, 838, "ID"), (840, 847, "UT"),
        (850, 865, "AZ"), (870, 884, "NM"), (889, 898, "NV"),
        (900, 961, "CA"), (970, 979, "OR"), (980, 994, "WA"),
        (995, 999, "AK"), (10, 14, "MA"), (50, 54, "VT"),
        (60, 69, "CT"), (70, 89, "NJ"),
    ]
    for lo, hi, state in ranges:
        if lo <= prefix <= hi:
            return state
    return ""


def enrich_state_from_zip(rows: list[dict], state_key: str = "State", zip_key: str = "Zip") -> int:
    """Enrich rows by filling missing State from ZIP code.

    Returns the number of rows enriched.
    """
    enriched = 0
    for row in rows:
        state = str(row.get(state_key, "") or "").strip()
        if state and state.lower() not in ("", "nan", "none"):
            continue  # Already has state

        raw_zip = str(row.get(zip_key, "") or "").strip()
        if not raw_zip or raw_zip.lower() in ("nan", "none", ""):
            continue

        inferred = zip_to_state(raw_zip)
        if inferred:
            row[state_key] = inferred
            enriched += 1

    return enriched
