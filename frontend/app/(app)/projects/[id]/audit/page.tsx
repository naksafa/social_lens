"use client";

import { ClipboardCheck } from "lucide-react";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { AuditPointCard } from "@/components/project/audit-point";
import { PlatformBadge } from "@/components/project/badges";
import { GeneratePanel } from "@/components/project/generate-panel";
import { ImpactEffortMatrix } from "@/components/project/impact-effort";
import { EmptyState } from "@/components/project/states";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAnalytics, useAudit } from "@/hooks/use-api";
import { errorMessage } from "@/lib/api";
import { keys, projectsApi } from "@/services/projects";
import type { AuditPoint } from "@/types/api";

function Section({ title, items, tone }: { title: string; items: AuditPoint[]; tone: "positive" | "negative" | "neutral" }) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
      {items.length ? (
        items.map((p, i) => <AuditPointCard key={p.title + i} p={p} tone={tone} />)
      ) : (
        <p className="text-sm text-muted-foreground">Nothing notable.</p>
      )}
    </div>
  );
}

export default function AuditPage() {
  const { id } = useParams<{ id: string }>();
  const { mutate } = useSWRConfig();
  const { data: analytics } = useAnalytics(id);
  const { data: audit, mutate: mutateAudit } = useAudit(id);
  const a = audit?.content;

  async function generate(instructions: string, useAi: boolean) {
    try {
      const res = await projectsApi.generateAudit(id, instructions, useAi);
      await mutateAudit(res, { revalidate: false });
      await mutate(keys.projects);
      toast.success(`Audit v${res.version} generated`);
    } catch (err) {
      toast.error("Audit generation failed", { description: errorMessage(err) });
    }
  }

  return (
    <div className="space-y-6">
      <GeneratePanel
        what="Audit"
        output={audit}
        onGenerate={generate}
        disabled={!analytics}
        disabledReason={!analytics ? "Run an analysis first." : undefined}
      />

      {!a ? (
        <EmptyState
          icon={ClipboardCheck}
          title="No audit yet"
          description="The audit interprets the verified analytics: strengths, weaknesses, opportunities, content gaps and prioritized actions - each with evidence and confidence."
        />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Executive summary</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="max-w-4xl leading-relaxed">{a.executive_summary}</p>
            </CardContent>
          </Card>

          <Tabs defaultValue="swot">
            <TabsList className="h-auto flex-wrap">
              <TabsTrigger value="swot">Strengths & weaknesses</TabsTrigger>
              <TabsTrigger value="opps">Opportunities & risks</TabsTrigger>
              <TabsTrigger value="content">Content patterns & gaps</TabsTrigger>
              <TabsTrigger value="platforms">Platform breakdown</TabsTrigger>
              <TabsTrigger value="actions">Priority actions</TabsTrigger>
            </TabsList>
            <TabsContent value="swot" className="mt-4 grid gap-6 lg:grid-cols-2">
              <Section title="Strengths" items={a.strengths} tone="positive" />
              <Section title="Weaknesses" items={a.weaknesses} tone="negative" />
            </TabsContent>
            <TabsContent value="opps" className="mt-4 grid gap-6 lg:grid-cols-2">
              <Section title="Opportunities" items={a.opportunities} tone="positive" />
              <Section title="Risks" items={a.risks} tone="negative" />
            </TabsContent>
            <TabsContent value="content" className="mt-4 space-y-6">
              <div className="grid gap-6 lg:grid-cols-2">
                <Section title="Best-performing patterns" items={a.best_content_patterns} tone="positive" />
                <Section title="Worst-performing patterns" items={a.worst_content_patterns} tone="negative" />
              </div>
              <div className="grid gap-6 lg:grid-cols-2">
                <Section title="Content gaps" items={a.content_gaps} tone="neutral" />
                <Section title="Audience insights" items={a.audience_insights} tone="neutral" />
              </div>
            </TabsContent>
            <TabsContent value="platforms" className="mt-4 grid gap-4 lg:grid-cols-2">
              {a.platform_audits.map((pa) => (
                <Card key={pa.platform}>
                  <CardHeader>
                    <CardTitle>
                      <PlatformBadge platform={pa.platform} />
                    </CardTitle>
                    <CardDescription>{pa.summary}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm">
                    <p>{pa.performance_assessment}</p>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <p className="mb-1 text-xs font-medium text-emerald-700 dark:text-emerald-400">Strengths</p>
                        <ul className="list-disc space-y-0.5 pl-4 text-muted-foreground">
                          {pa.strengths.map((x) => <li key={x}>{x}</li>)}
                          {!pa.strengths.length && <li>—</li>}
                        </ul>
                      </div>
                      <div>
                        <p className="mb-1 text-xs font-medium text-amber-700 dark:text-amber-400">Weaknesses</p>
                        <ul className="list-disc space-y-0.5 pl-4 text-muted-foreground">
                          {pa.weaknesses.map((x) => <li key={x}>{x}</li>)}
                          {!pa.weaknesses.length && <li>—</li>}
                        </ul>
                      </div>
                    </div>
                    {pa.data_limitations.length > 0 && (
                      <p className="text-xs text-muted-foreground">Data limitations: {pa.data_limitations.join("; ")}</p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </TabsContent>
            <TabsContent value="actions" className="mt-4 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Impact / effort</CardTitle>
                  <CardDescription>Start top-left: high impact, low effort.</CardDescription>
                </CardHeader>
                <CardContent>
                  <ImpactEffortMatrix items={a.priority_actions} />
                </CardContent>
              </Card>
              <div className="space-y-3">
                {a.priority_actions.map((p, i) => (
                  <AuditPointCard key={p.title + i} p={p} tone="neutral" />
                ))}
              </div>
            </TabsContent>
          </Tabs>

          {a.data_limitations.length > 0 && (
            <Card size="sm">
              <CardContent>
                <p className="text-xs font-medium">Data limitations</p>
                <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
                  {a.data_limitations.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
