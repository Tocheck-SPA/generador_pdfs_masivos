import { NextResponse } from "next/server";
import { getStore } from "@/server/store";
import { jsonError, requireSession } from "@/server/api-helpers";

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  { params }: { params: { jobId: string } }
) {
  const gate = await requireSession();
  if (!gate.ok) return gate.response;
  try {
    const url = await getStore().getDownloadUrl(params.jobId);
    if (!url) return jsonError("La descarga aún no está disponible", 404);
    return NextResponse.redirect(url, 302);
  } catch {
    return jsonError("No se pudo obtener la descarga", 500);
  }
}
