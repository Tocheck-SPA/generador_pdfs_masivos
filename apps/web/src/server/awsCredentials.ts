import { awsCredentialsProvider } from "@vercel/oidc-aws-credentials-provider";
import { getVercelOidcToken } from "@vercel/oidc";

type AwsCredentialsProvider = ReturnType<typeof awsCredentialsProvider> | (() => Promise<{
  accessKeyId: string;
  secretAccessKey: string;
  sessionToken?: string;
}>);

export type WorkerAwsAuthMode = "oidc" | "static" | "default";

/**
 * Credenciales para invocar Lambda / firmar S3 desde Vercel.
 * Preferencia: OIDC (WORKER_AWS_ROLE_ARN) → keys estáticas → default chain.
 * Las keys estáticas no deben quedar en Production si el usuario IAM ya no existe.
 */
export function workerAwsAuthMode(): WorkerAwsAuthMode {
  if (firstEnv("WORKER_AWS_ROLE_ARN", "AWS_ROLE_ARN", "AWS_S3_ROLE_ARN")) return "oidc";
  if (firstEnv("WORKER_AWS_ACCESS_KEY_ID") && firstEnv("WORKER_AWS_SECRET_ACCESS_KEY")) {
    return "static";
  }
  return "default";
}

export function workerAwsCredentials(): AwsCredentialsProvider | undefined {
  const roleArn = firstEnv("WORKER_AWS_ROLE_ARN", "AWS_ROLE_ARN", "AWS_S3_ROLE_ARN");
  if (roleArn) {
    // Vercel docs: aud sts.amazonaws.com para STS AssumeRoleWithWebIdentity.
    return awsCredentialsProvider({
      roleArn,
      audience: "sts.amazonaws.com",
      clientConfig: { region: firstEnv("WORKER_AWS_REGION", "AWS_REGION") || "us-east-1" },
    });
  }

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

  return undefined;
}

export async function oidcClaimHint(): Promise<string> {
  const mode = workerAwsAuthMode();
  try {
    const token = await getVercelOidcToken();
    const payload = decodeJwtPayload(token);
    if (!payload) return ` (auth=${mode})`;
    const iss = payload.iss ?? "?";
    const aud = payload.aud ?? "?";
    const sub = payload.sub ?? "?";
    return ` (auth=${mode}; oidc iss=${iss} aud=${aud} sub=${sub})`;
  } catch {
    return ` (auth=${mode}; oidc token no disponible)`;
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
