"""
security.py
============================================================================
Evidentiary integrity layer.

Bharatiya Sakshya Adhiniyam (BSA), 2023 - Section 63 governs admissibility
of "electronic records" as documentary evidence. In practice this requires
the prosecution to produce a certificate identifying the device/process
that produced the record and attesting to its integrity (analogous to the
old IT Act S.65B certificate regime).

This module gives the platform a verifiable, tamper-evident chain of
custody by SHA-256 hashing:
  1. Every raw uploaded file at ingestion time (before any AI processing
     touches it) -> proves what was originally submitted.
  2. Every derived graph edge (relationship) the AI pipeline asserts
     -> proves which specific extraction produced which specific claim,
        and lets an analyst / court reproduce and verify it independently.

Hashes are computed on canonicalized data (sorted JSON keys, fixed
separators) so the same logical fact always hashes identically regardless
of dict ordering - required for verification and Section 63 certification.
============================================================================
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict


def sha256_file(file_path: str) -> str:
    """
    Compute the SHA-256 digest of a file on disk, streaming in chunks so
    large CDR dumps / video evidence don't blow up laptop-scale RAM.

    This hash is what goes into the BSA S.63 certificate as the
    "hash value of the electronic record" at the point of seizure/upload.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Hash raw bytes directly (used for in-memory uploads before flush)."""
    return hashlib.sha256(data).hexdigest()


def _canonicalize(obj: Dict[str, Any]) -> str:
    """
    Deterministic JSON serialization: sorted keys, no whitespace ambiguity.
    Guarantees that hashing the "same" edge/fact always yields the same
    digest, which is essential for independent verification in court.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def hash_edge(source_id: str, target_id: str, relationship_type: str,
              properties: Dict[str, Any] | None = None) -> str:
    """
    Generate a SHA-256 hash for a single extracted relationship (graph edge)
    asserted by the AI pipeline, e.g. (Person A)-[TRANSFERRED_FUNDS]->(Person B).

    This hash becomes an immutable property on the edge itself in Neo4j,
    so any later tampering with the edge's properties changes the hash and
    is immediately detectable during an audit / evidentiary review.
    """
    canonical_payload = {
        "source_id": source_id,
        "target_id": target_id,
        "relationship_type": relationship_type,
        "properties": properties or {},
    }
    return hashlib.sha256(_canonicalize(canonical_payload).encode("utf-8")).hexdigest()


def generate_custody_record(entity_hash: str, source_file_hash: str,
                             extraction_method: str, analyst_id: str = "SYSTEM_AI_PIPELINE"
                             ) -> Dict[str, Any]:
    """
    Build a full chain-of-custody record for a single extracted fact
    (node or edge), suitable for attachment to a BSA Section 63 certificate.

    Fields map to what a S.63 certificate typically must state:
      - identity of the device/process (extraction_method)
      - the record's hash at the time of production
      - the source record it was derived from (traceability)
      - a timestamp (UTC, ISO-8601) for the timeline of events
    """
    return {
        "entity_hash": entity_hash,
        "derived_from_source_hash": source_file_hash,
        "extraction_method": extraction_method,
        "certifying_process": analyst_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "compliance_tag": "BSA_2023_SECTION_63",
    }


def verify_integrity(file_path: str, expected_hash: str) -> bool:
    """
    Re-hash a file on disk and compare against a previously recorded hash.
    Used at any point in the workflow (e.g. before re-running analytics,
    or when a defense counsel disputes a piece of evidence) to prove the
    underlying file has not been altered since ingestion.
    """
    return sha256_file(file_path) == expected_hash
