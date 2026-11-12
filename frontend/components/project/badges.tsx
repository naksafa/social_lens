import { AlertTriangle, Bot, CircleCheck, Info, ShieldAlert, Sparkles, Workflow } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { PLATFORM_LABEL, platformColor } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Confidence, Severity } from "@/types/api";

const CONFIDENCE_HELP: Record<Confidence, string> = {
  high: "Large sample, statistically significant, meaningful effect size.",
  medium: "Moderate sample or weaker statistical evidence - treat as a strong hint.",
  low: "Small sample or not significant - a hypothesis to test, not a fact.",
};

export function ConfidenceBadge({ level, className }: { level: Confidence; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Badge
            variant="outline"
            className={cn(
              "gap-1 font-normal",
              level === "high" && "border-primary/40 text-primary",
              level === "medium" && "border-amber-500/40 text-amber-700 dark:text-amber-400",
              level === "low" && "text-muted-foreground",
              className,
            )}
          />
        }
      >
        <span
          aria-hidden
          className={cn(
            "size-1.5 rounded-full",
            level === "high" ? "bg-primary" : level === "medium" ? "bg-amber-500" : "bg-muted-foreground/50",
          )}
        />
        {level} confidence
      </TooltipTrigger>
      <TooltipContent className="max-w-64">{CONFIDENCE_HELP[level]}</TooltipContent>
    </Tooltip>
  );
}

const SEVERITY_ICON = { critical: ShieldAlert, high: AlertTriangle, medium: AlertTriangle, low: Info, info: Info };

export function SeverityBadge({ severity }: { severity: Severity | "critical" | "high" | "medium" | "low" }) {
  const Icon = SEVERITY_ICON[severity] ?? Info;
  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1 font-normal capitalize",
        (severity === "critical" || severity === "high") && "border-red-500/40 text-red-700 dark:text-red-400",
        severity === "medium" && "border-amber-500/40 text-amber-700 dark:text-amber-400",
      )}
    >
      <Icon className="size-3" />
      {severity}
    </Badge>
  );
}

export function LevelBadge({ label, level }: { label: string; level: string }) {
  return (
    <Badge variant="secondary" className="font-normal">
      {label}: <span className="font-medium capitalize">{level}</span>
    </Badge>
  );
}

export function PlatformBadge({ platform }: { platform: string | null | undefined }) {
  const p = platform ?? "all";
  return (
    <Badge variant="outline" className="gap-1.5 font-normal">
      {p !== "all" && <span aria-hidden className="size-2 rounded-full" style={{ background: platformColor(p) }} />}
      {PLATFORM_LABEL[p] ?? p}
    </Badge>
  );
}

export function BasisBadge({ basis }: { basis: "data_backed" | "general_best_practice" }) {
  return basis === "data_backed" ? (
    <Badge variant="outline" className="gap-1 font-normal text-emerald-700 dark:text-emerald-400">
      <CircleCheck className="size-3" /> Data-backed
    </Badge>
  ) : (
    <Badge variant="outline" className="gap-1 font-normal text-muted-foreground">
      <Info className="size-3" /> Best practice
    </Badge>
  );
}

export function GeneratedByBadge({ by, model }: { by: "llm" | "rules"; model?: string | null }) {
  return by === "llm" ? (
    <Badge variant="outline" className="gap-1 font-normal">
      <Sparkles className="size-3 text-primary" /> AI{model ? ` · ${model}` : ""}
    </Badge>
  ) : (
    <Tooltip>
      <TooltipTrigger render={<Badge variant="outline" className="gap-1 font-normal" />}>
        <Workflow className="size-3" /> Rule-based engine
      </TooltipTrigger>
      <TooltipContent className="max-w-64">
        Composed deterministically from the analytics and rule-based insights (no AI provider configured). Add an
        API key to get AI-written output.
      </TooltipContent>
    </Tooltip>
  );
}

export function AiIcon() {
  return <Bot className="size-4" />;
}
