"use client";

import { useState } from "react";
import GenerateForm from "./GenerateForm";
import HistoryTable from "./HistoryTable";

type Tab = "generar" | "historial";

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("generar");
  const [highlightJobId, setHighlightJobId] = useState<string | null>(null);

  function handleCreated(jobId: string): void {
    setHighlightJobId(jobId);
    setTab("historial");
  }

  return (
    <div>
      <div className="tabs-bar" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "generar"}
          className={`tab ${tab === "generar" ? "active" : ""}`}
          onClick={() => setTab("generar")}
        >
          Generar reportes
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "historial"}
          className={`tab ${tab === "historial" ? "active" : ""}`}
          onClick={() => setTab("historial")}
        >
          Historial
        </button>
      </div>

      {tab === "generar" ? (
        <GenerateForm onCreated={handleCreated} />
      ) : (
        <HistoryTable highlightJobId={highlightJobId} />
      )}
    </div>
  );
}
