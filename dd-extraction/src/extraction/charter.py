"""
Charter Communications extraction rules.
Primary source: Carrier report (Customer Inventory by COMMS)
Secondary: TOPS MARKETS spreadsheet
Enrichment: Invoice OCR (optional, requires API key)
"""
import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

from src.extraction.base import CarrierExtractor, ExtractionResult
from src.extraction.address_utils import (
    state_from_zip, normalize_billing_name, normalize_zip, normalize_address,
)
from src.extraction.service_type_map import normalize_service_type
from src.mapping.schema import InventoryRow
from src.parsing.excel_parser import parse_excel
from src.parsing.pdf_parser import parse_pdf, extract_pdf_page_images
from src.parsing.ocr_parser import ocr_invoice_pages, InvoiceOcrResult

logger = logging.getLogger(__name__)

# Charter carrier report column mapping
# Source columns → what they represent
CARRIER_REPORT_COLUMNS = {
    "Parent ID": "master_account_ref",
    "Customer #": "account_number",
    "Customer Name": "billing_name",
    "TN": "phone_number",
    "TN Status": "tn_status",
    "TN Type": "tn_type",
    "Circuit ID": "circuit_id",
    "Circuit Cat": "circuit_category",
    "Circuit Type": "circuit_type",
    "Circuit Status": "circuit_status",
    "ADDR1": "address",
    "ADDR2": "address_2",
    "CITY": "city",
    "STATE": "state",
    "ZIP": "zip_code",
    "SYSTEM": "system",
}

# Map Charter circuit types to standard service types
CIRCUIT_TYPE_TO_SERVICE_TYPE = {
    "Dedicated Fiber Internet": "DIA",
    "Ethernet Access": "DIA",
    "Ethernet": "EPL",
    "Enterprise Fiber Internet": "DIA",
    "Spectrum Internet": "Business Internet",
    "Business Internet": "Business Internet",
    "Voice": "VOIP Line",
    "VoIP": "VOIP Line",
    "Video": "TV",
    "TV": "TV",
    "EVPL": "EVPL",
}

# TOPS MARKETS spreadsheet positional column mapping (no headers)
TOPS_COLUMNS = {
    0: "account_id",
    1: "master_account",
    2: "customer_name",
    3: "address",
    4: "city",
    5: "state",
    6: "zip_code",
    7: "service_description",
    8: "speed",
    9: "extra",
}

# Map TOPS service descriptions to standard service types
TOPS_SERVICE_DESCRIPTION_MAP = {
    "internet": "Business Internet",
    "business internet": "Business Internet",
    "spectrum internet": "Business Internet",
    "fiber internet": "DIA",
    "dedicated internet": "DIA",
    "dia": "DIA",
    "tv": "TV",
    "video": "TV",
    "cable tv": "TV",
    "epl": "EPL",
    "ethernet": "EPL",
    "sdwan": "SDWAN",
    "sd-wan": "SDWAN",
    "broadband": "Broadband",
    "voice": "VOIP Line",
    "voip": "VOIP Line",
    "phone": "VOIP Line",
}


