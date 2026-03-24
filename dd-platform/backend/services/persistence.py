from __future__ import annotations
"""
Persistence service — Neon PostgreSQL backend.
Stores project configs, checklists, extraction runs, and file metadata.
"""
import logging
import os
from pathlib import Path

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# Load .env file if it exists
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    logger.warning("DATABASE_URL not set — persistence disabled. Create a .env file with DATABASE_URL.")


def _get_conn():
    """Get a database connection. Returns None if DATABASE_URL not configured."""
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL)


# ─── Projects ───────────────────────────────────────────

def load_projects() -> dict[str, dict]:
    """Load all projects from database."""
    try:
        conn = _get_conn()
        if conn is None:
            return {}
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name, input_dir, output_dir, reference_file, extraction_dir FROM projects ORDER BY created_at")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {r["id"]: dict(r) for r in rows}
    except Exception as e:
        logger.warning(f"Failed to load projects from DB: {e}")
        return {}


def save_project(project: dict) -> None:
    """Upsert a project."""
    try:
        conn = _get_conn()
        if conn is None:
            return
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO projects (id, name, input_dir, output_dir, reference_file, extraction_dir)
            VALUES (%(id)s, %(name)s, %(input_dir)s, %(output_dir)s, %(reference_file)s, %(extraction_dir)s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                input_dir = EXCLUDED.input_dir,
                output_dir = EXCLUDED.output_dir,
                reference_file = EXCLUDED.reference_file,
                extraction_dir = EXCLUDED.extraction_dir,
                updated_at = NOW()
        """, project)
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Saved project to DB: {project['id']}")
    except Exception as e:
        logger.error(f"Failed to save project: {e}")


def delete_project(project_id: str) -> bool:
    """Delete a project."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        conn.close()
        return deleted
    except Exception as e:
        logger.error(f"Failed to delete project: {e}")
        return False


# ─── Checklists ─────────────────────────────────────────

def load_checklist(project_id: str) -> list[dict]:
    """Load checklist items for a project."""
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM checklist_items WHERE project_id = %s ORDER BY item_index",
            (project_id,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Failed to load checklist: {e}")
        return []


def save_checklist(project_id: str, items: list[dict]) -> None:
    """Save checklist items (replace all)."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        # Clear existing
        cur.execute("DELETE FROM checklist_items WHERE project_id = %s", (project_id,))
        # Insert new
        for i, item in enumerate(items):
            # Items have dynamic columns like "Checklist", "Agent - Yes/No", "QA - Yes/No"
            text = item.get("Checklist", "")
            agent = item.get("Agent - Yes/No", "")
            qa = item.get("QA - Yes/No", "")
            cur.execute(
                """INSERT INTO checklist_items (project_id, item_index, checklist_text, agent_status, qa_status)
                   VALUES (%s, %s, %s, %s, %s)""",
                (project_id, i, text, agent, qa)
            )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Saved {len(items)} checklist items for {project_id}")
    except Exception as e:
        logger.error(f"Failed to save checklist: {e}")


# ─── Extraction Runs ────────────────────────────────────

def save_extraction_run(
    project_id: str,
    carrier_key: str,
    carrier_name: str,
    total_rows: int,
    s_rows: int,
    c_rows: int,
    tsocc_rows: int,
    qa_passed: int,
    qa_total: int,
    duration: float,
    output_file: str,
) -> None:
    """Record an extraction run."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO extraction_runs
                (project_id, carrier_key, carrier_name, total_rows, s_rows, c_rows,
                 tsocc_rows, qa_passed, qa_total, duration_seconds, output_file)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (project_id, carrier_key, carrier_name, total_rows, s_rows, c_rows,
              tsocc_rows, qa_passed, qa_total, duration, output_file))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save extraction run: {e}")


def get_extraction_runs(project_id: str) -> list[dict]:
    """Get all extraction runs for a project."""
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM extraction_runs WHERE project_id = %s ORDER BY created_at DESC",
            (project_id,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Failed to load extraction runs: {e}")
        return []


# ─── Uploaded Files ─────────────────────────────────────

def save_uploaded_file(
    project_id: str, carrier: str, doc_type: str,
    file_name: str, file_path: str, size_bytes: int,
) -> None:
    """Record an uploaded file."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO uploaded_files (project_id, carrier, doc_type, file_name, file_path, size_bytes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (project_id, carrier, doc_type, file_name, file_path, size_bytes))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save uploaded file record: {e}")


def get_uploaded_files(project_id: str) -> list[dict]:
    """Get all uploaded files for a project."""
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM uploaded_files WHERE project_id = %s ORDER BY uploaded_at DESC",
            (project_id,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Failed to load uploaded files: {e}")
        return []
