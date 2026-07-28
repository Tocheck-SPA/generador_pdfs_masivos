import { randomUUID } from "node:crypto";
import { Pool } from "pg";
import { presignArtifact } from "@/server/artifactStorage";
import type { CreateJobInput, DeliveryMode, JobSummary } from "@/lib/types";
import type { JobStatus } from "@/lib/status";
import type { CreateJobResult, JobStore } from "./types";

const g = globalThis as unknown as { __tocheckPgPool?: Pool };

function getPool(): Pool {
  if (g.__tocheckPgPool) return g.__tocheckPgPool;
  const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_URL?.includes("localhost")
      ? undefined
      : { rejectUnauthorized: false },
  });
  g.__tocheckPgPool = pool;
  return pool;
}

interface JobRow {
  id: string;
  source_company_id: string;
  source_company_name: string | null;
  source_form_id: string;
  source_form_name: string | null;
  date_from: Date;
  date_to_exclusive: Date;
  delivery_mode: string;
  status: string;
  total_responses: number;
  processed_responses: number;
  successful_responses: number;
  failed_responses: number;
  progress_percent: number;
  current_step: string | null;
  warning_message: string | null;
  error_message: string | null;
  created_at: Date;
  recipients: string[] | null;
  has_download: boolean;
}

function toDateOnly(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function rowToSummary(row: JobRow): JobSummary {
  return {
    id: row.id,
    companyId: Number(row.source_company_id),
    companyName: row.source_company_name,
    formId: Number(row.source_form_id),
    formName: row.source_form_name,
    dateFrom: toDateOnly(row.date_from),
    dateToExclusive: toDateOnly(row.date_to_exclusive),
    deliveryMode: row.delivery_mode as DeliveryMode,
    status: row.status as JobStatus,
    totalResponses: row.total_responses,
    processedResponses: row.processed_responses,
    successfulResponses: row.successful_responses,
    failedResponses: row.failed_responses,
    progressPercent: row.progress_percent,
    currentStep: row.current_step,
    warningMessage: row.warning_message,
    errorMessage: row.error_message,
    recipients: row.recipients ?? [],
    hasDownload: row.has_download,
    createdAt: row.created_at.toISOString(),
  };
}

const SELECT_JOB = `
  SELECT j.*,
    (SELECT array_agg(r.email ORDER BY r.email)
       FROM report_job_recipients r WHERE r.job_id = j.id) AS recipients,
    EXISTS (SELECT 1 FROM report_artifacts a
       WHERE a.job_id = j.id AND a.artifact_type = 'zip') AS has_download
  FROM report_jobs j
`;

export class PgStore implements JobStore {
  async createJob(input: CreateJobInput): Promise<CreateJobResult> {
    const pool = getPool();
    const client = await pool.connect();
    try {
      await client.query("BEGIN");

      let createdByUserId: string | null = null;
      if (input.createdByEmail) {
        const userRes = await client.query<{ id: string }>(
          `INSERT INTO app_users (email) VALUES ($1)
           ON CONFLICT (email) DO UPDATE SET last_login_at = now()
           RETURNING id`,
          [input.createdByEmail]
        );
        createdByUserId = userRes.rows[0]?.id ?? null;
      }

      const idempotencyKey = randomUUID();
      const jobRes = await client.query<{ id: string; status: string }>(
        `INSERT INTO report_jobs
          (created_by_user_id, source_company_id, source_company_name,
           source_form_id, source_form_name, date_from, date_to_exclusive,
           filters, delivery_mode, include_consolidated_pdf, status,
           total_responses, idempotency_key)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'pending',$11,$12)
         RETURNING id, status`,
        [
          createdByUserId,
          input.companyId,
          input.companyName,
          input.formId,
          input.formName,
          `${input.dateFrom}T00:00:00Z`,
          `${input.dateToExclusive}T00:00:00Z`,
          JSON.stringify({ evaluationPointIds: input.evaluationPointIds }),
          input.deliveryMode,
          input.includeConsolidatedPdf,
          input.responseRefs.length,
          idempotencyKey,
        ]
      );
      const jobId = jobRes.rows[0].id;

      for (const email of input.recipients) {
        await client.query(
          `INSERT INTO report_job_recipients (job_id, email) VALUES ($1,$2)`,
          [jobId, email]
        );
      }

      for (const ref of input.responseRefs) {
        const responseDate = new Date(ref.completedAt).toISOString();
        await client.query(
          `INSERT INTO report_job_items
            (job_id, source_response_id, source_response_date, source_evaluation_point_id)
           VALUES ($1,$2,$3,$4)
           ON CONFLICT (job_id, source_response_id) DO NOTHING`,
          [jobId, ref.responseId, responseDate, ref.evaluationPointId]
        );
      }

      await client.query("COMMIT");
      return { jobId, status: jobRes.rows[0].status };
    } catch (err) {
      await client.query("ROLLBACK");
      throw err;
    } finally {
      client.release();
    }
  }

  async listJobs(limit = 20): Promise<JobSummary[]> {
    const pool = getPool();
    const res = await pool.query<JobRow>(
      `${SELECT_JOB} ORDER BY j.created_at DESC LIMIT $1`,
      [limit]
    );
    return res.rows.map(rowToSummary);
  }

  async getJob(jobId: string): Promise<JobSummary | null> {
    const pool = getPool();
    const res = await pool.query<JobRow>(`${SELECT_JOB} WHERE j.id = $1`, [jobId]);
    return res.rows[0] ? rowToSummary(res.rows[0]) : null;
  }

  async retryJob(jobId: string): Promise<JobSummary | null> {
    const pool = getPool();
    await pool.query(
      `UPDATE report_jobs
         SET status = 'pending', processed_responses = 0, successful_responses = 0,
             failed_responses = 0, progress_percent = 0, current_step = NULL,
             error_code = NULL, error_message = NULL, warning_message = NULL,
             locked_at = NULL, locked_by = NULL, heartbeat_at = NULL,
             updated_at = now()
       WHERE id = $1 AND status = 'failed'`,
      [jobId]
    );
    return this.getJob(jobId);
  }

  async cancelJob(jobId: string): Promise<JobSummary | null> {
    const pool = getPool();
    await pool.query(
      `UPDATE report_jobs
         SET status = CASE
               WHEN status IN ('pending') THEN 'cancelled'
               ELSE 'cancel_requested' END,
             cancelled_at = CASE WHEN status = 'pending' THEN now() ELSE cancelled_at END,
             updated_at = now()
       WHERE id = $1
         AND status NOT IN ('completed','completed_with_warnings','failed','cancelled')`,
      [jobId]
    );
    return this.getJob(jobId);
  }

  async getDownloadUrl(jobId: string): Promise<string | null> {
    const pool = getPool();
    const res = await pool.query<{
      storage_key: string;
      storage_provider: string | null;
      storage_bucket: string | null;
    }>(
      `SELECT storage_key, storage_provider, storage_bucket FROM report_artifacts
        WHERE job_id = $1 AND artifact_type = 'zip'
        ORDER BY created_at DESC LIMIT 1`,
      [jobId]
    );
    const artifact = res.rows[0];
    if (!artifact) return null;
    return presignArtifact({
      provider: artifact.storage_provider,
      bucket: artifact.storage_bucket,
      key: artifact.storage_key,
    });
  }

  async upsertUser(email: string, name: string | null): Promise<void> {
    const pool = getPool();
    await pool.query(
      `INSERT INTO app_users (email, name, last_login_at)
       VALUES ($1,$2, now())
       ON CONFLICT (email) DO UPDATE
         SET last_login_at = now(),
             name = COALESCE(EXCLUDED.name, app_users.name)`,
      [email, name]
    );
  }
}
