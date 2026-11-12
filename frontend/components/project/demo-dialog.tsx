"use client";

import { FlaskConical, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { PlatformBadge } from "@/components/project/badges";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDemoBusinesses } from "@/hooks/use-api";
import { errorMessage } from "@/lib/api";
import { titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";
import { keys, projectsApi } from "@/services/projects";

const DAYS = { "30": "30 days", "60": "60 days", "90": "90 days", "180": "180 days" };

export function DemoDialog({ size = "default" }: { size?: "default" | "lg" }) {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const { data: businesses } = useDemoBusinesses();
  const [open, setOpen] = useState(false);
  const [business, setBusiness] = useState("agency_uae");
  const [days, setDays] = useState("90");
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    try {
      const project = await projectsApi.demo(business, Number(days), Math.floor(Math.random() * 1000));
      await mutate(keys.projects);
      toast.success("Demo project ready", { description: "Synthetic exports were imported, mapped and analyzed." });
      setOpen(false);
      router.push(`/projects/${project.id}`);
    } catch (err) {
      toast.error("Demo generation failed", { description: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size={size} />}>
        <FlaskConical /> Try demo
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Generate a demo project</DialogTitle>
          <DialogDescription>
            Creates realistic synthetic exports in each platform&apos;s native format and runs them through the full
            pipeline: detection, column mapping, validation, normalization and analytics.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          {(businesses ?? []).map((b) => (
            <button
              key={b.key}
              type="button"
              onClick={() => setBusiness(b.key)}
              className={cn(
                "w-full rounded-lg border p-3 text-left transition-colors hover:bg-muted/50",
                business === b.key && "border-primary ring-1 ring-primary",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{b.business_name}</span>
                <span className="text-xs text-muted-foreground">{b.city_market}</span>
              </div>
              <p className="text-xs text-muted-foreground">
                {b.industry} · Goal: {b.marketing_objectives.map(titleCase).slice(0, 2).join(", ")}
              </p>
              <div className="mt-2 flex flex-wrap gap-1">
                {b.platforms.map((p) => (
                  <PlatformBadge key={p} platform={p} />
                ))}
              </div>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <Label htmlFor="demo-days">History</Label>
          <Select items={DAYS} value={days} onValueChange={(v) => v && setDays(v)}>
            <SelectTrigger id="demo-days" className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(DAYS).map(([v, l]) => (
                <SelectItem key={v} value={v}>
                  {l}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <DialogFooter>
          <Button onClick={run} disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : <FlaskConical />}
            {busy ? "Generating & analyzing…" : "Generate demo"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
