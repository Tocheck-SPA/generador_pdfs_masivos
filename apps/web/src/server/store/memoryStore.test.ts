import { beforeEach, describe, expect, it } from "vitest";
import { MemoryStore, stepJob, __resetMemoryStore } from "./memoryStore";
import type { CreateJobInput } from "@/lib/types";

function makeInput(count: number): CreateJobInput {
  return {
    companyId: 254,
    companyName: "Tarragona Retail",
    formId: 100,
    formName: "Inspección Preventiva",
    dateFrom: "2026-07-01",
    dateToExclusive: "2026-08-01",
    evaluationPointIds: [],
    recipients: ["a@tocheck.cl"],
    deliveryMode: "auto",
    includeConsolidatedPdf: false,
    createdByEmail: "a@tocheck.cl",
    responseRefs: Array.from({ length: count }, (_, i) => ({
      responseId: 1000 + i,
      evaluationPointId: 900,
      completedAt: "2026-07-10T10:00:00",
    })),
  };
}

describe("MemoryStore", () => {
  beforeEach(() => __resetMemoryStore());

  it("creates a job that appears in the list as pending", async () => {
    const store = new MemoryStore();
    const { jobId, status } = await store.createJob(makeInput(3));
    expect(status).toBe("pending");

    const jobs = await store.listJobs();
    expect(jobs).toHaveLength(1);
    expect(jobs[0].id).toBe(jobId);
    expect(jobs[0].totalResponses).toBe(3);
    expect(jobs[0].hasDownload).toBe(false);
  });

  it("progresses through the simulated lifecycle to completion", async () => {
    const store = new MemoryStore();
    const { jobId } = await store.createJob(makeInput(3));

    // Drive the simulator deterministically.
    let guard = 0;
    while (stepJob(jobId) && guard < 100) guard += 1;

    const job = await store.getJob(jobId);
    expect(job).not.toBeNull();
    expect(["completed", "completed_with_warnings"]).toContain(job!.status);
    expect(job!.progressPercent).toBe(100);
    expect(job!.processedResponses).toBe(3);
    expect(job!.successfulResponses + job!.failedResponses).toBe(3);
    expect(job!.hasDownload).toBe(true);
  });

  it("never lets progress go backwards", async () => {
    const store = new MemoryStore();
    const { jobId } = await store.createJob(makeInput(30));
    let last = 0;
    let guard = 0;
    do {
      const job = await store.getJob(jobId);
      expect(job!.progressPercent).toBeGreaterThanOrEqual(last);
      last = job!.progressPercent;
      guard += 1;
    } while (stepJob(jobId) && guard < 200);
  });

  it("cancels an active job", async () => {
    const store = new MemoryStore();
    const { jobId } = await store.createJob(makeInput(3));
    stepJob(jobId); // -> fetching_source_data
    const cancelled = await store.cancelJob(jobId);
    expect(cancelled!.status).toBe("cancelled");
  });
});
