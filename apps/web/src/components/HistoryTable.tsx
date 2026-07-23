"use client";

import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import type { JobSummary } from "@/lib/types";
import { isActiveStatus } from "@/lib/status";
import ProgressBar from "./ProgressBar";
import StatusBadge from "./StatusBadge";

const POLL_MS = 2500;

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-CL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** date_to_exclusive is exclusive; show the inclusive last day. */
function periodLabel(job: JobSummary): string {
  const to = new Date(`${job.dateToExclusive}T00:00:00`);
  to.setDate(to.getDate() - 1);
  const toStr = `${to.getFullYear()}-${String(to.getMonth() + 1).padStart(2, "0")}-${String(
    to.getDate()
  ).padStart(2, "0")}`;
  return `${job.dateFrom} → ${toStr}`;
}

export default function HistoryTable({
  highlightJobId,
}: {
  highlightJobId: string | null;
}) {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/jobs");
      if (!res.ok) return;
      const data = (await res.json()) as JobSummary[];
      setJobs(data);
    } catch {
      // Ignore transient polling errors.
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Poll while any job is active.
  const anyActive = jobs.some((j) => isActiveStatus(j.status));
  useEffect(() => {
    if (!anyActive) return;
    timerRef.current = setInterval(() => void load(), POLL_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [anyActive, load]);

  function toggleExpand(id: string): void {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function act(jobId: string, action: "retry" | "cancel"): Promise<void> {
    try {
      await fetch(`/api/jobs/${jobId}/${action}`, { method: "POST" });
      await load();
    } catch {
      // no-op
    }
  }

  async function copyLink(jobId: string): Promise<void> {
    const url = `${window.location.origin}/api/jobs/${jobId}/download`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(jobId);
      setTimeout(() => setCopied((c) => (c === jobId ? null : c)), 1800);
    } catch {
      // Clipboard may be unavailable; ignore.
    }
  }

  if (loaded && jobs.length === 0) {
    return (
      <div className="table-wrap">
        <div className="empty-state">Aún no hay reportes generados.</div>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Empresa</th>
            <th>Formulario</th>
            <th>Periodo</th>
            <th>Cantidad</th>
            <th>Estado</th>
            <th>Destinatarios</th>
            <th>Acción</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => {
            const active = isActiveStatus(job.status);
            const isOpen = expanded.has(job.id);
            return (
              <Fragment key={job.id}>
                <tr
                  className={job.id === highlightJobId ? "highlight-row" : undefined}
                >
                  <td>{formatDate(job.createdAt)}</td>
                  <td>{job.companyName ?? job.companyId}</td>
                  <td>{job.formName ?? job.formId}</td>
                  <td>{periodLabel(job)}</td>
                  <td>{job.totalResponses}</td>
                  <td>
                    <StatusBadge status={job.status} />
                    {active && (
                      <div style={{ marginTop: 8 }}>
                        <ProgressBar percent={job.progressPercent} />
                        {job.currentStep && (
                          <div className="progress-step">{job.currentStep}</div>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="recipients-cell">
                    {job.recipients.map((r) => (
                      <span className="recipient-pill" key={r}>
                        {r}
                      </span>
                    ))}
                  </td>
                  <td>
                    <div className="row-actions">
                      {job.hasDownload && (
                        <a
                          className="btn btn-outline btn-sm"
                          href={`/api/jobs/${job.id}/download`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Descargar
                        </a>
                      )}
                      {job.hasDownload && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => copyLink(job.id)}
                        >
                          {copied === job.id ? "Copiado" : "Copiar enlace"}
                        </button>
                      )}
                      {job.status === "failed" && (
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => act(job.id, "retry")}
                        >
                          Reintentar
                        </button>
                      )}
                      {active && (
                        <button
                          type="button"
                          className="btn btn-danger-subtle btn-sm"
                          onClick={() => act(job.id, "cancel")}
                        >
                          Cancelar
                        </button>
                      )}
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => toggleExpand(job.id)}
                      >
                        {isOpen ? "Ocultar" : "Ver detalle"}
                      </button>
                    </div>
                  </td>
                </tr>
                {isOpen && (
                  <tr className="detail-row">
                    <td colSpan={8}>
                      <div className="detail-grid">
                        <div className="detail-item">
                          <span className="k">Total</span>
                          <span className="v">{job.totalResponses}</span>
                        </div>
                        <div className="detail-item">
                          <span className="k">Procesadas</span>
                          <span className="v">{job.processedResponses}</span>
                        </div>
                        <div className="detail-item">
                          <span className="k">Exitosas</span>
                          <span className="v">{job.successfulResponses}</span>
                        </div>
                        <div className="detail-item">
                          <span className="k">Con error</span>
                          <span className="v">{job.failedResponses}</span>
                        </div>
                      </div>
                      {job.warningMessage && (
                        <p className="detail-message warning">{job.warningMessage}</p>
                      )}
                      {job.errorMessage && (
                        <p className="detail-message error">{job.errorMessage}</p>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
