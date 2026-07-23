import { randomUUID } from "node:crypto";
import type { CreateJobInput, DeliveryMode, JobSummary } from "@/lib/types";
import type { JobStatus } from "@/lib/status";
import type { CreateJobResult, JobStore } from "./types";

interface JobRecord {
  id: string;
  companyId: number;
  companyName: string | null;
  formId: number;
  formName: string | null;
  dateFrom: string;
  dateToExclusive: string;
  deliveryMode: DeliveryMode;
  includeConsolidatedPdf: boolean;
  status: JobStatus;
  totalResponses: number;
  processedResponses: number;
  successfulResponses: number;
  failedResponses: number;
  progressPercent: number;
  currentStep: string | null;
  warningMessage: string | null;
  errorMessage: string | null;
  recipients: string[];
  downloadUrl: string | null;
  createdBy: string | null;
  createdAt: string;
  /** How many responses we have "started generating" (may exceed processed). */
  generatedCursor: number;
}

interface MemoryState {
  jobs: Map<string, JobRecord>;
  timers: Map<string, ReturnType<typeof setInterval>>;
}

// Survive dev HMR by hanging state off globalThis.
const g = globalThis as unknown as { __tocheckMemoryState?: MemoryState };
const state: MemoryState =
  g.__tocheckMemoryState ??
  (g.__tocheckMemoryState = { jobs: new Map(), timers: new Map() });

const SIM_ENABLED =
  process.env.NODE_ENV !== "test" && !process.env.VITEST;
const TICK_MS = 700;

function pct(record: JobRecord): number {
  switch (record.status) {
    case "pending":
      return 0;
    case "fetching_source_data":
      return 5;
    case "generating_pdfs": {
      const share = record.totalResponses
        ? record.processedResponses / record.totalResponses
        : 1;
      return Math.min(85, 5 + Math.round(80 * share));
    }
    case "creating_bundle":
      return 88;
    case "uploading":
      return 93;
    case "sending_email":
      return 97;
    case "completed":
    case "completed_with_warnings":
      return 100;
    default:
      return record.progressPercent;
  }
}

function setStep(record: JobRecord): void {
  if (record.status === "generating_pdfs") {
    record.currentStep = `Generando PDF ${record.processedResponses} de ${record.totalResponses}`;
  } else {
    const map: Partial<Record<JobStatus, string>> = {
      fetching_source_data: "Preparando datos",
      creating_bundle: "Preparando archivos",
      uploading: "Subiendo archivos",
      sending_email: "Enviando correo",
      cancel_requested: "Cancelando",
    };
    record.currentStep = map[record.status] ?? null;
  }
  record.progressPercent = Math.max(record.progressPercent, pct(record));
}

/** Advance a job one logical step. Returns true if more work remains. */
export function stepJob(jobId: string): boolean {
  const record = state.jobs.get(jobId);
  if (!record) return false;

  if (record.status === "cancel_requested") {
    record.status = "cancelled";
    record.currentStep = null;
    return false;
  }

  switch (record.status) {
    case "pending":
      record.status = "fetching_source_data";
      setStep(record);
      return true;
    case "fetching_source_data":
      record.status = "generating_pdfs";
      setStep(record);
      return true;
    case "generating_pdfs": {
      const batch = Math.max(1, Math.ceil(record.totalResponses / 25));
      for (let i = 0; i < batch && record.generatedCursor < record.totalResponses; i++) {
        record.generatedCursor += 1;
        // Fail roughly one in seven items to exercise warnings.
        if (record.generatedCursor % 7 === 0) {
          record.failedResponses += 1;
        } else {
          record.successfulResponses += 1;
        }
        record.processedResponses += 1;
      }
      setStep(record);
      if (record.processedResponses >= record.totalResponses) {
        record.status = "creating_bundle";
        setStep(record);
      }
      return true;
    }
    case "creating_bundle":
      record.status = "uploading";
      setStep(record);
      return true;
    case "uploading":
      record.status = "sending_email";
      setStep(record);
      return true;
    case "sending_email":
      record.status =
        record.failedResponses > 0 ? "completed_with_warnings" : "completed";
      record.progressPercent = 100;
      record.currentStep = null;
      record.downloadUrl = `https://reportes.tocheck.local/descargas/${record.id}.zip`;
      if (record.failedResponses > 0) {
        record.warningMessage = `${record.failedResponses} de ${record.totalResponses} respuestas no pudieron generarse.`;
      }
      return false;
    default:
      return false;
  }
}

