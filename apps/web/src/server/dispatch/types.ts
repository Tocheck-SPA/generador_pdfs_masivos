export type WorkerDispatchProvider = "disabled" | "gcp_cloud_run" | "aws_lambda";

export interface WorkerDispatchInput {
  jobId: string;
  request: Request;
}

export interface WorkerDispatchResult {
  provider: WorkerDispatchProvider;
  externalExecutionId?: string;
}

export interface WorkerDispatcher {
  dispatch(input: WorkerDispatchInput): Promise<WorkerDispatchResult>;
}
