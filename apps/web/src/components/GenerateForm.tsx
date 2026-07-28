"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  CountResult,
  DeliveryMode,
  SourceCompany,
  SourceEvaluationPoint,
  SourceForm,
  SourceSnapshotStatus,
} from "@/lib/types";
import { defaultDateRange } from "@/lib/dates";
import { MAX_RECIPIENTS_PER_JOB } from "@/lib/constants";
import MultiEmail, { isValidEmail } from "./MultiEmail";

const MAX_RECIPIENTS = Number(
  process.env.NEXT_PUBLIC_MAX_RECIPIENTS ?? MAX_RECIPIENTS_PER_JOB
);

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return (await res.json()) as T;
}

export default function GenerateForm({
  onCreated,
}: {
  onCreated: (jobId: string) => void;
}) {
  const [companies, setCompanies] = useState<SourceCompany[]>([]);
  const [forms, setForms] = useState<SourceForm[]>([]);
  const [points, setPoints] = useState<SourceEvaluationPoint[]>([]);

  const [companyId, setCompanyId] = useState<number | null>(null);
  const [formId, setFormId] = useState<number | null>(null);
  const [{ dateFrom, dateTo }, setRange] = useState(() => defaultDateRange());
  const [allPoints, setAllPoints] = useState(true);
  const [selectedPoints, setSelectedPoints] = useState<number[]>([]);
  const [recipients, setRecipients] = useState<string[]>([]);
  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode>("auto");

  const [count, setCount] = useState<CountResult | null>(null);
  const [countLoading, setCountLoading] = useState(false);
  const [snapshotStatus, setSnapshotStatus] = useState<SourceSnapshotStatus | null>(null);
  const [snapshotStatusLoading, setSnapshotStatusLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  // Load companies once.
  useEffect(() => {
    getJson<SourceCompany[]>("/api/source/companies")
      .then(setCompanies)
      .catch(() => setFormError("No se pudieron cargar las empresas."));
  }, []);

  // Load forms when company changes.
  useEffect(() => {
    if (companyId === null) {
      setForms([]);
      return;
    }
    getJson<SourceForm[]>(`/api/source/forms?companyId=${companyId}`)
      .then(setForms)
      .catch(() => setForms([]));
  }, [companyId]);

  // Load evaluation points when form or dates change.
  useEffect(() => {
    if (companyId === null || formId === null) {
      setPoints([]);
      return;
    }
    const qs = new URLSearchParams({
      companyId: String(companyId),
      formId: String(formId),
      dateFrom,
      dateTo,
    });
    getJson<SourceEvaluationPoint[]>(`/api/source/evaluation-points?${qs}`)
      .then((data) => {
        setPoints(data);
        setSelectedPoints((prev) => prev.filter((id) => data.some((p) => p.id === id)));
      })
      .catch(() => setPoints([]));
  }, [companyId, formId, dateFrom, dateTo]);

  // En modo snapshot, verifica que una ingesta completada cubra todo el rango.
  useEffect(() => {
    if (companyId === null || dateFrom > dateTo) {
      setSnapshotStatus(null);
      setSnapshotStatusLoading(false);
      return;
    }
    const qs = new URLSearchParams({
      companyId: String(companyId),
      dateFrom,
      dateTo,
    });
    let active = true;
    setSnapshotStatusLoading(true);
    getJson<SourceSnapshotStatus>(`/api/source/status?${qs}`)
      .then((data) => {
        if (active) setSnapshotStatus(data);
      })
      .catch(() => {
        if (active) setSnapshotStatus(null);
      })
      .finally(() => {
        if (active) setSnapshotStatusLoading(false);
      });
    return () => {
      active = false;
    };
  }, [companyId, dateFrom, dateTo]);

  const effectivePointIds = useMemo(
    () => (allPoints ? [] : selectedPoints),
    [allPoints, selectedPoints]
  );

  // Debounced count.
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refreshCount = useCallback(() => {
    if (companyId === null || formId === null || dateFrom > dateTo) {
      setCount(null);
      return;
    }
    setCountLoading(true);
    const body = {
      companyId,
      formId,
      dateFrom,
      dateTo,
      evaluationPointIds: effectivePointIds,
    };
    fetch("/api/reports/count", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error())))
      .then((data: CountResult) => setCount(data))
      .catch(() => setCount(null))
      .finally(() => setCountLoading(false));
  }, [companyId, formId, dateFrom, dateTo, effectivePointIds]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(refreshCount, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [refreshCount]);

  function onCompanyChange(value: string): void {
    const id = value ? Number(value) : null;
    setCompanyId(id);
    setFormId(null);
    setPoints([]);
    setSelectedPoints([]);
    setAllPoints(true);
    setCount(null);
  }

  function onFormChange(value: string): void {
    setFormId(value ? Number(value) : null);
    setSelectedPoints([]);
    setAllPoints(true);
    setCount(null);
  }

  function togglePoint(id: number): void {
    setAllPoints(false);
    setSelectedPoints((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  }

  function onAllPointsToggle(checked: boolean): void {
    setAllPoints(checked);
    if (checked) setSelectedPoints([]);
  }

  const validRecipients = recipients.filter(isValidEmail);
  const hasInvalidRecipient = recipients.some((e) => !isValidEmail(e));
  const pointsValid = allPoints || selectedPoints.length > 0;
  const hasCount = count !== null && count.totalResponses > 0;
  const snapshotUnavailable =
    snapshotStatus?.isSnapshot === true && !snapshotStatus.isCovered;

  const formValid =
    companyId !== null &&
    formId !== null &&
    dateFrom <= dateTo &&
    pointsValid &&
    validRecipients.length > 0 &&
    !hasInvalidRecipient &&
    hasCount &&
    !snapshotStatusLoading &&
    // Si hay respuestas contadas, no bloqueamos por cobertura de sync
    // (el aviso naranja puede seguir visible cuando !isCovered).
    (!snapshotUnavailable || hasCount) &&
    !submitting;

  function formatSnapshotDate(value: string | null): string {
    if (!value) return "sin registro";
    return new Intl.DateTimeFormat("es-CL", {
      timeZone: "America/Santiago",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
      .format(new Date(value))
      .replace(", ", " ");
  }

  async function handleSubmit(): Promise<void> {
    setFormError(null);
    const nextErrors: Record<string, string> = {};
    if (companyId === null) nextErrors.company = "Selecciona una empresa.";
    if (formId === null) nextErrors.form = "Selecciona un formulario.";
    if (dateFrom > dateTo) nextErrors.dates = "El rango de fechas es inválido.";
    if (!pointsValid) nextErrors.points = "Selecciona al menos un punto.";
    if (validRecipients.length === 0)
      nextErrors.recipients = "Agrega al menos un destinatario válido.";
    else if (hasInvalidRecipient)
      nextErrors.recipients = "Hay correos inválidos (en rojo).";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          companyId,
          formId,
          dateFrom,
          dateTo,
          evaluationPointIds: effectivePointIds,
          recipients: validRecipients,
          deliveryMode,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setFormError(data?.error ?? "No se pudo generar el reporte.");
        return;
      }
      onCreated(data.jobId as string);
    } catch {
      setFormError("No se pudo generar el reporte.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card center-card">
      <h3 className="content-title">Generar reportes</h3>
      <p className="content-subtitle">
        Elige los filtros y destinatarios del envío.
      </p>

      {formError && <div className="form-alert">{formError}</div>}

      {/* Empresa */}
      <div className="field">
        <label className="field-label" htmlFor="company">
          Empresa
        </label>
        <select
          id="company"
          className="form-control"
          value={companyId ?? ""}
          onChange={(e) => onCompanyChange(e.target.value)}
        >
          <option value="">Selecciona una empresa</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        {errors.company && <p className="field-error">{errors.company}</p>}
      </div>

      {/* Formulario */}
      <div className="field">
        <label className="field-label" htmlFor="form">
          Formulario
        </label>
        <select
          id="form"
          className="form-control"
          value={formId ?? ""}
          disabled={companyId === null}
          onChange={(e) => onFormChange(e.target.value)}
        >
          <option value="">Selecciona un formulario</option>
          {forms.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
        {errors.form && <p className="field-error">{errors.form}</p>}
      </div>

      {/* Rango de fechas */}
      <div className="field">
        <label className="field-label">Rango de fechas</label>
        <div className="field-row">
          <div>
            <input
              type="date"
              className="form-control"
              aria-label="Desde"
              value={dateFrom}
              disabled={companyId === null}
              onChange={(e) => setRange((r) => ({ ...r, dateFrom: e.target.value }))}
            />
          </div>
          <div>
            <input
              type="date"
              className="form-control"
              aria-label="Hasta"
              value={dateTo}
              disabled={companyId === null}
              onChange={(e) => setRange((r) => ({ ...r, dateTo: e.target.value }))}
            />
          </div>
        </div>
        {errors.dates && <p className="field-error">{errors.dates}</p>}
      </div>

      {snapshotStatus?.isSnapshot && (
        <div className={`snapshot-status ${snapshotUnavailable ? "uncovered" : "covered"}`}>
          <p className="snapshot-last-update">
            Última actualización de datos: {formatSnapshotDate(snapshotStatus.lastSuccessfulSyncAt)}
          </p>
          {snapshotUnavailable && (
            <p className="snapshot-warning">
              La última ingesta no cubre todo este rango de fechas. Aun así puedes
              generar si hay respuestas; para cubrir el período completo ejecuta
              una ingesta con --date-from / --date-to-exclusive.
            </p>
          )}
        </div>
      )}

      {/* Puntos de evaluación */}
      <div className="field">
        <label className="field-label">Puntos de evaluación</label>
        <div className={`points-box ${formId === null ? "disabled" : ""}`}>
          <label className="point-item">
            <input
              type="checkbox"
              checked={allPoints}
              disabled={formId === null}
              onChange={(e) => onAllPointsToggle(e.target.checked)}
            />
            Todos los puntos
          </label>
          {points.length > 0 && <div className="point-divider" />}
          {points.map((p) => (
            <label className="point-item" key={p.id}>
              <input
                type="checkbox"
                checked={allPoints || selectedPoints.includes(p.id)}
                disabled={formId === null}
                onChange={() => togglePoint(p.id)}
              />
              {p.name}
              {p.zone ? ` — ${p.zone}` : ""}
            </label>
          ))}
        </div>
        {errors.points && <p className="field-error">{errors.points}</p>}
      </div>

      {/* Destinatarios */}
      <div className="field">
        <label className="field-label" htmlFor="recipients">
          Destinatarios
        </label>
        <MultiEmail
          id="recipients"
          emails={recipients}
          onChange={setRecipients}
          max={MAX_RECIPIENTS}
        />
        {errors.recipients && <p className="field-error">{errors.recipients}</p>}
      </div>

      {/* Forma de entrega */}
      <div className="field">
        <label className="field-label" htmlFor="delivery">
          Forma de entrega
        </label>
        <select
          id="delivery"
          className="form-control"
          value={deliveryMode}
          onChange={(e) => setDeliveryMode(e.target.value as DeliveryMode)}
        >
          <option value="auto">Automático</option>
          <option value="attachments">Adjuntar ZIP</option>
          <option value="download_link">Enlace de descarga</option>
        </select>
      </div>

      {/* Conteo */}
      {companyId !== null && formId !== null && !countLoading && count !== null && (
        <p className={`count-hint ${count.totalResponses === 0 ? "zero" : ""}`}>
          {count.totalResponses === 0
            ? "No se encontraron respuestas para los filtros seleccionados."
            : `Se encontraron ${count.totalResponses} respuestas en ${count.totalEvaluationPoints} puntos de evaluación.`}
        </p>
      )}

      <button
        type="button"
        className="btn btn-primary"
        disabled={!formValid}
        onClick={handleSubmit}
      >
        {submitting ? "Generando…" : "Generar y enviar"}
      </button>
    </div>
  );
}
