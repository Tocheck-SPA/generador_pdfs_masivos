import { getVercelOidcToken } from "@vercel/oidc";
import type { WorkerDispatchInput, WorkerDispatchResult } from "./types";

type TokenResponse = { access_token?: string; accessToken?: string };

export async function dispatchCloudRunJob(
  input: WorkerDispatchInput
): Promise<WorkerDispatchResult> {
  const projectId = required("GCP_PROJECT_ID");
  const region = required("CLOUD_RUN_REGION");
  const jobName = required("CLOUD_RUN_JOB_NAME");
  const accessToken = process.env.GCP_ACCESS_TOKEN || await getGoogleAccessToken();
  const endpoint = `https://run.googleapis.com/v2/projects/${encodeURIComponent(projectId)}` +
    `/locations/${encodeURIComponent(region)}/jobs/${encodeURIComponent(jobName)}:run`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      overrides: {
        containerOverrides: [{ args: ["run-job", "--job-id", input.jobId] }],
      },
    }),
  });
  const body = await response.json().catch(() => ({})) as { name?: string };
  if (!response.ok) throw new Error(`Cloud Run no aceptó la ejecución (${response.status}).`);
  return { provider: "gcp_cloud_run", externalExecutionId: body.name };
}

async function getGoogleAccessToken(): Promise<string> {
  const subjectToken = await getVercelOidcToken();
  const projectNumber = required("GCP_WORKLOAD_IDENTITY_PROJECT_NUMBER");
  const pool = required("GCP_WORKLOAD_IDENTITY_POOL");
  const provider = required("GCP_WORKLOAD_IDENTITY_PROVIDER");
  const serviceAccount = required("GCP_SERVICE_ACCOUNT_EMAIL");
  const audience = `//iam.googleapis.com/projects/${projectNumber}/locations/global/` +
    `workloadIdentityPools/${pool}/providers/${provider}`;

  const exchange = await fetch("https://sts.googleapis.com/v1/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:token-exchange",
      audience,
      scope: "https://www.googleapis.com/auth/cloud-platform",
      requested_token_type: "urn:ietf:params:oauth:token-type:access_token",
      subject_token_type: "urn:ietf:params:oauth:token-type:jwt",
      subject_token: subjectToken,
    }),
  });
  const exchanged = await readToken(exchange, "STS");
  const impersonation = await fetch(
    `https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${encodeURIComponent(serviceAccount)}:generateAccessToken`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${exchanged}`, "Content-Type": "application/json" },
      body: JSON.stringify({ scope: ["https://www.googleapis.com/auth/cloud-platform"] }),
    },
  );
  return readToken(impersonation, "IAM Credentials");
}

async function readToken(response: Response, service: string): Promise<string> {
  const body = await response.json() as TokenResponse;
  const token = body.access_token ?? body.accessToken;
  if (!response.ok || !token) throw new Error(`${service} no entregó un token válido (${response.status}).`);
  return token;
}

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Falta la variable ${name}.`);
  return value;
}
