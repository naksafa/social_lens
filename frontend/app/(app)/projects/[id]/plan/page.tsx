"use client";

import { CalendarDays, LayoutList } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PlatformBadge } from "@/components/project/badges";
import { GeneratePanel } from "@/components/project/generate-panel";
import { EmptyState } from "@/components/project/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { usePlan, useStrategy } from "@/hooks/use-api";
import { errorMessage } from "@/lib/api";
import { PLATFORM_LABEL, platformColor } from "@/lib/format";
import { cn } from "@/lib/utils";
import { projectsApi } from "@/services/projects";
import type { ContentPlanEntry } from "@/types/api";

function tomorrow() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}

function CalendarView({ entries, start }: { entries: ContentPlanEntry[]; start: string }) {
  const startDate = new Date(`${start}T00:00:00`);
  const lead = (startDate.getDay() + 6) % 7; // Monday-first grid
  const cells = Array.from({ length: lead + 30 }, (_, i) => (i < lead ? null : i - lead + 1));
  return (
    <div className="overflow-x-auto">
      <div className="grid min-w-[760px] grid-cols-7 gap-1.5">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
          <div key={d} className="pb-1 text-center text-xs font-medium text-muted-foreground">
            {d}
          </div>
        ))}
        {cells.map((day, i) => {
          if (day === null) return <div key={`pad${i}`} />;
          const date = new Date(startDate);
          date.setDate(date.getDate() + day - 1);
          const items = entries.filter((e) => e.day === day);
          return (
            <div key={day} className="min-h-28 rounded-lg border bg-card p-1.5">
              <p className="mb-1 text-[11px] text-muted-foreground">
                {date.toLocaleDateString("en", { month: "short", day: "numeric" })}
              </p>
              <div className="space-y-1">
                {items.map((e, j) => (
                  <div
                    key={j}
                    className="rounded border-l-2 bg-muted/50 px-1.5 py-1 text-[11px] leading-tight"
                    style={{ borderLeftColor: platformColor(e.platform) }}
                    title={`${e.hook}\n\n${e.concept}`}
                  >
                    <p className="font-medium">{e.format}</p>
                    <p className="line-clamp-2 text-muted-foreground">{e.topic}</p>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function PlanPage() {
  const { id } = useParams<{ id: string }>();
  const { data: strategy } = useStrategy(id);
  const { data: plan, mutate: mutatePlan } = usePlan(id);
  const [start, setStart] = useState(tomorrow);
  const [filter, setFilter] = useState<string>("all");
  const [view, setView] = useState<"table" | "calendar">("table");
  const p = plan?.content;

  async function generate(instructions: string, useAi: boolean) {
    try {
      const res = await projectsApi.generatePlan(id, instructions, start, useAi);
      await mutatePlan(res, { revalidate: false });
      toast.success(`Content plan v${res.version} generated`, { description: `${res.content.entries.length} posts scheduled` });
    } catch (err) {
      toast.error("Content plan generation failed", { description: errorMessage(err) });
    }
  }

  const platforms = Array.from(new Set((p?.entries ?? []).map((e) => e.platform)));
  const entries = (p?.entries ?? []).filter((e) => filter === "all" || e.platform === filter);

  return (
    <div className="space-y-6">
      <GeneratePanel
        what="Content plan"
        output={plan}
        onGenerate={generate}
        disabled={!strategy}
        disabledReason={!strategy ? "Generate the strategy first - the plan follows its frequencies and pillar mix." : undefined}
        extra={
          <div className="flex items-center gap-2">
            <Label htmlFor="start" className="text-sm font-normal">
              Starts
            </Label>
            <Input id="start" type="date" value={start} onChange={(e) => setStart(e.target.value)} className="h-8 w-40" />
          </div>
        }
      />

      {!p ? (
        <EmptyState
          icon={CalendarDays}
          title="No content plan yet"
          description="A realistic 30-day calendar: platform, pillar, format, topic, hook, CTA, objective and KPI for every post - plus a bank of content ideas."
        />
      ) : (
        <>
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle>30-day calendar</CardTitle>
                  <CardDescription>{p.plan_summary}</CardDescription>
                </div>
                <div className="flex items-center gap-1 rounded-lg bg-muted p-0.5">
                  <Button variant={view === "table" ? "secondary" : "ghost"} size="sm" onClick={() => setView("table")}>
                    <LayoutList /> Table
                  </Button>
                  <Button variant={view === "calendar" ? "secondary" : "ghost"} size="sm" onClick={() => setView("calendar")}>
                    <CalendarDays /> Calendar
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-2" role="group" aria-label="Filter by platform">
                {["all", ...platforms].map((pl) => (
                  <button
                    key={pl}
                    type="button"
                    onClick={() => setFilter(pl)}
                    aria-pressed={filter === pl}
                    className={cn(
                      "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors",
                      filter === pl ? "border-primary bg-primary/10 text-foreground" : "text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {pl !== "all" && <span aria-hidden className="size-2 rounded-full" style={{ background: platformColor(pl) }} />}
                    {PLATFORM_LABEL[pl] ?? pl}
                    <span className="tabular-nums">
                      {pl === "all" ? p.entries.length : p.entries.filter((e) => e.platform === pl).length}
                    </span>
                  </button>
                ))}
              </div>
            </CardHeader>
            <CardContent className={view === "table" ? "overflow-x-auto p-0" : ""}>
              {view === "calendar" ? (
                <CalendarView entries={entries} start={p.start_date ?? start} />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="pl-4">Date</TableHead>
                      <TableHead>Platform</TableHead>
                      <TableHead>Pillar</TableHead>
                      <TableHead>Format</TableHead>
                      <TableHead>Topic & hook</TableHead>
                      <TableHead>CTA</TableHead>
                      <TableHead className="pr-4">Objective / KPI</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entries.map((e, i) => (
                      <TableRow key={i} className="align-top">
                        <TableCell className="pl-4 whitespace-nowrap">
                          <p className="font-medium">Day {e.day}</p>
                          <p className="text-xs text-muted-foreground">
                            {e.date ? new Date(`${e.date}T00:00:00`).toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" }) : ""}
                          </p>
                        </TableCell>
                        <TableCell>
                          <PlatformBadge platform={e.platform} />
                        </TableCell>
                        <TableCell>{e.pillar}</TableCell>
                        <TableCell>{e.format}</TableCell>
                        <TableCell className="max-w-96 whitespace-normal">
                          <p className="font-medium">{e.topic}</p>
                          <p className="text-sm italic text-muted-foreground">“{e.hook}”</p>
                          <p className="mt-1 text-xs text-muted-foreground">{e.concept}</p>
                        </TableCell>
                        <TableCell className="max-w-40 whitespace-normal text-sm">{e.cta}</TableCell>
                        <TableCell className="pr-4 whitespace-normal">
                          <p className="text-sm">{e.objective}</p>
                          <p className="text-xs text-muted-foreground">{e.kpi}</p>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {p.ideas.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Content ideas</CardTitle>
                <CardDescription>Built on historical patterns and content gaps.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {p.ideas.map((idea, i) => (
                  <div key={i} className="rounded-lg border p-3">
                    <div className="flex flex-wrap items-center gap-1">
                      <PlatformBadge platform={idea.platform} />
                      <Badge variant="outline" className="font-normal">{idea.format}</Badge>
                      <Badge variant="outline" className="font-normal">{idea.pillar}</Badge>
                    </div>
                    <p className="mt-2 font-medium">{idea.title}</p>
                    <p className="text-sm italic text-muted-foreground">“{idea.hook}”</p>
                    <p className="mt-1 text-sm">{idea.concept}</p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      Caption: {idea.caption_direction} · CTA: {idea.cta} · Goal: {idea.goal}
                    </p>
                    <p className="mt-1 text-[11px] text-muted-foreground">Based on: {idea.based_on}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
          {p.notes.length > 0 && <p className="text-xs text-muted-foreground">{p.notes.join(" ")}</p>}
        </>
      )}
    </div>
  );
}
