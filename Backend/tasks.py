"""
tasks.py
============================================================================
Async AI processing pipeline, executed by Celery workers.

Pipeline stages for an uploaded FIR (scanned document) or CDR (call detail
record spreadsheet / intercept audio):

  1. run_paddleocr()               - OCR scanned FIR pages to raw text
  2. run_whisper_transcription()   - ASR on intercepted call audio
  3. extract_entities_indicbert()  - NER over the text -> POLE entities
  4. phonetic aliasing              - Double Metaphone code per person name,
                                       so "Rauf"/"Rouf"/"Raouf" resolve together
  5. push_to_graph()                - MERGE nodes + evidence-hashed edges into
                                       Neo4j via database.py

MOCKING NOTE:
This prototype mocks stages 1-3 with deterministic stub functions that
return realistic-shaped output, instead of loading real PaddleOCR /
Faster-Whisper / IndicBERT model weights. This keeps the container small
and the demo runnable on a laptop with no GPU and no internet access.
The function signatures and return shapes match what the real libraries
would produce, so swapping in real inference later is a drop-in change
(see the commented "REAL IMPLEMENTATION" blocks under each mock).
============================================================================
"""

import os
import uuid
import random
from typing import Dict, List

from metaphone import doublemetaphone

from celery_app import celery_app
from database import get_db
from security import sha256_file, hash_edge, generate_custody_record


# ==========================================================================
# STAGE 1: OCR (mocked)
# ==========================================================================
def run_paddleocr(file_path: str) -> str:
    """
    MOCK: Simulates PaddleOCR output for a scanned FIR page.
    Returns extracted raw text as PaddleOCR's recognition stage would.

    REAL IMPLEMENTATION (production, GPU workstation, offline model cache):
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang='en',
                         det_model_dir='/models/paddle/det',
                         rec_model_dir='/models/paddle/rec')
        result = ocr.ocr(file_path, cls=True)
        return "\n".join([line[1][0] for page in result for line in page])
    """
    # Deterministic mock FIR narrative for demo purposes.
    return (
        "FIR No. 0142/2026, PS Andheri. Complainant states accused "
        "Shaikh Rauf @ Bhai Rauf, along with associate Imran Sheikh, "
        "conspired to transfer illicit funds amounting to Rs. 4,50,000 "
        "via UPI ID rauf.traders@upi to account held by Vikram Nair. "
        "Meeting reportedly took place at Marol Naka on 12-08-2026. "
        "Vehicle MH-02-AB-1234 was used to transport cash."
    )


# ==========================================================================
# STAGE 2: ASR / Transcription (mocked)
# ==========================================================================
def run_whisper_transcription(audio_path: str) -> str:
    """
    MOCK: Simulates faster-whisper transcription of an intercepted call
    recording (a common CDR-adjacent evidence type).

    REAL IMPLEMENTATION:
        from faster_whisper import WhisperModel
        model = WhisperModel("medium", device="cpu", compute_type="int8",
                              download_root="/models/whisper")
        segments, info = model.transcribe(audio_path, language="hi")
        return " ".join([seg.text for seg in segments])
    """
    return (
        "Bhai Rauf yahan bol raha hoon. Vikram ko bolo paisa "
        "kal tak Marol wale account mein transfer kar de. "
        "Imran ko bhi is baare mein pata hai."
    )


