from __future__ import annotations
"""Dashboard router: stats, spending, service type distribution, enhanced metrics."""
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Request

from services.analytics_service import (
    get_dashboard_stats, get_spend_by_carrier,
    get_service_type_distribution, get_charge_type_distribution,
    load_inventory,
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


@router.get("/projects/{project_id}/dashboard/enhanced")
async def enhanced_dashboard(project_id: str, request: Request):
    """Enhanced dashboard metrics: S/C/U breakdown, contract expiry, data quality, cost analysis."""
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    ref_file = proj.get("reference_file", "")
    df = load_inventory(ref_file)
    if df.empty:
        return {
            "scu_breakdown": [], "contract_expiry": [], "data_quality": {},
            "cost_by_service_type": [], "top_locations": [], "health_score": 0,
        }

    # Column lookups
    carrier_col = next((c for c in df.columns if c.lower() == "carrier"), "Carrier")
    scu_col = next((c for c in df.columns if "service or component" in c.lower()), "Service or Component")
    mrc_col = next((c for c in df.columns if "monthly recurring" in c.lower()), "Monthly Recurring Cost")
    svc_col = next((c for c in df.columns if c.lower() == "service type"), "Service Type")
    status_col = next((c for c in df.columns if c.lower() == "status"), None)
    addr_col = next((c for c in df.columns if "service address 1" in c.lower()), None)
    contract_exp_col = next((c for c in df.columns if "expiration" in c.lower()), None)
    m2m_col = next((c for c in df.columns if "month-to-month" in c.lower()), None)

    df["_mrc"] = pd.to_numeric(df[mrc_col], errors="coerce").fillna(0)

    # 1. S/C/U Breakdown by carrier
    scu_breakdown = []
    for carrier in df[carrier_col].dropna().unique():
        c_df = df[df[carrier_col] == carrier]
        scu_breakdown.append({
            "carrier": carrier,
            "s_rows": int((c_df[scu_col].astype(str).str.strip() == "S").sum()),
            "c_rows": int((c_df[scu_col].astype(str).str.strip() == "C").sum()),
            "t_rows": int(c_df[scu_col].astype(str).str.strip().str.startswith("T").sum()),
            "u_rows": int((c_df[scu_col].astype(str).str.strip() == "U").sum()),
            "total": len(c_df),
            "mrc": round(float(c_df["_mrc"].sum()), 2),
        })
    scu_breakdown.sort(key=lambda x: x["total"], reverse=True)

    # 2. Contract Expiration Analysis
    contract_expiry = []
    if contract_exp_col:
        exp_dates = pd.to_datetime(df[contract_exp_col], errors="coerce")
        valid_exp = exp_dates.dropna()
        if len(valid_exp) > 0:
            now = pd.Timestamp.now()
            expired = (valid_exp < now).sum()
            within_90 = ((valid_exp >= now) & (valid_exp < now + pd.Timedelta(days=90))).sum()
            within_year = ((valid_exp >= now) & (valid_exp < now + pd.Timedelta(days=365))).sum()
            beyond_year = (valid_exp >= now + pd.Timedelta(days=365)).sum()
            contract_expiry = [
                {"category": "Expired", "count": int(expired), "color": "#ef4444"},
                {"category": "Within 90 days", "count": int(within_90), "color": "#f59e0b"},
                {"category": "Within 1 year", "count": int(within_year - within_90), "color": "#3b82f6"},
                {"category": "Beyond 1 year", "count": int(beyond_year), "color": "#10b981"},
            ]

    # 3. Month-to-Month analysis
    m2m_count = 0
    if m2m_col:
        m2m_count = int(df[m2m_col].astype(str).str.lower().str.contains("yes", na=False).sum())

    # 4. Data Quality Score
    required_cols = ["Carrier", "Service Type", "Billing Name", "Service Address 1",
                     "City", "State", "Zip", "Monthly Recurring Cost", "Charge Type"]
    quality_scores = {}
    for col_name in required_cols:
        col = next((c for c in df.columns if c.strip().lower() == col_name.lower()), None)
        if col:
            populated = df[col].notna() & (df[col].astype(str).str.strip() != "")
            quality_scores[col_name] = round(populated.mean() * 100, 1)
    avg_quality = round(sum(quality_scores.values()) / len(quality_scores), 1) if quality_scores else 0

    # 5. Cost by Service Type
    cost_by_svc = (
        df.groupby(svc_col).agg(
            mrc=("_mrc", "sum"),
            count=(svc_col, "size"),
            s_count=(scu_col, lambda x: (x.astype(str).str.strip() == "S").sum()),
        )
        .sort_values("mrc", ascending=False)
        .head(10)
        .reset_index()
    )
    cost_by_service_type = [
        {
            "service_type": row[svc_col],
            "mrc": round(float(row["mrc"]), 2),
            "count": int(row["count"]),
            "services": int(row["s_count"]),
        }
        for _, row in cost_by_svc.iterrows()
    ]

    # 6. Top Locations by Spend
    top_locations = []
    if addr_col:
        loc_spend = (
            df.groupby(addr_col)["_mrc"].sum()
            .sort_values(ascending=False)
            .head(10)
        )
        top_locations = [
            {"address": str(addr), "mrc": round(float(mrc), 2)}
            for addr, mrc in loc_spend.items()
            if pd.notna(addr) and str(addr).strip()
        ]

    # 7. Status Distribution
    status_dist = []
    if status_col:
        for status, count in df[status_col].value_counts().items():
            if pd.notna(status):
                status_dist.append({"status": str(status), "count": int(count)})

    # 8. Health Score (0-100)
    health = avg_quality * 0.4  # 40% from data quality
    if len(df) > 0:
        s_rows = (df[scu_col].astype(str).str.strip() == "S").sum()
        if s_rows > 0:
            health += 20  # Has services
        if df["_mrc"].sum() > 0:
            health += 20  # Has cost data
        if contract_exp_col and pd.to_datetime(df[contract_exp_col], errors="coerce").notna().sum() > 0:
            health += 10  # Has contract dates
        if m2m_count > 0:
            health += 10  # Has M2M tracking

    return {
        "scu_breakdown": scu_breakdown,
        "contract_expiry": contract_expiry,
        "month_to_month_count": m2m_count,
        "data_quality": quality_scores,
        "avg_data_quality": avg_quality,
        "cost_by_service_type": cost_by_service_type,
        "top_locations": top_locations,
        "status_distribution": status_dist,
        "health_score": min(round(health), 100),
    }
