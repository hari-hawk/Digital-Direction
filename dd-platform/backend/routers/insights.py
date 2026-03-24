"""Insights router: audit flags, cost analysis, anomaly detection."""
from fastapi import APIRouter, Request

from services.analytics_service import get_insights, get_spend_by_carrier

router = APIRouter(tags=["insights"])


@router.get("/projects/{project_id}/insights")
async def project_insights(project_id: str, request: Request):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    return get_insights(proj["reference_file"])


@router.get("/projects/{project_id}/insights/cost-breakdown")
async def cost_breakdown(project_id: str, request: Request):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    carriers = get_spend_by_carrier(proj["reference_file"])

    # Compute per-carrier breakdown
    for c in carriers:
        if c["service_count"] > 0:
            c["avg_mrc_per_service"] = round(c["mrc"] / c["service_count"], 2)
        else:
            c["avg_mrc_per_service"] = 0

    return carriers
