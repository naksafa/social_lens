"use client";

import { ArrowRight, CheckCircle2, Circle, Lightbulb, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ConfidenceBadge, PlatformBadge, SeverityBadge } from "@/components/project/badges";
import { StatCard } from "@/components/project/stat-card";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi, useFiles, useInsights, useProject } from "@/hooks/use-api";
import { compact, dateTime, num, OBJECTIVES, pct, PLATFORM_LABEL, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { keys } from "@/services/projects";
import type { AIOutput, AnalyticsRun, AuditContent, ContentPlanContent, StrategyContent } from "@/types/api";

export default function ProjectOverviewPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project } = useProject(id);
  const { data: files } = useFiles(id);
  const { data: runs } = useApi<AnalyticsRun[]>(keys.runs(id));
  const { data: insights } = useInsights(id);
  const { data: audit } = useApi<AIOutput<AuditContent>>(keys.audit(id));
  const { data: strategy } = useApi<AIOutput<StrategyContent>>(keys.strategy(id));
  const { data: plan } = useApi<AIOutput<ContentPlanContent>>(keys.plan(id));

  const run = runs?.find((r) => r.status === "completed");
  const headline = run?.summary.headline;
  const mapped = (files ?? []).some((f) => f.status !== "uploaded");

  const steps = [
    { label: "Upload exports", done: (files?.length ?? 0) > 0, href: "data", hint: "CSV / XLSX from each platform" },
    { label: "Confirm column mapping", done: mapped, href: "data", hint: "Review auto-detected fields" },
    { label: "Import & analyze", done: !!run, href: "data", hint: "KPIs, statistics, rule-based insights" },
    { label: "Generate audit", done: !!audit, href: "audit", hint: "AI interpretation of verified analytics" },
    { label: "Build strategy", done: !!strategy, href: "strategy", hint: "Platform roles, pillars, KPIs" },
    { label: "30-day content plan", done: !!plan, href: "plan", hint: "Calendar and content ideas" },
    { label: "Export report", done: false, href: "report", hint: "HTML / PDF" },
  ];
  const next = steps.find((s) => !s.done) ?? steps[steps.length - 1];
  const top = insights?.insights ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-6">
        {headline ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Posts analyzed" value={compact(headline.total_posts)} sub={`${shortDate(run?.period_start)} – ${shortDate(run?.period_end)}`} />
              <StatCard label="Platforms" value={Object.keys(headline.platforms).length} sub={Object.keys(headline.platforms).map((p) => PLATFORM_LABEL[p]).join(", ")} />
              <StatCard
                label="Statistical findings"
                value={headline.findings.total}
                sub={`${headline.findings.high_confidence} high confidence · ${headline.findings.significant} significant`}
                help="Group comparisons, correlations, trends and regression terms; p-values are Benjamini-Hochberg adjusted."
              />
              <StatCard
                label="Issues flagged"
                value={headline.insight_counts.negative}
                sub={`${headline.insight_counts.high_severity} high severity · ${headline.insight_counts.positive} strengths`}
              />
            </div>
            <Card>
              <CardHeader>
                <CardTitle>Platforms at a glance</CardTitle>
                <CardDescription>Analysis v{run?.analysis_version} · {dateTime(run?.finished_at)}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                {Object.entries(headline.platforms).map(([p, h]) => (
                  <div key={p} className="rounded-lg border p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <PlatformBadge platform={p} />
                      <span className="text-xs text-muted-foreground">{h.posts} posts · {num(h.posts_per_week, 1)}/wk</span>
                    </div>
                    <dl className="grid grid-cols-3 gap-2 text-sm">
                      <div>
                        <dt className="text-xs text-muted-foreground">Median {h.exposure_metric ?? "exposure"}</dt>
                        <dd className="font-medium tabular-nums">{compact(h.median_exposure)}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">Median ER</dt>
                        <dd className="font-medium tabular-nums">{pct(h.median_engagement_rate, 2)}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">Trend</dt>
                        <dd className="font-medium capitalize">{h.exposure_trend?.replace("_", " ") ?? "—"}</dd>
                      </div>
                    </dl>
                  </div>
                ))}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Key insights</CardTitle>
                <CardDescription>Deterministic rules applied to the analytics - before any AI.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {top.slice(0, 6).map((i) => (
                  <div key={i.id} className="flex gap-3">
                    {i.sentiment === "negative" ? (
                      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" />
                    ) : (
                      <Lightbulb className="mt-0.5 size-4 shrink-0 text-primary" />
                    )}
                    <div className="min-w-0 space-y-1">
                      <p className="text-sm font-medium">{i.title}</p>
                      <p className="text-sm text-muted-foreground">{i.description}</p>
                      <div className="flex flex-wrap gap-1">
                        <SeverityBadge severity={i.severity} />
                        <ConfidenceBadge level={i.confidence} />
                      </div>
                    </div>
                  </div>
                ))}
                <Link href={`/projects/${id}/analytics`} className={buttonVariants({ variant: "link", size: "sm" })}>
                  Explore analytics <ArrowRight />
                </Link>
              </CardContent>
            </Card>
          </>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Get started</CardTitle>
              <CardDescription>Upload exports from each platform to run the analysis.</CardDescription>
            </CardHeader>
            <CardContent>
              <Link href={`/projects/${id}/data`} className={buttonVariants()}>
                Upload data <ArrowRight />
              </Link>
            </CardContent>
          </Card>
        )}
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Workflow</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-1">
              {steps.map((s) => {
                const isNext = s === next;
                return (
                  <li key={s.label}>
                    <Link
                      href={`/projects/${id}/${s.href}`}
                      className={cn("flex items-start gap-2.5 rounded-lg px-2 py-1.5 hover:bg-muted/60", isNext && "bg-primary/5")}
                    >
                      {s.done ? (
                        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" />
                      ) : (
                        <Circle className={cn("mt-0.5 size-4 shrink-0", isNext ? "text-primary" : "text-muted-foreground/50")} />
                      )}
                      <span>
                        <span className={cn("block text-sm", isNext && "font-medium text-primary")}>{s.label}</span>
                        <span className="block text-xs text-muted-foreground">{s.hint}</span>
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ol>
          </CardContent>
        </Card>
        {project?.business_profile && (
          <Card>
            <CardHeader>
              <CardTitle>Business context</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Objective</p>
                <p>{project.business_profile.business_objective}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Marketing objectives</p>
                <p>
                  {project.business_profile.marketing_objectives
                    .map((o) => OBJECTIVES.find((x) => x.value === o)?.label ?? o)
                    .join(", ")}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Target audience</p>
                <p>{project.business_profile.target_audience}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Timezone</p>
                <p>{project.timezone}</p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
