/**
 * Date helpers. The UI sends `dateFrom` and `dateTo` as inclusive calendar
 * days (YYYY-MM-DD). Internally we always work with an EXCLUSIVE upper bound
 * equal to dateTo + 1 day at 00:00:00.
 */

const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/;

export function isValidDateOnly(value: string): boolean {
  if (!DATE_ONLY_RE.test(value)) return false;
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return false;
  // Guard against overflow (e.g. 2026-02-30 -> March).
  return toDateOnly(d) === value;
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** Format a Date as a local YYYY-MM-DD string. */
export function toDateOnly(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/**
 * Convert an inclusive calendar day (YYYY-MM-DD) to the exclusive upper bound
 * (the next day at 00:00:00) as a YYYY-MM-DD string.
 */
export function exclusiveUpperBound(dateTo: string): string {
  if (!isValidDateOnly(dateTo)) {
    throw new Error(`Fecha inválida: ${dateTo}`);
  }
  const d = new Date(`${dateTo}T00:00:00`);
  d.setDate(d.getDate() + 1);
  return toDateOnly(d);
}

/** Inclusive day difference between two YYYY-MM-DD strings (dateTo - dateFrom). */
export function dayRangeInclusive(dateFrom: string, dateTo: string): number {
  const from = new Date(`${dateFrom}T00:00:00`).getTime();
  const to = new Date(`${dateTo}T00:00:00`).getTime();
  return Math.round((to - from) / 86_400_000) + 1;
}

/** Default range: first day of the current month through today. */
export function defaultDateRange(now: Date = new Date()): { dateFrom: string; dateTo: string } {
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  return { dateFrom: toDateOnly(first), dateTo: toDateOnly(now) };
}