function stopTimer(jobId: string): void {
  const timer = state.timers.get(jobId);
  if (timer) {
    clearInterval(timer);
    state.timers.delete(jobId);
  }
}

function startSimulator(jobId: string): void {
  if (!SIM_ENABLED) return;
  stopTimer(jobId);
  const timer = setInterval(() => {
    const more = stepJob(jobId);
    if (!more) stopTimer(jobId);
  }, TICK_MS);
  // Do not keep the event loop alive because of the simulator.
  if (typeof timer.unref === "function") timer.unref();
  state.timers.set(jobId, timer);
}

function toSummary(record: JobRecord): JobSummary {
  return {
    id: record.id,
    companyId: record.companyId,
    companyName: record.companyName,
    formId: record.formId,
    formName: record.formName,
    dateFrom: record.dateFrom,
    dateToExclusive: record.dateToExclusive,
    deliveryMode: record.deliveryMode,
    status: record.status,
    totalResponses: record.totalResponses,
    processedResponses: record.processedResponses,
    successfulResponses: record.successfulResponses,
    failedResponses: record.failedResponses,
    progressPercent: record.progressPercent,
    currentStep: record.currentStep,
    warningMessage: record.warningMessage,
    errorMessage: record.errorMessage,
    recipients: [...record.recipients],
    hasDownload: record.downloadUrl !== null,
    createdAt: record.createdAt,
  };
}

export class MemoryStore implements JobStore {
  async createJob(input: CreateJobInput): Promise<CreateJobResult> {
    const id = randomUUID();
    const record: JobRecord = {
      id,
      companyId: input.companyId,
      companyName: input.companyName,
      formId: input.formId,
      formName: input.formName,
      dateFrom: input.dateFrom,
      dateToExclusive: input.dateToExclusive,
      deliveryMode: input.deliveryMode,
      includeConsolidatedPdf: input.includeConsolidatedPdf,
      status: "pending",
      totalResponses: input.responseRefs.length,
      processedResponses: 0,
      successfulResponses: 0,
      failedResponses: 0,
      progressPercent: 0,
      currentStep: "Pendiente",
      warningMessage: null,
      errorMessage: null,
      recipients: [...input.recipients],
      downloadUrl: null,
      createdBy: input.createdByEmail,
      createdAt: new Date().toISOString(),
      generatedCursor: 0,
    };
    state.jobs.set(id, record);
    startSimulator(id);
    return { jobId: id, status: record.status };
  }

  async listJobs(limit = 20): Promise<JobSummary[]> {
    return [...state.jobs.values()]
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
      .slice(0, limit)
      .map(toSummary);
  }

  async getJob(jobId: string): Promise<JobSummary | null> {
    const record = state.jobs.get(jobId);
    return record ? toSummary(record) : null;
  }

  async retryJob(jobId: string): Promise<JobSummary | null> {
    const record = state.jobs.get(jobId);
    if (!record) return null;
    if (record.status !== "failed") return toSummary(record);
    record.status = "pending";
    record.processedResponses = 0;
    record.successfulResponses = 0;
    record.failedResponses = 0;
    record.progressPercent = 0;
    record.generatedCursor = 0;
    record.currentStep = "Pendiente";
    record.errorMessage = null;
    record.warningMessage = null;
    record.downloadUrl = null;
    startSimulator(jobId);
    return toSummary(record);
  }

  async cancelJob(jobId: string): Promise<JobSummary | null> {
    const record = state.jobs.get(jobId);
    if (!record) return null;
    const terminal =
      record.status === "completed" ||
      record.status === "completed_with_warnings" ||
      record.status === "failed" ||
      record.status === "cancelled";
    if (terminal) return toSummary(record);
    stopTimer(jobId);
    record.status = "cancelled";
    record.currentStep = null;
    return toSummary(record);
  }

  async getDownloadUrl(jobId: string): Promise<string | null> {
    return state.jobs.get(jobId)?.downloadUrl ?? null;
  }

  async upsertUser(): Promise<void> {
    // No users table in the memory backend.
  }
}

/** Test helper: create a job without starting the auto-simulator. */
export function __resetMemoryStore(): void {
  for (const id of state.timers.keys()) stopTimer(id);
  state.jobs.clear();
}
