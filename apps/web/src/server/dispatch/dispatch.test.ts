import { afterEach, describe, expect, it, vi } from "vitest";
import { dispatchWorkerJob } from "./index";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("worker dispatcher", () => {
  it("does not call infrastructure when disabled", async () => {
    vi.stubEnv("WORKER_DISPATCH_PROVIDER", "disabled");
    const result = await dispatchWorkerJob({
      jobId: "job-1",
      request: new Request("https://example.test/api/jobs"),
    });
    expect(result).toEqual({ provider: "disabled" });
  });

  it("rejects an unknown provider", async () => {
    vi.stubEnv("WORKER_DISPATCH_PROVIDER", "unknown");
    await expect(dispatchWorkerJob({
      jobId: "job-1",
      request: new Request("https://example.test/api/jobs"),
    })).rejects.toThrow("WORKER_DISPATCH_PROVIDER inválido");
  });
});
