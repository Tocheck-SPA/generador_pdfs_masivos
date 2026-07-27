import { NextResponse } from "next/server";
import { exclusiveUpperBound } from "@/lib/dates";
import { jsonError, requireSession, zodMessage } from "@/server/api-helpers";
import { getSource } from "@/server/source";
import { snapshotStatusQuerySchema } from "@/validation/schemas";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const gate = await requireSession();
  if (!gate.ok) return gate.response;

  const { searchParams } = new URL(request.url);
  const parsed = snapshotStatusQuerySchema.safeParse({
    companyId: searchParams.get("companyId") ?? "",
    dateFrom: searchParams.get("dateFrom") ?? "",
    dateTo: searchParams.get("dateTo") ?? "",
  });
  if (!parsed.success) return jsonError(zodMessage(parsed.error));
  if (parsed.data.dateFrom > parsed.data.dateTo) {
    return jsonError("El rango de fechas es invÃ¡lido");
  }

  try {
    const status = await getSource().getSnapshotStatus(
      parsed.data.companyId,
      parsed.data.dateFrom,
      exclusiveUpperBound(parsed.data.dateTo)
    );
    return NextResponse.json(status);
  } catch {
    return jsonError("No se pudo consultar la cobertura de datos", 500);
  }
}