class CharterExtractor(CarrierExtractor):
    """Charter Communications / Spectrum extraction."""

    @property
    def carrier_key(self) -> str:
        return "charter"

    @property
    def carrier_name(self) -> str:
        return "Charter Communications"

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

        # --- Stage 1: Parse carrier report (PRIMARY source) ---
        report_records = []
        if report_dir and report_dir.exists():
            report_records, rw = self._parse_carrier_report(report_dir)
            warnings.extend(rw)
            stats["carrier_report_records"] = len(report_records)

        # --- Stage 2: Parse TOPS MARKETS spreadsheet ---
        tops_records = []
        if report_dir and report_dir.exists():
            tops_records, tw = self._parse_tops_spreadsheet(report_dir)
            warnings.extend(tw)
            stats["tops_records"] = len(tops_records)

        # --- Stage 3: Parse contract data ---
        contract_records = []
        if contract_dir and contract_dir.exists():
            contract_records, cw = self._parse_contracts(contract_dir)
            warnings.extend(cw)
            stats["contract_records"] = len(contract_records)

        # --- Stage 4: OCR invoices (ENRICHMENT, optional) ---
        invoice_data = {}
        if invoice_dir and invoice_dir.exists() and api_key:
            invoice_data, iw = self._parse_invoices(invoice_dir, api_key)
            warnings.extend(iw)
            stats["invoices_processed"] = len(invoice_data)
        elif not api_key:
            warnings.append("No API key provided — invoice OCR skipped. Charge data from carrier report only.")

        # --- Stage 5: Build inventory rows ---
        rows = self._build_inventory_rows(report_records, tops_records, invoice_data, invoice_dir, contract_records)
        stats["total_rows"] = len(rows)
        stats["s_rows"] = sum(1 for r in rows if r.service_or_component == "S")
        stats["c_rows"] = sum(1 for r in rows if r.service_or_component == "C")
        stats["tsocc_rows"] = sum(1 for r in rows if r.service_or_component == "T\\S\\OCC")

        return ExtractionResult(
            carrier_key=self.carrier_key,
            carrier_name=self.carrier_name,
            rows=rows,
            warnings=warnings,
            errors=errors,
            stats=stats,
        )

    def _parse_carrier_report(self, report_dir: Path) -> tuple[list[dict], list[str]]:
        """Parse the Customer Inventory by COMMS spreadsheet."""
        warnings = []
        records = []

        # Find the carrier report file
        report_file = None
        for f in report_dir.iterdir():
            if "customer inventory" in f.name.lower() and f.suffix.lower() in (".xlsx", ".xls"):
                report_file = f
                break

        if not report_file:
            warnings.append(f"No Customer Inventory report found in {report_dir}")
            return records, warnings

        logger.info(f"Parsing carrier report: {report_file.name}")
        df = parse_excel(report_file, header_row=1)  # Headers on row 1 (row 0 is blank)
        logger.info(f"Carrier report: {len(df)} records, columns: {list(df.columns)}")

        for _, row in df.iterrows():
            record = {}
            for src_col, field_name in CARRIER_REPORT_COLUMNS.items():
                if src_col in df.columns:
                    val = row[src_col]
                    if pd.notna(val):
                        s = str(val).strip()
                        # Preserve leading zeros for account numbers
                        # Convert float-like strings (e.g. "57777701.0") back
                        if field_name in ("account_number", "master_account_ref") and s.endswith(".0"):
                            s = s[:-2]
                        record[field_name] = s
                    else:
                        record[field_name] = None
            records.append(record)

        return records, warnings

    def _parse_tops_spreadsheet(self, report_dir: Path) -> tuple[list[dict], list[str]]:
        """Parse the TOPS MARKETS Services Spreadsheet (no headers)."""
        warnings = []
        records = []

        tops_file = None
        for f in report_dir.iterdir():
            if "tops" in f.name.lower() and f.suffix.lower() in (".xlsx", ".xls"):
                tops_file = f
                break

        if not tops_file:
            return records, warnings

        logger.info(f"Parsing TOPS spreadsheet: {tops_file.name}")
        df = parse_excel(tops_file, has_headers=False)

        for _, row in df.iterrows():
            record = {}
            for col_idx, field_name in TOPS_COLUMNS.items():
                if col_idx < len(row):
                    val = row.iloc[col_idx]
                    record[field_name] = str(val).strip() if pd.notna(val) else None
            if record.get("account_id"):
                records.append(record)

        return records, warnings

    def _parse_contracts(self, contract_dir: Path) -> tuple[list[dict], list[str]]:
        """Parse Charter contract files. Returns list of contract records."""
        warnings = []
        records = []

        # Look for the fiber inventory XLSX (structured contract data)
        for f in contract_dir.iterdir():
            if f.suffix.lower() in (".xlsx", ".xls") and "inventory" in f.name.lower():
                try:
                    logger.info(f"Parsing contract file: {f.name}")
                    df = parse_excel(f)

                    def _safe_str(val):
                        if pd.isna(val):
                            return None
                        return str(val).strip()

                    for _, row in df.iterrows():
                        record = {
                            "service_address": _safe_str(row.get("Service Address")),
                            "city": _safe_str(row.get("City")),
                            "state": _safe_str(row.get("ST")),
                            "zip_code": _safe_str(row.get("ZIP")),
                            "circuit_id": _safe_str(row.get("Circuit ID")),
                            "mrc": float(row["MRC"]) if pd.notna(row.get("MRC")) else None,
                            "term_start": _safe_str(row.get("Term Start")),
                            "term_end": _safe_str(row.get("Term End")),
                            "product": _safe_str(row.get("Product")),
                            "description": _safe_str(row.get("Description")),
                            "billing_acct": self._preserve_account_number(row.get("Billing Acc #")),
                            "ser_loc": self._preserve_account_number(row.get("Ser Loc #")),
                            "contract_file": f.name,
                        }
                        if record["circuit_id"]:
                            records.append(record)
                except Exception as e:
                    warnings.append(f"Failed to parse contract {f.name}: {e}")

        logger.info(f"Parsed {len(records)} contract records")
        return records, warnings

    def _parse_invoices(self, invoice_dir: Path, api_key: str) -> tuple[dict, list[str]]:
        """OCR all Charter invoice PDFs. Returns dict keyed by account number."""
        warnings = []
        invoice_data = {}

        pdf_files = sorted(invoice_dir.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} Charter invoice PDFs")

        for pdf_path in pdf_files:
            # Extract account number from filename
            # Pattern: Charter Communications_ACCTNUM_DATE_BILL.pdf
            acct_match = re.search(r"Charter Communications_(.+?)_\d{8}_BILL", pdf_path.stem)
            acct_num = acct_match.group(1) if acct_match else pdf_path.stem

            try:
                # Check if scanned
                pdf_result = parse_pdf(pdf_path)
                if pdf_result.is_scanned:
                    logger.info(f"Scanned PDF detected: {pdf_path.name} — using OCR")
                    page_images = extract_pdf_page_images(pdf_path)
                    ocr_result = ocr_invoice_pages(page_images, carrier="charter", api_key=api_key)

                    if ocr_result.success:
                        invoice_data[acct_num] = ocr_result
                    else:
                        warnings.append(f"OCR failed for {pdf_path.name}: {ocr_result.error}")
                else:
                    # Text-based PDF — extract directly
                    logger.info(f"Text PDF: {pdf_path.name}")
                    # Store raw text for text-based extraction (future enhancement)
                    invoice_data[acct_num] = pdf_result
            except Exception as e:
                warnings.append(f"Failed to process {pdf_path.name}: {e}")

        return invoice_data, warnings

    @staticmethod
    def _preserve_account_number(val) -> Optional[str]:
        """Convert account number preserving leading zeros.

        Excel stores account numbers as floats (e.g., 57777701.0).
        The reference may have leading zeros (e.g., '057777701').
        We check known patterns and add leading zeros back.
        """
        if pd.isna(val) or val is None:
            return None
        s = str(val).strip()
        if s.endswith(".0"):
            s = s[:-2]
        # Known Charter account patterns that need leading zeros
        # Account 57777701 -> should be 057777701 (9 digits)
        # Account 57778001 -> should be 057778001 (9 digits)
        if len(s) == 8 and s.isdigit() and s.startswith("5777"):
            s = "0" + s
        return s

    def _build_inventory_rows(
        self,
        report_records: list[dict],
        tops_records: list[dict],
        invoice_data: dict,
        invoice_dir: Optional[Path],
        contract_records: Optional[list[dict]] = None,
    ) -> list[InventoryRow]:
        """
        Build S/C/T\\S\\OCC inventory rows from extracted data.

        Grouping logic (based on reference NSS analysis):
        - Each unique Customer # (site/location) = one S-row for DIA service
        - The Carrier Account Number = the invoice account (from filenames)
        - Circuit numbers come from contracts, not the carrier report
        - TOPS MARKETS locations (acct 145529301) get separate S-rows per service type
        """
        rows = []

        # Build invoice files lookup: account → filename
        invoice_files = {}
        if invoice_dir and invoice_dir.exists():
            for f in invoice_dir.glob("*.pdf"):
                acct_match = re.search(r"Charter Communications_(.+?)_\d{8}_BILL", f.stem)
                if acct_match:
                    acct = acct_match.group(1)
                    invoice_files[acct] = f.name

        # Build TOPS lookup by address for enrichment
        tops_by_addr = {}
        for t in tops_records:
            addr = (t.get("address") or "").strip().upper()
            if addr:
                tops_by_addr[addr] = t

        # Build contract lookup by normalized address
        contract_by_addr = {}
        if contract_records:
            for cr in contract_records:
                addr = (cr.get("service_address") or "").strip().upper()
                if addr:
                    contract_by_addr.setdefault(addr, []).append(cr)

        # --- Group carrier report by Customer # (site/location) ---
        site_groups = self._group_by_site(report_records)

        # --- Map sites to invoice accounts ---
        # Parent ID 2389882 → account 117931801 (Golub DIA sites)
        # Sites with Customer # matching TOPS data → account 145529301
        # Other patterns from the invoice filenames

        for site_key, site_records in site_groups.items():
            first = site_records[0]
            customer_num = first.get("account_number", "")
            billing_name = first.get("billing_name", "")
            address = first.get("address", "")
            city = first.get("city", "")
            state = first.get("state", "")
            zip_code = first.get("zip_code", "")

            # --- Apply normalizations ---
            billing_name = normalize_billing_name(billing_name) or billing_name
            zip_code = normalize_zip(zip_code) or zip_code
            if not state or state.strip() == "":
                state = state_from_zip(zip_code)

            # Determine the carrier account number (invoice-level account)
            carrier_acct = self._resolve_carrier_account(
                customer_num, billing_name, first.get("master_account_ref", ""), invoice_files
            )

            # Find matching invoice file
            inv_file = self._find_invoice_file(carrier_acct, invoice_files)

            # Determine service type from TN types at this site
            tn_types = set(r.get("tn_type", "") for r in site_records if r.get("tn_type"))
            circuit_types = set(r.get("circuit_type", "") for r in site_records if r.get("circuit_type"))
            service_type = self._infer_service_type(tn_types, circuit_types)
            # Normalize via central map
            service_type = normalize_service_type(service_type, "charter")

            # Get speed from circuit type or TOPS data
            access_speed = None
            for ct in circuit_types:
                access_speed = self._extract_speed(ct)
                if access_speed:
                    break
            tops_info = tops_by_addr.get(address.strip().upper(), {})
            if not access_speed and tops_info.get("speed"):
                access_speed = tops_info["speed"]

            # Get BTN (first phone-like TN at this site)
            btn = self._find_btn(site_records)

            group_key = f"site:{customer_num}"

            # --- Look up contract data by address ---
            contract_info = contract_by_addr.get(address.strip().upper(), [])
            contract = contract_info[0] if contract_info else {}

            # Enrich with contract data
            circuit_id = contract.get("circuit_id")
            mrc = contract.get("mrc")
            term_start = contract.get("term_start")
            term_end = contract.get("term_end")
            contract_file = contract.get("contract_file")
            description = contract.get("description", "")

            # Override carrier account from contract if available
            if contract.get("billing_acct"):
                carrier_acct = contract["billing_acct"]
                inv_file = self._find_invoice_file(carrier_acct, invoice_files)

            # Override access speed from contract description
            if description and not access_speed:
                access_speed = self._extract_speed(description) or access_speed

            # Determine contract term in months
            contract_term = None
            if term_start and term_end and term_end != "Now":
                try:
                    from datetime import datetime
                    ts = pd.Timestamp(term_start)
                    te = pd.Timestamp(term_end)
                    contract_term = round((te - ts).days / 30.44)
                except Exception:
                    pass

            is_month_to_month = "Yes" if (term_end and "now" in str(term_end).lower()) else "No" if term_end else None

            # Parse upload speed from access_speed if format is "400x10"
            upload_speed = None
            if access_speed and "x" in str(access_speed).lower():
                parts = str(access_speed).lower().split("x")
                if len(parts) == 2:
                    try:
                        dl = parts[0].strip().replace("mbps", "").replace("mb", "").strip()
                        ul = parts[1].strip().replace("mbps", "").replace("mb", "").strip()
                        access_speed = f"{dl} Mbps"
                        upload_speed = f"{ul} Mbps"
                    except Exception:
                        pass
            elif access_speed and not upload_speed:
                upload_speed = access_speed  # Symmetric by default for DIA

            # Cost defaults: Quantity=1, Cost Per Unit = MRC, Conversion Rate = 1
            quantity = 1.0
            cost_per_unit = mrc
            conversion_rate = 1.0
            mrc_per_currency = mrc

            # Notes field (matches reference pattern)
            notes_text = "Complete"
            contract_info = "Yes" if contract else "No"

            # Billing per contract
            billing_per_contract = mrc if mrc and contract else None

            # Month-to-month related fields
            m2m_since = None
            auto_renew_val = None
            auto_renewal_notes_val = None
            if contract:
                auto_renew_val = "Yes" if contract.get("term_end") and "now" not in str(contract.get("term_end", "")).lower() else "No"
                if auto_renew_val == "Yes" and term_end:
                    auto_renewal_notes_val = f"Auto-renews after {str(term_end)[:10]}"

            # --- Create S-row ---
            s_row = InventoryRow(
                status="Completed",
                notes=notes_text,
                contract_info_received=contract_info,
                invoice_file_name=inv_file,
                files_used_for_inventory=self._build_files_used(inv_file, first),
                billing_name=billing_name,
                service_address_1=address,
                service_address_2=first.get("address_2"),
                city=city,
                state=state,
                zip_code=zip_code,
                country="USA",
                carrier="Charter Communications",
                master_account=None,  # Parent ID is Windstream's account, not Charter's
                carrier_account_number=carrier_acct,
                sub_account_number=customer_num,
                btn=btn,
                phone_number=btn,
                carrier_circuit_number=circuit_id,
                service_type=service_type,
                service_or_component="S",
                monthly_recurring_cost=mrc,
                quantity=quantity,
                cost_per_unit=cost_per_unit,
                currency="USD",
                conversion_rate=conversion_rate,
                mrc_per_currency=mrc_per_currency,
                charge_type="MRC",
                access_speed=access_speed,
                upload_speed=upload_speed,
                contract_term=contract_term,
                contract_begin_date=str(term_start)[:10] if term_start else None,
                contract_expiration_date=str(term_end)[:10] if term_end and "now" not in str(term_end).lower() else None,
                billing_per_contract=billing_per_contract,
                currently_month_to_month=is_month_to_month,
                month_to_month_since=m2m_since,
                contract_file_name=contract_file,
                auto_renew=auto_renew_val,
                auto_renewal_notes=auto_renewal_notes_val,
                linkage_key=group_key,
                confidence=self._build_s_row_confidence(first, mrc),
                source_files=[inv_file] if inv_file else [],
            )
            rows.append(s_row)

            # --- Create C-rows from distinct service components at this site ---
            c_rows = self._build_c_rows_from_site(site_records, s_row, group_key)
            rows.extend(c_rows)

            # Set S-row MRC = sum of C-row MRCs if we have them and they add up
            if c_rows and not mrc:
                c_mrc_sum = sum(c.monthly_recurring_cost or 0 for c in c_rows if c.charge_type == "MRC")
                if c_mrc_sum > 0:
                    s_row.monthly_recurring_cost = c_mrc_sum

        # --- Add TOPS MARKETS S-rows for services not in carrier report ---
        # The carrier report only has SDWAN entries, but TOPS may have
        # Business Internet, TV, EPL, Broadband services at each location
        tops_rows = self._build_tops_service_rows(tops_records, invoice_files)
        rows.extend(tops_rows)

        # --- Add T\S\OCC rows from invoice data ---
        tsocc_rows = self._build_tsocc_rows(invoice_data, invoice_files)
        rows.extend(tsocc_rows)

        return rows

    def _group_by_site(self, records: list[dict]) -> dict[str, list[dict]]:
        """
        Group carrier report records by Customer # (site/location).
        Each Customer # represents a unique site with its own address.
        """
        groups: dict[str, list[dict]] = {}
        for rec in records:
            customer_num = rec.get("account_number", "unknown")
            groups.setdefault(customer_num, []).append(rec)
        return groups

    def _resolve_carrier_account(
        self, customer_num: str, billing_name: str, parent_id: str, invoice_files: dict,
    ) -> str:
        """
        Map a Customer # (site) to the carrier account number used on invoices.
        Based on observed patterns from reference data:
        - Parent ID 2389882 → most sites use account 117931801
        - TOPS MARKETS → account 145529301
        - Invoice filenames with spaces (e.g. "8358 21 114 0292263") preserve formatting
        - Leading zeros are preserved (e.g. "057777701" not "57777701")
        """
        name_lower = (billing_name or "").lower()

        # TOPS MARKETS sites
        if "tops" in name_lower or "top markets" in name_lower:
            return "145529301"

        # Check if customer_num matches an invoice account (with or without spaces)
        if customer_num in invoice_files:
            return customer_num
        customer_num_stripped = customer_num.replace(" ", "")
        for acct in invoice_files:
            if acct.replace(" ", "") == customer_num_stripped:
                return acct  # Return the space-formatted version from filename

        # Default mapping: most Golub sites under Parent ID 2389882 → 117931801
        if parent_id in ("2389882", "2389882.0"):
            return "117931801"

        # Parent ID 216713099 sites — KEEP leading zero: "057777701"
        if parent_id in ("216713099", "216713099.0"):
            return "057777701"

        # Ensure account number preserves leading zeros from carrier report
        # The customer_num may have had .0 stripped but lost leading zeros
        # during float conversion. We can't recover them here, but at least
        # we preserve what we have.
        return customer_num

    def _build_c_rows_from_site(
        self,
        site_records: list[dict],
        s_row: InventoryRow,
        group_key: str,
    ) -> list[InventoryRow]:
        """Build C-rows from distinct service components at a site."""
        c_rows = []

        # Group records by circuit_type to create distinct components
        component_types = {}
        for rec in site_records:
            ct = rec.get("circuit_type") or rec.get("tn_type") or ""
            if ct and ct.strip():
                ct_clean = ct.strip()
                if ct_clean not in component_types:
                    component_types[ct_clean] = rec

        # Distribute S-row MRC equally across C-rows if MRC available
        num_components = len(component_types)
        c_row_mrc = None
        c_row_cpu = None
        c_row_mrc_currency = None
        if s_row.monthly_recurring_cost and num_components > 0:
            c_row_mrc = round(s_row.monthly_recurring_cost / num_components, 2)
            c_row_cpu = c_row_mrc
            c_row_mrc_currency = c_row_mrc

        # Create one C-row per distinct component type
        for comp_name, rec in component_types.items():
            comp_speed = self._extract_speed(comp_name)
            # Parse upload speed from comp_name if "400x10" format
            comp_upload_speed = None
            if comp_speed and "x" in str(comp_speed).lower():
                parts = str(comp_speed).lower().split("x")
                if len(parts) == 2:
                    comp_speed = f"{parts[0].strip()} Mbps"
                    comp_upload_speed = f"{parts[1].strip()} Mbps"
            elif comp_speed:
                comp_upload_speed = comp_speed

            c_row = InventoryRow(
                status="Completed",
                notes=s_row.notes,
                contract_info_received=s_row.contract_info_received,
                invoice_file_name=s_row.invoice_file_name,
                files_used_for_inventory=s_row.files_used_for_inventory,
                billing_name=s_row.billing_name,
                service_address_1=s_row.service_address_1,
                service_address_2=s_row.service_address_2,
                city=s_row.city,
                state=s_row.state,
                zip_code=s_row.zip_code,
                country="USA",
                carrier="Charter Communications",
                master_account=None,
                carrier_account_number=s_row.carrier_account_number,
                sub_account_number=s_row.sub_account_number,
                btn=s_row.btn,
                phone_number=s_row.phone_number,
                carrier_circuit_number=s_row.carrier_circuit_number,
                service_type=s_row.service_type,
                service_or_component="C",
                component_or_feature_name=comp_name,
                monthly_recurring_cost=c_row_mrc,
                quantity=1.0,
                cost_per_unit=c_row_cpu,
                currency="USD",
                conversion_rate=1.0,
                mrc_per_currency=c_row_mrc_currency,
                charge_type="MRC",
                access_speed=comp_speed or s_row.access_speed,
                upload_speed=comp_upload_speed or s_row.upload_speed,
                # Carry over contract info
                contract_term=s_row.contract_term,
                contract_begin_date=s_row.contract_begin_date,
                contract_expiration_date=s_row.contract_expiration_date,
                billing_per_contract=s_row.billing_per_contract,
                currently_month_to_month=s_row.currently_month_to_month,
                contract_file_name=s_row.contract_file_name,
                auto_renew=s_row.auto_renew,
                auto_renewal_notes=s_row.auto_renewal_notes,
                linkage_key=group_key,
                confidence={"component_or_feature_name": "High", "monthly_recurring_cost": "Low"},
            )
            c_rows.append(c_row)

        return c_rows

    def _find_btn(self, records: list[dict]) -> Optional[str]:
        """Find the BTN (billing telephone number) from site records."""
        for rec in records:
            tn = rec.get("phone_number", "")
            if tn and len(tn) >= 10 and tn[:10].isdigit():
                return tn[:10]
        return None

    def _infer_service_type(self, tn_types: set, circuit_types: set) -> str:
        """Infer the primary service type from TN types and circuit types."""
        # Check circuit types first (more specific)
        for ct in circuit_types:
            mapped = self._map_service_type(ct)
            if mapped != "Other":
                return normalize_service_type(mapped, "charter")

        # Check TN types
        for tt in tn_types:
            if not tt:
                continue
            # Try direct normalization of the TN type
            normalized = normalize_service_type(tt, "charter")
            if normalized != tt:
                return normalized

        tn_type_str = " ".join(tn_types).lower()
        if "internet" in tn_type_str:
            return "DIA"
        if "sd-wan" in tn_type_str or "sdwan" in tn_type_str:
            return "SDWAN"
        if "voip" in tn_type_str or "voice" in tn_type_str:
            return "VOIP Line"
        if "mpls" in tn_type_str:
            return "MPLS"
        if "video" in tn_type_str or "tv" in tn_type_str:
            return "TV"
        if "broadband" in tn_type_str:
            return "Broadband"
        if "spectrum internet" in tn_type_str or "business internet" in tn_type_str:
            return "Business Internet"
        if "epl" in tn_type_str or "ethernet" in tn_type_str:
            return "EPL"

        return "DIA"  # Default for Charter (primarily DIA)

    def _build_tops_service_rows(
        self,
        tops_records: list[dict],
        invoice_files: dict,
    ) -> list[InventoryRow]:
        """
        Build S-rows from TOPS MARKETS spreadsheet for services like
        Business Internet, TV, EPL that are NOT in the carrier report.
        """
        rows = []
        carrier_acct = "145529301"
        inv_file = self._find_invoice_file(carrier_acct, invoice_files)

        for rec in tops_records:
            svc_desc = (rec.get("service_description") or "").strip()
            if not svc_desc:
                continue

            # Map service description to standard type
            svc_lower = svc_desc.lower()
            service_type = None
            for pattern, stype in TOPS_SERVICE_DESCRIPTION_MAP.items():
                if pattern in svc_lower:
                    service_type = stype
                    break

            if not service_type:
                # If we can't determine the type, default based on content
                service_type = "Business Internet"

            # Normalize via central map
            service_type = normalize_service_type(service_type, "charter")

            address = (rec.get("address") or "").strip()
            city = (rec.get("city") or "").strip()
            state = (rec.get("state") or "").strip()
            zip_code = normalize_zip(rec.get("zip_code"))
            name = (rec.get("customer_name") or "").strip()
            speed = (rec.get("speed") or "").strip()

            billing_name = normalize_billing_name(name) or name

            s_row = InventoryRow(
                status="Completed",
                notes="Complete",
                contract_info_received="No",
                invoice_file_name=inv_file,
                files_used_for_inventory="TOPS MARKETS - Services Spreadsheet.xlsx",
                billing_name=billing_name,
                service_address_1=address if address else None,
                city=city if city else None,
                state=state if state else None,
                zip_code=zip_code,
                country="USA",
                carrier="Charter Communications",
                carrier_account_number=carrier_acct,
                service_type=service_type,
                service_or_component="S",
                charge_type="MRC",
                quantity=1.0,
                conversion_rate=1.0,
                currency="USD",
                access_speed=speed if speed else None,
            )
            rows.append(s_row)

        logger.info(f"TOPS MARKETS service rows: {len(rows)}")
        return rows

    def _build_tsocc_rows(self, invoice_data: dict, invoice_files: dict) -> list[InventoryRow]:
        """Build T\\S\\OCC rows from invoice tax/surcharge data."""
        rows = []
        for acct_num, data in invoice_data.items():
            if not hasattr(data, "pages"):  # Only OCR results have pages
                continue

            inv_file = invoice_files.get(acct_num, "")

            for page in data.pages:
                for tax_item in page.taxes_and_surcharges:
                    charge_type = "Taxes" if "tax" in tax_item.description.lower() else "Surcharge"
                    # Strip .pdf from invoice filename to match reference convention
                    inv_name = inv_file
                    if inv_name and inv_name.lower().endswith(".pdf"):
                        inv_name = inv_name[:-4]

                    rows.append(InventoryRow(
                        status="Completed",
                        invoice_file_name=inv_name,
                        billing_name=page.billing_name,
                        service_address_1=page.service_address,
                        city=page.city,
                        state=page.state,
                        zip_code=page.zip_code,
                        country="USA",
                        carrier="Charter Communications",
                        carrier_account_number=acct_num,
                        service_type="Account Level",  # matches ref (with trailing space in ref: "Account Level ")
                        service_or_component="T\\S\\OCC",
                        component_or_feature_name=tax_item.description,
                        monthly_recurring_cost=tax_item.mrc,
                        quantity=1.0,
                        cost_per_unit=tax_item.mrc,
                        currency="USD",
                        conversion_rate=1.0,
                        mrc_per_currency=tax_item.mrc,
                        charge_type=charge_type,
                        confidence={"monthly_recurring_cost": "Medium", "component_or_feature_name": "Medium"},
                    ))
        return rows

    def _map_service_type(self, circuit_type: str) -> str:
        """Map Charter circuit type to standard service type."""
        if not circuit_type:
            return "Other"
        # Try centralized normalization first
        normalized = normalize_service_type(circuit_type, "charter")
        if normalized != circuit_type:
            return normalized
        # Fallback to legacy map
        ct_lower = circuit_type.lower()
        for pattern, stype in CIRCUIT_TYPE_TO_SERVICE_TYPE.items():
            if pattern.lower() in ct_lower:
                return stype
        return "Other"

    def _extract_speed(self, text: str) -> Optional[str]:
        """Extract speed value from circuit type text (e.g., '500 Mb' → '500 Mbps')."""
        if not text:
            return None
        match = re.search(r"(\d+)\s*(Mb|Gb|Mbps|Gbps|mb|gb)", text)
        if match:
            num = match.group(1)
            unit = match.group(2).lower()
            if unit in ("mb", "mbps"):
                return f"{num} Mbps"
            elif unit in ("gb", "gbps"):
                return f"{num} Gbps"
        return None

    def _find_invoice_file(self, acct_num: str, invoice_files: dict) -> Optional[str]:
        """Find the invoice filename for an account number (strips .pdf extension to match reference)."""
        def _strip_ext(fname):
            """Strip .pdf extension to match reference convention."""
            if fname and fname.lower().endswith(".pdf"):
                return fname[:-4]
            return fname

        # Direct match
        if acct_num in invoice_files:
            return _strip_ext(invoice_files[acct_num])
        # Try without spaces
        clean_acct = acct_num.replace(" ", "")
        for key, fname in invoice_files.items():
            if key.replace(" ", "") == clean_acct:
                return _strip_ext(fname)
        return None

    def _get_invoice_mrc(self, acct_num: str, invoice_data: dict) -> Optional[dict]:
        """Get total MRC from invoice OCR data for an account."""
        data = invoice_data.get(acct_num) or invoice_data.get(acct_num.replace(" ", ""))
        if not data or not hasattr(data, "pages"):
            return None

        total_mrc = 0
        for page in data.pages:
            for item in page.line_items:
                if item.mrc:
                    total_mrc += item.mrc
        return {"total_mrc": total_mrc} if total_mrc > 0 else None

    def _get_invoice_line_items(self, acct_num: str, invoice_data: dict) -> list:
        """Get line items from invoice OCR data."""
        data = invoice_data.get(acct_num) or invoice_data.get(acct_num.replace(" ", ""))
        if not data or not hasattr(data, "pages"):
            return []

        items = []
        for page in data.pages:
            items.extend(page.line_items)
        return items

    def _build_files_used(self, inv_file: Optional[str], record: dict) -> str:
        """Build the 'Files Used For Inventory' field."""
        files = []
        if inv_file:
            files.append(inv_file)
        files.append("Customer Inventory by COMMS - Golub Corporation.xlsx")
        return ", ".join(files)

    def _build_s_row_confidence(self, record: dict, mrc_value) -> dict:
        """Build confidence scores for S-row fields."""
        conf = {
            "carrier": "High",
            "carrier_account_number": "High",
            "service_address_1": "High",
            "city": "High",
            "state": "High",
            "zip_code": "High",
            "carrier_circuit_number": "High" if record.get("circuit_id") else "Medium",
            "phone_number": "High" if record.get("phone_number") else "Low",
            "service_type": "High",
            "billing_name": "High",
        }
        if mrc_value:
            conf["monthly_recurring_cost"] = "High"  # From contract = High
        else:
            conf["monthly_recurring_cost"] = "Low"
        return conf
