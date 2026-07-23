import { describe, expect, it } from "vitest";
import { FixtureSource } from "./fixtureSource";

const COMPANY = 254;
const FORM = 100;

function source(): FixtureSource {
  return new FixtureSource();
}

describe("FixtureSource.countResponses", () => {
  it("counts all responses for a form across the month (all points)", async () => {
    const result = await source().countResponses({
      companyId: COMPANY,
      formId: FORM,
      dateFrom: "2026-07-01",
      dateToExclusive: "2026-08-01",
      evaluationPointIds: [],
    });
    // Form 100 responses: 128483 (900), 128485 (901), 128490 (902) => 3 responses, 3 points.
    expect(result.totalResponses).toBe(3);
    expect(result.totalEvaluationPoints).toBe(3);
  });

  it("filters to a subset of evaluation points", async () => {
    const result = await source().countResponses({
      companyId: COMPANY,
      formId: FORM,
      dateFrom: "2026-07-01",
      dateToExclusive: "2026-08-01",
      evaluationPointIds: [900],
    });
    expect(result.totalResponses).toBe(1);
    expect(result.totalEvaluationPoints).toBe(1);
  });

  it("returns zero when the range excludes everything", async () => {
    const result = await source().countResponses({
      companyId: COMPANY,
      formId: FORM,
      dateFrom: "2026-01-01",
      dateToExclusive: "2026-02-01",
      evaluationPointIds: [],
    });
    expect(result.totalResponses).toBe(0);
    expect(result.totalEvaluationPoints).toBe(0);
  });

  it("excludes a response that falls exactly on the exclusive upper bound", async () => {
    // Response 128483 completedAt = 2026-07-05T10:30:00.
    // Upper bound of 2026-07-05 (exclusive) is 2026-07-05T00:00:00, so it is excluded;
    // it must be included when the bound is 2026-07-06.
    const excluded = await source().countResponses({
      companyId: COMPANY,
      formId: FORM,
      dateFrom: "2026-07-01",
      dateToExclusive: "2026-07-05",
      evaluationPointIds: [],
    });
    const included = await source().countResponses({
      companyId: COMPANY,
      formId: FORM,
      dateFrom: "2026-07-01",
      dateToExclusive: "2026-07-06",
      evaluationPointIds: [],
    });
    expect(excluded.totalResponses).toBe(0);
    expect(included.totalResponses).toBe(1);
  });
});

describe("FixtureSource catalogs", () => {
  it("lists only forms that have responses", async () => {
    const forms = await source().listForms(COMPANY);
    const ids = forms.map((f) => f.id).sort();
    // Form 100 and 101 both have responses in the fixtures.
    expect(ids).toEqual([100, 101]);
  });

  it("lists only evaluation points with responses in range", async () => {
    const points = await source().listEvaluationPoints({
      companyId: COMPANY,
      formId: FORM,
      dateFrom: "2026-07-01",
      dateToExclusive: "2026-08-01",
    });
    expect(points.map((p) => p.id).sort()).toEqual([900, 901, 902]);
  });
});
