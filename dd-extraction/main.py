#!/usr/bin/env python3
"""
Digital Direction Inventory Extraction Pipeline
CLI entry point.

Usage:
    python main.py --carrier charter --input-dir "path/to/inputs" --output-dir outputs/
    python main.py --carrier charter  # Uses default paths from config
    python main.py --carrier all      # Extract ALL carriers
    python main.py --carrier windstream granite peerless  # Extract specific carriers
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    CLIENT_INPUTS_DIR, INVOICES_DIR, CARRIER_REPORTS_DIR, CONTRACTS_DIR,
    OUTPUT_DIR, CARRIER_REGISTRY, ANTHROPIC_API_KEY,
)
from src.extraction.charter import CharterExtractor
from src.extraction.generic import GenericCarrierExtractor
from src.classification.row_classifier import (
    validate_row_classification, ensure_parent_child_inheritance, get_row_stats,
)
from src.confidence.scorer import get_confidence_summary, score_row_confidence
from src.validation.qa import validate_all
from src.output.generator import generate_inventory_excel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")


def _get_extractor(carrier_key: str, carrier_info: dict):
    """Get the appropriate extractor for a carrier."""
    extractor_type = carrier_info.get("extractor", "generic")
    if extractor_type == "charter":
        return CharterExtractor()
    else:
        return GenericCarrierExtractor(
            carrier_key=carrier_key,
            carrier_name=carrier_info["display_name"],
        )


def run_pipeline(
    carrier_key: str,
    input_dir: Path,
    output_dir: Path,
    api_key: str = "",
) -> dict:
    """Run the full extraction pipeline for a carrier."""
    start_time = time.time()

    carrier_info = CARRIER_REGISTRY.get(carrier_key)
    if not carrier_info:
        raise ValueError(f"Unknown carrier: {carrier_key}. Available: {list(CARRIER_REGISTRY.keys())}")

    extractor = _get_extractor(carrier_key, carrier_info)

    logger.info(f"=" * 60)
    logger.info(f"Starting extraction pipeline for: {carrier_info['display_name']}")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"API key: {'provided' if api_key else 'not provided (invoice OCR will be skipped)'}")
    logger.info(f"=" * 60)

    # Resolve input directories
    invoice_folder = carrier_info.get("invoice_folder", "")
    report_folder = carrier_info.get("report_folder", "")
    contract_folder = carrier_info.get("contract_folder", "")

    invoice_dir = input_dir / "Invoices" / invoice_folder if invoice_folder else None
    report_dir = input_dir / "Carrier Reports, Portal Data, ETC" / report_folder if report_folder else None
    contract_dir = input_dir / "Contracts" / contract_folder if contract_folder else None

    if invoice_dir:
        logger.info(f"Invoice dir: {invoice_dir} (exists: {invoice_dir.exists()})")
    if report_dir:
        logger.info(f"Report dir: {report_dir} (exists: {report_dir.exists()})")
    if contract_dir:
        logger.info(f"Contract dir: {contract_dir} (exists: {contract_dir.exists()})")

    # --- Stage 1: Extraction ---
    logger.info("\n--- Stage 1: Extraction ---")
    result = extractor.extract(
        invoice_dir=invoice_dir,
        report_dir=report_dir,
        contract_dir=contract_dir,
        api_key=api_key,
    )
    logger.info(f"Extraction complete: {len(result.rows)} rows generated")
    logger.info(f"Stats: {json.dumps(result.stats, indent=2)}")

    if result.warnings:
        logger.warning(f"Warnings ({len(result.warnings)}):")
        for w in result.warnings[:10]:
            logger.warning(f"  - {w}")

    if result.errors:
        logger.error(f"Errors ({len(result.errors)}):")
        for e in result.errors:
            logger.error(f"  - {e}")

    # --- Stage 2: Classification validation ---
    logger.info("\n--- Stage 2: Classification Validation ---")
    result.rows = ensure_parent_child_inheritance(result.rows)
    class_warnings = validate_row_classification(result.rows)
    if class_warnings:
        logger.warning(f"Classification warnings: {len(class_warnings)}")
        for w in class_warnings[:5]:
            logger.warning(f"  - {w}")
    row_stats = get_row_stats(result.rows)
    logger.info(f"Row classification: {json.dumps(row_stats)}")

    # --- Stage 2.5: Data Enrichment (ZIP→State, Component, Address, Service/Charge type validation) ---
    logger.info("\n--- Stage 2.5: Data Enrichment ---")
    from src.extraction.zip_state_lookup import zip_to_state
    from src.extraction.address_utils import normalize_address, normalize_city
    from src.extraction.service_type_map import validate_service_type, validate_charge_type

    # Experiment 1: ZIP→State lookup
    state_enriched = 0
    for row in result.rows:
        if (row.state or "").strip():
            continue
        raw_zip = (row.zip_code or "").strip()
        if raw_zip and raw_zip.lower() not in ("nan", "none", ""):
            inferred = zip_to_state(raw_zip)
            if inferred:
                row.state = inferred
                state_enriched += 1
    logger.info(f"Experiment 1 — ZIP→State: {state_enriched} rows enriched")

    # Experiment 2: Component/Feature Name inference from Service Type
    component_enriched = 0
    for row in result.rows:
        if row.component_or_feature_name and str(row.component_or_feature_name).strip():
            continue
        svc = (row.service_type or "").strip()
        scu = (row.service_or_component or "").strip()
        if svc and scu == "C":
            row.component_or_feature_name = svc
            component_enriched += 1
        elif svc and scu == "S":
            row.component_or_feature_name = f"{svc} Service"
            component_enriched += 1
    logger.info(f"Experiment 2 — Component name: {component_enriched} rows enriched")

    # Experiment 3: Address normalization (UPPERCASE → Title Case)
    addr_normalized = 0
    city_normalized = 0
    for row in result.rows:
        # Normalize service address to title case
        if row.service_address_1 and row.service_address_1.strip():
            original = row.service_address_1
            normalized = normalize_address(original)
            if normalized != original:
                row.service_address_1 = normalized
                addr_normalized += 1
        # Normalize city to title case
        if row.city and row.city.strip():
            original_city = row.city
            normalized_city = normalize_city(original_city)
            if normalized_city != original_city:
                row.city = normalized_city
                city_normalized += 1
        # Keep state as 2-letter uppercase (already enforced by ZIP→State)
        if row.state and row.state.strip():
            row.state = row.state.strip().upper()
    logger.info(f"Experiment 3 — Address normalization: {addr_normalized} addresses, {city_normalized} cities title-cased")

    # Experiment 4: Service type validation against DD platform dropdown
    svc_type_fixed = 0
    for row in result.rows:
        if row.service_type and row.service_type.strip():
            original = row.service_type
            validated = validate_service_type(original)
            if validated != original:
                row.service_type = validated
                svc_type_fixed += 1
    logger.info(f"Experiment 4 — Service type validation: {svc_type_fixed} rows normalized to valid dropdown values")

    # Experiment 4b: Charge type validation against DD platform dropdown
    charge_type_fixed = 0
    for row in result.rows:
        if row.charge_type and row.charge_type.strip():
            original = row.charge_type
            validated = validate_charge_type(original)
            if validated != original:
                row.charge_type = validated
                charge_type_fixed += 1
        # For T\S\OCC rows, ensure charge type is Taxes/Surcharge/OCC, not MRC
        if (row.service_or_component or "") == "T\\S\\OCC" and row.charge_type == "MRC":
            comp_name = (row.component_or_feature_name or "").lower()
            if "tax" in comp_name:
                row.charge_type = "Taxes"
                charge_type_fixed += 1
            elif "surcharge" in comp_name or "fee" in comp_name:
                row.charge_type = "Surcharge"
                charge_type_fixed += 1
            else:
                row.charge_type = "OCC"
                charge_type_fixed += 1
    logger.info(f"Experiment 4b — Charge type validation: {charge_type_fixed} rows normalized")

    # Experiment 5: Default addresses for carriers with no address data
    def _enrich_carrier_address(carrier_pattern: str, default_addr: str, default_city: str, default_state: str, default_zip: str):
        count = 0
        for row in result.rows:
            c = (row.carrier or "").strip().lower()
            if carrier_pattern not in c:
                continue
            if not (row.service_address_1 or "").strip():
                row.service_address_1 = default_addr
            if not (row.state or "").strip():
                row.state = default_state
                count += 1
            if not (row.zip_code or "").strip():
                row.zip_code = default_zip
                count += 1
            if not (row.city or "").strip():
                row.city = default_city
                count += 1
        return count

    p_count = _enrich_carrier_address("peerless", "Service Not Address Specific", "Buffalo", "NY", "14203")
    logger.info(f"Experiment 5a — Peerless addresses: {p_count} fields enriched")

    n_count = _enrich_carrier_address("nextiva", "Service Not Address Specific", "Buffalo", "NY", "14203")
    logger.info(f"Experiment 5b — Nextiva addresses: {n_count} fields enriched")

    s_count = _enrich_carrier_address("spectrotel", "Service Not Address Specific", "Buffalo", "NY", "14203")
    logger.info(f"Experiment 5c — Spectrotel addresses: {s_count} fields enriched")

    # Experiment 6: MRC inference — if MRC is missing, try to infer from charge data
    mrc_inferred = 0
    for row in result.rows:
        if row.monthly_recurring_cost is not None:
            continue
        # For S rows without MRC, check if cost_per_unit is available
        if row.cost_per_unit is not None and row.quantity is not None:
            row.monthly_recurring_cost = round(row.cost_per_unit * row.quantity, 2)
            row.mrc_per_currency = row.monthly_recurring_cost
            mrc_inferred += 1
    logger.info(f"Experiment 6 — MRC inference: {mrc_inferred} rows inferred from cost_per_unit * quantity")

    # --- Stage 3: Confidence scoring ---
    logger.info("\n--- Stage 3: Confidence Scoring ---")
    for row in result.rows:
        row.confidence = score_row_confidence(row)
    conf_summary = get_confidence_summary(result.rows)
    logger.info(f"Confidence: {json.dumps(conf_summary, indent=2)}")

    # --- Stage 4: QA Validation ---
    logger.info("\n--- Stage 4: QA Validation ---")
    qa_report = validate_all(result.rows)
    for rule in qa_report.rules:
        status = "PASS" if rule.passed else "FAIL"
        logger.info(f"  [{status}] {rule.rule_name}: {rule.pass_count}/{rule.checked_count}")
        if not rule.passed:
            for v in rule.violations[:3]:
                logger.warning(f"    - {v}")
            if len(rule.violations) > 3:
                logger.warning(f"    ... and {len(rule.violations) - 3} more violations")

    # --- Stage 5: Output Generation ---
    logger.info("\n--- Stage 5: Output Generation ---")
    output_dir = Path(output_dir)
    output_file = output_dir / f"{carrier_key}_inventory_output.xlsx"
    generate_inventory_excel(result.rows, output_file, carrier_info["display_name"])
    logger.info(f"Output written to: {output_file}")

    # --- Summary ---
    elapsed = time.time() - start_time
    summary = {
        "carrier": carrier_info["display_name"],
        "carrier_key": carrier_key,
        "total_rows": len(result.rows),
        "row_stats": row_stats,
        "qa_passed": qa_report.all_passed,
        "qa_summary": qa_report.summary,
        "confidence": conf_summary,
        "processing_time_seconds": round(elapsed, 2),
        "output_file": str(output_file),
        "warnings_count": len(result.warnings),
        "errors_count": len(result.errors),
    }

    logger.info(f"\n{'=' * 60}")
    logger.info(f"PIPELINE COMPLETE")
    logger.info(f"  Carrier: {summary['carrier']}")
    logger.info(f"  Rows: {summary['total_rows']}")
    logger.info(f"  QA: {'ALL PASSED' if summary['qa_passed'] else 'SOME FAILURES'}")
    logger.info(f"  Time: {summary['processing_time_seconds']}s")
    logger.info(f"  Output: {summary['output_file']}")
    logger.info(f"{'=' * 60}")

    return summary


def run_all_carriers(
    input_dir: Path,
    output_dir: Path,
    api_key: str = "",
    carriers: list[str] = None,
) -> dict:
    """Run extraction for multiple carriers and produce a combined output."""
    start_time = time.time()
    all_summaries = []
    all_rows = []
    total_warnings = 0
    total_errors = 0

    if carriers is None:
        carriers = list(CARRIER_REGISTRY.keys())

    logger.info(f"{'=' * 60}")
    logger.info(f"MULTI-CARRIER EXTRACTION: {len(carriers)} carriers")
    logger.info(f"Carriers: {', '.join(carriers)}")
    logger.info(f"{'=' * 60}")

    for carrier_key in carriers:
        carrier_info = CARRIER_REGISTRY.get(carrier_key)
        if not carrier_info:
            logger.warning(f"Unknown carrier key: {carrier_key}, skipping")
            continue

        try:
            logger.info(f"\n{'=' * 40}")
            logger.info(f"Processing: {carrier_info['display_name']}")
            logger.info(f"{'=' * 40}")

            # Run extraction (single pass, collect rows for combined output)
            extractor = _get_extractor(carrier_key, carrier_info)
            invoice_folder = carrier_info.get("invoice_folder", "")
            report_folder = carrier_info.get("report_folder", "")
            contract_folder = carrier_info.get("contract_folder", "")

            invoice_dir_path = input_dir / "Invoices" / invoice_folder if invoice_folder else None
            report_dir_path = input_dir / "Carrier Reports, Portal Data, ETC" / report_folder if report_folder else None
            contract_dir_path = input_dir / "Contracts" / contract_folder if contract_folder else None

            carrier_start = time.time()
            result = extractor.extract(
                invoice_dir=invoice_dir_path,
                report_dir=report_dir_path,
                contract_dir=contract_dir_path,
                api_key=api_key,
            )

            # Post-process rows
            result.rows = ensure_parent_child_inheritance(result.rows)

            # Enrichment (same as Stage 2.5 in single-carrier pipeline)
            from src.extraction.zip_state_lookup import zip_to_state
            from src.extraction.address_utils import normalize_address, normalize_city
            from src.extraction.service_type_map import validate_service_type, validate_charge_type
            for row in result.rows:
                # ZIP→State
                if not (row.state or "").strip():
                    raw_zip = (row.zip_code or "").strip()
                    if raw_zip and raw_zip.lower() not in ("nan", "none", ""):
                        inferred = zip_to_state(raw_zip)
                        if inferred:
                            row.state = inferred
                # Component name from service type
                if not (row.component_or_feature_name or "").strip():
                    svc = (row.service_type or "").strip()
                    scu = (row.service_or_component or "").strip()
                    if svc and scu == "C":
                        row.component_or_feature_name = svc
                    elif svc and scu == "S":
                        row.component_or_feature_name = f"{svc} Service"
                # Address normalization (UPPERCASE → Title Case)
                if row.service_address_1 and row.service_address_1.strip():
                    row.service_address_1 = normalize_address(row.service_address_1)
                if row.city and row.city.strip():
                    row.city = normalize_city(row.city)
                # Keep state as 2-letter uppercase
                if row.state and row.state.strip():
                    row.state = row.state.strip().upper()
                # Service type validation
                if row.service_type and row.service_type.strip():
                    row.service_type = validate_service_type(row.service_type)
                # Charge type validation
                if row.charge_type and row.charge_type.strip():
                    row.charge_type = validate_charge_type(row.charge_type)
                # T\S\OCC charge type correction
                if (row.service_or_component or "") == "T\\S\\OCC" and row.charge_type == "MRC":
                    comp_name = (row.component_or_feature_name or "").lower()
                    if "tax" in comp_name:
                        row.charge_type = "Taxes"
                    elif "surcharge" in comp_name or "fee" in comp_name:
                        row.charge_type = "Surcharge"
                    else:
                        row.charge_type = "OCC"
                # MRC inference from cost_per_unit * quantity
                if row.monthly_recurring_cost is None and row.cost_per_unit is not None and row.quantity is not None:
                    row.monthly_recurring_cost = round(row.cost_per_unit * row.quantity, 2)
                    row.mrc_per_currency = row.monthly_recurring_cost
                # Default addresses for carriers without address data
                c = (row.carrier or "").strip().lower()
                if any(p in c for p in ["peerless", "nextiva", "spectrotel"]):
                    if not (row.service_address_1 or "").strip():
                        row.service_address_1 = "Service Not Address Specific"
                    if not (row.state or "").strip():
                        row.state = "NY"
                    if not (row.zip_code or "").strip():
                        row.zip_code = "14203"
                    if not (row.city or "").strip():
                        row.city = "Buffalo"

            for row in result.rows:
                row.confidence = score_row_confidence(row)
            row_stats = get_row_stats(result.rows)

            # Write individual carrier output
            output_dir_path = Path(output_dir)
            output_file = output_dir_path / f"{carrier_key}_inventory_output.xlsx"
            if result.rows:
                generate_inventory_excel(result.rows, output_file, carrier_info["display_name"])

            carrier_elapsed = time.time() - carrier_start

            summary = {
                "carrier": carrier_info["display_name"],
                "carrier_key": carrier_key,
                "total_rows": len(result.rows),
                "row_stats": row_stats,
                "processing_time_seconds": round(carrier_elapsed, 2),
                "output_file": str(output_file),
                "warnings_count": len(result.warnings),
                "errors_count": len(result.errors),
            }
            all_summaries.append(summary)
            total_warnings += len(result.warnings)
            total_errors += len(result.errors)
            all_rows.extend(result.rows)

            logger.info(f"  {carrier_info['display_name']}: {len(result.rows)} rows in {carrier_elapsed:.1f}s")

        except Exception as e:
            logger.error(f"Failed to extract {carrier_info['display_name']}: {e}")
            all_summaries.append({
                "carrier": carrier_info["display_name"],
                "carrier_key": carrier_key,
                "total_rows": 0,
                "error": str(e),
            })

    # Generate combined output
    output_dir = Path(output_dir)
    if all_rows:
        combined_file = output_dir / "all_carriers_inventory_output.xlsx"
        generate_inventory_excel(all_rows, combined_file, "All Carriers")
        logger.info(f"\nCombined output: {combined_file} ({len(all_rows)} total rows)")

    elapsed = time.time() - start_time

    # Print summary table
    logger.info(f"\n{'=' * 70}")
    logger.info(f"MULTI-CARRIER EXTRACTION COMPLETE")
    logger.info(f"{'=' * 70}")
    logger.info(f"{'Carrier':<35} {'Rows':>8} {'Time':>8}")
    logger.info(f"{'-' * 35} {'-' * 8} {'-' * 8}")
    for s in all_summaries:
        rows = s.get("total_rows", 0)
        t = s.get("processing_time_seconds", 0)
        logger.info(f"{s['carrier']:<35} {rows:>8} {t:>7.1f}s")
    total_rows = sum(s.get("total_rows", 0) for s in all_summaries)
    logger.info(f"{'-' * 35} {'-' * 8} {'-' * 8}")
    logger.info(f"{'TOTAL':<35} {total_rows:>8} {elapsed:>7.1f}s")
    logger.info(f"{'=' * 70}")

    return {
        "total_carriers": len(carriers),
        "total_rows": total_rows,
        "processing_time_seconds": round(elapsed, 2),
        "carrier_summaries": all_summaries,
        "total_warnings": total_warnings,
        "total_errors": total_errors,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Digital Direction Inventory Extraction Pipeline",
    )
    parser.add_argument(
        "--carrier",
        required=True,
        nargs="+",
        help="Carrier(s) to extract. Use 'all' for all carriers, or list specific ones.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=CLIENT_INPUTS_DIR,
        help="Input directory containing Invoices/, Carrier Reports/, Contracts/",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Output directory for generated Excel files",
    )
    parser.add_argument(
        "--anthropic-api-key",
        default=ANTHROPIC_API_KEY,
        help="Anthropic API key for invoice OCR (optional)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--tier",
        type=int,
        choices=[1, 2, 3],
        help="Only extract carriers at this tier level or higher priority (lower number)",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine which carriers to run
    carriers = args.carrier
    if "all" in carriers:
        if args.tier:
            carriers = [k for k, v in CARRIER_REGISTRY.items() if v.get("tier", 99) <= args.tier]
        else:
            carriers = list(CARRIER_REGISTRY.keys())
    else:
        # Validate carrier names
        for c in carriers:
            if c not in CARRIER_REGISTRY:
                available = ", ".join(sorted(CARRIER_REGISTRY.keys()))
                parser.error(f"Unknown carrier: {c}. Available: {available}")

    # Run extraction
    if len(carriers) == 1:
        summary = run_pipeline(
            carrier_key=carriers[0],
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            api_key=args.anthropic_api_key,
        )
        # Write summary JSON
        summary_file = Path(args.output_dir) / f"{carriers[0]}_pipeline_summary.json"
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info(f"Summary written to: {summary_file}")
    else:
        summary = run_all_carriers(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            api_key=args.anthropic_api_key,
            carriers=carriers,
        )
        # Write combined summary JSON
        summary_file = Path(args.output_dir) / "all_carriers_pipeline_summary.json"
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info(f"Summary written to: {summary_file}")


if __name__ == "__main__":
    main()
