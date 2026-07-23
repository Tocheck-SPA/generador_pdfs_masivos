import { NextResponse } from "next/server";
import { getSource } from "@/server/source";
import { countBodySchema } from "@/validation/schemas";
import { exclusiveUpperBound } from "@/lib/dates";
import { jsonError, requireSession, zodMessage } from "@/server/api-helpers";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const gate = await requireSession();
  if (!gate.ok) return gate.response;

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return jsonError("JSON inválido");
  }

  const parsed = countBodySchema.safeParse(body);
  if (!parsed.success) return jsonError(zodMessage(parsed.error));

  const { companyId, formId, dateFrom, dateTo, evaluationPointIds } = parsed.data;
  if (dateFrom > dateTo) return jsonError("El rango de fechas es inválido");

  try {
    const result = await getSource().countResponses({
      companyId,
      formId,
      dateFrom,
      dateToExclusive: exclusiveUpperBound(dateTo),
      evaluationPointIds,
    });
    return NextResponse.json(result);
  } catch {
    return jsonError("No se pudo calcular el conteo", 500);
  }
}
