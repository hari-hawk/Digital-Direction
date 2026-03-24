"""Analytics service: reads inventory data and computes dashboard metrics."""
import logging
from pathlib import Path
from functools import lru_cache

import pandas as pd

logger = logging.getLogger(__name__)

# Cache for inventory data
_inventory_cache: dict[str, pd.DataFrame] = {}


def load_inventory(file_path: str, force_reload: bool = False) -> pd.DataFrame:
    """Load inventory data from Excel file with caching."""
    if file_path in _inventory_cache and not force_reload:
        return _inventory_cache[file_path]

    path = Path(file_path)
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_excel(path, sheet_name="Baseline", header=2)
    # Normalize column names
    df.columns = [str(c).strip() for c in df.columns]
    _inventory_cache[file_path] = df
    logger.info(f"Loaded inventory: {len(df)} rows from {path.name}")
    return df


def get_dashboard_stats(file_path: str) -> dict:
    """Compute dashboard summary statistics."""
    df = load_inventory(file_path)
    if df.empty:
        return {"total_mrc": 0, "carriers": 0, "services": 0, "rows": 0}

    carrier_col = next((c for c in df.columns if c.lower() == "carrier"), "Carrier")
    mrc_col = next((c for c in df.columns if "monthly recurring" in c.lower()), "Monthly Recurring Cost")
    scu_col = next((c for c in df.columns if "service or component" in c.lower()), "Service or Component")

    total_mrc = pd.to_numeric(df[mrc_col], errors="coerce").sum()
    carriers = df[carrier_col].nunique()
    s_rows = len(df[df[scu_col].astype(str).str.strip() == "S"])

    return {
        "total_mrc": round(float(total_mrc), 2),
        "carriers": int(carriers),
        "services": int(s_rows),
        "total_rows": len(df),
    }


def get_spend_by_carrier(file_path: str) -> list[dict]:
    """Get MRC totals per carrier."""
    df = load_inventory(file_path)
    if df.empty:
        return []

    carrier_col = next((c for c in df.columns if c.lower() == "carrier"), "Carrier")
    mrc_col = next((c for c in df.columns if "monthly recurring" in c.lower()), "Monthly Recurring Cost")
    scu_col = next((c for c in df.columns if "service or component" in c.lower()), "Service or Component")

    df["_mrc"] = pd.to_numeric(df[mrc_col], errors="coerce").fillna(0)

    result = (
        df.groupby(carrier_col)
        .agg(
            mrc=("_mrc", "sum"),
            row_count=(carrier_col, "size"),
            service_count=(scu_col, lambda x: (x.astype(str).str.strip() == "S").sum()),
        )
        .sort_values("mrc", ascending=False)
        .reset_index()
    )

    return [
        {
            "carrier": row[carrier_col],
            "mrc": round(float(row["mrc"]), 2),
            "row_count": int(row["row_count"]),
            "service_count": int(row["service_count"]),
        }
        for _, row in result.iterrows()
    ]


def get_service_type_distribution(file_path: str) -> list[dict]:
    """Get count and MRC by service type."""
    df = load_inventory(file_path)
    if df.empty:
        return []

    svc_col = next((c for c in df.columns if c.lower() == "service type"), "Service Type")
    mrc_col = next((c for c in df.columns if "monthly recurring" in c.lower()), "Monthly Recurring Cost")

    df["_mrc"] = pd.to_numeric(df[mrc_col], errors="coerce").fillna(0)

    result = (
        df.groupby(svc_col)
        .agg(count=(svc_col, "size"), mrc=("_mrc", "sum"))
        .sort_values("count", ascending=False)
        .reset_index()
    )

    return [
        {
            "service_type": row[svc_col],
            "count": int(row["count"]),
            "mrc": round(float(row["mrc"]), 2),
        }
        for _, row in result.iterrows()
        if pd.notna(row[svc_col])
    ]


def get_charge_type_distribution(file_path: str) -> list[dict]:
    """Get count by charge type."""
    df = load_inventory(file_path)
    if df.empty:
        return []

    charge_col = next((c for c in df.columns if "charge type" in c.lower()), "Charge Type")
    counts = df[charge_col].value_counts().to_dict()
    return [{"charge_type": k, "count": int(v)} for k, v in counts.items() if pd.notna(k)]


