import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Recommendation } from "@/types/api";

const LEVELS = ["high", "medium", "low"] as const;

/** 3x3 impact (rows) x effort (columns) matrix of recommendations. */
export function ImpactEffortMatrix({ items }: { items: Recommendation[] }) {
  const effortCols = [...LEVELS].reverse(); // low effort on the left
  return (
    <div className="overflow-x-auto">
      <div className="grid min-w-[480px] grid-cols-[72px_repeat(3,1fr)] gap-1.5 text-xs">
        <div />
        {effortCols.map((e) => (
          <div key={e} className="pb-1 text-center font-medium text-muted-foreground capitalize">
            {e} effort
          </div>
        ))}
        {LEVELS.map((impact) => (
          <div key={impact} className="contents">
            <div className="flex items-center font-medium text-muted-foreground capitalize">{impact} impact</div>
            {effortCols.map((effort) => {
              const cell = items.map((r, i) => ({ r, i })).filter(({ r }) => r.impact === impact && r.effort === effort);
              const quick = impact === "high" && effort === "low";
              return (
                <div
                  key={effort}
                  className={`min-h-16 rounded-lg border p-1.5 ${quick ? "border-primary/40 bg-primary/5" : "bg-muted/30"}`}
                >
                  <div className="flex flex-wrap gap-1">
                    {cell.map(({ r, i }) => (
                      <Tooltip key={i}>
                        <TooltipTrigger
                          render={
                            <span className="flex size-6 cursor-default items-center justify-center rounded-full bg-background text-[11px] font-medium ring-1 ring-border" />
                          }
                        >
                          {i + 1}
                        </TooltipTrigger>
                        <TooltipContent className="max-w-64">{r.title}</TooltipContent>
                      </Tooltip>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <ol className="mt-3 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
        {items.map((r, i) => (
          <li key={i}>
            <span className="font-medium text-foreground">{i + 1}.</span> {r.title}
          </li>
        ))}
      </ol>
    </div>
  );
}
