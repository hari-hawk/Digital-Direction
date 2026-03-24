from __future__ import annotations
"""Extraction router: run pipeline as background task, track progress, and manage notifications."""
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["extraction"])

# Load API key from .env
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ─── In-memory stores ────────────────────────────────────
# task_id -> { status, progress, current_carrier, elapsed_seconds, result, started_at, ... }
_tasks: dict[str, dict] = {}
# project_id -> [ { id, type, title, message, timestamp, read } ]
_notifications: dict[str, list[dict]] = {}


class ExtractionRequest(BaseModel):
    carrier_key: str
    api_key: Optional[str] = None


class NotificationReadRequest(BaseModel):
    pass


def _get_carrier_name(carrier_key: str) -> str:
    """Map carrier key to display name."""
    names = {
        "charter": "Charter Communications",
        "windstream": "Windstream",
        "granite": "Granite Telecommunications",
        "peerless": "Peerless Network",
    }
    return names.get(carrier_key, carrier_key.title())


def _add_notification(project_id: str, notif_type: str, title: str, message: str) -> dict:
    """Add a notification for a project."""
    notif = {
        "id": str(uuid.uuid4()),
        "type": notif_type,
        "title": title,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "read": False,
    }
    if project_id not in _notifications:
        _notifications[project_id] = []
    _notifications[project_id].insert(0, notif)
    # Keep only last 50 notifications
    _notifications[project_id] = _notifications[project_id][:50]
    return notif


def _run_extraction_background(
    task_id: str,
    project_id: str,
    proj: dict,
    carrier_key: str,
    api_key: str,
) -> None:
    """Run extraction in a background thread."""
    task = _tasks[task_id]
    task["status"] = "running"
    task["current_carrier"] = _get_carrier_name(carrier_key)
    task["progress"] = 10
    started_at = time.time()

    extraction_dir = Path(proj["extraction_dir"])
    main_script = extraction_dir / "main.py"

    if not main_script.exists():
        task["status"] = "failed"
        task["error"] = f"Extraction script not found at {main_script}"
        task["progress"] = 0
        elapsed = time.time() - started_at
        task["elapsed_seconds"] = round(elapsed, 1)
        _add_notification(
            project_id, "extraction_failed", "Extraction Failed",
            f"Extraction script not found for {_get_carrier_name(carrier_key)}."
        )
        return

    # Build command
    cmd = [
        sys.executable, str(main_script),
        "--carrier", carrier_key,
        "--input-dir", proj["input_dir"],
        "--output-dir", proj["output_dir"],
    ]
    if api_key:
        cmd.extend(["--anthropic-api-key", api_key])

    task["progress"] = 20

    try:
        # Use Popen for real-time progress tracking
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(extraction_dir),
        )

        # Simulate progress updates while process runs
        progress_steps = [30, 40, 50, 60, 70, 80, 85, 90]
        step_idx = 0

        while process.poll() is None:
            time.sleep(2)
            elapsed = time.time() - started_at
            task["elapsed_seconds"] = round(elapsed, 1)
            if step_idx < len(progress_steps):
                task["progress"] = progress_steps[step_idx]
                step_idx += 1
            # Timeout after 300 seconds
            if elapsed > 300:
                process.kill()
                task["status"] = "timeout"
                task["error"] = "Extraction timed out after 300 seconds"
                task["progress"] = 0
                _add_notification(
                    project_id, "extraction_failed", "Extraction Timed Out",
                    f"Extraction for {_get_carrier_name(carrier_key)} timed out after 5 minutes."
                )
                return

        stdout = process.stdout.read() if process.stdout else ""
        stderr = process.stderr.read() if process.stderr else ""
        task["progress"] = 95

        elapsed = time.time() - started_at
        task["elapsed_seconds"] = round(elapsed, 1)

        # Read summary file
        summary_file = Path(proj["output_dir"]) / f"{carrier_key}_pipeline_summary.json"
        summary = {}
        if summary_file.exists():
            with open(summary_file) as f:
                summary = json.load(f)

        if process.returncode == 0:
            task["status"] = "completed"
            task["progress"] = 100
            task["result"] = {
                "summary": summary,
                "stdout": stdout[-3000:] if stdout else "",
                "stderr": stderr[-1000:] if stderr else "",
            }

            # Build notification message
            total_rows = summary.get("total_rows", 0)
            proc_time = summary.get("processing_time_seconds", round(elapsed, 1))
            row_stats = summary.get("row_stats", {})
            carrier_count = len(set(
                v for k, v in row_stats.items() if isinstance(v, int)
            )) if row_stats else 1

            # Try to get accuracy from QA summary
            qa_summary = summary.get("qa_summary", {})
            qa_rules = qa_summary.get("rules", {})
            total_qa = len(qa_rules)
            passed_qa = sum(1 for r in qa_rules.values() if r.get("passed"))
            accuracy_pct = round((passed_qa / total_qa * 100), 1) if total_qa > 0 else 0

            message = (
                f"Extracted {total_rows:,} rows for {_get_carrier_name(carrier_key)} "
                f"in {proc_time}s."
            )
            if total_qa > 0:
                message += f" QA: {passed_qa}/{total_qa} rules passed ({accuracy_pct}%)."

            _add_notification(
                project_id, "extraction_complete", "Extraction Complete", message
            )
        else:
            task["status"] = "failed"
            task["progress"] = 0
            task["result"] = {
                "summary": summary,
                "stdout": stdout[-3000:] if stdout else "",
                "stderr": stderr[-1000:] if stderr else "",
            }
            _add_notification(
                project_id, "extraction_failed", "Extraction Failed",
                f"Extraction for {_get_carrier_name(carrier_key)} failed. Check logs for details."
            )

    except Exception as e:
        elapsed = time.time() - started_at
        task["elapsed_seconds"] = round(elapsed, 1)
        task["status"] = "failed"
        task["progress"] = 0
        task["error"] = str(e)
        _add_notification(
            project_id, "extraction_failed", "Extraction Failed",
            f"Error extracting {_get_carrier_name(carrier_key)}: {str(e)[:100]}"
        )


