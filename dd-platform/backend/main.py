from __future__ import annotations
"""Digital Direction POC — FastAPI Backend with persistent storage."""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import dashboard, documents, inventory, extraction, insights, accuracy
from services.persistence import load_projects, save_project

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Digital Direction POC", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration ---
CODE_AGENT_DIR = Path(__file__).resolve().parent.parent.parent
CLAUDE_DIR = CODE_AGENT_DIR.parent
CLIENT_INPUTS = CLAUDE_DIR / "Client Inputs" / "NSS POC Inputs and Output"
EXTRACTION_DIR = CODE_AGENT_DIR / "dd-extraction"
OUTPUT_DIR = EXTRACTION_DIR / "outputs"
NSS_REFERENCE = CLIENT_INPUTS / "Digital Direction_NSS_ Inventory File_01.22.2026_WIP_v3 BF- Sent to Techjays.xlsx"

# Upload directory for new projects
UPLOADS_DIR = CODE_AGENT_DIR / "dd-platform" / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# --- Load projects from persistent storage ---
# Default NSS project (always available)
NSS_PROJECT = {
    "id": "nss",
    "name": "NSS (Golub Corporation)",
    "input_dir": str(CLIENT_INPUTS),
    "output_dir": str(OUTPUT_DIR),
    "reference_file": str(NSS_REFERENCE),
    "extraction_dir": str(EXTRACTION_DIR),
}

# Load saved projects from disk, merge with defaults
saved_projects = load_projects()
app.state.projects = {"nss": NSS_PROJECT}
for pid, proj in saved_projects.items():
    if pid != "nss":  # Don't override the default NSS project
        app.state.projects[pid] = proj

app.state.default_project = "nss"
app.state.uploads_dir = str(UPLOADS_DIR)

logger.info(f"Loaded {len(app.state.projects)} projects ({len(saved_projects)} from disk)")

# --- Routers ---
app.include_router(dashboard.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(extraction.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(accuracy.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/projects")
async def list_projects():
    return list(app.state.projects.values())


@app.get("/api/projects/{project_id}/info")
async def project_info(project_id: str):
    """Return project metadata including data availability flags."""
    proj = app.state.projects.get(project_id)
    if not proj:
        return {"error": "Project not found"}

    ref_file = proj.get("reference_file", "") or ""
    has_reference = bool(ref_file) and Path(ref_file).exists() and Path(ref_file).is_file()

    out_dir = proj.get("output_dir", "")
    has_extracted = False
    if out_dir:
        output_dir = Path(out_dir)
        if output_dir.exists():
            has_extracted = bool(list(output_dir.glob("*_inventory_output.xlsx")))

    return {
        "id": proj.get("id", project_id),
        "name": proj.get("name", project_id),
        "has_reference": has_reference,
        "has_extracted": has_extracted,
        "default_source": "reference" if has_reference else ("extracted" if has_extracted else "none"),
    }


@app.post("/api/projects")
async def create_project(data: dict):
    """Create a new project with its own input/output directories. Persisted to disk."""
    project_id = data.get("id", "").strip().lower().replace(" ", "-")
    name = data.get("name", project_id)

    if not project_id:
        return {"error": "Project ID is required"}
    if project_id in app.state.projects:
        return {"error": f"Project '{project_id}' already exists"}

    # Create directory structure
    project_dir = UPLOADS_DIR / project_id
    input_dir = project_dir / "inputs"
    output_dir = project_dir / "outputs"
    for sub in ["Invoices", "Contracts", "Carrier Reports, Portal Data, ETC", "CSRs"]:
        (input_dir / sub).mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    project = {
        "id": project_id,
        "name": name,
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "reference_file": "",
        "extraction_dir": str(EXTRACTION_DIR),
    }

    # Save to memory AND disk
    app.state.projects[project_id] = project
    save_project(project)

    logger.info(f"Created project: {project_id} ({name})")
    return project


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    proj = app.state.projects.get(project_id)
    if not proj:
        return {"error": f"Project {project_id} not found"}
    return proj
