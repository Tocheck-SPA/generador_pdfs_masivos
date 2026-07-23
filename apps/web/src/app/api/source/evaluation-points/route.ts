import { NextResponse } from "next/server";
import { getSource } from "@/server/source";
import { evaluationPointsQuerySchema } from "@/validation/schemas";
import { exclusiveUpperBound } from "@/lib/dates";
import { jsonError, requireSession, zodMessage } from "@/server/api-helpers";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const gate = await requireSession();
  if (!gate.ok) return gate.response;

  const { searchParams } = new URL(request.url);
  const parsed = evaluationPointsQuerySchema.safeParse({
    companyId: searchParams.get("companyId") ?? "",
    formId: searchParams.get("formId") ?? "",
    dateFrom: searchParams.get("dateFrom") ?? "",
    dateTo: searchParams.get("dateTo") ?? "",
  });
  if (!parsed.success) return jsonError(zodMessage(parsed.error));

  const { companyId, formId, dateFrom, dateTo } = parsed.data;
  try {
    const points = await getSource().listEvaluationPoints({
      companyId,
      formId,
      dateFrom,
      dateToExclusive: exclusiveUpperBound(dateTo),
    });
    return NextResponse.json(points);
  } catch {
    return jsonError("No se pudieron cargar los puntos de evaluación", 500);
  }
}
