import { Pool } from "pg";
import type {
  CountResult,
  ResponseRef,
  SourceCompany,
  SourceEvaluationPoint,
  SourceFilters,
  SourceForm,
  SourceSnapshotStatus,
} from "@/lib/types";
import type { SourceReader } from "./types";

const g = globalThis as unknown as { __tocheckSnapshotPool?: Pool };

function getPool(): Pool {
  if (g.__tocheckSnapshotPool) return g.__tocheckSnapshotPool;
  g.__tocheckSnapshotPool = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_URL?.includes("localhost")
      ? undefined
      : { rejectUnauthorized: false },
  });
  return g.__tocheckSnapshotPool;
}

function fromBound(date: string): string {
  return `${date} 00:00:00`;
}

function toBound(date: string): string {
  return `${date} 00:00:00`;
}

export class PostgresSource implements SourceReader {
  async getSnapshotStatus(
    companyId: number,
    dateFrom: string,
    dateToExclusive: string
  ): Promise<SourceSnapshotStatus> {
    // Cobertura por días calendario (como la UI):
    // - date_from del sync <= inicio del dateFrom
    // - date_to_exclusive del sync > inicio del último día inclusive
    //   (dateToExclusive - 1 día). Así un ingest que terminó "hoy a las 12:00"
    //   cubre el dateTo=hoy, sin exigir medianoche del día siguiente.
    const result = await getPool().query(
      `SELECT
         latest.completed_at AS last_successful_sync_at,
         latest.date_from AS covered_from,
         latest.date_to_exclusive AS covered_to_exclusive,
         EXISTS (
           SELECT 1
             FROM source_sync_runs covered
            WHERE covered.company_id = $1
              AND covered.status = 'completed'
              AND covered.date_from <= $2::timestamp
              AND covered.date_to_exclusive > ($3::timestamp - INTERVAL '1 day')
         ) AS is_covered
         FROM (
           SELECT completed_at, date_from, date_to_exclusive
             FROM source_sync_runs
            WHERE company_id = $1 AND status = 'completed'
            ORDER BY completed_at DESC NULLS LAST
            LIMIT 1
         ) latest`,
      [companyId, fromBound(dateFrom), toBound(dateToExclusive)]
    );
    const row = result.rows[0];
    return {
      isSnapshot: true,
      lastSuccessfulSyncAt: row?.last_successful_sync_at
        ? new Date(row.last_successful_sync_at).toISOString()
        : null,
      coveredFrom: row?.covered_from ? new Date(row.covered_from).toISOString() : null,
      coveredToExclusive: row?.covered_to_exclusive
        ? new Date(row.covered_to_exclusive).toISOString()
        : null,
      isCovered: Boolean(row?.is_covered),
    };
  }

  async listCompanies(): Promise<SourceCompany[]> {
    const result = await getPool().query(
      "SELECT id, name, logo FROM source_catalog_companies ORDER BY name"
    );
    return result.rows.map((r) => ({
      id: Number(r.id), name: String(r.name ?? ""), logo: r.logo ?? null,
    }));
  }

  async listForms(companyId: number): Promise<SourceForm[]> {
    const result = await getPool().query(
      `SELECT id, company_id, name, code, scale, logo
         FROM source_catalog_forms WHERE company_id = $1 ORDER BY name`,
      [companyId]
    );
    return result.rows.map((r) => ({
      id: Number(r.id), companyId: Number(r.company_id), name: String(r.name ?? ""),
      code: r.code ?? null, scale: r.scale ?? null, logo: r.logo ?? null,
    }));
  }

  async listEvaluationPoints(
    filters: Omit<SourceFilters, "evaluationPointIds">
  ): Promise<SourceEvaluationPoint[]> {
    const result = await getPool().query(
      `SELECT DISTINCT evaluation_point_id AS id, evaluation_point_name AS name,
              evaluation_point_address AS address, evaluation_point_country AS country,
              zone_name AS zone
         FROM source_response_snapshots
        WHERE company_id = $1 AND form_id = $2
          AND completed_at >= $3 AND completed_at < $4
          AND evaluation_point_id IS NOT NULL
        ORDER BY name`,
      [filters.companyId, filters.formId, fromBound(filters.dateFrom), toBound(filters.dateToExclusive)]
    );
    return result.rows.map((r) => ({
      id: Number(r.id), companyId: filters.companyId, formId: filters.formId,
      name: String(r.name ?? ""), address: r.address ?? null,
      country: r.country ?? null, zone: r.zone ?? null,
    }));
  }

  private baseParams(filters: SourceFilters): { where: string; params: unknown[] } {
    const params: unknown[] = [
      filters.companyId, filters.formId,
      fromBound(filters.dateFrom), toBound(filters.dateToExclusive),
    ];
    let where = "company_id = $1 AND form_id = $2 AND completed_at >= $3 AND completed_at < $4";
    if (filters.evaluationPointIds.length > 0) {
      params.push(filters.evaluationPointIds);
      where += ` AND evaluation_point_id = ANY($${params.length}::bigint[])`;
    }
    return { where, params };
  }

  async countResponses(filters: SourceFilters): Promise<CountResult> {
    const { where, params } = this.baseParams(filters);
    const result = await getPool().query(
      `SELECT COUNT(*)::int AS total, COUNT(DISTINCT evaluation_point_id)::int AS points
         FROM source_response_snapshots WHERE ${where}`,
      params
    );
    return {
      totalResponses: Number(result.rows[0]?.total ?? 0),
      totalEvaluationPoints: Number(result.rows[0]?.points ?? 0),
    };
  }

  async listResponseIds(filters: SourceFilters): Promise<ResponseRef[]> {
    const { where, params } = this.baseParams(filters);
    const result = await getPool().query(
      `SELECT response_id AS id, evaluation_point_id AS point_id, completed_at
         FROM source_response_snapshots WHERE ${where}
        ORDER BY completed_at, response_id`,
      params
    );
    return result.rows.map((r) => ({
      responseId: Number(r.id),
      evaluationPointId: r.point_id === null ? null : Number(r.point_id),
      completedAt: String(r.completed_at),
    }));
  }
}
