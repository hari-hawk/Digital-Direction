"""
OCR parser using Claude Vision API for scanned invoice PDFs.
Sends page images to Claude and extracts structured invoice data.
"""
import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class InvoiceLineItem:
    description: str
    mrc: Optional[float] = None
    nrc: Optional[float] = None
    quantity: Optional[float] = None


@dataclass
class InvoicePage:
    page_number: int
    account_number: Optional[str] = None
    billing_name: Optional[str] = None
    service_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    billing_period: Optional[str] = None
    line_items: list[InvoiceLineItem] = field(default_factory=list)
    taxes_and_surcharges: list[InvoiceLineItem] = field(default_factory=list)
    total_amount: Optional[float] = None
    raw_text: Optional[str] = None


@dataclass
class InvoiceOcrResult:
    file_path: Path
    pages: list[InvoicePage]
    success: bool
    error: Optional[str] = None


# The extraction prompt sent to Claude with each invoice page image
CHARTER_EXTRACTION_PROMPT = """You are extracting data from a Charter Communications / Spectrum invoice page.
Extract the following information as JSON:

{
    "account_number": "the account number on the invoice",
    "billing_name": "the customer/billing name",
    "service_address": "the service address (street)",
    "city": "city",
    "state": "state abbreviation",
    "zip_code": "zip code",
    "billing_period": "billing period dates",
    "line_items": [
        {"description": "service/charge description", "mrc": monthly_amount_or_null, "nrc": one_time_amount_or_null, "quantity": qty_or_null}
    ],
    "taxes_and_surcharges": [
        {"description": "tax/surcharge name", "mrc": amount}
    ],
    "total_amount": total_amount_due
}

Rules:
- Extract ALL line items visible on this page
- MRC amounts are monthly recurring charges
- NRC amounts are one-time or non-recurring charges
- If a field is not visible on this page, set it to null
- Amounts should be numbers (not strings), e.g. 325.00 not "$325.00"
- Return ONLY the JSON, no other text
"""


def ocr_invoice_pages(
    page_images: list[bytes],
    carrier: str = "charter",
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
) -> InvoiceOcrResult:
    """
    Send invoice page images to Claude Vision API for structured extraction.

    Args:
        page_images: List of PNG image bytes, one per page
        carrier: Carrier key for prompt selection
        api_key: Anthropic API key (falls back to env var)
        model: Claude model to use
    """
    if not api_key:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return InvoiceOcrResult(
            file_path=Path("unknown"),
            pages=[],
            success=False,
            error="No ANTHROPIC_API_KEY provided. Invoice OCR skipped.",
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except ImportError:
        return InvoiceOcrResult(
            file_path=Path("unknown"),
            pages=[],
            success=False,
            error="anthropic package not installed. Run: pip install anthropic",
        )

    prompt = CHARTER_EXTRACTION_PROMPT  # TODO: carrier-specific prompts

    pages = []
    for i, img_bytes in enumerate(page_images):
        try:
            b64_image = base64.b64encode(img_bytes).decode("utf-8")
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64_image,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }],
            )

            # Parse the JSON response
            response_text = response.content[0].text.strip()
            # Handle markdown code blocks
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            data = json.loads(response_text)

            line_items = [
                InvoiceLineItem(
                    description=item.get("description", ""),
                    mrc=item.get("mrc"),
                    nrc=item.get("nrc"),
                    quantity=item.get("quantity"),
                )
                for item in data.get("line_items", [])
            ]

            taxes = [
                InvoiceLineItem(
                    description=item.get("description", ""),
                    mrc=item.get("mrc"),
                )
                for item in data.get("taxes_and_surcharges", [])
            ]

            pages.append(InvoicePage(
                page_number=i + 1,
                account_number=data.get("account_number"),
                billing_name=data.get("billing_name"),
                service_address=data.get("service_address"),
                city=data.get("city"),
                state=data.get("state"),
                zip_code=data.get("zip_code"),
                billing_period=data.get("billing_period"),
                line_items=line_items,
                taxes_and_surcharges=taxes,
                total_amount=data.get("total_amount"),
            ))

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse OCR response for page {i+1}: {e}")
            pages.append(InvoicePage(page_number=i + 1, raw_text=response_text))
        except Exception as e:
            logger.warning(f"OCR failed for page {i+1}: {e}")
            pages.append(InvoicePage(page_number=i + 1))

    return InvoiceOcrResult(
        file_path=Path("unknown"),
        pages=pages,
        success=True,
    )
