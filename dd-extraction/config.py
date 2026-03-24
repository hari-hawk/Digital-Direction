"""
Configuration for the Digital Direction extraction pipeline.
Paths, constants, and carrier registry.
"""
import os
from pathlib import Path

# Base paths - relative to the project's parent structure
_PROJECT_ROOT = Path(__file__).resolve().parent
_CLAUDE_ROOT = _PROJECT_ROOT.parent.parent  # Claude/ directory

CLIENT_INPUTS_DIR = _CLAUDE_ROOT / "Client Inputs" / "NSS POC Inputs and Output"
INVOICES_DIR = CLIENT_INPUTS_DIR / "Invoices"
CARRIER_REPORTS_DIR = CLIENT_INPUTS_DIR / "Carrier Reports, Portal Data, ETC"
CONTRACTS_DIR = CLIENT_INPUTS_DIR / "Contracts"

# Reference file (ground truth for validation)
NSS_REFERENCE_FILE = CLIENT_INPUTS_DIR / (
    "Digital Direction_NSS_ Inventory File_01.22.2026_WIP_v3 BF- Sent to Techjays.xlsx"
)

# Schema analysis file
SCHEMA_ANALYSIS_FILE = _CLAUDE_ROOT / "Research findings" / "Digital Direction - Inventory Schema Analysis.xlsx"

# Output directory
OUTPUT_DIR = _PROJECT_ROOT / "outputs"

