import { z } from "zod";
import { isValidDateOnly } from "@/lib/dates";

const dateOnly = z
  .string()
  .refine(isValidDateOnly, { message: "Fecha inválida (usa YYYY-MM-DD)" });

const idFromQuery = z
  .string()
  .regex(/^\d+$/, "Identificador inválido")
  .transform((v) => Number.parseInt(v, 10));

export const companyIdQuerySchema = z.object({ companyId: idFromQuery });

export const evaluationPointsQuerySchema = z.object({
  companyId: idFromQuery,
  formId: idFromQuery,
  dateFrom: dateOnly,
  dateTo: dateOnly,
});

export const snapshotStatusQuerySchema = z.object({
  companyId: idFromQuery,
  dateFrom: dateOnly,
  dateTo: dateOnly,
});

export const countBodySchema = z.object({
  companyId: z.number().int().positive(),
  formId: z.number().int().positive(),
  dateFrom: dateOnly,
  dateTo: dateOnly,
  evaluationPointIds: z.array(z.number().int().positive()).default([]),
});

export const deliveryModeSchema = z.enum(["auto", "attachments", "download_link"]);

const emailSchema = z.string().email("Correo inválido");

export const createJobBodySchema = z.object({
  companyId: z.number().int().positive(),
  formId: z.number().int().positive(),
  dateFrom: dateOnly,
  dateTo: dateOnly,
  evaluationPointIds: z.array(z.number().int().positive()).default([]),
  recipients: z.array(emailSchema).min(1, "Agrega al menos un destinatario"),
  deliveryMode: deliveryModeSchema,
  includeConsolidatedPdf: z.boolean().optional().default(false),
});

export type CountBody = z.infer<typeof countBodySchema>;
export type CreateJobBody = z.infer<typeof createJobBodySchema>;
