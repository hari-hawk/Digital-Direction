"""Pydantic models for API responses."""
from pydantic import BaseModel
from typing import Optional


class ProjectInfo(BaseModel):
    id: str
    name: str
    input_dir: str
    output_dir: str
    reference_file: Optional[str] = None


class StatsCard(BaseModel):
    label: str
    value: str
    detail: Optional[str] = None


class CarrierSpend(BaseModel):
    carrier: str
    mrc: float
    row_count: int
    service_count: int


class ServiceTypeCount(BaseModel):
    service_type: str
    count: int
    mrc: float


class DocumentInfo(BaseModel):
    name: str
    path: str
    carrier: str
    doc_type: str  # invoice, contract, carrier_report, csr
    format: str    # pdf, xlsx, csv, etc.
    size_bytes: int


class CarrierDocuments(BaseModel):
    carrier: str
    invoices: list[DocumentInfo]
    contracts: list[DocumentInfo]
    carrier_reports: list[DocumentInfo]
    csrs: list[DocumentInfo]


class InventoryRowOut(BaseModel):
    row_index: int
    data: dict
    confidence: dict = {}
    service_or_component: Optional[str] = None


class ExtractionRequest(BaseModel):
    carrier_key: str
    api_key: Optional[str] = None


class ExtractionStatus(BaseModel):
    status: str  # running, completed, failed
    carrier: str
    total_rows: int = 0
    s_rows: int = 0
    c_rows: int = 0
    accuracy_pct: Optional[float] = None
    qa_passed: bool = False
    qa_summary: dict = {}
    confidence_summary: dict = {}
    warnings: list[str] = []
    output_file: Optional[str] = None


class QARule(BaseModel):
    name: str
    passed: bool
    checked: int
    passed_count: int
    violations: list[str] = []


class InsightFlag(BaseModel):
    category: str
    severity: str  # critical, warning, info
    count: int
    description: str
    details: list[str] = []


class CostBreakdown(BaseModel):
    carrier: str
    total_mrc: float
    service_count: int
    avg_mrc: float
    service_types: list[dict]
