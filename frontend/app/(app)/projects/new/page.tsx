"use client";

import { ArrowRight, Check, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useMemo, useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/lib/api";
import { OBJECTIVES, PLATFORM_LABEL, PLATFORMS, platformColor } from "@/lib/format";
import { cn } from "@/lib/utils";
import { keys, projectsApi } from "@/services/projects";
import type { MarketingObjective, Platform } from "@/types/api";

function Field({
  id,
  label,
  hint,
  required,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>
        {label}
        {required && <span className="text-destructive">*</span>}
      </Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function Toggle({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors hover:bg-muted/60",
        active && "border-primary bg-primary/5 text-foreground ring-1 ring-primary",
      )}
    >
      <span
        className={cn(
          "flex size-4 items-center justify-center rounded border",
          active && "border-primary bg-primary text-primary-foreground",
        )}
      >
        {active && <Check className="size-3" />}
      </span>
      {children}
    </button>
  );
}

export default function NewProjectPage() {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const timezones = useMemo(() => {
    try {
      return Intl.supportedValuesOf("timeZone");
    } catch {
      return ["UTC", "Europe/Paris", "Europe/London", "Asia/Dubai", "America/New_York"];
    }
  }, []);
  const [tz, setTz] = useState(() => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [objectives, setObjectives] = useState<MarketingObjective[]>([]);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "").trim();
    const problems: string[] = [];
    if (!platforms.length) problems.push("Select at least one platform.");
    if (!objectives.length) problems.push("Select at least one marketing objective.");
    setErrors(problems);
    if (problems.length) return;

    const budget = get("monthly_budget");
    setBusy(true);
    try {
      const project = await projectsApi.create({
        name: get("name") || `${get("business_name")} social audit`,
        platforms,
        timezone: tz,
        business_profile: {
          business_name: get("business_name"),
          industry: get("industry"),
          country: get("country"),
          city_market: get("city_market") || null,
          products_services: get("products_services"),
          target_audience: get("target_audience"),
          business_objective: get("business_objective"),
          marketing_objectives: objectives,
          competitors: get("competitors")
            .split(",")
            .map((c) => c.trim())
            .filter(Boolean),
          monthly_budget: budget ? Number(budget) : null,
          budget_currency: get("budget_currency").toUpperCase() || null,
          current_posting_frequency: get("current_posting_frequency") || null,
          additional_instructions: get("additional_instructions") || null,
        },
      });
      await mutate(keys.projects);
      toast.success("Project created", { description: "Next: upload your platform exports." });
      router.push(`/projects/${project.id}/data`);
    } catch (err) {
      toast.error("Could not create project", { description: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="New analysis project"
        description="Tell us about the business. This context shapes the audit and strategy - it never changes the analytics."
      />
      <form onSubmit={submit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Business</CardTitle>
            <CardDescription>Who is this audit for?</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <Field id="business_name" label="Business name" required>
              <Input id="business_name" name="business_name" required maxLength={200} placeholder="Falcon Growth Studio" />
            </Field>
            <Field id="industry" label="Industry" required>
              <Input id="industry" name="industry" required maxLength={120} placeholder="Digital marketing agency" />
            </Field>
            <Field id="country" label="Country" required>
              <Input id="country" name="country" required maxLength={80} placeholder="United Arab Emirates" />
            </Field>
            <Field id="city_market" label="City / market">
              <Input id="city_market" name="city_market" maxLength={120} placeholder="Dubai" />
            </Field>
            <div className="sm:col-span-2">
              <Field id="products_services" label="Products / services" required>
                <Textarea id="products_services" name="products_services" required rows={2} maxLength={4000} />
              </Field>
            </div>
            <div className="sm:col-span-2">
              <Field id="target_audience" label="Target audience" required>
                <Textarea
                  id="target_audience"
                  name="target_audience"
                  required
                  rows={2}
                  maxLength={4000}
                  placeholder="e.g. SME founders in the UAE, 28-50"
                />
              </Field>
            </div>
            <div className="sm:col-span-2">
              <Field id="business_objective" label="Business objective" required>
                <Input
                  id="business_objective"
                  name="business_objective"
                  required
                  maxLength={4000}
                  placeholder="e.g. Generate qualified leads for monthly retainers"
                />
              </Field>
            </div>
            <Field id="competitors" label="Competitors" hint="Comma-separated, optional">
              <Input id="competitors" name="competitors" />
            </Field>
            <Field id="current_posting_frequency" label="Current posting frequency">
              <Input id="current_posting_frequency" name="current_posting_frequency" placeholder="e.g. 4x/week on Instagram" />
            </Field>
            <Field id="monthly_budget" label="Monthly marketing budget" hint="Optional">
              <div className="flex gap-2">
                <Input id="monthly_budget" name="monthly_budget" type="number" min={0} step="any" className="flex-1" />
                <Input name="budget_currency" aria-label="Currency" placeholder="USD" maxLength={3} className="w-20 uppercase" />
              </div>
            </Field>
            <Field id="timezone" label="Timezone" hint="Used to interpret post times for day/hour analysis">
              <Select items={Object.fromEntries(timezones.map((t) => [t, t]))} value={tz} onValueChange={(v) => v && setTz(v)}>
                <SelectTrigger id="timezone" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="max-h-72">
                  {timezones.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Goals & platforms</CardTitle>
            <CardDescription>
              The first objective is treated as primary - it weighs double in the performance index.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <p className="mb-2 text-sm font-medium">
                Marketing objectives<span className="text-destructive">*</span>
              </p>
              <div className="flex flex-wrap gap-2">
                {OBJECTIVES.map((o) => (
                  <Toggle
                    key={o.value}
                    active={objectives.includes(o.value)}
                    onClick={() => setObjectives((l) => toggle(l, o.value))}
                  >
                    {o.label}
                    {objectives[0] === o.value && <span className="text-xs text-primary">primary</span>}
                  </Toggle>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-2 text-sm font-medium">
                Platforms<span className="text-destructive">*</span>
              </p>
              <div className="flex flex-wrap gap-2">
                {PLATFORMS.map((p) => (
                  <Toggle key={p} active={platforms.includes(p)} onClick={() => setPlatforms((l) => toggle(l, p))}>
                    <span aria-hidden className="size-2 rounded-full" style={{ background: platformColor(p) }} />
                    {PLATFORM_LABEL[p]}
                  </Toggle>
                ))}
              </div>
            </div>
            <Field
              id="additional_instructions"
              label="Additional instructions for the AI"
              hint='e.g. "We want to position ourselves as premium" or "Do not recommend paid advertising".'
            >
              <Textarea id="additional_instructions" name="additional_instructions" rows={2} maxLength={4000} />
            </Field>
            <Field id="name" label="Project name" hint="Defaults to the business name">
              <Input id="name" name="name" maxLength={200} />
            </Field>
          </CardContent>
        </Card>

        {errors.length > 0 && (
          <ul className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        )}
        <div className="flex justify-end">
          <Button type="submit" size="lg" disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : null}
            Create project & upload data <ArrowRight />
          </Button>
        </div>
      </form>
    </div>
  );
}