# Carrier registry - maps carrier keys to display names and input folder names
# display_name must match the reference file's Carrier column exactly
CARRIER_REGISTRY = {
    "charter": {
        "display_name": "Charter Communications",
        "invoice_folder": "Charter Communications",
        "report_folder": "Charter",
        "contract_folder": "Charter",
        "tier": 1,
        "extractor": "charter",  # uses dedicated CharterExtractor
        # Known Charter account numbers from reference file — used to filter
        # the shared COMMS report which also contains Windstream data
        "known_accounts": [
            "057777701", "057778001", "065728001", "117931801",
            "143371001", "145529301",
            "8143 16 033 0055404", "8358 11 002 0022370",
            "8358 21 062 0249975", "8358 21 114 0215710",
            "8358 21 114 0292263", "8358 21 170 0107125",
        ],
        "parent_id": "216713099",  # The actual Charter parent in COMMS report
    },
    "windstream": {
        "display_name": "Windstream",
        "invoice_folder": "Windstream",
        "report_folder": "Windstream",
        "contract_folder": "Windstream",
        "tier": 1,
        "extractor": "generic",
        "parent_id": "2389882",  # Windstream parent in shared COMMS report
    },
    "granite": {
        "display_name": "Granite",
        "invoice_folder": "Granite",
        "report_folder": "Granite",
        "contract_folder": "Granite",
        "tier": 1,
        "extractor": "generic",
    },
    "peerless": {
        "display_name": "Peerless Network",
        "invoice_folder": "Peerless Network",
        "report_folder": "Peerless Network",
        "contract_folder": "Peerless Network",
        "tier": 2,
        "extractor": "generic",
    },
    "consolidated": {
        "display_name": "Consolidated Communications",
        "invoice_folder": "Consolidated Communications",
        "report_folder": "Consolidated Communications",
        "contract_folder": "Consolidated Communications",
        "tier": 2,
        "extractor": "generic",
    },
    "spectrotel": {
        "display_name": "Spectrotel",
        "invoice_folder": "Spectrotel",
        "report_folder": "Spectrotel",
        "contract_folder": "Spectrotel",
        "tier": 2,
        "extractor": "generic",
    },
    "frontier": {
        "display_name": "Frontier",
        "invoice_folder": "Frontier",
        "report_folder": "Frontier",
        "contract_folder": "Frontier",
        "tier": 2,
        "extractor": "generic",
    },
    "verizon": {
        "display_name": "Verizon",
        "invoice_folder": "Verizon",
        "report_folder": "",
        "contract_folder": "Verizon",
        "tier": 3,
        "extractor": "generic",
    },
    "delhi_telephone": {
        "display_name": "Delhi Telephone",
        "invoice_folder": "Delhi Telephone Company",
        "report_folder": "",
        "contract_folder": "",
        "tier": 3,
        "extractor": "generic",
    },
    "champlain": {
        "display_name": "Champlain Technology",
        "invoice_folder": "Champlain Technology",
        "report_folder": "",
        "contract_folder": "",
        "tier": 3,
        "extractor": "generic",
    },
    "nextiva": {
        "display_name": "Nextiva",
        "invoice_folder": "Nextiva",
        "report_folder": "Nextiva",
        "contract_folder": "Nextiva",
        "tier": 2,
        "extractor": "generic",
    },
    "wvt_fiber": {
        "display_name": "WVT Fiber",
        "invoice_folder": "WVT Fiber",
        "report_folder": "",
        "contract_folder": "",
        "tier": 3,
        "extractor": "generic",
    },
    "tds_telecom": {
        "display_name": "TDS Telecom",
        "invoice_folder": "TDS Telecom",
        "report_folder": "",
        "contract_folder": "",
        "tier": 3,
        "extractor": "generic",
    },
    "statetel": {
        "display_name": "StateTel",
        "invoice_folder": "StateTel",
        "report_folder": "StateTel",
        "contract_folder": "StateTel",
        "tier": 3,
        "extractor": "generic",
    },
    "directv": {
        "display_name": "Directv",
        "invoice_folder": "Directv",
        "report_folder": "",
        "contract_folder": "",
        "tier": 3,
        "extractor": "generic",
    },
    "bcn_telecom": {
        "display_name": "BCN Telecom",
        "invoice_folder": "BCN Telecom",
        "report_folder": "",
        "contract_folder": "BCN Telecom",
        "tier": 3,
        "extractor": "generic",
    },
    "allstar": {
        "display_name": "Allstar Systems",
        "invoice_folder": "Allstar Systems",
        "report_folder": "",
        "contract_folder": "",
        "tier": 3,
        "extractor": "generic",
    },
    "lumen": {
        "display_name": "Lumen",
        "invoice_folder": "Lumen",
        "report_folder": "Lumen",
        "contract_folder": "Lumen",
        "tier": 2,
        "extractor": "generic",
    },
    "crown_castle": {
        "display_name": "Crown Castle",
        "invoice_folder": "Crown Castle",
        "report_folder": "",
        "contract_folder": "Crown Castle",
        "tier": 3,
        "extractor": "generic",
    },
    "firstlight": {
        "display_name": "FirstLight Fiber",
        "invoice_folder": "FirstLight",
        "report_folder": "",
        "contract_folder": "FirstLight",
        "tier": 3,
        "extractor": "generic",
    },
    "message_media": {
        "display_name": "Message Media",
        "invoice_folder": "Message Media",
        "report_folder": "Message Media",
        "contract_folder": "Message Media",
        "tier": 3,
        "extractor": "generic",
    },
    "mid_hudson": {
        "display_name": "Mid Hudson",
        "invoice_folder": "Mid Hudson",
        "report_folder": "",
        "contract_folder": "",
        "tier": 3,
        "extractor": "generic",
    },
    "zayo": {
        "display_name": "Zayo",
        "invoice_folder": "Zayo",
        "report_folder": "",
        "contract_folder": "Zayo",
        "tier": 3,
        "extractor": "generic",
    },
    "t_mobile": {
        "display_name": "T-Mobile",
        "invoice_folder": "T-Mobile",
        "report_folder": "",
        "contract_folder": "",
        "tier": 3,
        "extractor": "generic",
    },
    "verizon_wireless": {
        "display_name": "Verizon Wireless",
        "invoice_folder": "Verizon Wireless",
        "report_folder": "",
        "contract_folder": "",
        "tier": 3,
        "extractor": "generic",
    },
}

# Master carrier name list — used for auto-detection from filenames, folder names, and data
# These are the canonical carrier names used across the platform
MASTER_CARRIER_NAMES = [
    "Allstar Systems",
    "BCN Telecom",
    "Champlain Technology",
    "Charter Communications",
    "Consolidated Communications",
    "Crown Castle",
    "Delhi Telephone Company",
    "Directv",
    "FirstLight (Fiber)",
    "Frontier",
    "Granite",
    "Lumen",
    "Message Media",
    "Mid Hudson",
    "Nextiva",
    "Peerless Network",
    "Spectrotel",
    "StateTel",
    "TDS Telecom",
    "T-Mobile",
    "Verizon",
    "Verizon Wireless",
    "Windstream",
    "WVT Fiber",
    "Zayo",
]

# Anthropic API key for OCR (optional - pipeline degrades gracefully without it)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# Processing limits
MAX_OCR_PAGES_PER_INVOICE = 20
OCR_TIMEOUT_SECONDS = 60
