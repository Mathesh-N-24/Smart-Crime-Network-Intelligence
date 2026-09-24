"use client";

// ============================================================================
// page.tsx
// Tactical dashboard root: 3-pane layout wiring together the Left Panel
// (ingestion + confidence filter), Center Canvas (force graph), and Right
// Panel (suspect profile + analytics + disruption simulation), with the
// Evidentiary Dossier docked at the bottom as a collapsible audit strip.
// ============================================================================

import { useState } from "react";
import UploadPanel from "@/components/UploadPanel";
import GraphCanvas from "@/components/GraphCanvas";
import SuspectProfile from "@/components/SuspectProfile";
import EvidentiaryDossier from "@/components/EvidentiaryDossier";

type SelectedNode = { id: string; label: string; type: string; confidence: number } | null;

export default function Home() {
  const [minConfidence, setMinConfidence] = useState(0.0);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [selectedNode, setSelectedNode] = useState<SelectedNode>(null);

  return (
    <div className="flex flex-col h-screen">
      {/* Top status bar */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-tactical-border bg-tactical-panel">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-tactical-accent animate-pulse" />
          <h1 className="text-sm font-bold tracking-widest text-tactical-accent uppercase">
            CNAS // Criminal Network Analysis System
          </h1>
        </div>
        <div className="text-[10px] text-tactical-muted uppercase tracking-widest">
          Air-Gapped Deployment &middot; Zero-Trust Data Sovereignty &middot; POLE Model Active
        </div>
      </header>

      {/* 3-pane layout */}
      <div className="flex flex-1 overflow-hidden">
        <aside className="w-72 flex-shrink-0">
          <UploadPanel
            minConfidence={minConfidence}
            onConfidenceChange={setMinConfidence}
            onIngestComplete={() => setRefreshTrigger((t) => t + 1)}
          />
        </aside>

        <main className="flex-1">
          <GraphCanvas
            minConfidence={minConfidence}
            refreshTrigger={refreshTrigger}
            onNodeSelect={setSelectedNode}
          />
        </main>

        <aside className="w-80 flex-shrink-0">
          <SuspectProfile selectedNode={selectedNode} />
        </aside>
      </div>

      {/* Bottom: evidentiary audit dossier */}
      <EvidentiaryDossier refreshTrigger={refreshTrigger} />
    </div>
  );
}
