"use client";

// ============================================================================
// SuspectProfile.tsx
// Right Panel: selected-node detail, GDS centrality/community scores, and
// the "Simulate Node Disruption" What-If action - the primary decision
// support tool for planning arrests/interdictions.
// ============================================================================

import { useEffect, useState } from "react";
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type SelectedNode = { id: string; label: string; type: string; confidence: number } | null;

export default function SuspectProfile({ selectedNode }: { selectedNode: SelectedNode }) {
  const [betweenness, setBetweenness] = useState<any[]>([]);
  const [louvain, setLouvain] = useState<any[]>([]);
  const [simResult, setSimResult] = useState<any>(null);
  const [simulating, setSimulating] = useState(false);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  async function fetchAnalytics() {
    try {
      const [bwRes, lvRes] = await Promise.all([
        axios.get(`${API_BASE}/analytics/betweenness`),
        axios.get(`${API_BASE}/analytics/louvain`),
      ]);
      setBetweenness(bwRes.data.results || []);
      setLouvain(lvRes.data.results || []);
    } catch {
      // GDS may not be ready yet on first boot before any data is ingested.
    }
  }

  async function runDisruptionSimulation() {
    if (!selectedNode) return;
    setSimulating(true);
    setSimResult(null);
    try {
      const res = await axios.post(`${API_BASE}/simulate-disruption/${selectedNode.id}`);
      setSimResult(res.data);
    } catch {
      setSimResult({ operational_assessment: "Simulation failed - check backend/GDS status." });
    } finally {
      setSimulating(false);
    }
  }

  const selectedBetweenness = betweenness.find((b) => b.node_id === selectedNode?.id);
  const selectedCommunity = louvain.find((l) => l.node_id === selectedNode?.id);

  return (
    <div className="flex flex-col h-full p-4 gap-5 bg-tactical-panel border-l border-tactical-border overflow-y-auto">
      <div>
        <h2 className="text-tactical-accent text-xs tracking-widest uppercase mb-3">
          Suspect / Entity Profile
        </h2>
        {selectedNode ? (
          <div className="space-y-1.5 text-sm">
            <p><span className="text-tactical-muted">Name:</span> {selectedNode.label}</p>
            <p><span className="text-tactical-muted">Type:</span> {selectedNode.type}</p>
            <p><span className="text-tactical-muted">Entity ID:</span>{" "}
              <span className="text-[11px] break-all">{selectedNode.id}</span>
            </p>
            <p><span className="text-tactical-muted">AI Confidence:</span>{" "}
              {Math.round(selectedNode.confidence * 100)}%
            </p>
            <p><span className="text-tactical-muted">Betweenness Score:</span>{" "}
              {selectedBetweenness ? selectedBetweenness.betweenness_score.toFixed(2) : "—"}
            </p>
            <p><span className="text-tactical-muted">Community / Syndicate ID:</span>{" "}
              {selectedCommunity ? selectedCommunity.communityId : "—"}
            </p>
          </div>
        ) : (
          <p className="text-xs text-tactical-muted">Click a node on the graph canvas to inspect.</p>
        )}
      </div>

      <div>
        <h2 className="text-tactical-accent text-xs tracking-widest uppercase mb-2">
          Top Betweenness (Bagman Candidates)
        </h2>
        <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
          {betweenness.slice(0, 8).map((b) => (
            <div key={b.node_id} className="flex justify-between text-[11px]">
              <span className="truncate">{b.label}</span>
              <span className="text-tactical-amber">{b.betweenness_score.toFixed(1)}</span>
            </div>
          ))}
          {betweenness.length === 0 && (
            <p className="text-[11px] text-tactical-muted">No data yet - ingest evidence first.</p>
          )}
        </div>
      </div>

      <div>
        <h2 className="text-tactical-accent text-xs tracking-widest uppercase mb-2">
          What-If: Node Disruption
        </h2>
        <button
          onClick={runDisruptionSimulation}
          disabled={!selectedNode || simulating}
          className="w-full bg-tactical-red/10 border border-tactical-red text-tactical-red text-xs uppercase tracking-wider py-2 rounded hover:bg-tactical-red/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          {simulating ? "Simulating..." : "Simulate Removal of Selected Node"}
        </button>

        {simResult && (
          <div className="mt-3 text-[11px] space-y-1 border border-tactical-border rounded p-2 bg-tactical-bg">
            <p className="text-tactical-muted">
              Components: {simResult.before?.connected_components} → {simResult.after?.connected_components}
            </p>
            <p className="text-tactical-muted">
              Largest cluster: {simResult.before?.largest_component_size} → {simResult.after?.largest_component_size}
            </p>
            <p className={simResult.fragmentation_delta > 0 ? "text-tactical-accent" : "text-tactical-amber"}>
              {simResult.operational_assessment}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
