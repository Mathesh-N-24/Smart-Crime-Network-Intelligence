"""
graph_analytics.py
============================================================================
Neo4j Graph Data Science (GDS) analytics layer.

Two core algorithms drive the investigative value of this platform:

1. BETWEENNESS CENTRALITY
   Identifies nodes that sit on the most shortest-paths between other
   nodes - operationally, these are the "money mules" / "bagmen" / cutouts
   who bridge otherwise-disconnected parts of a syndicate (e.g. the person
   who physically carries cash between two cells that never communicate
   directly). High betweenness + low degree is a classic mule signature.

2. LOUVAIN COMMUNITY DETECTION
   Partitions the graph into densely-connected clusters - operationally,
   these correspond to distinct syndicates/cells/modules of a larger
   network, letting an analyst see "this is actually 3 separate gangs
   sharing 2 common financiers" instead of one undifferentiated blob.

Both use Neo4j GDS's in-memory graph projection so the underlying stored
graph is never mutated by analysis - a hard requirement for evidentiary
integrity (analytics must never alter source-of-truth data).
============================================================================
"""

from typing import Dict, List
from database import Neo4jConnection

PROJECTED_GRAPH_NAME = "cnas_graph"


def _ensure_projection(db: Neo4jConnection, exclude_node_id: str = None):
    """
    Create (or refresh) the in-memory GDS graph projection.
    `exclude_node_id` supports the What-If disruption simulation by
    projecting the network with a specific node's relationships removed,
    without touching the persisted Neo4j graph.
    """
    # Drop any stale projection first (GDS projections are named + cached).
    db.run(f"""
        CALL gds.graph.exists('{PROJECTED_GRAPH_NAME}') YIELD exists
        WHERE exists
        CALL gds.graph.drop('{PROJECTED_GRAPH_NAME}') YIELD graphName
        RETURN graphName
    """)

    if exclude_node_id:
        # Projection query that filters out the disrupted node entirely -
        # this is the "temporarily remove a node in memory" simulation.
        node_query = f"""
            MATCH (n)
            WHERE NOT coalesce(n.person_id, n.object_id, n.location_id, n.event_id) = '{exclude_node_id}'
            RETURN id(n) AS id
        """
        rel_query = f"""
            MATCH (a)-[r]->(b)
            WHERE NOT coalesce(a.person_id, a.object_id, a.location_id, a.event_id) = '{exclude_node_id}'
              AND NOT coalesce(b.person_id, b.object_id, b.location_id, b.event_id) = '{exclude_node_id}'
            RETURN id(a) AS source, id(b) AS target
        """
        db.run(f"""
            CALL gds.graph.project.cypher(
                '{PROJECTED_GRAPH_NAME}',
                "{node_query}",
                "{rel_query}"
            )
        """)
    else:
        db.run(f"""
            CALL gds.graph.project(
                '{PROJECTED_GRAPH_NAME}',
                ['Person', 'Object', 'Location', 'Event'],
                {{
                    ASSOCIATED_WITH: {{orientation: 'UNDIRECTED'}},
                    TRANSFERRED_FUNDS: {{orientation: 'NATURAL'}},
                    COMMUNICATED_WITH: {{orientation: 'UNDIRECTED'}},
                    PRESENT_AT: {{orientation: 'NATURAL'}},
                    PARTICIPATED_IN: {{orientation: 'NATURAL'}},
                    OWNS: {{orientation: 'NATURAL'}}
                }}
            )
        """)


# ----------------------------------------------------------------------
# 1. BETWEENNESS CENTRALITY -> money mule / bagman identification
# ----------------------------------------------------------------------
BETWEENNESS_QUERY = f"""
CALL gds.betweenness.stream('{PROJECTED_GRAPH_NAME}')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS node, score
RETURN
    coalesce(node.person_id, node.object_id, node.location_id, node.event_id) AS node_id,
    coalesce(node.name, node.description) AS label,
    labels(node)[0] AS node_type,
    score AS betweenness_score
ORDER BY betweenness_score DESC
LIMIT 25
"""


def run_betweenness_centrality(db: Neo4jConnection) -> List[Dict]:
    """
    Nodes ranked highest here, despite often having few direct
    connections (low degree), are the highest-value targets for
    surveillance/interdiction: removing them fragments communication or
    financial flow between otherwise-isolated cells.
    """
    _ensure_projection(db)
    return db.run(BETWEENNESS_QUERY)


