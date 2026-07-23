export type JobStatus =
  | "pending"
  | "processing"
  | "fetching_source_data"
  | "generating_pdfs"
  | "creating_bundle"
  | "uploading"
  | "sending_email"
  | "completed"
  | "completed_with_warnings"
  | "failed"
  | "cancel_requested"
  | "cancelled";

/** Internal status -> user-visible Spanish label. */
export const STATUS_LABELS: Record<JobStatus, string> = {
  pending: "Pendiente",
  processing: "Procesando",
  fetching_source_data: "Preparando datos",
  generating_pdfs: "Generando PDF",
  creating_bundle: "Preparando archivos",
  uploading: "Subiendo archivos",
  sending_email: "Enviando correo",
  completed: "Completado",
  completed_with_warnings: "Completado con advertencias",
  failed: "Fallido",
  cancel_requested: "Cancelando",
  cancelled: "Cancelado",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status as JobStatus] ?? status;
}

/** Statuses that mean the job is still moving (poll while any is active). */
export const ACTIVE_STATUSES: ReadonlySet<JobStatus> = new Set<JobStatus>([
  "pending",
  "processing",
  "fetching_source_data",
  "generating_pdfs",
  "creating_bundle",
  "uploading",
  "sending_email",
  "cancel_requested",
]);

export function isActiveStatus(status: string): boolean {
  return ACTIVE_STATUSES.has(status as JobStatus);
}

export function isTerminalStatus(status: string): boolean {
  return (
    status === "completed" ||
    status === "completed_with_warnings" ||
    status === "failed" ||
    status === "cancelled"
  );
}
