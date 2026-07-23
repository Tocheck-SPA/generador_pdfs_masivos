"use client";

import { statusLabel, type JobStatus } from "@/lib/status";

function badgeClass(status: string): string {
  switch (status) {
    case "completed":
      return "badge-completed";
    case "completed_with_warnings":
      return "badge-warning";
    case "failed":
      return "badge-failed";
    case "cancelled":
      return "badge-cancelled";
    case "pending":
      return "badge-pending";
    default:
      return "badge-processing";
  }
}

export default function StatusBadge({ status }: { status: JobStatus | string }) {
  return <span className={`badge ${badgeClass(status)}`}>{statusLabel(status)}</span>;
}
