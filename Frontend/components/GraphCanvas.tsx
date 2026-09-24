"use client";

// ============================================================================
// GraphCanvas.tsx
// Center Canvas: interactive force-directed graph visualization.
// Uses react-force-graph-2d (Canvas-based, not WebGL/3D) specifically
// because it renders smoothly on integrated-GPU laptops - the 3D variant
// is unnecessary overhead for this use case and would hurt the
// "everyday laptop" performance requirement.
// ============================================================================

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import axios from "axios";

// Dynamically imported with ssr:false - force-graph relies on `window`
// and cannot be server-rendered by Next.js.
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const NODE_COLORS: Record<string, string> = {
  Person: "#39ff88",
  Object: "#ffb020",
  Location: "#4da6ff",
  Event: "#ff4d4d",
};

type GraphNode = { id: string; label: string; type: string; confidence: number };
type GraphLink = { source: string; target: string; relationship: string; confidence: number; evidence_hash: string };

type GraphCanvasProps = {
  minConfidence: number;
  refreshTrigger: number;
  onNodeSelect: (node: GraphNode | null) => void;
};

export default function GraphCanvas({ minConfidence, refreshTrigger, onNodeSelect }: GraphCanvasProps) {
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({
    nodes: [], links: [],
  });
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchGraph();
  }, [minConfidence, refreshTrigger]);

  async function fetchGraph() {
    try {
      const res = await axios.get(`${API_BASE}/graph`, { params: { min_confidence: minConfidence } });
      setGraphData(res.data);
    } catch {
      // Air-gapped demo fallback: keep last known graph rather than blanking
      // the canvas on a transient backend hiccup.
    }
  }

  return (
    <div ref={containerRef} className="relative flex-1 h-full bg-tactical-bg overflow-hidden">
      <div className="absolute top-3 left-3 z-10 text-[10px] text-tactical-muted uppercase tracking-widest">
        Network Topology &middot; {graphData.nodes.length} nodes &middot; {graphData.links.length} edges
      </div>

      <div className="absolute top-3 right-3 z-10 flex gap-3 text-[10px] text-tactical-muted">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
            {type}
          </div>
        ))}
      </div>

      <ForceGraph2D
        graphData={graphData as any}
        backgroundColor="#0a0e0f"
        nodeLabel={(n: any) => `${n.label} (${n.type}) — confidence ${Math.round(n.confidence * 100)}%`}
        nodeColor={(n: any) => NODE_COLORS[n.type] || "#5a6b6f"}
        nodeRelSize={5}
        linkColor={() => "#1f2b2e"}
        linkWidth={(l: any) => Math.max(0.5, l.confidence * 2)}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkLabel={(l: any) => `${l.relationship} — confidence ${Math.round(l.confidence * 100)}%`}
        onNodeClick={(node: any) => onNodeSelect(node)}
        onBackgroundClick={() => onNodeSelect(null)}
        cooldownTicks={80}
      />
    </div>
  );
}
