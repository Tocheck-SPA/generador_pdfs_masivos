import { NextResponse } from "next/server";
import { getStore } from "@/server/store";
import { jsonError, requireSession } from "@/server/api-helpers";
import { dispatchWorkerJob } from "@/server/dispatch";

export const runtime = "nodejs";

export async function POST(
  request: Request,
  { params }: { params: { jobId: string } }
) {
  const gate = await requireSession();
  if (!gate.ok) return gate.response;
  try {
    const job = await getStore().retryJob(params.jobId);
    if (!job) return jsonError("Trabajo no encontrado", 404);
    try {
      await dispatchWorkerJob({ jobId: job.id, request });
    } catch (dispatchError) {
      console.error("No se pudo despertar el worker para reintento", dispatchError);
      return jsonError("Trabajo reprogramado, pero no se pudo iniciar el procesador", 502);
    }
    return NextResponse.json(job);
  } catch {
    return jsonError("No se pudo reintentar el trabajo", 500);
  }
}
