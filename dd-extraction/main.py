#!/usr/bin/env python3
"""
Digital Direction Inventory Extraction Pipeline
CLI entry point.

Usage:
    python main.py --carrier charter --input-dir "path/to/inputs" --output-dir outputs/
    python main.py --carrier charter  # Uses default paths from config
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

# Carrier extractor registry
EXTRACTORS = {
    "charter": CharterExtractor,
}


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

    extractor_cls = EXTRACTORS.get(carrier_key)
    if not extractor_cls:
        raise ValueError(f"No extractor implemented for: {carrier_key}")

    logger.info(f"=" * 60)
    logger.info(f"Starting extraction pipeline for: {carrier_info['display_name']}")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"API key: {'provided' if api_key else 'not provided (invoice OCR will be skipped)'}")
    logger.info(f"=" * 60)

    # Resolve input directories
    invoice_dir = input_dir / "Invoices" / carrier_info["invoice_folder"]
    report_dir = input_dir / "Carrier Reports, Portal Data, ETC" / carrier_info["report_folder"]
    contract_dir = input_dir / "Contracts" / carrier_info["contract_folder"]

    logger.info(f"Invoice dir: {invoice_dir} (exists: {invoice_dir.exists()})")
    logger.info(f"Report dir: {report_dir} (exists: {report_dir.exists()})")
    logger.info(f"Contract dir: {contract_dir} (exists: {contract_dir.exists()})")

    # --- Stage 1: Extraction ---
    logger.info("\n--- Stage 1: Extraction ---")
    extractor = extractor_cls()
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


def main():
    parser = argparse.ArgumentParser(
        description="Digital Direction Inventory Extraction Pipeline",
    )
    parser.add_argument(
        "--carrier",
        required=True,
        choices=list(CARRIER_REGISTRY.keys()),
        help="Carrier to extract (e.g., charter)",
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

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    summary = run_pipeline(
        carrier_key=args.carrier,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        api_key=args.anthropic_api_key,
    )

    # Write summary JSON
    summary_file = Path(args.output_dir) / f"{args.carrier}_pipeline_summary.json"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info(f"Summary written to: {summary_file}")


if __name__ == "__main__":
    main()
