import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { FindingsList } from "@/components/analytics/findings-list";
import { Dropzone } from "@/components/project/dropzone";
import { ImpactEffortMatrix } from "@/components/project/impact-effort";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { Finding, Recommendation } from "@/types/api";

const wrap = (ui: ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);

const finding = (id: string, confidence: Finding["confidence"]): Finding => ({
  id,
  category: "format",
  platform: "instagram",
  statement: `Statement ${id}`,
  metric: "er",
  values: {},
  sample_size: 30,
  p_value: 0.01,
  p_adjusted: 0.02,
  effect_size: 0.4,
  effect_size_label: "medium",
  difference_pct: 40,
  method: "Mann-Whitney U",
  confidence,
  confidence_reasons: [],
  limitations: [],
  significant: true,
});

describe("FindingsList", () => {
  it("hides low-confidence findings until requested", () => {
    wrap(<FindingsList findings={[finding("a", "high"), finding("b", "low")]} />);
    expect(screen.getByText("Statement a")).toBeInTheDocument();
    expect(screen.queryByText("Statement b")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Show 1 low-confidence finding/ }));
    expect(screen.getByText("Statement b")).toBeInTheDocument();
  });
});

describe("ImpactEffortMatrix", () => {
  it("numbers recommendations and lists them", () => {
    const rec = (title: string, impact: "high" | "low", effort: "high" | "low"): Recommendation => ({
      title, explanation: "", evidence: "", evidence_refs: [], platform: "all", impact, effort,
      confidence: "high", basis: "data_backed", priority: "high",
    });
    wrap(<ImpactEffortMatrix items={[rec("Quick win", "high", "low"), rec("Big bet", "high", "high")]} />);
    expect(screen.getByText("Quick win")).toBeInTheDocument();
    expect(screen.getByText("Big bet")).toBeInTheDocument();
    expect(screen.getAllByText("1").length).toBeGreaterThan(0);
  });
});

describe("Dropzone", () => {
  it("accepts CSV/XLSX and rejects other files", () => {
    const onFiles = vi.fn();
    const { container } = render(<Dropzone onFiles={onFiles} />);
    const input = container.querySelector("input[type=file]") as HTMLInputElement;
    const good = new File(["a,b"], "ig.csv", { type: "text/csv" });
    const bad = new File(["x"], "notes.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [good, bad] } });
    expect(onFiles).toHaveBeenCalledWith([good]);
    expect(screen.getByText(/Unsupported file type: notes.pdf/)).toBeInTheDocument();
  });
});
