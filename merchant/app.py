"""
Merchant server: serves an agent-readable catalog.
Every served action is written to the audit trail.
"""
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from audit.audit import write_event

app = FastAPI(title="TrailKart Merchant", version="0.1.0")

CATALOG_PATH = Path(__file__).resolve().parent / "catalog.json"


@app.get("/")
def root():
    # Front door: anyone landing on / gets sent straight to the catalog.
    return RedirectResponse(url="/catalog")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/catalog")
def get_catalog():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    write_event(
        actor="merchant",
        action="catalog_served",
        detail={"item_count": len(catalog["items"])},
        reason="buyer agent requested the agent-readable catalog",
    )
    return catalog