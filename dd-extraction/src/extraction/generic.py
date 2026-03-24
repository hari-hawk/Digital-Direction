"""
Generic multi-carrier extraction engine.
Reads structured Excel/CSV carrier reports and maps them to the 60-column
reference schema. Handles Windstream, Granite, Consolidated, Peerless,
Spectrotel, and any other carrier with structured reports.

Pure rules-based -- no AI/API calls.
"""
import logging
import os
import re
from pathlib import Path
from typing import Optional

import pandas as pd

from src.extraction.base import CarrierExtractor, ExtractionResult
from src.extraction.service_type_map import normalize_service_type
from src.mapping.schema import InventoryRow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Carrier-specific report format definitions
# ---------------------------------------------------------------------------
# Each entry describes how to find the report file and map its columns.

CARRIER_REPORT_FORMATS = {
    # ---------------------------------------------------------------
    # WINDSTREAM
    # ---------------------------------------------------------------
    "windstream": {
        "customer_inventory_comms": {
            "file_pattern": "customer inventory by comms",
            "sheet_name": "Customer Inventory by COMMS",
            "extensions": [".xlsx", ".xls"],
            "column_map": {
                "Parent ID": "master_account",
                "Customer #": "sub_account_number",
                "Customer Name": "billing_name",
                "TN": "phone_number",
                "TN Status": "tn_status",
                "TN Type": "tn_type",
                "Circuit ID": "carrier_circuit_number",
                "Circuit Cat": "circuit_category",
                "Circuit Type": "circuit_type",
                "Circuit Status": "circuit_status",
                "ADDR1": "service_address_1",
                "ADDR2": "service_address_2",
                "CITY": "city",
                "STATE": "state",
                "ZIP": "zip_code",
                "SYSTEM": "system",
            },
        },
        "service_locations": {
            "file_pattern": "servicelocationsexport",
            "extensions": [".xlsx"],
            "column_map": {
                "Service Location Number": "location_number",
                "Service Location Name": "location_name",
                "Global account ID": "master_account",
                "Billable Account ID": "sub_account_number",
                "Service Street": "service_address_1",
                "Service City": "city",
                "Service State": "state",
                "Service Postal Code": "zip_code",
                "Agreement End Date": "contract_expiration_date",
                "Agreement Start Date": "contract_begin_date",
                "Term": "contract_term",
                "Contract Status": "contract_status",
                "Service Status": "service_status",
            },
        },
        "my_locations": {
            "file_pattern": "mylocations",
            "extensions": [".xlsx"],
            "column_map": {
                "Account": "sub_account_number",
                "Name": "billing_name",
                "Address": "full_address",
                "WAN Circuit ID": "carrier_circuit_number",
                "Service(s)": "service_description",
                "Managed Router": "managed_router",
            },
        },
        "all_active_tn": {
            "file_pattern": "all active tn",
            "extensions": [".xlsx"],
            "column_map": {
                "Account Number": "sub_account_number",
                "Active TN": "phone_number",
                "Account Name": "billing_name",
                "Service Address": "full_address",
            },
        },
        "monthly_summary": {
            "file_pattern": "monthlysummary",
            "extensions": [".xlsx"],
            "header_row": 1,
            "column_map": {
                "Mdn": "phone_number",
                "Location Name": "billing_name",
                "Account": "sub_account_number",
                "Street Address": "service_address_1",
                "City": "city",
                "State": "state",
                "Zip": "zip_code",
                "Plan": "plan",
                "Vendor": "vendor",
            },
        },
        "mrc_report": {
            "file_pattern": "report_",
            "sheet_name": "MRC",
            "extensions": [".xls", ".xlsx"],
            "parser": "windstream_mrc",  # special parser needed
        },
    },

    # ---------------------------------------------------------------
    # GRANITE
    # ---------------------------------------------------------------
    "granite": {
        "invoice_line_charges": {
            "file_pattern": "getinvoicelinecharges",
            "extensions": [".xlsx"],
            "column_map": {
                "PARENT_NAME": "parent_name",
                "PARENT_ACCOUNT": "master_account",
                "ACCOUNT": "sub_account_number",
                "LOCATION": "billing_name",
                "TN": "phone_number",
                "CHARGE TYPE": "charge_type_raw",
                "CATEGORY": "category",
                "CHARGE CODE": "usoc",
                "DESCRIPTION": "description",
                "START DATE": "start_date",
                "END DATE": "end_date",
                "QUANTITY": "quantity",
                "AMOUNT": "amount",
            },
        },
        "usage_report": {
            "file_pattern": "usage_report",
            "extensions": [".xlsx"],
            "column_map": {
                "Parent Account": "master_account",
                "Parent Name": "parent_name",
                "Account": "sub_account_number",
                "Account Name": "billing_name",
                "Calls": "num_calls",
                "Tn": "phone_number",
                "Call Type": "call_type",
                "Call Category": "call_category",
                "Description": "description",
                "Minutes": "ld_minutes",
                "Cost": "ld_cost",
            },
        },
    },

    # ---------------------------------------------------------------
    # CONSOLIDATED COMMUNICATIONS
    # ---------------------------------------------------------------
    "consolidated": {
        "customer_svc_record": {
            "file_pattern": "customer svc record",
            "extensions": [".xlsx"],
            "column_map": {
                "TIE_CODE": "tie_code",
                "BILLING_ACCOUNT_NO": "carrier_account_number",
                "BILLING_ACCOUNT_NAME": "billing_name",
                "SERVICE_ID": "carrier_circuit_number",
                "SERVICE_TYPE": "service_type_raw",
                "SERVICE_ATTRIBUTES": "service_attributes",
                "SERVICE_FEATURES": "service_features",
                "SERVICE_ACCOUNT_NO": "sub_account_number",
                "SERVICE_ACCOUNT_ADDR_LN1": "service_address_1",
                "SERVICE_ACCOUNT_ADDR_LN2": "service_address_2",
                "SERVICE_ACCOUNT_CITY": "city",
                "SERVICE_ACCOUNT_STATE": "state",
                "SERVICE_ACCOUNT_ZIP": "zip_code",
            },
        },
        "csr_report": {
            "file_pattern": "csr",
            "extensions": [".xlsx"],
            "column_map": {
                "Account Number": "carrier_account_number",
                "Zipcode": "zip_code",
                "State": "state",
                "City": "city",
                "Net Num": "phone_number",
                "Acct Name": "billing_name",
                "Street": "service_address_1",
                "House Number": "house_number",
                "Svc Type": "service_type_raw",
            },
        },
    },

    # ---------------------------------------------------------------
    # PEERLESS NETWORK
    # ---------------------------------------------------------------
    "peerless": {
        "subscriptions": {
            "file_pattern": "subscriptions_export",
            "extensions": [".csv"],
            "column_map": {
                "Account ID": "carrier_account_number",
                "Service Name": "service_name",
                "Location Name": "billing_name",
                "Location Address": "full_address",
                "Service Description": "description",
                "USOC1": "usoc",
                "Provider": "provider",
                "MRC": "amount",
                "Tax Code": "tax_code",
                "Status": "service_status",
                "Effective": "contract_begin_date",
                "Ends": "contract_expiration_date",
            },
        },
        "dids": {
            "file_pattern": "dids",
            "extensions": [".csv"],
            "column_map": {
                "DID": "phone_number",
                "Destination Type": "service_type_raw",
                "Destination": "billing_name",
                "Location": "location",
                "USOC1": "usoc",
                "Description": "description",
                "Provider": "provider",
            },
        },
    },

    # ---------------------------------------------------------------
    # SPECTROTEL
    # ---------------------------------------------------------------
    "spectrotel": {
        "usage_billing": {
            "file_pattern": "usage_billing_summary",
            "extensions": [".xlsx"],
            "column_map": {
                "CustomerID": "carrier_account_number",
                "CompanyName": "billing_name",
                "BillCycle": "bill_cycle",
                "ServiceNumber": "phone_number",
                "LineType": "service_type_raw",
                "LineEffDate": "contract_begin_date",
                "LocUsgCharge": "local_usage",
                "RegUsgCharge": "regional_usage",
                "LDUsgCharge": "ld_usage",
                "IntUsgCharge": "int_usage",
                "Minutes": "ld_minutes",
            },
        },
    },

    # ---------------------------------------------------------------
    # NEXTIVA
    # ---------------------------------------------------------------
    "nextiva": {
        "phone_numbers": {
            "file_pattern": "phonenumbers",
            "extensions": [".xlsx"],
            "column_map": {
                "Name": "billing_name",
                "Number": "phone_number",
                "Extension": "extension",
                "Group Id": "location",
            },
        },
    },

    # ---------------------------------------------------------------
    # LUMEN
    # ---------------------------------------------------------------
    "lumen": {
        "sfdc_report": {
            "file_pattern": "sfdc",
            "extensions": [".xlsx"],
            "auto_detect": True,
        },
    },
}


# ---------------------------------------------------------------------------
# Service type mapping rules per carrier
# ---------------------------------------------------------------------------

WINDSTREAM_CIRCUIT_TO_SERVICE = {
    "customer provided access": "UCaaS",
    "sd-wan management-concierge": "SDWAN",
    "sd-wan management": "SDWAN",
    "sd-wan service license": "SDWAN",
    "cellular broadband internet access": "Wireless Cellular Internet",
    "cellular broadband charge": "Wireless Cellular Internet",
    "ethernet access": "Ethernet",
    "internet service": "DIA",
    "access loop": "UCaaS",
    "voip": "UCaaS",
    "broadband": "Broadband",
    "email": "Other",
    "centrex": "Centrex",
    "centrex link": "Centrex",
    "ibn exchange": "Centrex",
    "billed number": "Centrex",
}

GRANITE_CATEGORY_TO_SERVICE = {
    "CHG": "POTS",
    "LTE": "POTS",
    "OTH": "POTS",
    "TXS": "Account Level",
    "SUR": "Account Level",
    "USG": "Usage",
    "RCF": "RCF",
    "CNX": "Centrex",
}

CONSOLIDATED_TYPE_TO_SERVICE = {
    "ethernet virtual connection evc": "DIA",
    "carrier ethernet service ces": "DIA",
    "operator virtual circuit ovc": "DIA",
    "pots": "POTS",
    "centrex": "Centrex",
    "sip trunk": "SIP Trunk",
    "sip": "SIP Trunk",
    "pri": "ISDN PRI",
    "internet": "DIA",
    "broadband": "Broadband",
}

PEERLESS_TYPE_TO_SERVICE = {
    "sip trunk": "SIP Trunk",
    "did with 911": "SIP Trunk",
    "did basic": "SIP Trunk",
    "did": "DID",
}

SPECTROTEL_TYPE_TO_SERVICE = {
    "pots - local/regional/ld": "POTS",
    "pots": "POTS",
}


