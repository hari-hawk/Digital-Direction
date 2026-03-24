"""Dashboard router: stats, spending, service type distribution."""
from fastapi import APIRouter, Request

from services.analytics_service import (
    get_dashboard_stats, get_spend_by_carrier,
    get_service_type_distribution, get_charge_type_distribution,
)
from services.file_service import scan_project_files

router = APIRouter(tags=["dashboard"])


@router.get("/projects/{project_id}/stats")
async def project_stats(project_id: str, request: Request):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    ref_file = proj.get("reference_file", "")
    stats = get_dashboard_stats(ref_file)

    # Document counts
    carriers = scan_project_files(proj["input_dir"])
    total_docs = sum(
        len(cd.invoices) + len(cd.contracts) + len(cd.carrier_reports) + len(cd.csrs)
        for cd in carriers.values()
    )

    stats["total_documents"] = total_docs
    stats["carrier_list"] = sorted(carriers.keys())
    return stats


@router.get("/projects/{project_id}/spend-by-carrier")
async def spend_by_carrier(project_id: str, request: Request):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return []
    return get_spend_by_carrier(proj["reference_file"])


@router.get("/projects/{project_id}/service-types")
async def service_types(project_id: str, request: Request):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return []
    return get_service_type_distribution(proj["reference_file"])


@router.get("/projects/{project_id}/charge-types")
async def charge_types(project_id: str, request: Request):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return []
    return get_charge_type_distribution(proj["reference_file"])
