"use client";

import { Target } from "lucide-react";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { MixChart } from "@/components/charts/charts";
import { AuditPointCard } from "@/components/project/audit-point";
import { PlatformBadge } from "@/components/project/badges";
import { GeneratePanel } from "@/components/project/generate-panel";
import { ImpactEffortMatrix } from "@/components/project/impact-effort";
import { EmptyState } from "@/components/project/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAudit, useStrategy } from "@/hooks/use-api";
import { errorMessage } from "@/lib/api";
import { PLATFORM_LABEL, titleCase } from "@/lib/format";
import { keys, projectsApi } from "@/services/projects";

const PILLAR_ORDER = ["educational", "promotional", "social_proof", "entertainment", "brand", "community", "other"];

export default function StrategyPage() {
  const { id } = useParams<{ id: string }>();
  const { mutate } = useSWRConfig();
  const { data: audit } = useAudit(id);
  const { data: strategy, mutate: mutateStrategy } = useStrategy(id);
  const s = strategy?.content;

  async function generate(instructions: string, useAi: boolean) {
    try {
      const res = await projectsApi.generateStrategy(id, instructions, useAi);
      await mutateStrategy(res, { revalidate: false });
      await mutate(keys.projects);
      toast.success(`Strategy v${res.version} generated`);
    } catch (err) {
      toast.error("Strategy generation failed", { description: errorMessage(err) });
    }
  }

  const pillarKey = (name: string) => name.toLowerCase().replace(/[\s-]+/g, "_");

  return (
    <div className="space-y-6">
      <GeneratePanel
        what="Strategy"
        output={strategy}
        onGenerate={generate}
        disabled={!audit}
        disabledReason={!audit ? "Generate the audit first - the strategy builds on it." : undefined}
      />

      {!s ? (
        <EmptyState
          icon={Target}
          title="No strategy yet"
          description="A platform-specific strategy: roles, content pillars, posting frequency, formats, CTA and video approach, KPIs and a 30-day action plan."
        />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Strategy summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="max-w-4xl leading-relaxed">{s.strategy_summary}</p>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {s.strategic_objectives.map((o) => (
                  <div key={o.objective} className="rounded-lg border p-3">
                    <p className="text-sm font-medium">{o.objective}</p>
                    <p className="mt-1 text-xs text-muted-foreground">KPI: {o.kpi}</p>
                    <p className="text-xs text-muted-foreground">
                      Target: {o.target} · {o.timeframe}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            {s.platform_strategies.map((p) => (
              <Card key={p.platform}>
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <PlatformBadge platform={p.platform} />
                    <Badge variant="secondary">{p.posting_frequency}</Badge>
                  </div>
                  <CardTitle className="mt-2">{p.role}</CardTitle>
                  <CardDescription>{p.goal}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div className="flex flex-wrap gap-1">
                    {p.formats.map((f) => (
                      <Badge key={f} variant="outline" className="font-normal">
                        {f}
                      </Badge>
                    ))}
                  </div>
                  <MixChart
                    order={PILLAR_ORDER}
                    rows={[{ label: "Target mix", mix: Object.fromEntries(p.content_mix.map((m) => [pillarKey(m.pillar), m.share_pct])) }]}
                  />
                  <dl className="space-y-2">
                    {[
                      ["Hooks", p.hook_guidance],
                      ["CTA", p.cta_approach],
                      ["Video", p.video_guidance],
                      ["Community", p.community_approach],
                      ["Why", p.rationale],
                    ].map(([k, v]) => (
                      <div key={k} className="grid grid-cols-[84px_1fr] gap-2">
                        <dt className="text-xs font-medium text-muted-foreground">{k}</dt>
                        <dd className="text-sm">{v}</dd>
                      </div>
                    ))}
                  </dl>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Content pillars</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {s.content_pillars.map((p) => (
                <div key={p.name} className="rounded-lg border p-3">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{p.name}</p>
                    <Badge variant="secondary">{p.target_share_pct}%</Badge>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">{p.description}</p>
                  <ul className="mt-2 list-disc pl-4 text-xs text-muted-foreground">
                    {p.example_topics.map((t) => (
                      <li key={t}>{t}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Playbook</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              {[
                ["Formats", s.format_strategy],
                ["Video", s.video_strategy],
                ["Captions", s.caption_strategy],
                ["Calls-to-action", s.cta_strategy],
                ["Community", s.community_strategy],
                ["Growth", s.growth_strategy],
                ["Audience", s.audience_strategy],
              ].map(([k, v]) => (
                <div key={k}>
                  <p className="text-xs font-medium text-muted-foreground">{k}</p>
                  <p className="text-sm">{v}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>30-day action plan</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {s.action_plan_30_days.map((w) => (
                <div key={w.week} className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">Week {w.week}</p>
                  <p className="font-medium">{w.focus}</p>
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-muted-foreground">
                    {w.actions.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>KPIs to track</CardTitle>
              <CardDescription>Baselines come from the analytics; targets are relative.</CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>KPI</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead>Definition</TableHead>
                    <TableHead>Baseline</TableHead>
                    <TableHead>Target</TableHead>
                    <TableHead>Review</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {s.measurement_plan.map((k, i) => (
                    <TableRow key={k.kpi + k.platform + i}>
                      <TableCell className="font-medium">{k.kpi}</TableCell>
                      <TableCell>{PLATFORM_LABEL[k.platform] ?? k.platform}</TableCell>
                      <TableCell className="max-w-64 whitespace-normal text-muted-foreground">{k.definition}</TableCell>
                      <TableCell>{k.baseline}</TableCell>
                      <TableCell>{titleCase(k.target_direction)}</TableCell>
                      <TableCell>{k.review_cadence}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recommendations</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <ImpactEffortMatrix items={s.recommendations} />
              {s.recommendations.map((r, i) => (
                <AuditPointCard key={r.title + i} p={r} />
              ))}
              {s.assumptions.length > 0 && (
                <p className="text-xs text-muted-foreground">Assumptions: {s.assumptions.join(" ")}</p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