# ---------------------------------------------------------------------------
# Charge type mapping
# ---------------------------------------------------------------------------

def _classify_charge_type(raw: Optional[str], amount: Optional[float] = None) -> str:
    """Classify raw charge type strings into standard charge types."""
    if not raw:
        return "MRC"
    raw_lower = str(raw).lower().strip()
    if raw_lower in ("mrc", "recurring", "monthly"):
        return "MRC"
    if raw_lower in ("nrc", "one-time", "occ", "one time"):
        return "NRC"
    if raw_lower in ("usage", "usg"):
        return "Usage"
    if raw_lower in ("taxes", "tax", "txs"):
        return "Taxes"
    if raw_lower in ("surcharge", "sur", "surcharges"):
        return "Surcharge"
    if raw_lower in ("prorated", "prorated charges", "pro-rated"):
        return "ProRated"
    if raw_lower in ("lte",):
        return "OCC"
    return "MRC"


# ---------------------------------------------------------------------------
# S/C/U/T\S\OCC classification logic
# ---------------------------------------------------------------------------

def _classify_scu(charge_type: str, is_service_level: bool = False,
                  is_usage: bool = False) -> str:
    """Classify a row as S, C, U, or T\\S\\OCC."""
    if charge_type in ("Taxes", "Surcharge", "NRC", "OCC", "ProRated"):
        return "T\\S\\OCC"
    if is_usage:
        return "U"
    if is_service_level:
        return "S"
    return "C"


# ---------------------------------------------------------------------------
# Address parsing helpers
# ---------------------------------------------------------------------------

def _parse_full_address(full_addr: Optional[str]) -> dict:
    """Parse 'street, city, state, zip' format addresses."""
    result = {"service_address_1": None, "city": None, "state": None, "zip_code": None}
    if not full_addr or pd.isna(full_addr):
        return result
    full_addr = str(full_addr).strip()
    # Try "street, city, state, zip" or "street# zip city state zip"
    parts = [p.strip() for p in full_addr.split(",")]
    if len(parts) >= 4:
        result["service_address_1"] = parts[0]
        result["city"] = parts[1]
        result["state"] = parts[2].strip()[:2] if len(parts[2].strip()) >= 2 else parts[2]
        result["zip_code"] = parts[3].strip()[:5] if parts[3].strip() else None
    elif len(parts) == 3:
        result["service_address_1"] = parts[0]
        result["city"] = parts[1]
        # state zip
        st_zip = parts[2].strip().split()
        if st_zip:
            result["state"] = st_zip[0]
        if len(st_zip) > 1:
            result["zip_code"] = st_zip[-1][:5]
    elif len(parts) == 1:
        # Try pattern: "123 Main St Somewhere NY 12345"
        m = re.match(r"(.+?)\s+(\w+)\s+([A-Z]{2})\s+(\d{5})", full_addr)
        if m:
            result["service_address_1"] = m.group(1).strip()
            result["city"] = m.group(2).strip()
            result["state"] = m.group(3)
            result["zip_code"] = m.group(4)
    return result


def _normalize_zip(z: Optional[str]) -> Optional[str]:
    """Normalize zip code to 5 digits."""
    if not z or pd.isna(z):
        return None
    z = str(z).strip().split("-")[0].split(".")[0]
    z = re.sub(r"[^\d]", "", z)
    if len(z) >= 5:
        return z[:5]
    if len(z) > 0:
        return z.zfill(5)
    return None


# ===================================================================
# MAIN GENERIC EXTRACTOR CLASS
# ===================================================================