def get_inventory_rows(
    file_path: str,
    carrier: str = None,
    service_type: str = None,
    charge_type: str = None,
    scu_code: str = None,
    status: str = None,
    search: str = None,
    sort_by: str = None,
    sort_dir: str = "asc",
    page: int = 1,
    page_size: int = 100,
) -> dict:
    """Get paginated inventory rows with filters and sorting."""
    df = load_inventory(file_path)
    if df.empty:
        return {"rows": [], "total": 0, "page": page, "page_size": page_size, "columns": list(df.columns)}

    carrier_col = next((c for c in df.columns if c.lower() == "carrier"), "Carrier")
    svc_col = next((c for c in df.columns if c.lower() == "service type"), "Service Type")
    charge_col = next((c for c in df.columns if "charge type" in c.lower()), "Charge Type")
    scu_col = next((c for c in df.columns if "service or component" in c.lower()), "Service or Component")
    status_col = next((c for c in df.columns if c.lower() == "status"), None)

    # Apply filters
    mask = pd.Series([True] * len(df))
    if carrier:
        mask &= df[carrier_col].astype(str).str.contains(carrier, case=False, na=False)
    if service_type:
        mask &= df[svc_col].astype(str).str.contains(service_type, case=False, na=False)
    if charge_type:
        mask &= df[charge_col].astype(str).str.strip() == charge_type
    if scu_code:
        mask &= df[scu_col].astype(str).str.strip() == scu_code
    if status and status_col:
        mask &= df[status_col].astype(str).str.contains(status, case=False, na=False)
    if search:
        text_mask = pd.Series([False] * len(df))
        for col in df.columns:
            text_mask |= df[col].astype(str).str.contains(search, case=False, na=False)
        mask &= text_mask

    filtered = df[mask].copy()

    # Apply sorting
    if sort_by and sort_by in filtered.columns:
        ascending = sort_dir != "desc"
        filtered = filtered.sort_values(sort_by, ascending=ascending, na_position="last")

    total = len(filtered)

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    page_df = filtered.iloc[start:end]

    rows = []
    for idx, row in page_df.iterrows():
        row_dict = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                row_dict[col] = None
            elif hasattr(val, 'item'):
                row_dict[col] = val.item()
            elif hasattr(val, 'isoformat'):
                row_dict[col] = val.isoformat()
            else:
                row_dict[col] = val
        rows.append({
            "row_index": int(idx),
            "data": row_dict,
            "service_or_component": str(row.get(scu_col, "")).strip(),
        })

    return {
        "rows": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "columns": list(df.columns),
    }


def get_insights(file_path: str) -> list[dict]:
    """Compute audit insight flags."""
    df = load_inventory(file_path)
    if df.empty:
        return []

    insights = []
    mrc_col = next((c for c in df.columns if "monthly recurring" in c.lower()), "Monthly Recurring Cost")
    scu_col = next((c for c in df.columns if "service or component" in c.lower()), "Service or Component")
    carrier_col = next((c for c in df.columns if c.lower() == "carrier"), "Carrier")
    svc_col = next((c for c in df.columns if c.lower() == "service type"), "Service Type")

    df["_mrc"] = pd.to_numeric(df[mrc_col], errors="coerce").fillna(0)

    # Flag: zero-cost services
    s_rows = df[df[scu_col].astype(str).str.strip() == "S"]
    zero_cost = s_rows[s_rows["_mrc"] == 0]
    if len(zero_cost) > 0:
        insights.append({
            "category": "Zero-Cost Services",
            "severity": "warning",
            "count": len(zero_cost),
            "description": f"{len(zero_cost)} services have $0 MRC — verify if intentional",
            "details": [f"{row[carrier_col]}: {row.get('Service Address 1', 'N/A')}" for _, row in zero_cost.head(10).iterrows()],
        })

    # Flag: high-cost outliers per service type
    svc_stats = s_rows.groupby(svc_col)["_mrc"].agg(["mean", "std", "count"])
    for svc_type, stats in svc_stats.iterrows():
        if stats["count"] < 3 or stats["std"] == 0:
            continue
        threshold = stats["mean"] + 2 * stats["std"]
        outliers = s_rows[(s_rows[svc_col] == svc_type) & (s_rows["_mrc"] > threshold)]
        if len(outliers) > 0:
            insights.append({
                "category": f"Cost Outliers: {svc_type}",
                "severity": "info",
                "count": len(outliers),
                "description": f"{len(outliers)} {svc_type} services above 2σ (>${threshold:.0f}/mo vs avg ${stats['mean']:.0f})",
                "details": [
                    f"{row[carrier_col]}: ${row['_mrc']:.2f}/mo at {row.get('Service Address 1', 'N/A')}"
                    for _, row in outliers.head(5).iterrows()
                ],
            })

    # Flag: missing required fields
    required_cols = ["Carrier", "Service Type", "Billing Name", "Service Address 1", "City", "State", "Zip"]
    for col_name in required_cols:
        col = next((c for c in df.columns if c.strip() == col_name), None)
        if col:
            missing = df[df[col].isna() | (df[col].astype(str).str.strip() == "")]
            if len(missing) > 0:
                insights.append({
                    "category": f"Missing: {col_name}",
                    "severity": "critical" if col_name in ("Carrier", "Service Type") else "warning",
                    "count": len(missing),
                    "description": f"{len(missing)} rows missing {col_name}",
                    "details": [],
                })

    return sorted(insights, key=lambda x: {"critical": 0, "warning": 1, "info": 2}[x["severity"]])
