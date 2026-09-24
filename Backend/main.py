"""
main.py
============================================================================
FastAPI application - the synchronous API surface for the tactical
dashboard. Heavy AI work is never done here; it's always dispatched to
Celery (tasks.py) so the API stays responsive on laptop-scale hardware
even while a large CDR batch is being processed in the background.

Endpoints:
  POST /ingest                      - upload FIR/CDR, dispatch AI pipeline
  GET  /task-status/{task_id}       - poll pipeline progress
  GET  /graph                       - fetch graph for visualization (confidence-filtered)
  GET  /analytics/betweenness       - money-mule / bagman ranking
  GET  /analytics/louvain           - syndicate/cell clustering
  POST /simulate-disruption/{id}    - What-If node removal simulation
  GET  /dossier                     - BSA Section 63 evidentiary dossier feed
  GET  /health                      - liveness check
============================================================================
"""

import os
import uuid
import shutil
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import get_db
from security import sha256_file
from graph_analytics import (
    run_betweenness_centrality,
    run_louvain_communities,
    simulate_node_disruption,
)
from tasks import process_document
from celery_app import celery_app


EVIDENCE_STORE_PATH = os.getenv("EVIDENCE_STORE_PATH", "/data/evidence")
os.makedirs(EVIDENCE_STORE_PATH, exist_ok=True)

app = FastAPI(
    title="AI-Powered Criminal Network Analysis System (CNAS)",
    description="Air-gapped POLE graph intelligence platform for law enforcement.",
    version="0.1.0-prototype",
)

# CORS restricted to localhost origins only - this platform is designed to
# never be reachable from outside the station LAN / analyst workstation.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# INGESTION
# --------------------------------------------------------------------------
@app.post("/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    doc_type: str = Form(..., description="fir_scan | cdr_audio | cdr_text"),
):
    """
    Accepts a raw evidence file, persists it immutably to the append-only
    evidence store, computes its BSA S.63 source hash BEFORE any AI touches
    it, then dispatches the async extraction pipeline.
    """
    if doc_type not in {"fir_scan", "cdr_audio", "cdr_text"}:
        raise HTTPException(400, "doc_type must be one of: fir_scan, cdr_audio, cdr_text")

    source_doc_id = str(uuid.uuid4())
    dest_path = os.path.join(EVIDENCE_STORE_PATH, f"{source_doc_id}_{file.filename}")

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Hash computed synchronously and immediately, at the moment of receipt -
    # this is the timestamp/hash pair that anchors the chain of custody.
    original_hash = sha256_file(dest_path)

    task = process_document.delay(dest_path, doc_type, source_doc_id)

    return {
        "source_doc_id": source_doc_id,
        "filename": file.filename,
        "original_file_sha256": original_hash,
        "task_id": task.id,
        "status": "QUEUED",
        "message": "Evidence hashed and pipeline dispatched to worker.",
    }


@app.get("/task-status/{task_id}")
async def task_status(task_id: str):
    """Poll for Celery task progress -> drives a live progress UI."""
    result = celery_app.AsyncResult(task_id)
    response = {"task_id": task_id, "state": result.state}
    if result.state == "PROGRESS":
        response["meta"] = result.info
    elif result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(result.info)
    return response


# --------------------------------------------------------------------------
# GRAPH QUERYING
# --------------------------------------------------------------------------
@app.get("/graph")
async def get_graph(min_confidence: float = 0.0, limit: int = 500):
    """Return a JSON-safe graph for react-force-graph-2d."""
    if not 0.0 <= min_confidence <= 1.0:
        raise HTTPException(400, "min_confidence must be between 0.0 and 1.0")
    limit = max(1, min(int(limit), 5000))

    db = get_db()
    rows = db.get_full_graph(min_confidence=min_confidence, limit=limit)

    nodes = {}
    links = []

    for row in rows:
        a = row.get("a") or {}
        b = row.get("b") or {}
        r = row.get("r") or {}
        a_labels = row.get("a_labels") or ["Unknown"]
        b_labels = row.get("b_labels") or ["Unknown"]

        a_id = a.get("person_id") or a.get("object_id") or a.get("location_id") or a.get("event_id")
        b_id = b.get("person_id") or b.get("object_id") or b.get("location_id") or b.get("event_id")
        if a_id is None or b_id is None:
            continue

        a_id, b_id = str(a_id), str(b_id)
        nodes[a_id] = {
            "id": a_id,
            "label": a.get("name") or a.get("description") or a_id,
            "type": a_labels[0],
            "confidence": float(a.get("confidence", 1.0)),
        }
        nodes[b_id] = {
            "id": b_id,
            "label": b.get("name") or b.get("description") or b_id,
            "type": b_labels[0],
            "confidence": float(b.get("confidence", 1.0)),
        }
        links.append({
            "source": a_id,
            "target": b_id,
            "relationship": row.get("relationship") or "RELATED",
            "confidence": float(r.get("confidence", 1.0)),
            "evidence_hash": r.get("evidence_hash"),
        })

    return {"nodes": list(nodes.values()), "links": links}


# --------------------------------------------------------------------------
# GRAPH ANALYTICS (Neo4j GDS)
# --------------------------------------------------------------------------
@app.get("/analytics/betweenness")
async def get_betweenness():
    """Ranked money-mule / bagman candidates by betweenness centrality."""
    db = get_db()
    try:
        return {"results": run_betweenness_centrality(db)}
    except Exception as exc:
        raise HTTPException(500, f"GDS betweenness computation failed: {exc}")


@app.get("/analytics/louvain")
async def get_louvain():
    """Detected syndicate/cell clusters via Louvain community detection."""
    db = get_db()
    try:
        return {"results": run_louvain_communities(db)}
    except Exception as exc:
        raise HTTPException(500, f"GDS Louvain computation failed: {exc}")


# --------------------------------------------------------------------------
# WHAT-IF DISRUPTION SIMULATION
# --------------------------------------------------------------------------
@app.post("/simulate-disruption/{node_id}")
async def simulate_disruption(node_id: str):
    """
    Temporarily removes a node from an IN-MEMORY graph projection only
    (the persisted Neo4j graph is never altered) and returns fragmentation
    metrics comparing before/after network topology. Powers the
    "Simulate Node Disruption" button on the Right Panel.
    """
    db = get_db()
    try:
        return simulate_node_disruption(db, node_id)
    except Exception as exc:
        raise HTTPException(500, f"Disruption simulation failed: {exc}")


# --------------------------------------------------------------------------
# BSA SECTION 63 EVIDENTIARY DOSSIER
# --------------------------------------------------------------------------
@app.get("/dossier")
async def get_dossier():
    """
    Every relationship in the graph with its SHA-256 evidence hash,
    confidence, source document, and timestamp - the data behind the
    frontend's Evidentiary Dossier component, ready to be exported/printed
    as an annexure to a BSA Section 63 certificate.
    """
    db = get_db()
    return {"dossier_entries": db.get_dossier_edges()}


# --------------------------------------------------------------------------
# HEALTH
# --------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "cnas-backend"}