# ─── Endpoints ───────────────────────────────────────────

@router.post("/projects/{project_id}/extract")
async def run_extraction(project_id: str, req: ExtractionRequest, request: Request):
    """Start background extraction and return task ID immediately."""
    proj = request.app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    # Create task
    task_id = str(uuid.uuid4())
    api_key = req.api_key or ANTHROPIC_API_KEY

    _tasks[task_id] = {
        "task_id": task_id,
        "project_id": project_id,
        "carrier_key": req.carrier_key,
        "carrier_name": _get_carrier_name(req.carrier_key),
        "status": "started",
        "progress": 0,
        "current_carrier": _get_carrier_name(req.carrier_key),
        "elapsed_seconds": 0,
        "result": None,
        "error": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    # Add "started" notification
    _add_notification(
        project_id, "extraction_started", "Extraction Started",
        f"Starting extraction for {_get_carrier_name(req.carrier_key)}..."
    )

    # Launch background thread
    thread = threading.Thread(
        target=_run_extraction_background,
        args=(task_id, project_id, proj, req.carrier_key, api_key),
        daemon=True,
    )
    thread.start()

    return {"task_id": task_id, "status": "started"}


@router.get("/projects/{project_id}/extraction/task/{task_id}")
async def get_task_progress(project_id: str, task_id: str):
    """Get progress of a running extraction task."""
    task = _tasks.get(task_id)
    if not task:
        return {"error": "Task not found"}
    if task["project_id"] != project_id:
        return {"error": "Task does not belong to this project"}
    return task


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


# ─── Notifications ───────────────────────────────────────

@router.get("/projects/{project_id}/notifications")
async def get_notifications(project_id: str):
    """Get all notifications for a project."""
    notifs = _notifications.get(project_id, [])
    unread_count = sum(1 for n in notifs if not n["read"])
    return {"notifications": notifs, "unread_count": unread_count}


@router.post("/projects/{project_id}/notifications/{notification_id}/read")
async def mark_notification_read(project_id: str, notification_id: str):
    """Mark a single notification as read."""
    notifs = _notifications.get(project_id, [])
    for n in notifs:
        if n["id"] == notification_id:
            n["read"] = True
            return {"status": "ok"}
    return {"error": "Notification not found"}


@router.post("/projects/{project_id}/notifications/read-all")
async def mark_all_notifications_read(project_id: str):
    """Mark all notifications as read."""
    notifs = _notifications.get(project_id, [])
    for n in notifs:
        n["read"] = True
    return {"status": "ok", "count": len(notifs)}