# ----------------------------------------------------------------------
# 2. LOUVAIN COMMUNITY DETECTION -> syndicate / cell clustering
# ----------------------------------------------------------------------
LOUVAIN_QUERY = f"""
CALL gds.louvain.stream('{PROJECTED_GRAPH_NAME}')
YIELD nodeId, communityId
WITH gds.util.asNode(nodeId) AS node, communityId
RETURN
    communityId,
    coalesce(node.person_id, node.object_id, node.location_id, node.event_id) AS node_id,
    coalesce(node.name, node.description) AS label,
    labels(node)[0] AS node_type
ORDER BY communityId, label
"""


def run_louvain_communities(db: Neo4jConnection) -> List[Dict]:
    """
    Groups nodes into their detected syndicate/cluster. Frontend colors
    graph nodes by communityId so an analyst visually sees cell boundaries.
    """
    _ensure_projection(db)
    return db.run(LOUVAIN_QUERY)


# ----------------------------------------------------------------------
# WHAT-IF DISRUPTION SIMULATION
# ----------------------------------------------------------------------
def simulate_node_disruption(db: Neo4jConnection, node_id: str) -> Dict:
    """
    Projects the graph EXCLUDING the given node (in-memory only - the
    persisted graph in Neo4j is never modified), then recomputes topology
    metrics to answer: "If we arrest/interdict this person tonight, does
    the network actually fragment, or does it route around them?"

    Returns before/after community counts and the largest remaining
    connected component size, which is the operational signal analysts
    care about (does disruption meaningfully break the network apart).
    """
    # --- BEFORE metrics (full network) ---
    _ensure_projection(db)
    before_communities = db.run(f"""
        CALL gds.louvain.stats('{PROJECTED_GRAPH_NAME}')
        YIELD communityCount, modularity
        RETURN communityCount, modularity
    """)
    before_wcc = db.run(f"""
        CALL gds.wcc.stats('{PROJECTED_GRAPH_NAME}')
        YIELD componentCount
        RETURN componentCount
    """)
    before_largest = db.run(f"""
        CALL gds.wcc.stream('{PROJECTED_GRAPH_NAME}')
        YIELD nodeId, componentId
        RETURN componentId, count(*) AS size
        ORDER BY size DESC LIMIT 1
    """)

    # --- AFTER metrics (node excluded from projection) ---
    _ensure_projection(db, exclude_node_id=node_id)
    after_communities = db.run(f"""
        CALL gds.louvain.stats('{PROJECTED_GRAPH_NAME}')
        YIELD communityCount, modularity
        RETURN communityCount, modularity
    """)
    after_wcc = db.run(f"""
        CALL gds.wcc.stats('{PROJECTED_GRAPH_NAME}')
        YIELD componentCount
        RETURN componentCount
    """)
    after_largest = db.run(f"""
        CALL gds.wcc.stream('{PROJECTED_GRAPH_NAME}')
        YIELD nodeId, componentId
        RETURN componentId, count(*) AS size
        ORDER BY size DESC LIMIT 1
    """)

    # Clean up the in-memory projection so it doesn't linger and consume
    # laptop-scale RAM across repeated simulations.
    db.run(f"""
        CALL gds.graph.exists('{PROJECTED_GRAPH_NAME}') YIELD exists
        WHERE exists
        CALL gds.graph.drop('{PROJECTED_GRAPH_NAME}') YIELD graphName
        RETURN graphName
    """)

    before_frag = before_wcc[0]["componentCount"] if before_wcc else 0
    after_frag = after_wcc[0]["componentCount"] if after_wcc else 0

    return {
        "disrupted_node_id": node_id,
        "before": {
            "connected_components": before_frag,
            "community_count": before_communities[0]["communityCount"] if before_communities else 0,
            "modularity": before_communities[0]["modularity"] if before_communities else 0,
            "largest_component_size": before_largest[0]["size"] if before_largest else 0,
        },
        "after": {
            "connected_components": after_frag,
            "community_count": after_communities[0]["communityCount"] if after_communities else 0,
            "modularity": after_communities[0]["modularity"] if after_communities else 0,
            "largest_component_size": after_largest[0]["size"] if after_largest else 0,
        },
        "fragmentation_delta": after_frag - before_frag,
        "operational_assessment": (
            "HIGH IMPACT: network fragments into more isolated components."
            if after_frag > before_frag else
            "LOW IMPACT: network remains connected via alternate paths - "
            "consider targeting a higher-betweenness node instead."
        ),
    }
