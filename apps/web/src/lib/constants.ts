/** Runtime limits, read from env with sensible defaults. */

function intEnv(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export const MAX_RECIPIENTS_PER_JOB = intEnv("MAX_RECIPIENTS_PER_JOB", 20);
export const MAX_DATE_RANGE_DAYS = intEnv("MAX_DATE_RANGE_DAYS", 366);
export const MAX_RESPONSES_PER_JOB = intEnv("MAX_RESPONSES_PER_JOB", 1000);
