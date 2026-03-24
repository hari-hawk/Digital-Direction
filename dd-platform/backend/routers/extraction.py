"""Extraction router: run pipeline and get results."""
import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["extraction"])


class ExtractionRequest(BaseModel):
    carrier_key: str
    api_key: Optional[str] = None


@router.post("/projects/{project_id}/extract")
async def run_extraction(project_id: str, req: ExtractionRequest, request: Request):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    extraction_dir = Path(proj["extraction_dir"])
    main_script = extraction_dir / "main.py"

    if not main_script.exists():
        return {"error": f"Extraction script not found at {main_script}"}

    # Build command
    cmd = [
        sys.executable, str(main_script),
        "--carrier", req.carrier_key,
        "--input-dir", proj["input_dir"],
        "--output-dir", proj["output_dir"],
    ]
    if req.api_key:
        cmd.extend(["--anthropic-api-key", req.api_key])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(extraction_dir),
        )

        # Read summary file
        summary_file = Path(proj["output_dir"]) / f"{req.carrier_key}_pipeline_summary.json"
        summary = {}
        if summary_file.exists():
            with open(summary_file) as f:
                summary = json.load(f)

        return {
            "status": "completed" if result.returncode == 0 else "failed",
            "summary": summary,
            "stdout": result.stdout[-3000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else "",
        }

    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": "Extraction timed out after 300 seconds"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@router.get("/projects/{project_id}/extraction/status")
async def extraction_status(project_id: str, carrier_key: str, request: Request):
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    summary_file = Path(proj["output_dir"]) / f"{carrier_key}_pipeline_summary.json"
    if not summary_file.exists():
        return {"status": "not_run", "carrier": carrier_key}

    with open(summary_file) as f:
        summary = json.load(f)

    return {"status": "completed", **summary}


@router.get("/projects/{project_id}/extraction/carriers")
async def available_carriers(project_id: str, request: Request):
    """List carriers available for extraction."""
    return [
        {"key": "charter", "name": "Charter Communications", "tier": 1, "status": "ready"},
        {"key": "windstream", "name": "Windstream", "tier": 2, "status": "planned"},
        {"key": "granite", "name": "Granite Telecommunications", "tier": 3, "status": "planned"},
        {"key": "peerless", "name": "Peerless Network", "tier": 2, "status": "planned"},
    ]
