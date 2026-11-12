"use client";

import { Info } from "lucide-react";

import { PlatformBadge } from "@/components/project/badges";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { num, pct, platformColor, titleCase } from "@/lib/format";
import type { AnalyticsSections } from "@/types/api";

const QUESTIONS: Record<string, { q: string; fmt: (v: number) => string }> = {
  strongest_relative_engagement: { q: "Strongest engagement relative to its own exposure", fmt: (v) => pct(v, 2) },
  most_traffic: { q: "Generates the most traffic", fmt: (v) => `${num(v)} clicks` },
  most_traffic_efficient: { q: "Most click-efficient", fmt: (v) => `${num(v, 1)} per 1k` },
  strongest_video_retention: { q: "Strongest video retention", fmt: (v) => pct(v, 1) },
  most_consistent_publishing: { q: "Most consistent publishing", fmt: (v) => `${num(v)}/100` },
  strongest_follower_conversion: { q: "Best follower conversion", fmt: (v) => `${num(v, 2)} per 1k` },
};

const DIMENSIONS = ["engagement", "traffic", "growth", "consistency", "video"];

export function CrossPlatformPanel({ cross }: { cross: AnalyticsSections["cross_platform"] }) {
  const under = cross.answers.underutilized;
  return (
    <div className="space-y-6">
      <div className="flex gap-3 rounded-xl border bg-muted/40 p-4 text-sm">
        <Info className="mt-0.5 size-4 shrink-0 text-primary" />
        <p className="text-muted-foreground">{cross.methodology}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(QUESTIONS).map(([key, { q, fmt }]) => {
          const a = cross.answers[key];
          return (
            <Card key={key} size="sm">
              <CardContent className="space-y-2">
                <p className="text-xs text-muted-foreground">{q}</p>
                {a ? (
                  <div className="flex items-center justify-between gap-2">
                    <PlatformBadge platform={a.platform} />
                    <span className="text-lg font-semibold tabular-nums">{a.value !== undefined && a.value !== null ? fmt(a.value) : "—"}</span>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Insufficient data to determine this.</p>
                )}
              </CardContent>
            </Card>
          );
        })}
        <Card size="sm" className={under ? "ring-primary/40" : ""}>
          <CardContent className="space-y-2">
            <p className="text-xs text-muted-foreground">Appears underutilized</p>
            {under ? (
              <>
                <PlatformBadge platform={under.platform} />
                <p className="text-xs text-muted-foreground">{under.reason}</p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No platform stands out.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {cross.normalized_scores.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Relative platform scores</CardTitle>
            <CardDescription>Rank-based 0-100 per dimension (100 = best of your platforms). Not comparable to other accounts.</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Platform</TableHead>
                  {DIMENSIONS.map((d) => (
                    <TableHead key={d} className="text-right">
                      {titleCase(d)}
                    </TableHead>
                  ))}
                  <TableHead className="text-right">Overall</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {cross.normalized_scores.map((r) => (
                  <TableRow key={r.platform}>
                    <TableCell>
                      <PlatformBadge platform={r.platform} />
                    </TableCell>
                    {DIMENSIONS.map((d) => (
                      <TableCell key={d} className="text-right">
                        {r.scores[d] !== undefined ? (
                          <div className="ml-auto flex w-24 items-center justify-end gap-2">
                            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                              <div className="h-full rounded-full" style={{ width: `${r.scores[d]}%`, background: platformColor(r.platform) }} />
                            </div>
                            <span className="w-7 tabular-nums">{r.scores[d]}</span>
                          </div>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    ))}
                    <TableCell className="text-right font-medium tabular-nums">{num(r.overall)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Comparison table</CardTitle>
          <CardDescription>Ratios are within each platform&apos;s own exposure metric.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Platform</TableHead>
                <TableHead>Exposure metric</TableHead>
                <TableHead className="text-right">Share of posts</TableHead>
                <TableHead className="text-right">Posts/wk</TableHead>
                <TableHead className="text-right">Median ER</TableHead>
                <TableHead className="text-right">Clicks / 1k</TableHead>
                <TableHead className="text-right">Follows / 1k</TableHead>
                <TableHead className="text-right">Video completion</TableHead>
                <TableHead>Exposure trend</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cross.platforms.map((r) => (
                <TableRow key={r.platform}>
                  <TableCell>
                    <PlatformBadge platform={r.platform} />
                  </TableCell>
                  <TableCell>{r.exposure_metric ?? "—"}</TableCell>
                  <TableCell className="text-right tabular-nums">{pct(r.share_of_posts_pct, 0)}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(r.posts_per_week, 1)}</TableCell>
                  <TableCell className="text-right tabular-nums">{pct(r.median_er, 2)}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(r.clicks_per_1k_exposure, 1)}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(r.follows_per_1k_exposure, 2)}</TableCell>
                  <TableCell className="text-right tabular-nums">{pct(r.median_video_completion, 1)}</TableCell>
                  <TableCell className="capitalize">{r.exposure_trend?.replace("_", " ") ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
