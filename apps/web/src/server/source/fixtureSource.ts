import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import type {
  CountResult,
  ResponseRef,
  SourceCompany,
  SourceEvaluationPoint,
  SourceFilters,
  SourceForm,
} from "@/lib/types";
import type { SourceReader } from "./types";

interface RawCompany {
  id: number;
  name: string;
  logo: string | null;
}
interface RawForm {
  id: number;
  companyId: number;
  name: string;
  code: string | null;
}
interface RawEvaluationPoint {
  id: number;
  companyId: number;
  formId: number;
  name: string;
  zone: string | null;
}
interface RawResponse {
  responseId: number;
  companyId: number;
  formId: number;
  evaluationPointId: number | null;
  completedAt: string;
}

/** Resolve the repo-root fixtures directory, trying several candidates. */
function resolveFixturesDir(): string {
  const candidates = [
    process.env.FIXTURES_DIR,
    path.join(process.cwd(), "..", "..", "fixtures"),
    path.join(process.cwd(), "..", "fixtures"),
    path.join(process.cwd(), "fixtures"),
  ].filter((c): c is string => Boolean(c));

  for (const candidate of candidates) {
    if (existsSync(path.join(candidate, "companies.json"))) {
      return candidate;
    }
  }
  // Fall back to the most likely path; readFile will surface a clear error.
  return path.join(process.cwd(), "..", "..", "fixtures");
}

async function loadJson<T>(dir: string, file: string): Promise<T> {
  const raw = await readFile(path.join(dir, file), "utf8");
  return JSON.parse(raw) as T;
}

/**
 * Compare a naive completedAt (e.g. "2026-07-05T10:30:00") against a
 * YYYY-MM-DD boundary. String comparison works because both use the same
 * lexicographically-ordered ISO layout.
 */
function afterOrEqual(completedAt: string, dateFrom: string): boolean {
  return completedAt >= `${dateFrom}T00:00:00`;
}
function before(completedAt: string, dateToExclusive: string): boolean {
  return completedAt < `${dateToExclusive}T00:00:00`;
}

export class FixtureSource implements SourceReader {
  private dir = resolveFixturesDir();

  private async companies(): Promise<RawCompany[]> {
    return loadJson<RawCompany[]>(this.dir, "companies.json");
  }
  private async forms(): Promise<RawForm[]> {
    return loadJson<RawForm[]>(this.dir, "forms.json");
  }
  private async points(): Promise<RawEvaluationPoint[]> {
    return loadJson<RawEvaluationPoint[]>(this.dir, "evaluation_points.json");
  }
  private async responses(): Promise<RawResponse[]> {
    return loadJson<RawResponse[]>(this.dir, "responses.json");
  }

  async listCompanies(): Promise<SourceCompany[]> {
    const companies = await this.companies();
    return companies.map((c) => ({ id: c.id, name: c.name, logo: c.logo ?? null }));
  }

  async listForms(companyId: number): Promise<SourceForm[]> {
    const [forms, responses] = await Promise.all([this.forms(), this.responses()]);
    const formIdsWithResponses = new Set(
      responses.filter((r) => r.companyId === companyId).map((r) => r.formId)
    );
    return forms
      .filter((f) => f.companyId === companyId && formIdsWithResponses.has(f.id))
      .map((f) => ({
        id: f.id,
        companyId: f.companyId,
        name: f.name,
        code: f.code ?? null,
      }));
  }

  async listEvaluationPoints(
    filters: Omit<SourceFilters, "evaluationPointIds">
  ): Promise<SourceEvaluationPoint[]> {
    const [points, responses] = await Promise.all([this.points(), this.responses()]);
    const inRange = responses.filter(
      (r) =>
        r.companyId === filters.companyId &&
        r.formId === filters.formId &&
        r.evaluationPointId !== null &&
        afterOrEqual(r.completedAt, filters.dateFrom) &&
        before(r.completedAt, filters.dateToExclusive)
    );
    const pointIdsWithResponses = new Set(inRange.map((r) => r.evaluationPointId));

    const seen = new Set<number>();
    const result: SourceEvaluationPoint[] = [];
    for (const p of points) {
      if (
        p.companyId === filters.companyId &&
        p.formId === filters.formId &&
        pointIdsWithResponses.has(p.id) &&
        !seen.has(p.id)
      ) {
        seen.add(p.id);
        result.push({
          id: p.id,
          companyId: p.companyId,
          formId: p.formId,
          name: p.name,
          zone: p.zone ?? null,
        });
      }
    }
    return result;
  }

  private async matching(filters: SourceFilters): Promise<RawResponse[]> {
    const responses = await this.responses();
    const pointSet = new Set(filters.evaluationPointIds);
    const includeAll = pointSet.size === 0;
    return responses.filter(
      (r) =>
        r.companyId === filters.companyId &&
        r.formId === filters.formId &&
        afterOrEqual(r.completedAt, filters.dateFrom) &&
        before(r.completedAt, filters.dateToExclusive) &&
        (includeAll ||
          (r.evaluationPointId !== null && pointSet.has(r.evaluationPointId)))
    );
  }

  async countResponses(filters: SourceFilters): Promise<CountResult> {
    const matches = await this.matching(filters);
    const points = new Set<number>();
    for (const r of matches) {
      if (r.evaluationPointId !== null) points.add(r.evaluationPointId);
    }
    return { totalResponses: matches.length, totalEvaluationPoints: points.size };
  }

  async listResponseIds(filters: SourceFilters): Promise<ResponseRef[]> {
    const matches = await this.matching(filters);
    return matches.map((r) => ({
      responseId: r.responseId,
      evaluationPointId: r.evaluationPointId,
      completedAt: r.completedAt,
    }));
  }
}
