"use client";

import { AlertTriangle, ArrowLeft, Check, Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { ErrorState, LoadingGrid } from "@/components/project/states";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApi, useCanonicalFields } from "@/hooks/use-api";
import { errorMessage } from "@/lib/api";
import { PLATFORM_LABEL, PLATFORMS } from "@/lib/format";
import { cn } from "@/lib/utils";
import { keys, projectsApi } from "@/services/projects";
import type { FilePreview, Platform, UploadedFile } from "@/types/api";

const IGNORE = "__ignore__";

function ConfidenceMeter({ value, method }: { value: number; method: string }) {
  const pctVal = Math.round(value * 100);
  const tone = method === "manual" ? "bg-primary" : value >= 0.85 ? "bg-emerald-500" : value >= 0.6 ? "bg-amber-500" : "bg-muted-foreground/40";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted" role="meter" aria-valuenow={pctVal} aria-valuemin={0} aria-valuemax={100} aria-label="Mapping confidence">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${pctVal}%` }} />
      </div>
      <span className="w-9 text-xs tabular-nums text-muted-foreground">{method === "unmapped" ? "—" : `${pctVal}%`}</span>
    </div>
  );
}

export default function MappingPage() {
  const { id, fileId } = useParams<{ id: string; fileId: string }>();
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const { data: file, error, mutate: mutateFile } = useApi<UploadedFile>(keys.file(id, fileId));
  const { data: preview } = useApi<FilePreview>(keys.preview(id, fileId));
  const { data: fields } = useCanonicalFields();
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [platform, setPlatform] = useState<Platform | null>(null);
  const [busy, setBusy] = useState<"confirm" | "detect" | null>(null);

  useEffect(() => {
    if (!file) return;
    // Sync local edit state when the server-side mapping (re)loads.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMapping(Object.fromEntries(file.mappings.map((m) => [m.source_column, m.target_field ?? IGNORE])));
    setPlatform(file.platform);
  }, [file]);

  const fieldItems = useMemo(
    () => ({ [IGNORE]: "Ignore column", ...Object.fromEntries((fields ?? []).map((f) => [f.name, f.label])) }),
    [fields],
  );
  const fieldType = useMemo(() => Object.fromEntries((fields ?? []).map((f) => [f.name, f.type])), [fields]);

  const targets = Object.values(mapping).filter((t) => t !== IGNORE);
  const duplicates = new Set(targets.filter((t, i) => targets.indexOf(t) !== i));
  const hasDate = targets.includes("published_at");
  const hasMetric = targets.some((t) => ["number", "duration", "percent"].includes(fieldType[t]));
  const canConfirm = !!platform && hasDate && hasMetric && duplicates.size === 0;

  async function redetect(p: Platform | null) {
    setBusy("detect");
    try {
      await mutateFile(await projectsApi.detectMapping(id, fileId, p), { revalidate: false });
      toast.success("Mapping re-detected");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function confirm() {
    if (!platform) return;
    setBusy("confirm");
    try {
      await projectsApi.confirmMapping(
        id,
        fileId,
        platform,
        Object.entries(mapping).map(([source_column, t]) => ({ source_column, target_field: t === IGNORE ? null : t })),
      );
      await Promise.all([mutate(keys.files(id)), mutateFile()]);
      toast.success("Mapping confirmed");
      router.push(`/projects/${id}/data`);
    } catch (err) {
      toast.error("Mapping not saved", { description: errorMessage(err) });
    } finally {
      setBusy(null);
    }
  }

  if (error) return <ErrorState error={error} />;
  if (!file) return <LoadingGrid rows={1} />;

  const profiles = Object.fromEntries(file.columns.map((c) => [c.name, c]));

  return (
    <div className="space-y-6">
      <Link href={`/projects/${id}/data`} className={buttonVariants({ variant: "ghost", size: "sm" })}>
        <ArrowLeft /> Back to files
      </Link>

      <Card>
        <CardHeader>
          <CardTitle>{file.original_filename}</CardTitle>
          <CardDescription>
            {file.row_count} rows · {file.column_count} columns
            {file.header_row > 0 && ` · header found on row ${file.header_row + 1}`}
            {file.sheet_name && ` · sheet "${file.sheet_name}"`}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-4">
          <div className="space-y-1.5">
            <p className="text-sm font-medium">Platform</p>
            <Select
              items={PLATFORM_LABEL}
              value={platform}
              onValueChange={(v) => setPlatform((v as Platform) ?? null)}
            >
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Select platform" />
              </SelectTrigger>
              <SelectContent>
                {PLATFORMS.map((p) => (
                  <SelectItem key={p} value={p}>
                    {PLATFORM_LABEL[p]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {file.detected_platform && (
            <p className="pb-1.5 text-sm text-muted-foreground">
              Detected {PLATFORM_LABEL[file.detected_platform]} with {Math.round((file.detection_confidence ?? 0) * 100)}%
              confidence
            </p>
          )}
          <Button variant="outline" size="sm" onClick={() => redetect(platform)} disabled={busy !== null} className="mb-0.5">
            {busy === "detect" ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            Re-detect mapping{platform && platform !== file.platform ? ` for ${PLATFORM_LABEL[platform]}` : ""}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Column mapping</CardTitle>
          <CardDescription>
            Each source column is matched to a canonical field by alias and fuzzy matching, checked against the
            column&apos;s values. Low-confidence matches are flagged for review.
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">Source column</TableHead>
                <TableHead>Sample values</TableHead>
                <TableHead>Maps to</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead className="pr-4">Method</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {file.mappings.map((m) => {
                const value = mapping[m.source_column] ?? IGNORE;
                const dup = value !== IGNORE && duplicates.has(value);
                const changed = (m.target_field ?? IGNORE) !== value;
                const prof = profiles[m.source_column];
                return (
                  <TableRow key={m.source_column} className={cn(m.needs_review && !m.confirmed && !changed && "bg-amber-500/5")}>
                    <TableCell className="pl-4 font-medium">
                      <div className="flex items-center gap-1.5">
                        {m.needs_review && !m.confirmed && !changed && (
                          <AlertTriangle className="size-3.5 text-amber-600" aria-label="Needs review" />
                        )}
                        {m.source_column}
                      </div>
                      {prof && (
                        <p className="text-xs font-normal text-muted-foreground">
                          {prof.inferred_type} · {prof.null_pct}% empty
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="max-w-56 truncate text-xs text-muted-foreground" title={prof?.sample_values.join(" | ")}>
                      {prof?.sample_values.slice(0, 3).join(" · ") || "—"}
                    </TableCell>
                    <TableCell>
                      <Select
                        items={fieldItems}
                        value={value}
                        onValueChange={(v) => setMapping((cur) => ({ ...cur, [m.source_column]: v ?? IGNORE }))}
                      >
                        <SelectTrigger size="sm" className={cn("w-52", dup && "border-destructive")} aria-invalid={dup}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="max-h-80">
                          <SelectItem value={IGNORE}>Ignore column</SelectItem>
                          {(fields ?? []).map((f) => (
                            <SelectItem key={f.name} value={f.name}>
                              {f.label}
                              {f.required ? " *" : ""}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {dup && <p className="mt-1 text-xs text-destructive">Mapped more than once</p>}
                    </TableCell>
                    <TableCell>
                      <ConfidenceMeter value={changed ? 1 : m.confidence} method={changed ? "manual" : m.method} />
                    </TableCell>
                    <TableCell className="pr-4">
                      <Badge variant="outline" className="font-normal capitalize">
                        {changed ? "manual" : m.method}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 pt-4">
          <ul className="space-y-0.5 text-sm">
            <li className={hasDate ? "text-muted-foreground" : "text-destructive"}>
              {hasDate ? <Check className="mr-1 inline size-3.5" /> : "• "}A publish date column is mapped (required)
            </li>
            <li className={hasMetric ? "text-muted-foreground" : "text-destructive"}>
              {hasMetric ? <Check className="mr-1 inline size-3.5" /> : "• "}At least one performance metric is mapped
            </li>
            {!platform && <li className="text-destructive">• Select the platform</li>}
          </ul>
          <Button onClick={confirm} disabled={!canConfirm || busy !== null}>
            {busy === "confirm" ? <Loader2 className="animate-spin" /> : <Check />} Confirm mapping
          </Button>
        </div>
      </Card>

      {preview && (
        <Card>
          <CardHeader>
            <CardTitle>Preview</CardTitle>
            <CardDescription>First {preview.rows.length} of {preview.total_rows} rows as parsed from the file.</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  {preview.columns.map((c) => (
                    <TableHead key={c} className="whitespace-nowrap first:pl-4">
                      {c}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {preview.rows.map((r, i) => (
                  <TableRow key={i}>
                    {preview.columns.map((c) => (
                      <TableCell key={c} className="max-w-48 truncate text-xs first:pl-4" title={r[c] ?? ""}>
                        {r[c] ?? ""}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
