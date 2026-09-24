"use client";

// ============================================================================
// EvidentiaryDossier.tsx
// "BSA Section 63 Evidentiary Dossier" - lists every extracted
// relationship alongside its verifiable SHA-256 hash, confidence, source
// document, and timestamp. This is the printable/exportable annexure an
// investigating officer attaches to a Section 63 certificate when
// submitting the AI-derived link-analysis as documentary evidence.
// ============================================================================

import { useEffect, useState } from "react";
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type DossierEntry = {
  source_name: string;
  source_id: string;
  target_name: string;
  target_id: string;
  relationship_type: string;
  evidence_hash: string;
  confidence: number;
  source_document_id: string;
  timestamp: string;
};

export default function EvidentiaryDossier({ refreshTrigger }: { refreshTrigger: number }) {
  const [entries, setEntries] = useState<DossierEntry[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (open) fetchDossier();
  }, [open, refreshTrigger]);

  async function fetchDossier() {
    try {
      const res = await axios.get(`${API_BASE}/dossier`);
      setEntries(res.data.dossier_entries || []);
    } catch {
      setEntries([]);
    }
  }

  return (
    <div className="border-t border-tactical-border bg-tactical-panel">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left px-4 py-2 text-[11px] uppercase tracking-widest text-tactical-accent hover:bg-tactical-bg/50"
      >
        {open ? "▾" : "▸"} BSA Section 63 Evidentiary Dossier ({entries.length} verified relationships)
      </button>

      {open && (
        <div className="max-h-64 overflow-y-auto px-4 pb-3">
          <table className="w-full text-[10px] border-collapse">
            <thead>
              <tr className="text-tactical-muted border-b border-tactical-border">
                <th className="text-left py-1 pr-2">Relationship</th>
                <th className="text-left py-1 pr-2">Source</th>
                <th className="text-left py-1 pr-2">Target</th>
                <th className="text-left py-1 pr-2">Confidence</th>
                <th className="text-left py-1 pr-2">SHA-256 Evidence Hash</th>
                <th className="text-left py-1 pr-2">Source Doc</th>
                <th className="text-left py-1">Timestamp (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => (
                <tr key={i} className="border-b border-tactical-border/50 hover:bg-tactical-bg/40">
                  <td className="py-1 pr-2 text-tactical-accent">{e.relationship_type}</td>
                  <td className="py-1 pr-2">{e.source_name}</td>
                  <td className="py-1 pr-2">{e.target_name}</td>
                  <td className="py-1 pr-2">{Math.round((e.confidence || 0) * 100)}%</td>
                  <td className="py-1 pr-2 font-mono text-tactical-muted break-all">{e.evidence_hash}</td>
                  <td className="py-1 pr-2 text-tactical-muted break-all">{e.source_document_id}</td>
                  <td className="py-1 text-tactical-muted">{e.timestamp}</td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-3 text-center text-tactical-muted">
                    No relationships ingested yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <p className="text-[9px] text-tactical-muted mt-2 leading-relaxed">
            Each hash is computed over the canonicalized (source, target, relationship type,
            confidence) tuple at extraction time and is independently reproducible for
            certification under Bharatiya Sakshya Adhiniyam, 2023, Section 63.
          </p>
        </div>
      )}
    </div>
  );
}
