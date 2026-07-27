import mysql from "mysql2/promise";
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

// Fuente real de ToCheck: AWS RDS MySQL, solo lectura.
// Espeja las consultas del worker (mismas tablas), con placeholders posicionales.

const g = globalThis as unknown as { __tocheckMysqlPool?: mysql.Pool };

function getPool(): mysql.Pool {
  if (g.__tocheckMysqlPool) return g.__tocheckMysqlPool;
  const useSsl = process.env.SOURCE_DATABASE_USE_SSL === "true";
  const pool = mysql.createPool({
    host: process.env.RDS_HOST,
    port: Number(process.env.RDS_PORT ?? 3306),
    user: process.env.RDS_USER,
    password: process.env.RDS_PASS,
    database: process.env.RDS_DB,
    connectionLimit: 4,
    charset: "utf8mb4",
    ssl: useSsl ? { rejectUnauthorized: false } : undefined,
    dateStrings: true, // fecha_hora como string, no Date, para comparaciones ISO estables
  });
  g.__tocheckMysqlPool = pool;
  return pool;
}

function fromBound(dateFrom: string): string {
  return `${dateFrom} 00:00:00`;
}
function toBound(dateToExclusive: string): string {
  return `${dateToExclusive} 00:00:00`;
}

type Row = Record<string, unknown>;

async function query(sql: string, params: unknown[]): Promise<Row[]> {
  const [rows] = await getPool().query(sql, params);
  return rows as Row[];
}

export class MysqlSource implements SourceReader {
  async getSnapshotStatus(): Promise<SourceSnapshotStatus> {
    return {
      isSnapshot: false,
      lastSuccessfulSyncAt: null,
      coveredFrom: null,
      coveredToExclusive: null,
      isCovered: true,
    };
  }

  async listCompanies(): Promise<SourceCompany[]> {
    const rows = await query(
      `SELECT DISTINCT e.id AS id, e.empresa AS name, e.logo AS logo
         FROM respuesta_formulario rf
         INNER JOIN empresa e ON e.id = rf.id_empresa
        ORDER BY e.empresa`,
      []
    );
    return rows.map((r) => ({
      id: Number(r.id),
      name: String(r.name ?? ""),
      logo: (r.logo as string | null) ?? null,
    }));
  }

  async listForms(companyId: number): Promise<SourceForm[]> {
    const rows = await query(
      `SELECT DISTINCT f.id AS id, f.nombre AS name, f.codigo AS code
         FROM respuesta_formulario rf
         INNER JOIN formulario f ON f.id = rf.id_formulario
        WHERE rf.id_empresa = ?
        ORDER BY f.nombre`,
      [companyId]
    );
    return rows.map((r) => ({
      id: Number(r.id),
      companyId,
      name: String(r.name ?? ""),
      code: (r.code as string | null) ?? null,
    }));
  }

  async listEvaluationPoints(
    filters: Omit<SourceFilters, "evaluationPointIds">
  ): Promise<SourceEvaluationPoint[]> {
    const rows = await query(
      `SELECT DISTINCT pe.id AS id, pe.nombre_punto AS name, z.zona AS zone
         FROM respuesta_formulario rf
         LEFT JOIN punto_evaluacion pe ON pe.id = rf.id_punto_evaluacion
         LEFT JOIN zona z ON z.id = pe.id_zona
        WHERE rf.id_empresa = ? AND rf.id_formulario = ?
          AND rf.fecha_hora >= ? AND rf.fecha_hora < ?
          AND pe.id IS NOT NULL
        ORDER BY pe.nombre_punto`,
      [filters.companyId, filters.formId, fromBound(filters.dateFrom), toBound(filters.dateToExclusive)]
    );
    return rows.map((r) => ({
      id: Number(r.id),
      companyId: filters.companyId,
      formId: filters.formId,
      name: String(r.name ?? ""),
      zone: (r.zone as string | null) ?? null,
    }));
  }

  async countResponses(filters: SourceFilters): Promise<CountResult> {
    const includeAll = filters.evaluationPointIds.length === 0;
    const params: unknown[] = [
      filters.companyId,
      filters.formId,
      fromBound(filters.dateFrom),
      toBound(filters.dateToExclusive),
    ];
    let pointClause = "";
    if (!includeAll) {
      pointClause = " AND rf.id_punto_evaluacion IN (?)";
      params.push(filters.evaluationPointIds);
    }
    const rows = await query(
      `SELECT COUNT(DISTINCT rf.id_respuesta) AS total,
              COUNT(DISTINCT rf.id_punto_evaluacion) AS points
         FROM respuesta_formulario rf
        WHERE rf.id_empresa = ? AND rf.id_formulario = ?
          AND rf.fecha_hora >= ? AND rf.fecha_hora < ?${pointClause}`,
      params
    );
    const row = rows[0] ?? {};
    return {
      totalResponses: Number(row.total ?? 0),
      totalEvaluationPoints: Number(row.points ?? 0),
    };
  }

  async listResponseIds(filters: SourceFilters): Promise<ResponseRef[]> {
    const includeAll = filters.evaluationPointIds.length === 0;
    const params: unknown[] = [
      filters.companyId,
      filters.formId,
      fromBound(filters.dateFrom),
      toBound(filters.dateToExclusive),
    ];
    let pointClause = "";
    if (!includeAll) {
      pointClause = " AND rf.id_punto_evaluacion IN (?)";
      params.push(filters.evaluationPointIds);
    }
    const rows = await query(
      `SELECT DISTINCT rf.id_respuesta AS id, rf.id_punto_evaluacion AS point_id,
              rf.fecha_hora AS completed_at
         FROM respuesta_formulario rf
        WHERE rf.id_empresa = ? AND rf.id_formulario = ?
          AND rf.fecha_hora >= ? AND rf.fecha_hora < ?${pointClause}
        ORDER BY rf.fecha_hora, rf.id_respuesta`,
      params
    );
    return rows.map((r) => ({
      responseId: Number(r.id),
      evaluationPointId: r.point_id === null ? null : Number(r.point_id),
      completedAt: String(r.completed_at),
    }));
  }
}
