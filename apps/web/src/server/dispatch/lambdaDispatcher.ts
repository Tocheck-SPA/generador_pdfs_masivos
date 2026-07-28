import { InvokeCommand, LambdaClient } from "@aws-sdk/client-lambda";
import { oidcClaimHint, workerAwsCredentials } from "../awsCredentials";
import type { WorkerDispatchInput, WorkerDispatchResult } from "./types";

let client: LambdaClient | null = null;

function getClient(): LambdaClient {
  if (client) return client;
  // En Vercel, AWS_REGION / varios AWS_* están reservados; usar WORKER_*.
  const credentials = workerAwsCredentials();
  client = new LambdaClient({
    region: required("WORKER_AWS_REGION", "AWS_REGION"),
    ...(credentials ? { credentials } : {}),
  });
  return client;
}

export async function dispatchLambdaJob(
  input: WorkerDispatchInput
): Promise<WorkerDispatchResult> {
  try {
    const result = await getClient().send(new InvokeCommand({
      FunctionName: required("WORKER_LAMBDA_FUNCTION_NAME", "AWS_LAMBDA_FUNCTION_NAME"),
      Qualifier: process.env.WORKER_LAMBDA_QUALIFIER || process.env.AWS_LAMBDA_QUALIFIER || undefined,
      InvocationType: "Event",
      Payload: Buffer.from(JSON.stringify({ schemaVersion: 1, jobId: input.jobId })),
    }));
    if (result.StatusCode !== undefined && result.StatusCode !== 202) {
      throw new Error(`Lambda no aceptó la ejecución (${result.StatusCode}).`);
    }
    return { provider: "aws_lambda", externalExecutionId: result.$metadata.requestId };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const hint = await oidcClaimHint();
    throw new Error(`${message}${hint}`);
  }
}

function env(...names: string[]): string | undefined {
  for (const name of names) {
    const value = process.env[name];
    if (value) return value;
  }
  return undefined;
}

function required(...names: string[]): string {
  const value = env(...names);
  if (!value) throw new Error(`Falta la variable ${names.join(" o ")}.`);
  return value;
}
