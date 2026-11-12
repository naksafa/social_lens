"use client";

import { useState } from "react";

import { ConfidenceBadge } from "@/components/project/badges";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { num, titleCase } from "@/lib/format";
import type { Finding } from "@/types/api";

/** Statistical findings with their evidence: n, adjusted p, effect size, method and caveats. */
export function FindingsList({ findings, initial = 6 }: { findings: Finding[]; initial?: number }) {
  const [all, setAll] = useState(false);
  const [showLow, setShowLow] = useState(false);
  const visible = findings.filter((f) => showLow || f.confidence !== "low");
  const shown = all ? visible : visible.slice(0, initial);
  const lowCount = findings.filter((f) => f.confidence === "low").length;

  if (!findings.length) return <p className="text-sm text-muted-foreground">No statistical findings for this selection.</p>;
  return (
    <div className="space-y-3">
      <ul className="divide-y">
        {shown.map((f) => (
          <li key={f.id} className="py-3 first:pt-0">
            <p className="text-sm">{f.statement}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <ConfidenceBadge level={f.confidence} />
              <span className="rounded bg-muted px-1.5 py-0.5">{titleCase(f.category)}</span>
              <span>n = {f.sample_size}</span>
              {f.p_adjusted !== null && <span>adj. p = {f.p_adjusted < 0.001 ? "<0.001" : num(f.p_adjusted, 3)}</span>}
              {f.effect_size !== null && (
                <span>
                  effect = {num(f.effect_size, 2)}
                  {f.effect_size_label ? ` (${f.effect_size_label})` : ""}
                </span>
              )}
              <Tooltip>
                <TooltipTrigger render={<button type="button" className="underline decoration-dotted underline-offset-2" />}>
                  method
                </TooltipTrigger>
                <TooltipContent className="max-w-72">
                  <p>{f.method}</p>
                  {f.confidence_reasons.length > 0 && <p className="mt-1">Confidence: {f.confidence_reasons.join("; ")}</p>}
                  {f.limitations.length > 0 && <p className="mt-1">{f.limitations.join(" ")}</p>}
                </TooltipContent>
              </Tooltip>
            </div>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        {visible.length > initial && (
          <Button variant="outline" size="sm" onClick={() => setAll((v) => !v)}>
            {all ? "Show fewer" : `Show all ${visible.length}`}
          </Button>
        )}
        {lowCount > 0 && (
          <Button variant="ghost" size="sm" onClick={() => setShowLow((v) => !v)}>
            {showLow ? "Hide" : "Show"} {lowCount} low-confidence finding{lowCount > 1 ? "s" : ""}
          </Button>
        )}
      </div>
    </div>
  );
}
