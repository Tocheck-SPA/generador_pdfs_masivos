import { InvokeCommand, LambdaClient } from "@aws-sdk/client-lambda";
import { awsCredentialsProvider } from "@vercel/oidc-aws-credentials-provider";
import type { WorkerDispatchInput, WorkerDispatchResult } from "./types";

let client: LambdaClient | null = null;

function getClient(): LambdaClient {
  if (client) return client;
  const roleArn = process.env.AWS_ROLE_ARN;
  client = new LambdaClient({
    region: required("AWS_REGION"),
    ...(roleArn
      ? { credentials: awsCredentialsProvider({ roleArn }) }
      : {}),
  });
  return client;
}

export async function dispatchLambdaJob(
  input: WorkerDispatchInput
): Promise<WorkerDispatchResult> {
  const result = await getClient().send(new InvokeCommand({
    FunctionName: required("AWS_LAMBDA_FUNCTION_NAME"),
    Qualifier: process.env.AWS_LAMBDA_QUALIFIER || undefined,
    InvocationType: "Event",
    Payload: Buffer.from(JSON.stringify({ schemaVersion: 1, jobId: input.jobId })),
  }));
  if (result.StatusCode !== undefined && result.StatusCode !== 202) {
    throw new Error(`Lambda no aceptó la ejecución (${result.StatusCode}).`);
  }
  return { provider: "aws_lambda", externalExecutionId: result.$metadata.requestId };
}

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Falta la variable ${name}.`);
  return value;
}
