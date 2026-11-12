import { describe, expect, it } from "vitest";

import { compact, formatLabel, num, pct, signedPct, titleCase } from "@/lib/format";

describe("format helpers", () => {
  it("formats numbers and handles missing values", () => {
    expect(compact(15230)).toBe("15.2K");
    expect(compact(null)).toBe("—");
    expect(num(1234.567, 1)).toBe("1,234.6");
    expect(pct(4.256, 2)).toBe("4.26%");
    expect(pct(undefined)).toBe("—");
    expect(signedPct(12.5)).toBe("+12.5%");
    expect(signedPct(-3)).toBe("-3.0%");
  });

  it("labels formats and snake_case values", () => {
    expect(formatLabel("short_video")).toBe("Short videos");
    expect(formatLabel("unknown_kind")).toBe("Unknown Kind");
    expect(titleCase("social_proof")).toBe("Social Proof");
  });
});
