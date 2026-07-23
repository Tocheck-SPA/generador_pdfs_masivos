import { NextResponse } from "next/server";
import { getStore } from "@/server/store";
import { jsonError, requireSession } from "@/server/api-helpers";

export const runtime = "nodejs";

export async function POST(
  _request: Request,
  { params }: { params: { jobId: string } }
) {
  const gate = await requireSession();
  if (!gate.ok) return gate.response;
  try {
    const job = await getStore().cancelJob(params.jobId);
    if (!job) return jsonError("Trabajo no encontrado", 404);
    return NextResponse.json(job);
  } catch {
    return jsonError("No se pudo cancelar el trabajo", 500);
  }
}
