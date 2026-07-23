import type { JobStatus } from "./status";

export type DeliveryMode = "auto" | "attachments" | "download_link";

/** ---------- Source catalog types ---------- */
export interface SourceCompany {
  id: number;
  name: string;
  logo: string | null;
}

export interface SourceForm {
  id: number;
  companyId: number;
  name: string;
  code: string | null;
}

export interface SourceEvaluationPoint {
  id: number;
  companyId: number;
  formId: number;
  name: string;
  zone: string | null;
}

export interface CountResult {
  totalResponses: number;
  totalEvaluationPoints: number;
}

export interface ResponseRef {
  responseId: number;
  evaluationPointId: number | null;
  completedAt: string;
}

export interface SourceFilters {
  companyId: number;
  formId: number;
  /** Inclusive lower bound, YYYY-MM-DD. */
  dateFrom: string;
  /** Exclusive upper bound, YYYY-MM-DD. */
  dateToExclusive: string;
  /** Empty array => include all points. */
  evaluationPointIds: number[];
}

/** ---------- Job DTOs (what the API returns to the UI) ---------- */
export interface JobRecipient {
  email: string;
  deliveryStatus: string;
}

export interface JobSummary {
  id: string;
  companyId: number;
  companyName: string | null;
  formId: number;
  formName: string | null;
  dateFrom: string;
  dateToExclusive: string;
  deliveryMode: DeliveryMode;
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
  hasDownload: boolean;
  createdAt: string;
}

export interface CreateJobInput {
  companyId: number;
  companyName: string | null;
  formId: number;
  formName: string | null;
  dateFrom: string;
  dateToExclusive: string;
  evaluationPointIds: number[];
  recipients: string[];
  deliveryMode: DeliveryMode;
  includeConsolidatedPdf: boolean;
  createdByEmail: string | null;
  responseRefs: ResponseRef[];
}
