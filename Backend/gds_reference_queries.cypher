// ============================================================================
// gds_reference_queries.cypher
// Standalone reference file: the raw Cypher/GDS queries used by
// graph_analytics.py, provided here so an analyst can run them directly
// in the Neo4j Browser (http://localhost:7474) for ad-hoc investigation
// without going through the API.
// ============================================================================

// ----------------------------------------------------------------------
// 0. PROJECT THE IN-MEMORY GRAPH (required before any GDS algorithm)
// ----------------------------------------------------------------------
CALL gds.graph.project(
    'cnas_graph',
    ['Person', 'Object', 'Location', 'Event'],
    {
        ASSOCIATED_WITH:   {orientation: 'UNDIRECTED'},
        TRANSFERRED_FUNDS: {orientation: 'NATURAL'},
        COMMUNICATED_WITH: {orientation: 'UNDIRECTED'},
        PRESENT_AT:        {orientation: 'NATURAL'},
        PARTICIPATED_IN:   {orientation: 'NATURAL'},
        OWNS:              {orientation: 'NATURAL'}
    }
);

// ----------------------------------------------------------------------
// 1. BETWEENNESS CENTRALITY - identify money mules / bagmen / cutouts
// High score + low degree = classic mule signature (bridges cells that
// never talk directly).
// ----------------------------------------------------------------------
CALL gds.betweenness.stream('cnas_graph')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS node, score
RETURN
    coalesce(node.person_id, node.object_id, node.location_id, node.event_id) AS node_id,
    coalesce(node.name, node.description) AS label,
    labels(node)[0] AS node_type,
    score AS betweenness_score
ORDER BY betweenness_score DESC
LIMIT 25;

// ----------------------------------------------------------------------
// 2. LOUVAIN COMMUNITY DETECTION - cluster into syndicates/cells
// ----------------------------------------------------------------------
CALL gds.louvain.stream('cnas_graph')
YIELD nodeId, communityId
WITH gds.util.asNode(nodeId) AS node, communityId
RETURN
    communityId,
    coalesce(node.person_id, node.object_id, node.location_id, node.event_id) AS node_id,
    coalesce(node.name, node.description) AS label,
    labels(node)[0] AS node_type
ORDER BY communityId, label;

// Aggregate view: syndicate sizes, useful for triage of which cluster to
// investigate first.
CALL gds.louvain.stream('cnas_graph')
YIELD nodeId, communityId
RETURN communityId, count(*) AS syndicate_size
ORDER BY syndicate_size DESC;

// ----------------------------------------------------------------------
// 3. WEAKLY CONNECTED COMPONENTS - overall network fragmentation metric
// Used before/after disruption simulation to measure structural impact.
// ----------------------------------------------------------------------
CALL gds.wcc.stats('cnas_graph')
YIELD componentCount;

// ----------------------------------------------------------------------
// 4. DEGREE CENTRALITY - simple "who has the most direct contacts" view,
// useful as a cross-check against betweenness (hubs vs. bridges are
// operationally different: hubs are often visible/known; bridges are not).
// ----------------------------------------------------------------------
CALL gds.degree.stream('cnas_graph')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS node, score
RETURN
    coalesce(node.name, node.description) AS label,
    labels(node)[0] AS node_type,
    score AS degree
ORDER BY degree DESC
LIMIT 25;

// ----------------------------------------------------------------------
// 5. CLEAN UP - drop the in-memory projection when done to free RAM
// (important on laptop-class hardware).
// ----------------------------------------------------------------------
CALL gds.graph.drop('cnas_graph');