# ==========================================================================
# STAGE 3: NER - IndicBERT entity extraction (mocked)
# ==========================================================================
def extract_entities_indicbert(text: str) -> Dict[str, List[Dict]]:
    """
    MOCK: Simulates a fine-tuned IndicBERT NER model extracting POLE
    entities from OCR/ASR text (which is frequently code-mixed
    Hindi/Urdu/English, hence IndicBERT rather than a purely English NER).

    REAL IMPLEMENTATION:
        from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
        tokenizer = AutoTokenizer.from_pretrained("/models/indicbert-ner")
        model = AutoModelForTokenClassification.from_pretrained("/models/indicbert-ner")
        ner = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")
        raw_entities = ner(text)
        # ... map raw_entities into the POLE-typed shape below ...

    Returns entities keyed by POLE type, each carrying a mock confidence
    score in [0.75, 0.98] as a real model's softmax certainty would.
    """
    def conf():
        return round(random.uniform(0.75, 0.98), 2)

    persons = [
        {"name": "Shaikh Rauf", "aliases": ["Bhai Rauf"], "confidence": conf()},
        {"name": "Imran Sheikh", "aliases": [], "confidence": conf()},
        {"name": "Vikram Nair", "aliases": [], "confidence": conf()},
    ]
    objects = [
        {"object_type": "UPI_ID", "description": "rauf.traders@upi", "confidence": conf()},
        {"object_type": "VEHICLE", "description": "MH-02-AB-1234", "confidence": conf()},
        {"object_type": "BANK_ACCOUNT", "description": "Vikram Nair - linked account", "confidence": conf()},
    ]
    locations = [
        {"name": "Marol Naka", "lat": 19.1197, "lon": 72.8797, "confidence": conf()},
        {"name": "PS Andheri", "lat": 19.1136, "lon": 72.8697, "confidence": conf()},
    ]
    events = [
        {"event_type": "FUNDS_TRANSFER", "timestamp": "2026-08-12T00:00:00Z",
         "description": "Rs. 4,50,000 transferred via UPI", "confidence": conf()},
        {"event_type": "MEETING", "timestamp": "2026-08-12T00:00:00Z",
         "description": "In-person meeting at Marol Naka", "confidence": conf()},
    ]

    # Relationships the NER/relation-extraction step asserts between entities.
    relationships = [
        {"source": "Shaikh Rauf", "target": "Imran Sheikh", "type": "ASSOCIATED_WITH", "confidence": conf()},
        {"source": "Shaikh Rauf", "target": "Vikram Nair", "type": "TRANSFERRED_FUNDS", "confidence": conf()},
        {"source": "Shaikh Rauf", "target": "Marol Naka", "type": "PRESENT_AT", "confidence": conf()},
        {"source": "Imran Sheikh", "target": "Marol Naka", "type": "PRESENT_AT", "confidence": conf()},
    ]

    return {
        "persons": persons, "objects": objects,
        "locations": locations, "events": events,
        "relationships": relationships,
    }


# ==========================================================================
# STAGE 4: Phonetic aliasing (real logic - Double Metaphone)
# ==========================================================================
def compute_phonetic_alias(name: str) -> str:
    """
    Double Metaphone encoding, used for cross-document entity resolution
    of transliterated South Asian names where spelling varies wildly
    across FIRs, CDR subscriber records, and informant statements
    (e.g. "Shaikh"/"Sheikh"/"Shekh"/"Shaik" all encode similarly).
    Returns the primary code; the secondary code is available for
    looser matching if the primary yields no hits.
    """
    primary, _secondary = doublemetaphone(name)
    return primary


