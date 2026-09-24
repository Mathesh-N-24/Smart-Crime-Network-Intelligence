"""
database.py
============================================================================
Neo4j access layer implementing the POLE data model
(Person, Object, Location, Event) - the standard entity model used across
UK/EU/Indian law-enforcement intelligence systems (e.g. i2 Analyst's
Notebook, Palantir Gotham use variants of the same model).

Design principles applied here:
  - MERGE (not CREATE) everywhere -> idempotent ingestion. Re-processing
    the same FIR/CDR twice never creates duplicate nodes; it strengthens
    confidence on the existing ones instead. This matters operationally
    because the same suspect appears across dozens of case files.
  - Every relationship carries `evidence_hash`, `confidence`, and
    `source_document_id` properties -> every edge in the graph is
    traceable back to a specific, hash-verified piece of evidence
    (supports BSA Section 63 auditability end-to-end, not just at upload).
  - Constraints on unique IDs enforce entity resolution correctness.
============================================================================
"""

import os
from typing import Any, Dict, List, Optional
from neo4j import GraphDatabase, basic_auth


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "cnas_secure_pass123")


class Neo4jConnection:
    """Thin wrapper around the official driver, reused across the app/worker."""

    def __init__(self):
        self._driver = GraphDatabase.driver(
            NEO4J_URI, auth=basic_auth(NEO4J_USER, NEO4J_PASSWORD)
        )

    def close(self):
        self._driver.close()

    def run(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict]:
        with self._driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

    # ------------------------------------------------------------------
    # SCHEMA SETUP
    # ------------------------------------------------------------------
    def init_constraints(self):
        """
        Uniqueness constraints for each POLE type. Run once at startup.
        Prevents entity duplication which would otherwise silently corrupt
        centrality/community-detection results downstream.
        """
        constraints = [
            "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.person_id IS UNIQUE",
            "CREATE CONSTRAINT object_id IF NOT EXISTS FOR (o:Object) REQUIRE o.object_id IS UNIQUE",
            "CREATE CONSTRAINT location_id IF NOT EXISTS FOR (l:Location) REQUIRE l.location_id IS UNIQUE",
            "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.event_id IS UNIQUE",
        ]
        for c in constraints:
            self.run(c)

    # ------------------------------------------------------------------
    # POLE NODE MERGES
    # ------------------------------------------------------------------
    def merge_person(self, person_id: str, name: str, aliases: List[str],
                      phonetic_code: str, confidence: float, source_doc_id: str) -> Dict:
        """
        Upsert a Person node. `phonetic_code` (Double Metaphone) allows
        later fuzzy-matching two spellings of the same name (e.g.
        "Shaikh Rauf" vs "Sheikh Rouf") onto one node during resolution.
        """
        query = """
        MERGE (p:Person {person_id: $person_id})
        ON CREATE SET
            p.name = $name,
            p.aliases = $aliases,
            p.phonetic_code = $phonetic_code,
            p.confidence = $confidence,
            p.first_seen_source = $source_doc_id,
            p.created_at = datetime()
        ON MATCH SET
            p.aliases = apoc.coll.toSet(coalesce(p.aliases, []) + $aliases),
            p.confidence = CASE WHEN $confidence > p.confidence THEN $confidence ELSE p.confidence END,
            p.last_updated = datetime()
        RETURN p
        """
        # NOTE: falls back gracefully if APOC isn't installed - see
        # merge_person_no_apoc below for the air-gapped-safe default path.
        try:
            return self.run(query, {
                "person_id": person_id, "name": name, "aliases": aliases,
                "phonetic_code": phonetic_code, "confidence": confidence,
                "source_doc_id": source_doc_id,
            })
        except Exception:
            return self.merge_person_no_apoc(
                person_id, name, aliases, phonetic_code, confidence, source_doc_id
            )

    def merge_person_no_apoc(self, person_id, name, aliases, phonetic_code,
                              confidence, source_doc_id) -> Dict:
        """APOC-free fallback (community Neo4j image ships without APOC by default)."""
        query = """
        MERGE (p:Person {person_id: $person_id})
        ON CREATE SET
            p.name = $name, p.aliases = $aliases, p.phonetic_code = $phonetic_code,
            p.confidence = $confidence, p.first_seen_source = $source_doc_id,
            p.created_at = datetime()
        ON MATCH SET
            p.confidence = CASE WHEN $confidence > p.confidence THEN $confidence ELSE p.confidence END,
            p.last_updated = datetime()
        RETURN p
        """
        return self.run(query, {
            "person_id": person_id, "name": name, "aliases": aliases,
            "phonetic_code": phonetic_code, "confidence": confidence,
            "source_doc_id": source_doc_id,
        })

    def merge_object(self, object_id: str, object_type: str, description: str,
                      confidence: float, source_doc_id: str) -> Dict:
        """Object = weapon, vehicle, bank account, SIM/IMEI, financial instrument, etc."""
        query = """
        MERGE (o:Object {object_id: $object_id})
        ON CREATE SET
            o.object_type = $object_type, o.description = $description,
            o.confidence = $confidence, o.first_seen_source = $source_doc_id,
            o.created_at = datetime()
        RETURN o
        """
        return self.run(query, {
            "object_id": object_id, "object_type": object_type,
            "description": description, "confidence": confidence,
            "source_doc_id": source_doc_id,
        })

    def merge_location(self, location_id: str, name: str, lat: Optional[float],
                        lon: Optional[float], source_doc_id: str) -> Dict:
        """Location = tower/cell ID, address, district, border checkpoint, etc."""
        query = """
        MERGE (l:Location {location_id: $location_id})
        ON CREATE SET
            l.name = $name, l.lat = $lat, l.lon = $lon,
            l.first_seen_source = $source_doc_id, l.created_at = datetime()
        RETURN l
        """
        return self.run(query, {
            "location_id": location_id, "name": name, "lat": lat, "lon": lon,
            "source_doc_id": source_doc_id,
        })

    def merge_event(self, event_id: str, event_type: str, timestamp: str,
                     description: str, source_doc_id: str) -> Dict:
        """Event = call, meeting, funds transfer, FIR-recorded incident, etc."""
        query = """
        MERGE (e:Event {event_id: $event_id})
        ON CREATE SET
            e.event_type = $event_type, e.timestamp = $timestamp,
            e.description = $description, e.first_seen_source = $source_doc_id,
            e.created_at = datetime()
        RETURN e
        """
        return self.run(query, {
            "event_id": event_id, "event_type": event_type, "timestamp": timestamp,
            "description": description, "source_doc_id": source_doc_id,
        })

    # ------------------------------------------------------------------
    # RELATIONSHIP CREATION (evidence-linked edges)
    # ------------------------------------------------------------------
    def create_relationship(self, source_id: str, source_label: str,
                             target_id: str, target_label: str,
                             rel_type: str, evidence_hash: str,
                             confidence: float, source_doc_id: str,
                             extra_props: Optional[Dict[str, Any]] = None) -> Dict:
        """
        Generic evidence-linked relationship creator. rel_type is
        parameterized safely via an allowlist (Cypher does not support
        parameterized relationship types directly).

        Common rel_types used across the platform:
          ASSOCIATED_WITH   - Person <-> Person, general link (co-accused, kin, gang)
          TRANSFERRED_FUNDS - Person -> Person / Object (financial flow, hawala, UPI)
          COMMUNICATED_WITH - Person <-> Person (CDR call/SMS linkage)
          PRESENT_AT        - Person -> Location (tower dump / travel record)
          PARTICIPATED_IN   - Person -> Event
          OWNS              - Person -> Object
        """
        allowed_rel_types = {
            "ASSOCIATED_WITH", "TRANSFERRED_FUNDS", "COMMUNICATED_WITH",
            "PRESENT_AT", "PARTICIPATED_IN", "OWNS",
        }
        if rel_type not in allowed_rel_types:
            raise ValueError(f"Unsupported relationship type: {rel_type}")

        props = extra_props or {}
        query = f"""
        MATCH (s:{source_label} {{{self._id_field(source_label)}: $source_id}})
        MATCH (t:{target_label} {{{self._id_field(target_label)}: $target_id}})
        MERGE (s)-[r:{rel_type}]->(t)
        ON CREATE SET
            r.evidence_hash = $evidence_hash,
            r.confidence = $confidence,
            r.source_document_id = $source_doc_id,
            r.created_at = datetime(),
            r += $extra_props
        RETURN type(r) AS relationship, s, t
        """
        return self.run(query, {
            "source_id": source_id, "target_id": target_id,
            "evidence_hash": evidence_hash, "confidence": confidence,
            "source_doc_id": source_doc_id, "extra_props": props,
        })

    @staticmethod
    def _id_field(label: str) -> str:
        return {
            "Person": "person_id", "Object": "object_id",
            "Location": "location_id", "Event": "event_id",
        }[label]

    # ------------------------------------------------------------------
    # QUERY / RETRIEVAL
    # ------------------------------------------------------------------
    def get_full_graph(self, min_confidence: float = 0.0, limit: int = 500) -> List[Dict]:
        """Return only JSON-serializable graph data.

        Never return Neo4j Node/Relationship objects to FastAPI.
        ``properties()`` converts them to plain dictionaries and
        ``type(r)`` gives the actual relationship type.
        """
        query = """
        MATCH (a)-[r]->(b)
        WHERE coalesce(r.confidence, 1.0) >= $min_confidence
        RETURN
            properties(a) AS a,
            properties(r) AS r,
            properties(b) AS b,
            labels(a) AS a_labels,
            labels(b) AS b_labels,
            type(r) AS relationship
        LIMIT $limit
        """
        return self.run(query, {"min_confidence": min_confidence, "limit": limit})

    def get_dossier_edges(self) -> List[Dict]:
        """
        Returns every relationship with its evidentiary metadata - powers
        the 'BSA Section 63 Evidentiary Dossier' panel on the frontend.
        """
        query = """
        MATCH (a)-[r]->(b)
        RETURN
            a.name AS source_name, coalesce(a.person_id, a.object_id, a.location_id, a.event_id) AS source_id,
            b.name AS target_name, coalesce(b.person_id, b.object_id, b.location_id, b.event_id) AS target_id,
            type(r) AS relationship_type,
            r.evidence_hash AS evidence_hash,
            r.confidence AS confidence,
            r.source_document_id AS source_document_id,
            toString(r.created_at) AS timestamp
        ORDER BY r.created_at DESC
        """
        return self.run(query)


# Singleton accessor used by FastAPI dependency injection and Celery tasks.
_connection: Optional[Neo4jConnection] = None


def get_db() -> Neo4jConnection:
    global _connection
    if _connection is None:
        _connection = Neo4jConnection()
        _connection.init_constraints()
    return _connection
