import { awsCredentialsProvider } from "@vercel/oidc-aws-credentials-provider";
import { getVercelOidcToken } from "@vercel/oidc";

type AwsCredentialsProvider = ReturnType<typeof awsCredentialsProvider> | (() => Promise<{
  accessKeyId: string;
  secretAccessKey: string;
  sessionToken?: string;
}>);

/**
 * Credenciales para invocar Lambda / firmar S3 desde Vercel.
 * Preferencia: keys estáticas WORKER_AWS_* (QA) → OIDC assume-role → default chain.
 */
export function workerAwsCredentials(): AwsCredentialsProvider | undefined {
  const accessKeyId = firstEnv("WORKER_AWS_ACCESS_KEY_ID");
  const secretAccessKey = firstEnv("WORKER_AWS_SECRET_ACCESS_KEY");
  if (accessKeyId && secretAccessKey) {
    const sessionToken = firstEnv("WORKER_AWS_SESSION_TOKEN");
    return async () => ({
      accessKeyId,
      secretAccessKey,
      ...(sessionToken ? { sessionToken } : {}),
    });
  }

  const roleArn = firstEnv("WORKER_AWS_ROLE_ARN", "AWS_ROLE_ARN", "AWS_S3_ROLE_ARN");
  if (!roleArn) return undefined;

  // Audience por defecto de Vercel (https://vercel.com/<team>).
  // Evitar aud custom hasta que el IdP/trust estén 100% alineados.
  return awsCredentialsProvider({ roleArn });
}

export async function oidcClaimHint(): Promise<string> {
  try {
    const token = await getVercelOidcToken();
    const payload = decodeJwtPayload(token);
    if (!payload) return "";
    const iss = payload.iss ?? "?";
    const aud = payload.aud ?? "?";
    const sub = payload.sub ?? "?";
    return ` (oidc iss=${iss} aud=${aud} sub=${sub})`;
  } catch {
    return " (oidc token no disponible)";
  }
}

function decodeJwtPayload(token: string): Record<string, string> | null {
  const parts = token.split(".");
  if (parts.length < 2) return null;
  try {
    const json = Buffer.from(parts[1], "base64url").toString("utf8");
    return JSON.parse(json) as Record<string, string>;
  } catch {
    return null;
  }
}

function firstEnv(...names: string[]): string | undefined {
  for (const name of names) {
    const value = process.env[name];
    if (value) return value;
  }
  return undefined;
}