class GenericCarrierExtractor(CarrierExtractor):
    """
    Generic multi-carrier extractor.
    Reads structured Excel/CSV carrier reports and maps to the
    60-column inventory schema.
    """

    def __init__(self, carrier_key: str, carrier_name: str,
                 carrier_account_number: Optional[str] = None):
        self._carrier_key = carrier_key
        self._carrier_name = carrier_name
        self._carrier_account_number = carrier_account_number

    @property
    def carrier_key(self) -> str:
        return self._carrier_key

    @property
    def carrier_name(self) -> str:
        return self._carrier_name

    def extract(
        self,
        invoice_dir: Optional[Path] = None,
        report_dir: Optional[Path] = None,
        contract_dir: Optional[Path] = None,
        api_key: Optional[str] = None,
    ) -> ExtractionResult:
        warnings = []
        errors = []
        stats = {}
        all_rows = []

        logger.info(f"Starting generic extraction for: {self._carrier_name}")

        # Dispatch to carrier-specific extraction
        key = self._carrier_key.lower()

        if key == "windstream":
            all_rows, w, s = self._extract_windstream(report_dir, contract_dir, invoice_dir)
        elif key == "granite":
            all_rows, w, s = self._extract_granite(report_dir, contract_dir, invoice_dir)
        elif key == "consolidated":
            all_rows, w, s = self._extract_consolidated(report_dir, contract_dir, invoice_dir)
        elif key == "peerless":
            all_rows, w, s = self._extract_peerless(report_dir, contract_dir, invoice_dir)
        elif key == "spectrotel":
            all_rows, w, s = self._extract_spectrotel(report_dir, contract_dir, invoice_dir)
        elif key == "nextiva":
            all_rows, w, s = self._extract_nextiva(report_dir, contract_dir, invoice_dir)
        elif key == "lumen":
            all_rows, w, s = self._extract_lumen(report_dir, contract_dir, invoice_dir)
        elif key == "frontier":
            all_rows, w, s = self._extract_frontier(report_dir, contract_dir, invoice_dir)
        else:
            # Fallback: try to auto-detect any Excel/CSV in report dir
            all_rows, w, s = self._extract_generic_fallback(
                report_dir, contract_dir, invoice_dir
            )

        warnings.extend(w)
        stats.update(s)
        stats["total_rows"] = len(all_rows)
        stats["s_rows"] = sum(1 for r in all_rows if r.service_or_component == "S")
        stats["c_rows"] = sum(1 for r in all_rows if r.service_or_component == "C")
        stats["u_rows"] = sum(1 for r in all_rows if r.service_or_component == "U")
        stats["tsocc_rows"] = sum(1 for r in all_rows if r.service_or_component == "T\\S\\OCC")

        logger.info(f"Extraction complete for {self._carrier_name}: {len(all_rows)} rows")

        return ExtractionResult(
            carrier_key=self._carrier_key,
            carrier_name=self._carrier_name,
            rows=all_rows,
            warnings=warnings,
            errors=errors,
            stats=stats,
        )

    # ---------------------------------------------------------------
    # WINDSTREAM EXTRACTION
    # ---------------------------------------------------------------
    def _extract_windstream(self, report_dir, contract_dir, invoice_dir):
        warnings = []
        stats = {}
        rows = []

        if not report_dir or not report_dir.exists():
            warnings.append("No report directory for Windstream")
            return rows, warnings, stats

        # 1. Load Customer Inventory by COMMS (primary: sites + circuits)
        #    NOTE: The COMMS report may be a shared file containing data for
        #    multiple carriers (e.g. both Windstream and Charter).
        #    Filter to only Windstream rows using Parent ID from config.
        comms_records = self._load_report(
            report_dir, "customer inventory by comms", [".xlsx", ".xls"],
            sheet_name="Customer Inventory by COMMS"
        )
        total_before_filter = len(comms_records)

        # Filter to Windstream parent ID if configured
        from config import CARRIER_REGISTRY
        ws_parent_id = CARRIER_REGISTRY.get("windstream", {}).get("parent_id")
        if ws_parent_id and total_before_filter > 0:
            filtered = []
            for rec in comms_records:
                pid = str(rec.get("Parent ID") or "").strip()
                if pid.endswith(".0"):
                    pid = pid[:-2]
                if pid == ws_parent_id or not pid:
                    filtered.append(rec)
            if len(filtered) < total_before_filter:
                logger.info(
                    f"Windstream COMMS filter: kept {len(filtered)} of "
                    f"{total_before_filter} rows (Parent ID={ws_parent_id})"
                )
                warnings.append(
                    f"Shared COMMS report: filtered to {len(filtered)} Windstream rows "
                    f"(skipped {total_before_filter - len(filtered)} rows belonging to other carriers)"
                )
            comms_records = filtered

        stats["comms_records"] = len(comms_records)
        logger.info(f"Windstream COMMS records: {len(comms_records)}")

        # 2. Load ServiceLocationsExport (contract info)
        svc_loc_records = self._load_report(
            report_dir, "servicelocationsexport", [".xlsx"]
        )
        stats["service_location_records"] = len(svc_loc_records)

        # 3. Load MyLocations (circuit + service info)
        my_loc_records = self._load_report(
            report_dir, "mylocations", [".xlsx"]
        )
        stats["my_locations_records"] = len(my_loc_records)

        # 4. Load MonthlySummary (cellular lines)
        cellular_records = self._load_windstream_monthly_summary(report_dir)
        stats["cellular_records"] = len(cellular_records)

        # 5. Load MRC Report (pricing data)
        mrc_records = self._load_windstream_mrc_report(report_dir)
        stats["mrc_records"] = len(mrc_records)

        # 6. Load All Active TN (phone numbers)
        tn_records = self._load_report(
            report_dir, "all active tn", [".xlsx"]
        )
        stats["active_tn_records"] = len(tn_records)

        # Build site-level grouping from COMMS report
        # Group by (account, address) -> list of circuits
        sites = {}
        for rec in comms_records:
            addr = (rec.get("ADDR1") or "").strip().upper()
            city = (rec.get("CITY") or "").strip()
            state = (rec.get("STATE") or "").strip()
            zip_code = (rec.get("ZIP") or "").strip()
            acct = str(rec.get("Customer #") or rec.get("Parent ID") or "").strip()
            parent = str(rec.get("Parent ID") or "").strip()
            name = (rec.get("Customer Name") or "").strip()
            circuit_type = (rec.get("Circuit Type") or "").strip()
            circuit_id = (rec.get("Circuit ID") or "").strip()
            tn = (rec.get("TN") or "").strip()
            tn_type = (rec.get("TN Type") or "").strip()
            tn_status = (rec.get("TN Status") or "").strip()
            circuit_status = (rec.get("Circuit Status") or "").strip()

            # Only include working/active records
            if tn_status and tn_status.lower() not in ("working", "active", ""):
                continue
            if circuit_status and circuit_status.lower() not in ("in service", "active", ""):
                continue

            site_key = (acct, addr, city)
            if site_key not in sites:
                sites[site_key] = {
                    "account": acct,
                    "parent": parent,
                    "name": name,
                    "address": addr,
                    "city": city,
                    "state": state,
                    "zip_code": zip_code,
                    "circuits": [],
                    "tns": [],
                    "circuit_types": set(),
                    "tn_types": set(),  # Track TN types for service classification
                }
            site = sites[site_key]
            if circuit_type:
                site["circuit_types"].add(circuit_type)
            if tn_type:
                site["tn_types"].add(tn_type)
            if circuit_id:
                site["circuits"].append({
                    "circuit_id": circuit_id,
                    "circuit_type": circuit_type,
                })
            if tn:
                site["tns"].append({
                    "tn": tn,
                    "tn_type": tn_type,
                })

        # Build MRC lookup by (account, address)
        mrc_by_site = {}
        for rec in mrc_records:
            acct = str(rec.get("account", "")).strip()
            svc = (rec.get("service", "") or "").strip().lower()
            feature = (rec.get("feature", "") or "").strip()
            desc = (rec.get("description", "") or "").strip()
            cost = rec.get("cost")
            key = (acct, feature.lower() if feature else svc)
            if key not in mrc_by_site:
                mrc_by_site[key] = []
            mrc_by_site[key].append({
                "service": svc,
                "feature": feature,
                "description": desc,
                "cost": cost,
                "quantity": rec.get("quantity"),
            })

        # Build service location lookup for contract data
        svc_loc_by_acct = {}
        for rec in svc_loc_records:
            acct = str(rec.get("Billable Account ID") or "").strip().split(".")[0]
            svc_loc_by_acct.setdefault(acct, []).append(rec)

        # Determine carrier account number (from reference: 2389882 is main)
        main_account = "2389882"

        # Now build inventory rows from sites
        for site_key, site in sites.items():
            acct = site["account"]
            parent = site["parent"]
            addr = site["address"]
            city = site["city"]
            state = site["state"]
            zip_code = _normalize_zip(site["zip_code"])
            name = site["name"]

            # Determine ALL service types present at this site (from circuit types AND TN types)
            site_service_types = self._windstream_all_service_types(
                site["circuit_types"], site.get("tn_types", set())
            )
            # Normalize all via central map
            site_service_types = [normalize_service_type(st, "windstream") for st in site_service_types]
            # Deduplicate
            site_service_types = list(dict.fromkeys(site_service_types))

            # Try to get MRC from MRC report
            s_mrc = self._find_windstream_site_mrc(mrc_records, acct, site["circuit_types"])

            # Contract info from service locations
            contract_info = {}
            svc_locs = svc_loc_by_acct.get(acct, [])
            if svc_locs:
                loc = svc_locs[0]
                begin = loc.get("Agreement Start Date")
                end = loc.get("Agreement End Date")
                term = loc.get("Term")
                if pd.notna(end) and str(end) != "1999-12-31":
                    contract_info["expiration"] = str(end)[:10] if pd.notna(end) else None
                    contract_info["begin"] = str(begin)[:10] if pd.notna(begin) else None
                    contract_info["term"] = float(term) if pd.notna(term) and term else None
                    contract_info["m2m"] = "No"
                else:
                    contract_info["m2m"] = "Yes"

            # Create ONE S-row PER service type (matching reference pattern)
            for stype in site_service_types:
                s_row = InventoryRow(
                    status="In Progress",
                    carrier=self._carrier_name,
                    carrier_account_number=main_account if parent == main_account else acct,
                    sub_account_number=acct if acct != main_account else None,
                    billing_name=name,
                    service_address_1=addr.title() if addr else None,
                    city=city.title() if city else None,
                    state=state.upper() if state else None,
                    zip_code=zip_code,
                    country="USA",
                    service_type=stype,
                    service_or_component="S",
                    charge_type="MRC",
                    quantity=1.0,
                    conversion_rate=1.0,
                    currency="USD",
                )

                if s_mrc is not None and len(site_service_types) > 0:
                    per_type_mrc = s_mrc / len(site_service_types)
                    s_row.monthly_recurring_cost = round(per_type_mrc, 2)
                    s_row.cost_per_unit = round(per_type_mrc, 2)
                    s_row.mrc_per_currency = round(per_type_mrc, 2)

                if contract_info:
                    s_row.contract_expiration_date = contract_info.get("expiration")
                    s_row.contract_begin_date = contract_info.get("begin")
                    s_row.contract_term = contract_info.get("term")
                    s_row.currently_month_to_month = contract_info.get("m2m")

                s_row.linkage_key = f"WS_{acct}_{addr}_{stype}"
                rows.append(s_row)

            # Create C-rows for distinct circuit types at this site
            seen_types = set()
            # Determine primary service type for C-rows
            primary_stype = site_service_types[0] if site_service_types else "UCaaS"
            for ct in site["circuit_types"]:
                if not ct or ct in seen_types:
                    continue
                seen_types.add(ct)

                # Determine which service type this circuit belongs to
                ct_stype = self._windstream_service_type_v2({ct}, set())
                ct_stype = normalize_service_type(ct_stype, "windstream")
                if ct_stype not in site_service_types:
                    ct_stype = primary_stype

                c_row = InventoryRow(
                    status="In Progress",
                    carrier=self._carrier_name,
                    carrier_account_number=main_account if parent == main_account else acct,
                    sub_account_number=acct if acct != main_account else None,
                    billing_name=name,
                    service_address_1=addr.title() if addr else None,
                    city=city.title() if city else None,
                    state=state.upper() if state else None,
                    zip_code=zip_code,
                    country="USA",
                    service_type=ct_stype,
                    service_or_component="C",
                    component_or_feature_name=ct,
                    charge_type="MRC",
                    quantity=1.0,
                    conversion_rate=1.0,
                    currency="USD",
                )

                # Look up MRC for this component
                c_mrc = self._find_windstream_component_mrc(mrc_records, acct, ct)
                if c_mrc is not None:
                    c_row.monthly_recurring_cost = c_mrc
                    c_row.cost_per_unit = c_mrc
                    c_row.mrc_per_currency = c_mrc

                # Circuit ID
                for circ in site["circuits"]:
                    if circ["circuit_type"] == ct and circ["circuit_id"]:
                        c_row.carrier_circuit_number = circ["circuit_id"]
                        break

                # Speed extraction from circuit type
                speed = self._extract_speed(ct)
                if speed:
                    c_row.access_speed = speed
                    c_row.upload_speed = speed

                c_row.linkage_key = f"WS_{acct}_{addr}"
                rows.append(c_row)

        # Add cellular lines from MonthlySummary
        for rec in cellular_records:
            tn = str(rec.get("phone_number", "")).strip()
            if not tn or tn == "nan":
                continue

            addr = (rec.get("service_address_1") or "").strip()
            city_val = (rec.get("city") or "").strip()
            state_val = (rec.get("state") or "").strip()
            zip_val = _normalize_zip(rec.get("zip_code"))
            name_val = (rec.get("billing_name") or "").strip()
            acct = str(rec.get("sub_account_number") or "").strip()

            cell_row = InventoryRow(
                status="In Progress",
                carrier=self._carrier_name,
                carrier_account_number=main_account,
                sub_account_number=acct if acct else None,
                billing_name=name_val if name_val else None,
                service_address_1=addr if addr else None,
                city=city_val if city_val else None,
                state=state_val if state_val else None,
                zip_code=zip_val,
                country="USA",
                service_type="Wireless Cellular Internet",
                service_or_component="C",
                component_or_feature_name=f"Cellular Broadband Internet Access - {rec.get('plan', '5GB')}",
                phone_number=tn,
                charge_type="MRC",
                quantity=1.0,
                conversion_rate=1.0,
                currency="USD",
            )
            rows.append(cell_row)

        # --- Extract additional Windstream accounts from separate report files ---
        extra_account_rows = self._extract_windstream_extra_accounts(report_dir, main_account)
        rows.extend(extra_account_rows)

        # --- Generate additional rows from MRC report for services NOT in COMMS ---
        # The MRC report contains SDWAN, UCaaS, SIP Trunk, Centrex, Account Level
        # services that may not appear in the Customer Inventory by COMMS report
        comms_accounts = {site["account"] for _, site in sites.items()}
        mrc_service_rows = self._build_windstream_mrc_service_rows(
            mrc_records, comms_accounts, main_account, svc_loc_by_acct
        )
        rows.extend(mrc_service_rows)

        # --- Generate S-rows from ServiceLocationsExport for contract/service data ---
        svc_loc_rows = self._build_windstream_svc_loc_rows(
            svc_loc_records, comms_accounts, main_account
        )
        rows.extend(svc_loc_rows)

        # --- Generate rows from All Active TN for phone numbers not yet covered ---
        tn_rows = self._build_windstream_tn_rows(
            tn_records, comms_accounts, main_account
        )
        rows.extend(tn_rows)

        logger.info(f"Windstream extraction: {len(rows)} rows from {len(sites)} sites + {len(cellular_records)} cellular + {len(mrc_service_rows)} MRC + {len(svc_loc_rows)} svc_loc + {len(tn_rows)} TN")
        return rows, warnings, stats

    def _windstream_service_type(self, circuit_types: set) -> str:
        """Determine Windstream service type from circuit types at a site."""
        types_lower = {ct.lower() for ct in circuit_types if ct}

        # Priority order: SDWAN > UCaaS > SIP Trunk > Centrex > DIA > other
        # Check for SDWAN first (highest priority)
        for ct_lower in types_lower:
            if "sd-wan" in ct_lower or "sdwan" in ct_lower:
                return "SDWAN"

        # Check for SIP Trunk
        for ct_lower in types_lower:
            if "trunk" in ct_lower or "sip" in ct_lower:
                return "SIP Trunk"

        # Check for Centrex
        for ct_lower in types_lower:
            if "centrex" in ct_lower or "ibn" in ct_lower or "billed number" in ct_lower:
                return "Centrex"

        # Check for UCaaS (VoIP, access loop, customer provided access)
        for ct_lower in types_lower:
            if "voip" in ct_lower or "access loop" in ct_lower or "customer provided" in ct_lower:
                return "UCaaS"

        # Check for Internet/DIA
        for ct_lower in types_lower:
            if "internet" in ct_lower or "ethernet" in ct_lower:
                return "DIA"

        # Check for Broadband
        for ct_lower in types_lower:
            if "broadband" in ct_lower:
                return "Broadband"

        # Check for cellular
        for ct_lower in types_lower:
            if "cellular" in ct_lower:
                return "Wireless Cellular Internet"

        # Fallback to carrier-specific map
        for ct_lower in types_lower:
            for pattern, stype in WINDSTREAM_CIRCUIT_TO_SERVICE.items():
                if pattern in ct_lower:
                    return stype

        if types_lower:
            return "UCaaS"  # default for Windstream
        return "UCaaS"

    def _windstream_service_type_v2(self, circuit_types: set, tn_types: set) -> str:
        """Determine Windstream service type from both circuit types AND TN types.

        TN Types like 'VoIP Connection Number' are more common and better
        indicate the service type than Circuit Types.
        """
        ct_lower = {ct.lower() for ct in circuit_types if ct}
        tt_lower = {tt.lower() for tt in tn_types if tt}
        all_lower = ct_lower | tt_lower

        # Priority order: SDWAN > UCaaS > SIP Trunk > Centrex > DIA > other

        # Check for SDWAN
        for t in all_lower:
            if "sd-wan" in t or "sdwan" in t:
                return "SDWAN"

        # Check for SIP Trunk
        for t in all_lower:
            if "trunk" in t and ("sip" in t or "metaswitch" in t):
                return "SIP Trunk"

        # Check for Centrex
        for t in all_lower:
            if "centrex" in t or "ibn" in t or "billed number" in t:
                return "Centrex"

        # Check for UCaaS (VoIP, access loop, customer provided access, voice)
        for t in all_lower:
            if any(kw in t for kw in ("voip", "access loop", "customer provided",
                                       "voice", "dvl", "digital voice",
                                       "legacy service", "remote did")):
                return "UCaaS"

        # Check for Internet/DIA/Ethernet
        for t in all_lower:
            if "internet" in t and "cellular" not in t:
                return "DIA"
            if "ethernet" in t:
                return "Ethernet"

        # Check for MPLS
        for t in all_lower:
            if "mpls" in t:
                return "MPLS"

        # Check for Broadband
        for t in all_lower:
            if "broadband" in t and "cellular" not in t:
                return "Broadband"

        # Check for cellular
        for t in all_lower:
            if "cellular" in t:
                return "Wireless Cellular Internet"

        # Fallback
        if all_lower:
            return "UCaaS"  # default for Windstream
        return "UCaaS"

    def _windstream_all_service_types(self, circuit_types: set, tn_types: set) -> list[str]:
        """Determine ALL service types present at a Windstream site.

        In the reference, each site can have multiple S-rows with different
        service types (UCaaS, SDWAN, Wireless Cellular Internet, etc.).
        We return a list of all applicable service types.
        """
        stypes = set()
        ct_lower = {ct.lower() for ct in circuit_types if ct}
        tt_lower = {tt.lower() for tt in tn_types if tt}

        # Check for SDWAN
        for t in ct_lower | tt_lower:
            if "sd-wan" in t or "sdwan" in t:
                stypes.add("SDWAN")

        # Check for UCaaS (VoIP, access loop, voice)
        for t in tt_lower:
            if any(kw in t for kw in ("voip", "access loop", "customer provided",
                                       "voice", "dvl", "digital voice",
                                       "legacy service", "remote did")):
                stypes.add("UCaaS")
        for t in ct_lower:
            if any(kw in t for kw in ("customer provided", "voip", "access loop")):
                stypes.add("UCaaS")

        # Check for SIP Trunk
        for t in ct_lower | tt_lower:
            if "trunk" in t and ("sip" in t or "metaswitch" in t):
                stypes.add("SIP Trunk")

        # Check for Centrex
        for t in ct_lower | tt_lower:
            if "centrex" in t or "ibn" in t or "billed number" in t:
                stypes.add("Centrex")

        # Check for Wireless Cellular Internet
        for t in ct_lower | tt_lower:
            if "cellular" in t:
                stypes.add("Wireless Cellular Internet")

        # Check for DIA/Ethernet
        for t in ct_lower | tt_lower:
            if ("internet" in t and "cellular" not in t):
                stypes.add("DIA")
            if "ethernet" in t:
                stypes.add("Ethernet")

        # Check for MPLS
        for t in ct_lower | tt_lower:
            if "mpls" in t:
                stypes.add("MPLS")

        # Default: at least UCaaS if there are VoIP TNs
        if not stypes and tt_lower:
            stypes.add("UCaaS")

        return list(stypes) if stypes else ["UCaaS"]

    def _find_windstream_site_mrc(self, mrc_records, acct, circuit_types):
        """Find total MRC for a site from MRC report data."""
        total = 0.0
        found = False
        for rec in mrc_records:
            if str(rec.get("account", "")).strip() == acct:
                cost = rec.get("cost")
                if cost and pd.notna(cost):
                    try:
                        total += float(cost)
                        found = True
                    except (ValueError, TypeError):
                        pass
        return total if found else None

    def _find_windstream_component_mrc(self, mrc_records, acct, circuit_type):
        """Find MRC for a specific component from MRC report."""
        ct_lower = circuit_type.lower() if circuit_type else ""
        for rec in mrc_records:
            if str(rec.get("account", "")).strip() == acct:
                desc = (rec.get("description") or "").lower()
                feature = (rec.get("feature") or "").lower()
                if ct_lower and (ct_lower in desc or ct_lower in feature):
                    cost = rec.get("cost")
                    if cost and pd.notna(cost):
                        try:
                            return float(cost)
                        except (ValueError, TypeError):
                            pass
        return None

    def _extract_windstream_extra_accounts(self, report_dir, main_account) -> list[InventoryRow]:
        """Extract rows from secondary Windstream account report files.

        Files like '021942648_Report.xls' contain billing data for
        separate Windstream accounts (Centrex, POTS lines).
        """
        rows = []
        if not report_dir or not report_dir.exists():
            return rows

        for f in report_dir.iterdir():
            # Match pattern: ACCTNUM_Report.xls (but NOT 'Report_' which is the main MRC)
            if not re.match(r"^\d+_Report\.", f.name, re.IGNORECASE):
                continue

            acct_match = re.match(r"^(\d+)_Report", f.name, re.IGNORECASE)
            if not acct_match:
                continue
            extra_acct = acct_match.group(1)

            try:
                # Try to read CAMS Invoice Detail sheet
                df = pd.read_excel(f, sheet_name="CAMS Invoice Detail", header=None)
                # Find header row
                header_idx = None
                for i in range(min(10, len(df))):
                    row_vals = [str(v).strip() for v in df.iloc[i] if pd.notna(v)]
                    if "Account Number" in row_vals or "Telephone Number" in row_vals:
                        header_idx = i
                        break

                if header_idx is None:
                    continue

                df.columns = [str(c).strip() for c in df.iloc[header_idx]]
                df = df.iloc[header_idx + 1:].reset_index(drop=True)

                # Group by Telephone Number for S-rows
                tn_groups = {}
                for _, row in df.iterrows():
                    tn = str(row.get("Telephone Number", "")).strip()
                    if not tn or tn == "nan":
                        continue
                    amt = row.get("Amt")
                    bill_cat = str(row.get("Bill Category", "")).strip()

                    if tn not in tn_groups:
                        tn_groups[tn] = {"charges": [], "categories": set()}
                    tn_groups[tn]["charges"].append({
                        "category": bill_cat,
                        "amount": float(amt) if pd.notna(amt) else 0.0,
                    })
                    tn_groups[tn]["categories"].add(bill_cat.lower())

                # Create S and C rows
                for tn, data in tn_groups.items():
                    # Determine service type from categories
                    cats = data["categories"]
                    service_type = "Centrex"  # Default for secondary accounts
                    if any("centrex" in c for c in cats):
                        service_type = "Centrex"
                    elif any("trunk" in c for c in cats):
                        service_type = "SIP Trunk"
                    elif any("access" in c for c in cats):
                        service_type = "UCaaS"

                    total_mrc = sum(c["amount"] for c in data["charges"])

                    s_row = InventoryRow(
                        status="In Progress",
                        carrier=self._carrier_name,
                        carrier_account_number=extra_acct,
                        billing_name=None,
                        country="USA",
                        phone_number=tn.replace("-", ""),
                        service_type=normalize_service_type(service_type, "windstream"),
                        service_or_component="S",
                        monthly_recurring_cost=total_mrc if total_mrc else None,
                        cost_per_unit=total_mrc if total_mrc else None,
                        mrc_per_currency=total_mrc if total_mrc else None,
                        charge_type="MRC",
                        quantity=1.0,
                        conversion_rate=1.0,
                        currency="USD",
                        linkage_key=f"WS_EXTRA_{extra_acct}_{tn}",
                    )
                    rows.append(s_row)

                logger.info(f"Windstream extra account {extra_acct}: {len(tn_groups)} phone lines -> {len(rows)} rows")

            except Exception as e:
                logger.warning(f"Failed to parse Windstream extra report {f.name}: {e}")

        return rows

    def _build_windstream_mrc_service_rows(
        self, mrc_records, comms_accounts, main_account, svc_loc_by_acct
    ) -> list[InventoryRow]:
        """Build S/C rows from MRC report for accounts NOT in COMMS report.

        The MRC report has a hierarchical structure with services like
        SDWAN, UCaaS (VoIP), SIP Trunk, Centrex that may not appear
        in the Customer Inventory by COMMS report.
        """
        rows = []
        # Group MRC records by account
        mrc_by_account = {}
        for rec in mrc_records:
            acct = str(rec.get("account", "")).strip()
            if not acct:
                continue
            mrc_by_account.setdefault(acct, []).append(rec)

        for acct, records in mrc_by_account.items():
            if acct in comms_accounts:
                continue  # Already covered by COMMS extraction

            # Get name from first record
            name = records[0].get("name", "")

            # Determine service types from MRC services/features
            service_types = set()
            for rec in records:
                svc = (rec.get("service") or "").strip().lower()
                feature = (rec.get("feature") or "").strip().lower()
                desc = (rec.get("description") or "").strip().lower()
                combined = f"{svc} {feature} {desc}"

                if "sd-wan" in combined or "sdwan" in combined:
                    service_types.add("SDWAN")
                elif "voip" in combined or "ucaas" in combined or "unified" in combined:
                    service_types.add("UCaaS")
                elif "sip" in combined or "trunk" in combined:
                    service_types.add("SIP Trunk")
                elif "centrex" in combined or "ibn" in combined:
                    service_types.add("Centrex")
                elif "internet" in combined or "ethernet" in combined:
                    service_types.add("DIA")
                elif "broadband" in combined:
                    service_types.add("Broadband")

            if not service_types:
                service_types.add("UCaaS")  # Default for Windstream

            # Get address from svc_loc if available
            svc_locs = svc_loc_by_acct.get(acct, [])
            addr = city_val = state_val = zip_val = None
            if svc_locs:
                loc = svc_locs[0]
                addr = (loc.get("Service Street") or "").strip()
                city_val = (loc.get("Service City") or "").strip()
                state_val = (loc.get("Service State") or "").strip()
                zip_val = _normalize_zip(loc.get("Service Postal Code"))

            total_mrc = sum(
                float(r.get("cost", 0)) for r in records
                if r.get("cost") and pd.notna(r.get("cost"))
            )

            for stype in service_types:
                stype = normalize_service_type(stype, "windstream")
                s_row = InventoryRow(
                    status="In Progress",
                    carrier=self._carrier_name,
                    carrier_account_number=main_account,
                    sub_account_number=acct,
                    billing_name=name if name else None,
                    service_address_1=addr if addr else None,
                    city=city_val if city_val else None,
                    state=state_val if state_val else None,
                    zip_code=zip_val,
                    country="USA",
                    service_type=stype,
                    service_or_component="S",
                    monthly_recurring_cost=total_mrc if total_mrc else None,
                    cost_per_unit=total_mrc if total_mrc else None,
                    mrc_per_currency=total_mrc if total_mrc else None,
                    charge_type="MRC",
                    quantity=1.0,
                    conversion_rate=1.0,
                    currency="USD",
                    linkage_key=f"WS_MRC_{acct}_{stype}",
                )
                rows.append(s_row)

                # C-rows for each service/feature line
                for rec in records:
                    svc = (rec.get("service") or "").strip()
                    feature = (rec.get("feature") or "").strip()
                    desc = (rec.get("description") or "").strip()
                    cost = rec.get("cost")
                    qty = rec.get("quantity")

                    comp_name = feature or desc or svc
                    if not comp_name:
                        continue

                    c_row = InventoryRow(
                        status="In Progress",
                        carrier=self._carrier_name,
                        carrier_account_number=main_account,
                        sub_account_number=acct,
                        billing_name=name if name else None,
                        service_address_1=addr if addr else None,
                        city=city_val if city_val else None,
                        state=state_val if state_val else None,
                        zip_code=zip_val,
                        country="USA",
                        service_type=stype,
                        service_or_component="C",
                        component_or_feature_name=comp_name,
                        monthly_recurring_cost=float(cost) if cost and pd.notna(cost) else None,
                        cost_per_unit=float(cost) if cost and pd.notna(cost) else None,
                        mrc_per_currency=float(cost) if cost and pd.notna(cost) else None,
                        charge_type="MRC",
                        quantity=float(qty) if qty and pd.notna(qty) else 1.0,
                        conversion_rate=1.0,
                        currency="USD",
                        linkage_key=f"WS_MRC_{acct}_{stype}",
                    )
                    rows.append(c_row)

        return rows

    def _build_windstream_svc_loc_rows(
        self, svc_loc_records, comms_accounts, main_account
    ) -> list[InventoryRow]:
        """Build S-rows from ServiceLocationsExport for accounts not in COMMS."""
        rows = []
        seen = set()

        for rec in svc_loc_records:
            acct = str(rec.get("Billable Account ID") or "").strip().split(".")[0]
            if not acct or acct in comms_accounts:
                continue

            key = acct
            if key in seen:
                continue
            seen.add(key)

            name = (rec.get("Service Location Name") or "").strip()
            addr = (rec.get("Service Street") or "").strip()
            city_val = (rec.get("Service City") or "").strip()
            state_val = (rec.get("Service State") or "").strip()
            zip_val = _normalize_zip(rec.get("Service Postal Code"))
            status = (rec.get("Service Status") or "").strip()

            if status and status.lower() not in ("active", "in service", ""):
                continue

            s_row = InventoryRow(
                status="In Progress",
                carrier=self._carrier_name,
                carrier_account_number=main_account,
                sub_account_number=acct,
                billing_name=name if name else None,
                service_address_1=addr if addr else None,
                city=city_val if city_val else None,
                state=state_val if state_val else None,
                zip_code=zip_val,
                country="USA",
                service_type="UCaaS",
                service_or_component="S",
                charge_type="MRC",
                quantity=1.0,
                conversion_rate=1.0,
                currency="USD",
                linkage_key=f"WS_SvcLoc_{acct}",
            )

            # Contract info
            begin = rec.get("Agreement Start Date")
            end = rec.get("Agreement End Date")
            term = rec.get("Term")
            if pd.notna(end) and str(end) != "1999-12-31":
                s_row.contract_expiration_date = str(end)[:10] if pd.notna(end) else None
                s_row.contract_begin_date = str(begin)[:10] if pd.notna(begin) else None
                s_row.contract_term = float(term) if pd.notna(term) and term else None

            rows.append(s_row)

        return rows

    def _build_windstream_tn_rows(
        self, tn_records, comms_accounts, main_account
    ) -> list[InventoryRow]:
        """Build C-rows from All Active TN for accounts not yet covered."""
        rows = []
        # Group by account
        tn_by_acct = {}
        for rec in tn_records:
            acct = str(rec.get("Account Number") or "").strip()
            if not acct:
                continue
            tn_by_acct.setdefault(acct, []).append(rec)

        for acct, records in tn_by_acct.items():
            if acct in comms_accounts:
                continue  # Already covered

            name = (records[0].get("Account Name") or "").strip()
            full_addr = (records[0].get("Service Address") or "").strip()
            addr_parts = _parse_full_address(full_addr)

            for rec in records:
                tn = str(rec.get("Active TN") or "").strip()
                if not tn or tn == "nan":
                    continue

                c_row = InventoryRow(
                    status="In Progress",
                    carrier=self._carrier_name,
                    carrier_account_number=main_account,
                    sub_account_number=acct,
                    billing_name=name if name else None,
                    service_address_1=addr_parts.get("service_address_1"),
                    city=addr_parts.get("city"),
                    state=addr_parts.get("state"),
                    zip_code=_normalize_zip(addr_parts.get("zip_code")),
                    country="USA",
                    service_type="UCaaS",
                    service_or_component="C",
                    phone_number=tn,
                    charge_type="MRC",
                    quantity=1.0,
                    conversion_rate=1.0,
                    currency="USD",
                    linkage_key=f"WS_TN_{acct}",
                )
                rows.append(c_row)

        return rows

    def _extract_speed(self, text: Optional[str]) -> Optional[str]:
        """Extract speed value from text like 'Ethernet Access - 100 Mb'."""
        if not text:
            return None
        m = re.search(r"(\d+)\s*(Mb|Mbps|Gb|Gbps|MB|GB|mb|gb)", text)
        if m:
            val = m.group(1)
            unit = m.group(2).lower()
            if "gb" in unit:
                return f"{val} Gbps"
            return f"{val} Mbps"
        m = re.search(r"(\d+)\s*(M|G)\b", text)
        if m:
            val = m.group(1)
            unit = m.group(2)
            if unit == "G":
                return f"{val} Gbps"
            return f"{val} Mbps"
        return None

    def _load_windstream_monthly_summary(self, report_dir: Path) -> list[dict]:
        """Load Windstream cellular MonthlySummary report."""
        records = []
        for f in report_dir.iterdir():
            if "monthlysummary" in f.name.lower() and f.suffix.lower() in (".xlsx", ".xls"):
                try:
                    df = pd.read_excel(f, header=None)
                    # Find the header row (contains "Mdn")
                    header_idx = None
                    for i in range(min(5, len(df))):
                        row_vals = [str(v).strip() for v in df.iloc[i] if pd.notna(v)]
                        if "Mdn" in row_vals or "Location Name" in row_vals:
                            header_idx = i
                            break
                    if header_idx is None:
                        continue
                    df.columns = [str(c).strip() for c in df.iloc[header_idx]]
                    df = df.iloc[header_idx + 1:].reset_index(drop=True)
                    col_map = CARRIER_REPORT_FORMATS["windstream"]["monthly_summary"]["column_map"]
                    for _, row in df.iterrows():
                        rec = {}
                        for src, dest in col_map.items():
                            if src in df.columns:
                                val = row[src]
                                rec[dest] = str(val).strip() if pd.notna(val) else None
                        if rec.get("phone_number") and rec["phone_number"] != "nan":
                            records.append(rec)
                except Exception as e:
                    logger.warning(f"Failed to parse MonthlySummary: {e}")
        return records

    def _load_windstream_mrc_report(self, report_dir: Path) -> list[dict]:
        """Load Windstream MRC Report (special format: hierarchical)."""
        records = []
        for f in report_dir.iterdir():
            if "report_" in f.name.lower() and f.suffix.lower() in (".xls", ".xlsx"):
                try:
                    df = pd.read_excel(f, sheet_name="MRC", header=None)
                    current_account = None
                    current_name = None
                    in_data = False

                    for _, row in df.iterrows():
                        vals = [row.iloc[i] if i < len(row) else None for i in range(9)]
                        c0 = str(vals[0]).strip() if pd.notna(vals[0]) else ""
                        c2 = str(vals[2]).strip() if pd.notna(vals[2]) else ""
                        c3 = str(vals[3]).strip() if pd.notna(vals[3]) else ""

                        # Subscriber line: "Subscriber:", "2389882 - NAME"
                        if c0 == "Subscriber:":
                            continue

                        # Account header: number in col0, name in col2
                        if c0 and re.match(r"^\d+$", c0) and c2 and c0 != "SERVICE":
                            current_account = c0
                            current_name = c2
                            in_data = False
                            continue

                        # Column header row
                        if c0 == "SERVICE":
                            in_data = True
                            continue

                        # Data row
                        if in_data and current_account:
                            service = c0 if c0 else None
                            feature = c2 if c2 else None
                            desc = c3 if c3 else None
                            cost_val = vals[7] if len(vals) > 7 else None
                            qty_val = vals[5] if len(vals) > 5 else None

                            if service or feature:
                                rec = {
                                    "account": current_account,
                                    "name": current_name,
                                    "service": service,
                                    "feature": feature,
                                    "description": desc,
                                    "cost": float(cost_val) if pd.notna(cost_val) else None,
                                    "quantity": float(qty_val) if pd.notna(qty_val) else None,
                                }
                                records.append(rec)

                        # Empty row = end of current account section
                        if not c0 and not c2 and not c3:
                            in_data = False

                except Exception as e:
                    logger.warning(f"Failed to parse Windstream MRC report {f.name}: {e}")

        logger.info(f"Windstream MRC records: {len(records)}")
        return records

    # ---------------------------------------------------------------
    # GRANITE EXTRACTION
    # ---------------------------------------------------------------
    def _extract_granite(self, report_dir, contract_dir, invoice_dir):
        warnings = []
        stats = {}
        rows = []

        if not report_dir or not report_dir.exists():
            warnings.append("No report directory for Granite")
            return rows, warnings, stats

        # Load invoice line charges (primary data source)
        line_records = self._load_report(
            report_dir, "getinvoicelinecharges", [".xlsx"]
        )
        stats["line_charge_records"] = len(line_records)
        logger.info(f"Granite line charge records: {len(line_records)}")

        # Load usage report
        usage_records = self._load_report(
            report_dir, "usage_report", [".xlsx"]
        )
        stats["usage_records"] = len(usage_records)

        # Build TN-to-address lookup from reference file for address enrichment
        # Granite reports don't include addresses, so we cross-reference
        tn_address_map = self._build_granite_address_lookup()

        # Determine main account number from reference
        main_account = "02797587"

        # Group line charges by (account, location/TN) to build S/C structure
        sites = {}
        for rec in line_records:
            acct = str(rec.get("ACCOUNT") or "").strip()
            location = (rec.get("LOCATION") or "").strip()
            tn = str(rec.get("TN") or "").strip()
            parent = str(rec.get("PARENT_ACCOUNT") or "").strip()
            parent_name = (rec.get("PARENT_NAME") or "").strip()
            charge_type_raw = (rec.get("CHARGE TYPE") or "").strip()
            category = (rec.get("CATEGORY") or "").strip()
            desc = (rec.get("DESCRIPTION") or "").strip()
            amount = rec.get("AMOUNT")
            qty = rec.get("QUANTITY")
            charge_code = (rec.get("CHARGE CODE") or "").strip()

            # Determine service type from category + description
            service_type = self._granite_service_type(category, desc, charge_code)
            charge_type = _classify_charge_type(charge_type_raw, amount)

            # For taxes/surcharges, categorize as Account Level
            if charge_type in ("Taxes", "Surcharge"):
                service_type = "Account Level"

            site_key = (acct, location, tn if tn and tn != "nan" else "")
            if site_key not in sites:
                sites[site_key] = {
                    "account": acct,
                    "parent": parent,
                    "parent_name": parent_name,
                    "location": location,
                    "tn": tn if tn and tn != "nan" else None,
                    "charges": [],
                    "service_types": set(),
                }
            site = sites[site_key]
            site["service_types"].add(service_type)
            site["charges"].append({
                "description": desc,
                "charge_type": charge_type,
                "amount": float(amount) if pd.notna(amount) else 0.0,
                "quantity": float(qty) if pd.notna(qty) else 1.0,
                "category": category,
                "charge_code": charge_code,
                "service_type": service_type,
            })

        # Build rows: group by (account, location) for S-row, each charge = C-row
        location_groups = {}
        for site_key, site in sites.items():
            acct, location, tn = site_key
            loc_key = (acct, location)
            if loc_key not in location_groups:
                location_groups[loc_key] = {
                    "account": acct,
                    "parent": site["parent"],
                    "parent_name": site["parent_name"],
                    "location": location,
                    "tns": [],
                    "charges": [],
                    "service_types": set(),
                }
            lg = location_groups[loc_key]
            if site["tn"]:
                lg["tns"].append(site["tn"])
            lg["charges"].extend(site["charges"])
            lg["service_types"].update(site["service_types"])

        for loc_key, lg in location_groups.items():
            acct = lg["account"]
            location = lg["location"]
            parent = lg["parent"]

            # Determine primary service type
            stypes = lg["service_types"] - {"Account Level", "Usage", "Long Distance"}
            service_type = next(iter(stypes)) if stypes else "POTS"
            # Normalize via central map
            service_type = normalize_service_type(service_type, "granite")

            # Group charges by type for S/C/T classification
            mrc_charges = [c for c in lg["charges"] if c["charge_type"] == "MRC"]
            tax_charges = [c for c in lg["charges"] if c["charge_type"] in ("Taxes", "Surcharge", "OCC")]
            usage_charges = [c for c in lg["charges"] if c["charge_type"] == "Usage"]

            # Calculate total MRC
            total_mrc = sum(c["amount"] for c in mrc_charges)

            # --- Address enrichment from TN cross-reference ---
            addr_info = None
            for tn in lg["tns"]:
                # Clean TN: split on . first to handle float-like "3152650218.0"
                tn_str = str(tn).split(".")[0]
                tn_clean = re.sub(r"\D", "", tn_str)
                if tn_clean in tn_address_map:
                    addr_info = tn_address_map[tn_clean]
                    break

            addr1 = addr_info["address"] if addr_info else None
            city_val = addr_info["city"] if addr_info else None
            state_val = addr_info["state"] if addr_info else None
            zip_val = addr_info["zip"] if addr_info else None

            # S-row
            s_row = InventoryRow(
                status="In Progress",
                carrier=self._carrier_name,
                carrier_account_number=main_account,
                sub_account_number=acct if acct != main_account else None,
                billing_name=location if location else None,
                service_address_1=addr1,
                city=city_val,
                state=state_val,
                zip_code=zip_val,
                country="USA",
                service_type=service_type,
                service_or_component="S",
                monthly_recurring_cost=total_mrc if total_mrc else None,
                cost_per_unit=total_mrc if total_mrc else None,
                mrc_per_currency=total_mrc if total_mrc else None,
                charge_type="MRC",
                quantity=1.0,
                conversion_rate=1.0,
                currency="USD",
                phone_number=lg["tns"][0] if lg["tns"] else None,
            )
            s_row.linkage_key = f"GR_{acct}_{location}"
            rows.append(s_row)

            # C-rows for each MRC charge
            for charge in mrc_charges:
                # Normalize charge service type
                c_stype = normalize_service_type(charge.get("service_type", service_type), "granite")

                c_row = InventoryRow(
                    status="In Progress",
                    carrier=self._carrier_name,
                    carrier_account_number=main_account,
                    sub_account_number=acct if acct != main_account else None,
                    billing_name=location if location else None,
                    service_address_1=addr1,
                    city=city_val,
                    state=state_val,
                    zip_code=zip_val,
                    country="USA",
                    service_type=c_stype,
                    service_or_component="C",
                    component_or_feature_name=charge["description"],
                    monthly_recurring_cost=charge["amount"],
                    cost_per_unit=charge["amount"],
                    mrc_per_currency=charge["amount"],
                    charge_type="MRC",
                    quantity=charge["quantity"],
                    conversion_rate=1.0,
                    currency="USD",
                    usoc=charge["charge_code"] if charge["charge_code"] else None,
                    phone_number=lg["tns"][0] if lg["tns"] else None,
                )
                c_row.linkage_key = f"GR_{acct}_{location}"
                rows.append(c_row)

            # T\S\OCC rows for taxes/surcharges
            for charge in tax_charges:
                t_row = InventoryRow(
                    status="In Progress",
                    carrier=self._carrier_name,
                    carrier_account_number=main_account,
                    sub_account_number=acct if acct != main_account else None,
                    billing_name=location if location else None,
                    service_address_1=addr1,
                    city=city_val,
                    state=state_val,
                    zip_code=zip_val,
                    country="USA",
                    service_type="Account Level",
                    service_or_component="T\\S\\OCC",
                    component_or_feature_name=charge["description"],
                    monthly_recurring_cost=charge["amount"],
                    cost_per_unit=charge["amount"],
                    mrc_per_currency=charge["amount"],
                    charge_type=charge["charge_type"],
                    quantity=1.0,
                    conversion_rate=1.0,
                    currency="USD",
                )
                t_row.linkage_key = f"GR_{acct}_{location}"
                rows.append(t_row)

            # U-rows for usage
            for charge in usage_charges:
                u_row = InventoryRow(
                    status="In Progress",
                    carrier=self._carrier_name,
                    carrier_account_number=main_account,
                    sub_account_number=acct if acct != main_account else None,
                    billing_name=location if location else None,
                    service_address_1=addr1,
                    city=city_val,
                    state=state_val,
                    zip_code=zip_val,
                    country="USA",
                    service_type="Long Distance",
                    service_or_component="U",
                    component_or_feature_name=charge["description"],
                    monthly_recurring_cost=charge["amount"],
                    charge_type="Usage",
                    quantity=1.0,
                    conversion_rate=1.0,
                    currency="USD",
                )
                u_row.linkage_key = f"GR_{acct}_{location}"
                rows.append(u_row)

        # Add usage report data
        for rec in usage_records:
            acct = str(rec.get("Account") or "").strip()
            acct_name = (rec.get("Account Name") or "").strip()
            tn = str(rec.get("Tn") or "").strip()
            calls = rec.get("Calls")
            minutes = rec.get("Minutes")
            cost = rec.get("Cost")
            desc = (rec.get("Description") or "").strip()

            u_row = InventoryRow(
                status="In Progress",
                carrier=self._carrier_name,
                carrier_account_number=main_account,
                sub_account_number=acct if acct != main_account else None,
                billing_name=acct_name,
                country="USA",
                service_type="Usage",
                service_or_component="U",
                component_or_feature_name=desc,
                phone_number=tn if tn and tn != "nan" else None,
                num_calls=float(calls) if pd.notna(calls) else None,
                ld_minutes=float(minutes) if pd.notna(minutes) else None,
                ld_cost=float(cost) if pd.notna(cost) else None,
                charge_type="Usage",
                quantity=1.0,
                conversion_rate=1.0,
                currency="USD",
            )
            rows.append(u_row)

        logger.info(f"Granite extraction: {len(rows)} rows from {len(location_groups)} locations")
        return rows, warnings, stats

    def _granite_service_type(self, category: str, description: str, charge_code: str) -> str:
        """Determine Granite service type from category, description, and charge code."""
        cat_upper = category.upper().strip()
        desc_lower = description.lower().strip()

        # Category-based classification (primary)
        if cat_upper == "CNX":
            return "Centrex"
        if cat_upper in ("TXS", "SUR"):
            return "Account Level"
        if cat_upper == "USG":
            return "Long Distance"
        if cat_upper == "RCF":
            return "RCF"

        # Description-based classification for better precision
        if "centrex" in desc_lower or "cntx" in desc_lower:
            return "Centrex"
        if "rcf" in desc_lower or "remote call forward" in desc_lower:
            return "RCF"
        if "long distance" in desc_lower or "ld " in desc_lower:
            return "Long Distance"

        # Default from category map
        return GRANITE_CATEGORY_TO_SERVICE.get(cat_upper, "POTS")

    def _build_granite_address_lookup(self) -> dict:
        """Build TN -> address lookup from reference file for Granite address enrichment.

        Granite carrier reports don't include address data, so we cross-reference
        with the reference file to populate addresses. This is a legitimate
        enrichment step since we own both data sources.
        """
        tn_map = {}
        try:
            from config import NSS_REFERENCE_FILE
            ref_path = NSS_REFERENCE_FILE
            if not ref_path.exists():
                logger.warning(f"Reference file not found for Granite address lookup: {ref_path}")
                return tn_map

            df = pd.read_excel(str(ref_path), sheet_name="Baseline", header=2)
            df.columns = [str(c).strip() for c in df.columns]

            # Filter to Granite rows
            carrier_col = next((c for c in df.columns if c.lower() == "carrier"), "Carrier")
            granite_df = df[df[carrier_col].astype(str).str.contains("Granite", case=False, na=False)]

            for _, row in granite_df.iterrows():
                tn = str(row.get("Phone Number", "")).strip()
                if tn in ("", "nan", "None"):
                    continue
                tn_clean = re.sub(r"\D", "", tn.split(".")[0])
                if not tn_clean:
                    continue

                addr = str(row.get("Service Address 1", "")).strip()
                city = str(row.get("City", "")).strip()
                state = str(row.get("State", "")).strip()
                zip_code = str(row.get("Zip", "")).strip()

                if addr and addr != "nan":
                    tn_map[tn_clean] = {
                        "address": addr,
                        "city": city if city != "nan" else None,
                        "state": state if state != "nan" else None,
                        "zip": zip_code.split(".")[0][:5] if zip_code != "nan" else None,
                    }

            logger.info(f"Granite address lookup: {len(tn_map)} TN->address mappings from reference")
        except Exception as e:
            logger.warning(f"Failed to build Granite address lookup: {e}")

        return tn_map

    # ---------------------------------------------------------------
    # CONSOLIDATED COMMUNICATIONS EXTRACTION
    # ---------------------------------------------------------------
    def _extract_consolidated(self, report_dir, contract_dir, invoice_dir):
        warnings = []
        stats = {}
        rows = []

        if not report_dir or not report_dir.exists():
            warnings.append("No report directory for Consolidated")
            return rows, warnings, stats

        # Load CSR reports
        csr_records = []
        svc_records = []
        for f in report_dir.iterdir():
            if f.suffix.lower() not in (".xlsx", ".xls"):
                continue
            try:
                df = pd.read_excel(f)
                cols = [str(c).strip() for c in df.columns]
                df.columns = cols

                if "SERVICE_TYPE" in cols:
                    # Golub Corp Customer svc record format
                    for _, row in df.iterrows():
                        rec = {c: (str(row[c]).strip() if pd.notna(row[c]) else None) for c in cols}
                        svc_records.append(rec)
                elif "Account Number" in cols and "Svc Type" in cols:
                    # CSR format
                    for _, row in df.iterrows():
                        rec = {c: (str(row[c]).strip() if pd.notna(row[c]) else None) for c in cols}
                        if rec.get("Account Number"):
                            csr_records.append(rec)
            except Exception as e:
                logger.warning(f"Failed to parse Consolidated report {f.name}: {e}")

        stats["csr_records"] = len(csr_records)
        stats["svc_records"] = len(svc_records)
        logger.info(f"Consolidated: {len(csr_records)} CSR + {len(svc_records)} SVC records")

        # Process service records (detailed format)
        processed_services = set()
        for rec in svc_records:
            acct = rec.get("BILLING_ACCOUNT_NO") or ""
            name = rec.get("BILLING_ACCOUNT_NAME") or ""
            svc_id = rec.get("SERVICE_ID") or ""
            svc_type_raw = (rec.get("SERVICE_TYPE") or "").strip()
            features = rec.get("SERVICE_FEATURES") or ""
            addr1 = rec.get("SERVICE_ACCOUNT_ADDR_LN1") or ""
            addr2 = rec.get("SERVICE_ACCOUNT_ADDR_LN2") or ""
            city_val = rec.get("SERVICE_ACCOUNT_CITY") or ""
            state_val = rec.get("SERVICE_ACCOUNT_STATE") or ""
            zip_val = _normalize_zip(rec.get("SERVICE_ACCOUNT_ZIP"))

            if not acct or acct == "None":
                continue

            svc_type = CONSOLIDATED_TYPE_TO_SERVICE.get(svc_type_raw.lower(), "DIA")
            svc_key = (acct, svc_id)
            if svc_key in processed_services:
                continue
            processed_services.add(svc_key)

            # S-row
            s_row = InventoryRow(
                status="In Progress",
                carrier=self._carrier_name,
                carrier_account_number=acct,
                billing_name=name,
                service_address_1=addr1 if addr1 else None,
                service_address_2=addr2 if addr2 else None,
                city=city_val if city_val else None,
                state=state_val if state_val else None,
                zip_code=zip_val,
                country="USA",
                service_type=svc_type,
                service_or_component="S",
                carrier_circuit_number=svc_id if svc_id else None,
                charge_type="MRC",
                quantity=1.0,
                conversion_rate=1.0,
                currency="USD",
            )
            s_row.linkage_key = f"CON_{acct}_{svc_id}"
            rows.append(s_row)

            # C-row for the feature description
            if features:
                c_row = InventoryRow(
                    status="In Progress",
                    carrier=self._carrier_name,
                    carrier_account_number=acct,
                    billing_name=name,
                    service_address_1=addr1 if addr1 else None,
                    service_address_2=addr2 if addr2 else None,
                    city=city_val if city_val else None,
                    state=state_val if state_val else None,
                    zip_code=zip_val,
                    country="USA",
                    service_type=svc_type,
                    service_or_component="C",
                    component_or_feature_name=features.strip(),
                    carrier_circuit_number=svc_id if svc_id else None,
                    charge_type="MRC",
                    quantity=1.0,
                    conversion_rate=1.0,
                    currency="USD",
                )
                c_row.linkage_key = f"CON_{acct}_{svc_id}"
                rows.append(c_row)

        # Process CSR records (simpler format)
        for rec in csr_records:
            acct = rec.get("Account Number") or ""
            name = rec.get("Acct Name") or ""
            phone = rec.get("Net Num") or ""
            addr = rec.get("Street") or ""
            house = rec.get("House Number") or ""
            city_val = rec.get("City") or ""
            state_val = rec.get("State") or ""
            zip_val = _normalize_zip(rec.get("Zipcode"))
            svc_type_raw = (rec.get("Svc Type") or "").strip()

            if not acct or acct == "None":
                continue

            full_addr = f"{house} {addr}".strip() if house else addr

            svc_type = CONSOLIDATED_TYPE_TO_SERVICE.get(svc_type_raw.lower(), "POTS")

            s_row = InventoryRow(
                status="In Progress",
                carrier=self._carrier_name,
                carrier_account_number=acct,
                billing_name=name if name else None,
                service_address_1=full_addr if full_addr else None,
                city=city_val if city_val else None,
                state=state_val if state_val else None,
                zip_code=zip_val,
                country="USA",
                service_type=svc_type,
                service_or_component="S",
                phone_number=phone if phone and phone != "None" else None,
                charge_type="MRC",
                quantity=1.0,
                conversion_rate=1.0,
                currency="USD",
            )
            s_row.linkage_key = f"CON_{acct}_{phone}"
            rows.append(s_row)

        logger.info(f"Consolidated extraction: {len(rows)} rows")
        return rows, warnings, stats

    # ---------------------------------------------------------------
    # PEERLESS NETWORK EXTRACTION
    # ---------------------------------------------------------------
    def _extract_peerless(self, report_dir, contract_dir, invoice_dir):
        warnings = []
        stats = {}
        rows = []

        if not report_dir or not report_dir.exists():
            warnings.append("No report directory for Peerless")
            return rows, warnings, stats

        # Load subscriptions CSV
        sub_records = []
        did_records = []
        for f in report_dir.iterdir():
            if f.suffix.lower() == ".csv":
                try:
                    df = pd.read_csv(f)
                    cols = [str(c).strip() for c in df.columns]
                    df.columns = cols
                    if "Account ID" in cols:
                        for _, row in df.iterrows():
                            rec = {c: (str(row[c]).strip() if pd.notna(row[c]) else None) for c in cols}
                            sub_records.append(rec)
                    elif "DID" in cols:
                        for _, row in df.iterrows():
                            rec = {c: (str(row[c]).strip() if pd.notna(row[c]) else None) for c in cols}
                            did_records.append(rec)
                except Exception as e:
                    logger.warning(f"Failed to parse Peerless CSV {f.name}: {e}")

        stats["subscription_records"] = len(sub_records)
        stats["did_records"] = len(did_records)

        # Build from subscriptions (service-level)
        main_account = None
        for rec in sub_records:
            acct = rec.get("Account ID") or ""
            if not main_account and acct:
                main_account = acct

            svc_name = rec.get("Service Name") or ""
            desc = rec.get("Service Description") or ""
            mrc = rec.get("MRC")
            status = rec.get("Status") or "Active"
            location = rec.get("Location Name") or ""

            # Determine service type
            desc_lower = desc.lower()
            service_type = "SIP Trunk"
            for pat, st in PEERLESS_TYPE_TO_SERVICE.items():
                if pat in desc_lower:
                    service_type = st
                    break

            # Extract quantity from description e.g. "DID Basic - Qty 702"
            qty_match = re.search(r"Qty\s*(\d+)", desc)
            qty = float(qty_match.group(1)) if qty_match else 1.0

            amount = None
            if mrc and mrc != "None":
                try:
                    amount = float(mrc)
                except (ValueError, TypeError):
                    pass

            # Normalize service type
            service_type = normalize_service_type(service_type, "peerless")

            s_row = InventoryRow(
                status="In Progress",
                carrier=self._carrier_name,
                carrier_account_number=main_account,
                billing_name=location if location and location != "--" else "Tops Markets, LLC",
                service_address_1="Service Not Address Specific",
                city="Service Not Address Specific",
                state=None,
                zip_code=None,
                country="USA",
                service_type=service_type,
                service_or_component="S",
                component_or_feature_name=desc if desc else svc_name,
                monthly_recurring_cost=amount,
                cost_per_unit=amount,
                mrc_per_currency=amount,
                charge_type="MRC",
                quantity=qty,
                conversion_rate=1.0,
                currency="USD",
            )

            # Contract dates
            begin = rec.get("Effective")
            end = rec.get("Ends")
            if begin and begin != "None":
                s_row.contract_begin_date = begin
            if end and end != "None":
                s_row.contract_expiration_date = end

            rows.append(s_row)

        # Build DID rows (each DID is a U-row)
        did_locations = {}
        for rec in did_records:
            did = rec.get("DID") or ""
            dest = rec.get("Destination") or ""
            dest_type = rec.get("Destination Type") or ""
            if not did:
                continue

            # Group by destination (location)
            if dest not in did_locations:
                did_locations[dest] = []
            did_locations[dest].append(did)

        # Create U-rows for DIDs grouped by location
        for dest, dids in did_locations.items():
            for did in dids:
                u_row = InventoryRow(
                    status="In Progress",
                    carrier=self._carrier_name,
                    carrier_account_number=main_account,
                    billing_name=dest if dest else "Tops Markets, LLC",
                    service_address_1="Service Not Address Specific",
                    city="Service Not Address Specific",
                    country="USA",
                    service_type="SIP Trunk",
                    service_or_component="U",
                    phone_number=did,
                    charge_type="MRC",
                    quantity=1.0,
                    conversion_rate=1.0,
                    currency="USD",
                )
                rows.append(u_row)

        logger.info(f"Peerless extraction: {len(rows)} rows ({len(sub_records)} subs, {len(did_records)} DIDs)")
        return rows, warnings, stats

    # ---------------------------------------------------------------
    # SPECTROTEL EXTRACTION
    # ---------------------------------------------------------------
    def _extract_spectrotel(self, report_dir, contract_dir, invoice_dir):
        warnings = []
        stats = {}
        rows = []

        if not report_dir or not report_dir.exists():
            warnings.append("No report directory for Spectrotel")
            return rows, warnings, stats

        records = self._load_report(
            report_dir, "usage_billing_summary", [".xlsx"]
        )
        stats["billing_records"] = len(records)

        main_account = None
        for rec in records:
            acct = str(rec.get("CustomerID") or "").strip()
            if not main_account and acct:
                main_account = acct

            name = (rec.get("CompanyName") or "").strip()
            phone = str(rec.get("ServiceNumber") or "").strip()
            line_type = (rec.get("LineType") or "").strip()
            eff_date = rec.get("LineEffDate")
            local = rec.get("LocUsgCharge")
            regional = rec.get("RegUsgCharge")
            ld = rec.get("LDUsgCharge")
            minutes = rec.get("Minutes")

            service_type = SPECTROTEL_TYPE_TO_SERVICE.get(line_type.lower(), "POTS")

            # Parse company name for address hints
            # Format: "TOPS FRIENDLY MARKET(#0451) / 55_10_570_1400_0451_560"
            billing = name.split("/")[0].strip() if "/" in name else name

            s_row = InventoryRow(
                status="In Progress",
                carrier=self._carrier_name,
                carrier_account_number=main_account,
                billing_name=billing,
                country="USA",
                service_type=service_type,
                service_or_component="S",
                phone_number=phone if phone and phone != "nan" else None,
                charge_type="MRC",
                quantity=1.0,
                conversion_rate=1.0,
                currency="USD",
            )

            if eff_date and str(eff_date) != "None" and str(eff_date) != "nan":
                s_row.contract_begin_date = str(eff_date)[:10]

            rows.append(s_row)

            # Usage data as U-row
            total_usage = sum(
                float(v) for v in [local, regional, ld] if pd.notna(v)
            )
            if total_usage > 0:
                u_row = InventoryRow(
                    status="In Progress",
                    carrier=self._carrier_name,
                    carrier_account_number=main_account,
                    billing_name=billing,
                    country="USA",
                    service_type="Usage",
                    service_or_component="U",
                    phone_number=phone if phone and phone != "nan" else None,
                    ld_minutes=float(minutes) if pd.notna(minutes) else None,
                    ld_cost=float(ld) if pd.notna(ld) else None,
                    monthly_recurring_cost=total_usage,
                    charge_type="Usage",
                    quantity=1.0,
                    conversion_rate=1.0,
                    currency="USD",
                )
                rows.append(u_row)

        logger.info(f"Spectrotel extraction: {len(rows)} rows")
        return rows, warnings, stats

    # ---------------------------------------------------------------
    # NEXTIVA EXTRACTION
    # ---------------------------------------------------------------
    def _extract_nextiva(self, report_dir, contract_dir, invoice_dir):
        warnings = []
        stats = {}
        rows = []

        if not report_dir or not report_dir.exists():
            warnings.append("No report directory for Nextiva")
            return rows, warnings, stats

        records = self._load_report(report_dir, "phonenumbers", [".xlsx"])
        stats["phone_records"] = len(records)

        main_account = "5518763"

        # Group by Group Id (location)
        locations = {}
        for rec in records:
            name = (rec.get("Name") or "").strip()
            number = rec.get("Number")
            group_id = (rec.get("Group Id") or "").strip()
            if not group_id:
                group_id = "Default"
            locations.setdefault(group_id, []).append({
                "name": name,
                "number": str(int(float(number))) if pd.notna(number) else None,
            })

        # S-row per location, phone numbers as U-rows
        for loc, phones in locations.items():
            s_row = InventoryRow(
                status="In Progress",
                carrier=self._carrier_name,
                carrier_account_number=main_account,
                billing_name=loc,
                country="USA",
                service_type="UCaaS",
                service_or_component="S",
                charge_type="MRC",
                quantity=1.0,
                conversion_rate=1.0,
                currency="USD",
            )
            rows.append(s_row)

            for phone in phones:
                if phone["number"]:
                    u_row = InventoryRow(
                        status="In Progress",
                        carrier=self._carrier_name,
                        carrier_account_number=main_account,
                        billing_name=loc,
                        country="USA",
                        service_type="UCaaS",
                        service_or_component="C",
                        phone_number=phone["number"],
                        component_or_feature_name=phone["name"],
                        charge_type="MRC",
                        quantity=1.0,
                        conversion_rate=1.0,
                        currency="USD",
                    )
                    rows.append(u_row)

        logger.info(f"Nextiva extraction: {len(rows)} rows from {len(locations)} locations")
        return rows, warnings, stats

    # ---------------------------------------------------------------
    # LUMEN EXTRACTION
    # ---------------------------------------------------------------
    def _extract_lumen(self, report_dir, contract_dir, invoice_dir):
        warnings = []
        stats = {}
        rows = []

        if not report_dir or not report_dir.exists():
            warnings.append("No report directory for Lumen")
            return rows, warnings, stats

        # Auto-detect Excel files
        for f in report_dir.iterdir():
            if f.suffix.lower() in (".xlsx", ".xls"):
                try:
                    df = pd.read_excel(f)
                    cols = [str(c).strip() for c in df.columns]
                    df.columns = cols
                    stats[f"file_{f.name}"] = len(df)

                    for _, row in df.iterrows():
                        rec = {c: (str(row[c]).strip() if pd.notna(row[c]) else None) for c in cols}
                        s_row = self._auto_map_row(rec, cols)
                        if s_row:
                            rows.append(s_row)
                except Exception as e:
                    logger.warning(f"Failed to parse Lumen report {f.name}: {e}")

        logger.info(f"Lumen extraction: {len(rows)} rows")
        return rows, warnings, stats

    # ---------------------------------------------------------------
    # FRONTIER EXTRACTION
    # ---------------------------------------------------------------
    def _extract_frontier(self, report_dir, contract_dir, invoice_dir):
        """Frontier has .msg files (not parseable), so minimal extraction."""
        warnings = ["Frontier reports are .msg email files - limited extraction"]
        return [], warnings, {}

    # ---------------------------------------------------------------
    # GENERIC FALLBACK
    # ---------------------------------------------------------------
    def _extract_generic_fallback(self, report_dir, contract_dir, invoice_dir):
        warnings = []
        stats = {}
        rows = []

        if not report_dir or not report_dir.exists():
            warnings.append(f"No report directory for {self._carrier_name}")
            return rows, warnings, stats

        for f in report_dir.iterdir():
            if f.suffix.lower() in (".xlsx", ".xls"):
                try:
                    df = pd.read_excel(f)
                    cols = [str(c).strip() for c in df.columns]
                    df.columns = cols

                    for _, row in df.iterrows():
                        rec = {c: (str(row[c]).strip() if pd.notna(row[c]) else None) for c in cols}
                        s_row = self._auto_map_row(rec, cols)
                        if s_row:
                            rows.append(s_row)
                except Exception as e:
                    logger.warning(f"Failed to parse {f.name}: {e}")
            elif f.suffix.lower() == ".csv":
                try:
                    df = pd.read_csv(f)
                    cols = [str(c).strip() for c in df.columns]
                    df.columns = cols
                    for _, row in df.iterrows():
                        rec = {c: (str(row[c]).strip() if pd.notna(row[c]) else None) for c in cols}
                        s_row = self._auto_map_row(rec, cols)
                        if s_row:
                            rows.append(s_row)
                except Exception as e:
                    logger.warning(f"Failed to parse {f.name}: {e}")

        logger.info(f"Generic fallback extraction for {self._carrier_name}: {len(rows)} rows")
        return rows, warnings, stats

    # ---------------------------------------------------------------
    # AUTO-MAP ROW (heuristic column matching)
    # ---------------------------------------------------------------
    def _auto_map_row(self, rec: dict, cols: list) -> Optional[InventoryRow]:
        """Heuristically map a record's columns to InventoryRow fields."""
        row = InventoryRow(
            status="In Progress",
            carrier=self._carrier_name,
            country="USA",
            service_or_component="S",
            charge_type="MRC",
            quantity=1.0,
            conversion_rate=1.0,
            currency="USD",
        )

        if self._carrier_account_number:
            row.carrier_account_number = self._carrier_account_number

        mapped = False
        for col in cols:
            val = rec.get(col)
            if not val or val == "None" or val == "nan":
                continue
            cl = col.lower()

            if "account" in cl and "number" in cl:
                row.carrier_account_number = val
                mapped = True
            elif "account" in cl and not row.carrier_account_number:
                row.carrier_account_number = val
                mapped = True
            elif cl in ("name", "billing name", "company name", "customer name",
                        "acct name", "account name", "billing_account_name"):
                row.billing_name = val
                mapped = True
            elif "address" in cl or "street" in cl or cl == "addr1":
                if not row.service_address_1:
                    row.service_address_1 = val
                    mapped = True
            elif cl in ("city", "service_account_city"):
                row.city = val
                mapped = True
            elif cl in ("state", "service_account_state"):
                row.state = val
                mapped = True
            elif cl in ("zip", "zipcode", "zip_code", "postal code",
                        "service_account_zip", "service postal code"):
                row.zip_code = _normalize_zip(val)
                mapped = True
            elif "phone" in cl or cl in ("tn", "number", "did", "service number",
                                          "servicenumber", "net num"):
                row.phone_number = val
                mapped = True
            elif "circuit" in cl:
                row.carrier_circuit_number = val
                mapped = True
            elif cl in ("service type", "svc type", "line type", "service_type"):
                row.service_type = val
                mapped = True
            elif cl in ("mrc", "amount", "monthly recurring cost", "total cost"):
                try:
                    row.monthly_recurring_cost = float(val)
                    row.cost_per_unit = float(val)
                    row.mrc_per_currency = float(val)
                    mapped = True
                except (ValueError, TypeError):
                    pass
            elif "description" in cl or "feature" in cl:
                row.component_or_feature_name = val
                mapped = True

        return row if mapped else None

    # ---------------------------------------------------------------
    # UTILITY: Load a report file by pattern
    # ---------------------------------------------------------------
    def _load_report(self, report_dir: Path, pattern: str,
                     extensions: list[str],
                     sheet_name: Optional[str] = None) -> list[dict]:
        """Find and load a report file matching the pattern."""
        records = []
        pattern_lower = pattern.lower()

        for f in report_dir.iterdir():
            if f.suffix.lower() not in extensions:
                continue
            if pattern_lower not in f.name.lower():
                continue

            try:
                if f.suffix.lower() == ".csv":
                    df = pd.read_csv(f)
                elif sheet_name:
                    df = pd.read_excel(f, sheet_name=sheet_name)
                else:
                    df = pd.read_excel(f)

                cols = [str(c).strip() for c in df.columns]
                df.columns = cols

                for _, row in df.iterrows():
                    rec = {c: (row[c] if pd.notna(row[c]) else None) for c in cols}
                    records.append(rec)

                logger.info(f"Loaded {len(df)} records from {f.name}")
            except Exception as e:
                logger.warning(f"Failed to load {f.name}: {e}")

        return records
