import { NextResponse } from "next/server";
import { getSource } from "@/server/source";
import { getStore } from "@/server/store";
import { createJobBodySchema } from "@/validation/schemas";
import { exclusiveUpperBound, dayRangeInclusive } from "@/lib/dates";
import {
  MAX_DATE_RANGE_DAYS,
  MAX_RECIPIENTS_PER_JOB,
  MAX_RESPONSES_PER_JOB,
} from "@/lib/constants";
import { jsonError, requireSession, zodMessage } from "@/server/api-helpers";
import { dispatchWorkerJob } from "@/server/dispatch";

export const runtime = "nodejs";

export async function GET() {
  const gate = await requireSession();
  if (!gate.ok) return gate.response;
  try {
    const jobs = await getStore().listJobs(20);
    return NextResponse.json(jobs);
  } catch {
    return jsonError("No se pudo cargar el historial", 500);
  }
}

export async function POST(request: Request) {
  const gate = await requireSession();
  if (!gate.ok) return gate.response;

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return jsonError("JSON inválido");
  }

  const parsed = createJobBodySchema.safeParse(body);
  if (!parsed.success) return jsonError(zodMessage(parsed.error));

  const {
    companyId,
    formId,
    dateFrom,
    dateTo,
    evaluationPointIds,
    recipients,
    deliveryMode,
    includeConsolidatedPdf,
  } = parsed.data;

  if (dateFrom > dateTo) return jsonError("El rango de fechas es inválido");

  const uniqueRecipients = Array.from(
    new Set(recipients.map((e) => e.trim().toLowerCase()))
  );
  if (uniqueRecipients.length > MAX_RECIPIENTS_PER_JOB) {
    return jsonError(
      `Máximo ${MAX_RECIPIENTS_PER_JOB} destinatarios por envío`
    );
  }

  const rangeDays = dayRangeInclusive(dateFrom, dateTo);
  if (rangeDays > MAX_DATE_RANGE_DAYS) {
    return jsonError(`El rango no puede superar ${MAX_DATE_RANGE_DAYS} días`);
  }

  const dateToExclusive = exclusiveUpperBound(dateTo);

  try {
    const source = getSource();
    const filters = { companyId, formId, dateFrom, dateToExclusive, evaluationPointIds };
    const responseRefs = await source.listResponseIds(filters);

    if (responseRefs.length === 0) {
      return jsonError("No se encontraron respuestas para los filtros seleccionados");
    }
    if (responseRefs.length > MAX_RESPONSES_PER_JOB) {
      return jsonError(
        `El envío supera el máximo de ${MAX_RESPONSES_PER_JOB} respuestas`
      );
    }

    const [companies, forms] = await Promise.all([
      source.listCompanies(),
      source.listForms(companyId),
    ]);
    const companyName = companies.find((c) => c.id === companyId)?.name ?? null;
    const formName = forms.find((f) => f.id === formId)?.name ?? null;

    const result = await getStore().createJob({
      companyId,
      companyName,
      formId,
      formName,
      dateFrom,
      dateToExclusive,
      evaluationPointIds,
      recipients: uniqueRecipients,
      deliveryMode,
      includeConsolidatedPdf,
      createdByEmail: gate.session.email,
      responseRefs,
    });
    try {
      await dispatchWorkerJob({ jobId: result.jobId, request });
    } catch (dispatchError) {
      console.error("No se pudo despertar el worker", dispatchError);
      return jsonError(
        `Trabajo creado (${result.jobId}), pero no se pudo iniciar el procesador`,
        502,
      );
    }
    return NextResponse.json(result, { status: 201 });
  } catch {
    return jsonError("No se pudo crear el trabajo", 500);
  }
}
