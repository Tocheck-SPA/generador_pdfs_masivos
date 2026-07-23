import { describe, expect, it } from "vitest";
import {
  dayRangeInclusive,
  defaultDateRange,
  exclusiveUpperBound,
  isValidDateOnly,
} from "./dates";

describe("dates", () => {
  it("computes the exclusive upper bound (dateTo + 1 day)", () => {
    expect(exclusiveUpperBound("2026-07-31")).toBe("2026-08-01");
    expect(exclusiveUpperBound("2026-07-05")).toBe("2026-07-06");
    // Month/year rollover.
    expect(exclusiveUpperBound("2026-12-31")).toBe("2027-01-01");
    // Leap year.
    expect(exclusiveUpperBound("2028-02-28")).toBe("2028-02-29");
  });

  it("validates YYYY-MM-DD strings and rejects overflow", () => {
    expect(isValidDateOnly("2026-07-01")).toBe(true);
    expect(isValidDateOnly("2026-13-01")).toBe(false);
    expect(isValidDateOnly("2026-02-30")).toBe(false);
    expect(isValidDateOnly("2026/07/01")).toBe(false);
    expect(isValidDateOnly("")).toBe(false);
  });

  it("counts inclusive days in a range", () => {
    expect(dayRangeInclusive("2026-07-01", "2026-07-01")).toBe(1);
    expect(dayRangeInclusive("2026-07-01", "2026-07-31")).toBe(31);
  });

  it("defaults to the first of the month through today", () => {
    const { dateFrom, dateTo } = defaultDateRange(new Date(2026, 6, 23));
    expect(dateFrom).toBe("2026-07-01");
    expect(dateTo).toBe("2026-07-23");
  });

  it("throws on an invalid date for the exclusive bound", () => {
    expect(() => exclusiveUpperBound("nope")).toThrow();
  });
});
