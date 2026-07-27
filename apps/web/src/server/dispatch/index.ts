import { dispatchCloudRunJob } from "./cloudRunDispatcher";
import { dispatchLambdaJob } from "./lambdaDispatcher";
import type {
  WorkerDispatchInput,
  WorkerDispatchProvider,
  WorkerDispatchResult,
} from "./types";

export type {
  WorkerDispatchInput,
  WorkerDispatchProvider,
  WorkerDispatchResult,
} from "./types";

export async function dispatchWorkerJob(
  input: WorkerDispatchInput
): Promise<WorkerDispatchResult> {
  const provider = configuredProvider();
  if (provider === "disabled") return { provider };
  if (provider === "gcp_cloud_run") return dispatchCloudRunJob(input);
  return dispatchLambdaJob(input);
}

function configuredProvider(): WorkerDispatchProvider {
  const configured = process.env.WORKER_DISPATCH_PROVIDER;
  if (configured === "disabled" || configured === "gcp_cloud_run" || configured === "aws_lambda") {
    return configured;
  }
  if (process.env.CLOUD_RUN_DISPATCH_ENABLED === "true") {
    console.warn("CLOUD_RUN_DISPATCH_ENABLED está obsoleto; usa WORKER_DISPATCH_PROVIDER=gcp_cloud_run.");
    return "gcp_cloud_run";
  }
  if (!configured) return "disabled";
  throw new Error(`WORKER_DISPATCH_PROVIDER inválido: ${configured}`);
}
