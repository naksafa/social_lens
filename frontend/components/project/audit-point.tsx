import { BasisBadge, ConfidenceBadge, LevelBadge, PlatformBadge, SeverityBadge } from "@/components/project/badges";
import { cn } from "@/lib/utils";
import type { AuditPoint, Recommendation } from "@/types/api";

export function AuditPointCard({
  p,
  tone = "neutral",
}: {
  p: AuditPoint | Recommendation;
  tone?: "positive" | "negative" | "neutral";
}) {
  const rec = "priority" in p ? p : null;
  return (
    <div
      className={cn(
        "rounded-lg border border-l-4 bg-card p-4",
        tone === "positive" && "border-l-emerald-500",
        tone === "negative" && "border-l-amber-500",
        tone === "neutral" && "border-l-primary/50",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 className="text-sm font-medium">{p.title}</h4>
        <PlatformBadge platform={p.platform} />
      </div>
      <p className="mt-1 text-sm text-muted-foreground">{p.explanation}</p>
      {p.evidence && p.evidence !== p.explanation && (
        <p className="mt-2 rounded-md bg-muted/60 px-2.5 py-1.5 text-xs">
          <span className="font-medium">Evidence: </span>
          {p.evidence}
        </p>
      )}
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {rec && <SeverityBadge severity={rec.priority} />}
        <LevelBadge label="Impact" level={p.impact} />
        {rec && <LevelBadge label="Effort" level={rec.effort} />}
        <ConfidenceBadge level={p.confidence} />
        <BasisBadge basis={p.basis} />
      </div>
    </div>
  );
}
