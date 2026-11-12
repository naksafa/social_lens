"use client";

import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Loader2,
  Play,
  Settings2,
  Trash2,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { PlatformBadge } from "@/components/project/badges";
import { Dropzone } from "@/components/project/dropzone";
import { ErrorState } from "@/components/project/states";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useFiles, useProject } from "@/hooks/use-api";
import { apiBlob, errorMessage } from "@/lib/api";
import { num } from "@/lib/format";
import { keys, projectsApi } from "@/services/projects";
import type { UploadedFile, ValidationIssue } from "@/types/api";

function StatusBadge({ f }: { f: UploadedFile }) {
  const review = f.mappings.filter((m) => m.needs_review && !m.confirmed).length;
  if (f.status === "normalized")
    return (
      <Badge variant="outline" className="gap-1 text-emerald-700 dark:text-emerald-400">
        <CheckCircle2 className="size-3" /> Imported
      </Badge>
    );
  if (f.status === "failed")
    return (
      <Badge variant="outline" className="gap-1 text-destructive">
        <XCircle className="size-3" /> Failed
      </Badge>
    );
  if (f.status === "mapped") return <Badge variant="secondary">Mapping confirmed</Badge>;
  return (
    <Badge variant="outline" className="gap-1 text-amber-700 dark:text-amber-400">
      <AlertTriangle className="size-3" /> {review ? `${review} column(s) to review` : "Confirm mapping"}
    </Badge>
  );
}

function Issues({ issues }: { issues?: ValidationIssue[] }) {
  if (!issues?.length) return <span className="text-xs text-muted-foreground">No issues</span>;
  return (
    <ul className="space-y-0.5 text-xs">
      {issues.slice(0, 4).map((i) => (
        <li
          key={i.code + i.column}
          className={
            i.severity === "error"
              ? "text-destructive"
              : i.severity === "warning"
                ? "text-amber-700 dark:text-amber-400"
                : "text-muted-foreground"
          }
        >
          {i.message}
        </li>
      ))}
      {issues.length > 4 && <li className="text-muted-foreground">+{issues.length - 4} more</li>}
    </ul>
  );
}