# ==========================================================================
# STAGE 5: Graph ingestion with evidentiary hashing
# ==========================================================================
def push_to_graph(entities: Dict, source_doc_id: str, source_file_hash: str) -> Dict:
    """
    Writes all extracted POLE entities and evidence-hashed relationships
    into Neo4j. Every node gets a deterministic ID (uuid5 keyed on name so
    re-running ingestion on the same document is idempotent); every edge
    gets a SHA-256 evidence_hash tying it back to the specific fact
    asserted, per security.py.
    """
    db = get_db()
    name_to_id = {}

    for p in entities["persons"]:
        pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, p["name"]))
        name_to_id[p["name"]] = ("Person", pid)
        db.merge_person(
            person_id=pid, name=p["name"], aliases=p["aliases"],
            phonetic_code=compute_phonetic_alias(p["name"]),
            confidence=p["confidence"], source_doc_id=source_doc_id,
        )

    for o in entities["objects"]:
        oid = str(uuid.uuid5(uuid.NAMESPACE_DNS, o["description"]))
        name_to_id[o["description"]] = ("Object", oid)
        db.merge_object(
            object_id=oid, object_type=o["object_type"],
            description=o["description"], confidence=o["confidence"],
            source_doc_id=source_doc_id,
        )

    for l in entities["locations"]:
        lid = str(uuid.uuid5(uuid.NAMESPACE_DNS, l["name"]))
        name_to_id[l["name"]] = ("Location", lid)
        db.merge_location(
            location_id=lid, name=l["name"], lat=l.get("lat"), lon=l.get("lon"),
            source_doc_id=source_doc_id,
        )

    for e in entities["events"]:
        eid = str(uuid.uuid5(uuid.NAMESPACE_DNS, e["description"]))
        name_to_id[e["description"]] = ("Event", eid)
        db.merge_event(
            event_id=eid, event_type=e["event_type"], timestamp=e["timestamp"],
            description=e["description"], source_doc_id=source_doc_id,
        )

    edges_created = []
    for rel in entities["relationships"]:
        src_label, src_id = name_to_id.get(rel["source"], (None, None))
        tgt_label, tgt_id = name_to_id.get(rel["target"], (None, None))
        if not src_id or not tgt_id:
            continue  # entity wasn't resolved this pass; skip defensively

        evidence_hash = hash_edge(src_id, tgt_id, rel["type"], {"confidence": rel["confidence"]})
        custody_record = generate_custody_record(
            entity_hash=evidence_hash, source_file_hash=source_file_hash,
            extraction_method="extract_entities_indicbert_v1",
        )

        db.create_relationship(
            source_id=src_id, source_label=src_label,
            target_id=tgt_id, target_label=tgt_label,
            rel_type=rel["type"], evidence_hash=evidence_hash,
            confidence=rel["confidence"], source_doc_id=source_doc_id,
            extra_props={"custody_timestamp": custody_record["timestamp_utc"]},
        )
        edges_created.append({"relationship": rel["type"], "evidence_hash": evidence_hash})

    return {"nodes_created": len(name_to_id), "edges_created": edges_created}


# ==========================================================================
# CELERY TASK: full pipeline orchestration
# ==========================================================================
@celery_app.task(bind=True, name="tasks.process_document")
def process_document(self, file_path: str, doc_type: str, source_doc_id: str):
    """
    Entry point enqueued by POST /ingest in main.py.

    doc_type: "fir_scan" | "cdr_audio" | "cdr_text"

    Every step is logged into task metadata so the frontend's task-status
    polling can show a live pipeline progress indicator on the Left Panel.
    """
    self.update_state(state="PROGRESS", meta={"stage": "hashing_source"})
    source_file_hash = sha256_file(file_path)

    self.update_state(state="PROGRESS", meta={"stage": "extraction"})
    if doc_type == "fir_scan":
        raw_text = run_paddleocr(file_path)
    elif doc_type == "cdr_audio":
        raw_text = run_whisper_transcription(file_path)
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()

    self.update_state(state="PROGRESS", meta={"stage": "ner_extraction"})
    entities = extract_entities_indicbert(raw_text)

    self.update_state(state="PROGRESS", meta={"stage": "graph_ingestion"})
    ingestion_result = push_to_graph(entities, source_doc_id, source_file_hash)

    return {
        "source_doc_id": source_doc_id,
        "source_file_hash": source_file_hash,
        "raw_text_preview": raw_text[:280],
        "entities_extracted": {
            "persons": len(entities["persons"]),
            "objects": len(entities["objects"]),
            "locations": len(entities["locations"]),
            "events": len(entities["events"]),
        },
        "graph_ingestion": ingestion_result,
        "status": "COMPLETE",
    }
