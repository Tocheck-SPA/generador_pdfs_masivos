import type { CreateJobInput, JobSummary } from "@/lib/types";

export interface CreateJobResult {
  jobId: string;
  status: string;
}

export interface JobStore {
  createJob(input: CreateJobInput): Promise<CreateJobResult>;
  listJobs(limit?: number): Promise<JobSummary[]>;
  getJob(jobId: string): Promise<JobSummary | null>;
  retryJob(jobId: string): Promise<JobSummary | null>;
  cancelJob(jobId: string): Promise<JobSummary | null>;
  /** Resolve the newest download URL for a job, or null if not ready. */
  getDownloadUrl(jobId: string): Promise<string | null>;
  /** Upsert the signed-in user (no-op for stores without a users table). */
  upsertUser(email: string, name: string | null): Promise<void>;
}