export default function DataPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const { data: project } = useProject(id);
  const { data: files, error } = useFiles(id);
  const [uploading, setUploading] = useState(false);
  const [step, setStep] = useState<"idle" | "normalizing" | "analyzing">("idle");

  const refresh = () => Promise.all([mutate(keys.files(id)), mutate(keys.project(id)), mutate(keys.projects)]);
  const pending = (files ?? []).filter((f) => f.status === "uploaded");
  const ready = (files ?? []).filter((f) => ["mapped", "normalized", "failed"].includes(f.status));

  async function upload(list: File[]) {
    setUploading(true);
    try {
      const res = await projectsApi.upload(id, list);
      toast.success(`${res.length} file(s) uploaded`, {
        description: res.map((f) => `${f.original_filename}: ${f.platform ?? "platform not detected"}`).join(" · "),
      });
      await refresh();
    } catch (err) {
      toast.error("Upload failed", { description: errorMessage(err) });
    } finally {
      setUploading(false);
    }
  }

  async function removeFile(f: UploadedFile) {
    if (!confirm(`Remove ${f.original_filename} and its imported posts?`)) return;
    await projectsApi.removeFile(id, f.id).catch((e) => toast.error(errorMessage(e)));
    await refresh();
  }

  async function normalizeAndAnalyze() {
    try {
      setStep("normalizing");
      const norm = await projectsApi.normalize(id);
      const failed = norm.files.filter((f) => f.status !== "normalized");
      if (failed.length) toast.warning(`${failed.length} file(s) could not be imported - see validation details.`);
      await refresh();
      if (!norm.total_posts) return;
      setStep("analyzing");
      const run = await projectsApi.analyze(id);
      toast.success(`Analysis v${run.analysis_version} complete`, {
        description: `${norm.total_posts} posts analyzed in ${num((run.duration_ms ?? 0) / 1000, 1)}s`,
      });
      await Promise.all([refresh(), mutate(keys.analytics(id)), mutate(keys.insights(id))]);
      router.push(`/projects/${id}/analytics`);
    } catch (err) {
      toast.error(step === "analyzing" ? "Analysis failed" : "Import failed", { description: errorMessage(err) });
    } finally {
      setStep("idle");
    }
  }

  async function downloadSample() {
    try {
      const blob = await apiBlob("/demo/dataset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ business: "agency_uae", days: 90, platforms: project?.platforms }),
      });
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement("a"), { href: url, download: "sociallens_sample_exports.zip" });
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Upload platform exports</CardTitle>
          <CardDescription>
            Instagram / Facebook (Meta Business Suite), TikTok Studio and LinkedIn page exports are recognized
            automatically. Other layouts work too - you can correct the column mapping.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Dropzone onFiles={upload} busy={uploading} />
          <button
            type="button"
            onClick={downloadSample}
            className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
          >
            <Download className="size-4" /> No exports at hand? Download synthetic sample files
          </button>
        </CardContent>
      </Card>

      {error ? (
        <ErrorState error={error} />
      ) : files && files.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Files</CardTitle>
            <CardDescription>Review each file&apos;s column mapping, then import and analyze.</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-4">File</TableHead>
                  <TableHead>Platform</TableHead>
                  <TableHead className="text-right">Rows</TableHead>
                  <TableHead className="text-right">Columns</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Validation</TableHead>
                  <TableHead className="pr-4" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {files.map((f) => (
                  <TableRow key={f.id}>
                    <TableCell className="pl-4">
                      <div className="flex items-center gap-2">
                        <FileSpreadsheet className="size-4 shrink-0 text-muted-foreground" />
                        <span className="max-w-56 truncate font-medium" title={f.original_filename}>
                          {f.original_filename}
                        </span>
                      </div>
                      {f.sheet_name && <p className="text-xs text-muted-foreground">Sheet: {f.sheet_name}</p>}
                    </TableCell>
                    <TableCell>
                      {f.platform ? <PlatformBadge platform={f.platform} /> : <Badge variant="outline">Unknown</Badge>}
                      {f.detection_confidence !== null && (
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          detected {Math.round((f.detection_confidence ?? 0) * 100)}%
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {num(f.row_count)}
                      {f.posts_imported !== null && (
                        <p className="text-xs text-muted-foreground">{num(f.posts_imported)} imported</p>
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{f.column_count}</TableCell>
                    <TableCell>
                      <StatusBadge f={f} />
                    </TableCell>
                    <TableCell className="max-w-72 whitespace-normal">
                      <Issues issues={f.validation?.issues} />
                    </TableCell>
                    <TableCell className="pr-4">
                      <div className="flex justify-end gap-1">
                        <Link
                          href={`/projects/${id}/data/${f.id}`}
                          className={buttonVariants({ variant: f.status === "uploaded" ? "default" : "outline", size: "sm" })}
                        >
                          <Settings2 /> Mapping
                        </Link>
                        <Button variant="ghost" size="icon-sm" aria-label="Remove file" onClick={() => removeFile(f)}>
                          <Trash2 />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 pt-4">
            <p className="text-sm text-muted-foreground">
              {pending.length
                ? `${pending.length} file(s) still need a confirmed mapping.`
                : `${ready.length} file(s) ready to import.`}
            </p>
            <Button onClick={normalizeAndAnalyze} disabled={!ready.length || step !== "idle"}>
              {step !== "idle" ? <Loader2 className="animate-spin" /> : <Play />}
              {step === "normalizing" ? "Importing…" : step === "analyzing" ? "Analyzing…" : "Import & run analysis"}
              {step === "idle" && <ArrowRight />}
            </Button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
