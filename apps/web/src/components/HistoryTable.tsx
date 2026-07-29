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

function formatDateParts(iso: string): { date: string; time: string } {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { date: iso, time: "" };
  return {
    date: d.toLocaleDateString("es-CL", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }),
    time: d.toLocaleTimeString("es-CL", {
      hour: "2-digit",
      minute: "2-digit",
    }),
  };
}

function periodParts(job: JobSummary): { from: string; to: string } {
  const [from, to] = periodLabel(job).split(" → ");
  return { from: `${from} →`, to };
}

function CalendarIcon() {
  return (
    <svg className="table-icon" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="5" width="16" height="15" rx="2" />
      <path d="M8 3v4M16 3v4M4 9h16" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg className="table-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 3h8l4 4v14H6z" />
      <path d="M14 3v5h4" />
    </svg>
  );
}

function UsersIcon() {
  return (
    <svg className="table-icon" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 20a5.5 5.5 0 0 1 11 0M16 5.5a3 3 0 0 1 0 5.8M16 13a5.5 5.5 0 0 1 4.5 4.5" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg className="button-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3v11M8 10l4 4 4-4M5 20h14" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg className="button-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m9.5 14.5 5-5M7 17H5a3 3 0 0 1 0-6h3M17 7h2a3 3 0 0 1 0 6h-3" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg className="button-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 12s3-5 9-5 9 5 9 5-3 5-9 5-9-5-9-5Z" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  );
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
            <th>Fecha y hora</th>
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
            const createdAt = formatDateParts(job.createdAt);
            const period = periodParts(job);
            return (
              <Fragment key={job.id}>
                <tr
                  className={job.id === highlightJobId ? "highlight-row" : undefined}
                >
                  <td>
                    <div className="table-cell-with-icon">
                      <CalendarIcon />
                      <span className="table-cell-stack">
                        <span>{createdAt.date}</span>
                        <span>{createdAt.time}</span>
                      </span>
                    </div>
                  </td>
                  <td>{job.companyName ?? job.companyId}</td>
                  <td>{job.formName ?? job.formId}</td>
                  <td>
                    <div className="table-cell-with-icon">
                      <CalendarIcon />
                      <span className="table-cell-stack">
                        <span>{period.from}</span>
                        <span>{period.to}</span>
                      </span>
                    </div>
                  </td>
                  <td>
                    <div className="table-cell-with-icon">
                      <FileIcon />
                      <span>{job.totalResponses}</span>
                    </div>
                  </td>
                  <td className="status-cell">
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
                    <div className="recipient-list">
                      <UsersIcon />
                      <div className="recipient-values">
                        {job.recipients.map((r) => (
                          <span className="recipient-pill" key={r}>
                            {r}
                          </span>
                        ))}
                      </div>
                    </div>
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
                          <DownloadIcon />
                          Descargar
                        </a>
                      )}
                      {job.hasDownload && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => copyLink(job.id)}
                        >
                          <LinkIcon />
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
                        <EyeIcon />
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
