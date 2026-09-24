"use client";

// ============================================================================
// UploadPanel.tsx
// Left Panel: evidence ingestion (FIR scans / CDR files) + the confidence
// filter slider that controls which extracted relationships are trusted
// enough to render on the Center Canvas. Analysts routinely need to hide
// low-confidence AI inferences when briefing a magistrate - this slider is
// the operational control for that.
// ============================================================================

import { useState } from "react";
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type UploadPanelProps = {
  minConfidence: number;
  onConfidenceChange: (val: number) => void;
  onIngestComplete: () => void;
};

export default function UploadPanel({
  minConfidence,
  onConfidenceChange,
  onIngestComplete,
}: UploadPanelProps) {
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("fir_scan");
  const [status, setStatus] = useState<string>("");
  const [taskId, setTaskId] = useState<string | null>(null);

  async function handleUpload() {
    if (!file) return;
    setStatus("Hashing & uploading evidence...");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("doc_type", docType);

    try {
      const res = await axios.post(`${API_BASE}/ingest`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setTaskId(res.data.task_id);
      setStatus(`Queued. SHA-256: ${res.data.original_file_sha256.slice(0, 16)}...`);
      pollTask(res.data.task_id);
    } catch (err) {
      setStatus("Ingestion failed - check backend connectivity.");
    }
  }

  async function pollTask(id: string) {
    const interval = setInterval(async () => {
      try {
        const res = await axios.get(`${API_BASE}/task-status/${id}`);
        const { state, meta, result } = res.data;
        if (state === "PROGRESS") {
          setStatus(`Pipeline stage: ${meta?.stage || "processing"}...`);
        } else if (state === "SUCCESS") {
          setStatus(
            `Complete. ${result?.graph_ingestion?.edges_created?.length ?? 0} evidence-hashed edges ingested.`
          );
          clearInterval(interval);
          onIngestComplete();
        } else if (state === "FAILURE") {
          setStatus("Pipeline failed - see worker logs.");
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, 1500);
  }

  return (
    <div className="flex flex-col h-full p-4 gap-6 bg-tactical-panel border-r border-tactical-border">
      <div>
        <h2 className="text-tactical-accent text-xs tracking-widest uppercase mb-3">
          Evidence Ingestion
        </h2>

        <label className="block text-xs text-tactical-muted mb-1">Document Type</label>
        <select
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          className="w-full bg-tactical-bg border border-tactical-border text-slate-200 text-sm rounded px-2 py-1.5 mb-3 focus:outline-none focus:border-tactical-accent"
        >
          <option value="fir_scan">FIR (Scanned Document)</option>
          <option value="cdr_audio">CDR - Intercept Audio</option>
          <option value="cdr_text">CDR - Text / Spreadsheet Export</option>
        </select>

        <div
          className="border-2 border-dashed border-tactical-border rounded-lg p-6 text-center cursor-pointer hover:border-tactical-accent transition-colors"
          onClick={() => document.getElementById("file-input")?.click()}
        >
          <input
            id="file-input"
            type="file"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <p className="text-xs text-tactical-muted">
            {file ? file.name : "Drop FIR / CDR file or click to browse"}
          </p>
        </div>

        <button
          onClick={handleUpload}
          disabled={!file}
          className="w-full mt-3 bg-tactical-accent/10 border border-tactical-accent text-tactical-accent text-xs uppercase tracking-wider py-2 rounded hover:bg-tactical-accent/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          Ingest &amp; Process
        </button>

        {status && (
          <p className="text-[11px] text-tactical-muted mt-2 break-words">{status}</p>
        )}
      </div>

      <div>
        <h2 className="text-tactical-accent text-xs tracking-widest uppercase mb-3">
          Confidence Filter
        </h2>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={minConfidence}
          onChange={(e) => onConfidenceChange(parseFloat(e.target.value))}
          className="w-full accent-tactical-accent"
        />
        <div className="flex justify-between text-[11px] text-tactical-muted mt-1">
          <span>0% (show all AI inferences)</span>
          <span className="text-tactical-accent">{Math.round(minConfidence * 100)}%</span>
        </div>
        <p className="text-[10px] text-tactical-muted mt-2 leading-relaxed">
          Relationships below this AI-confidence threshold are hidden from
          the graph canvas and excluded from disruption simulations, but
          remain fully logged in the Evidentiary Dossier for audit.
        </p>
      </div>
    </div>
  );
}
