"use client";

import { Loader2, ShieldCheck, ShieldQuestion, Sparkles } from "lucide-react";
import { type ReactNode, useState } from "react";

import { GeneratedByBadge } from "@/components/project/badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useHealth } from "@/hooks/use-health";
import { dateTime } from "@/lib/format";
import type { AIOutput, Verification } from "@/types/api";

export function VerificationBadge({ v }: { v?: Verification }) {
  if (!v || v.status === "deterministic") return null;
  const ok = v.status === "verified";
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            className={
              ok
                ? "inline-flex items-center gap-1 text-xs text-emerald-700 dark:text-emerald-400"
                : "inline-flex items-center gap-1 text-xs text-amber-700 dark:text-amber-400"
            }
          />
        }
      >
        {ok ? <ShieldCheck className="size-3.5" /> : <ShieldQuestion className="size-3.5" />}
        {ok ? `All ${v.numbers_checked} numbers verified` : `${v.unverified_count} number(s) to review`}
      </TooltipTrigger>
      <TooltipContent className="max-w-80">
        <p>{v.method}</p>
        {v.issues?.slice(0, 3).map((i) => (
          <p key={i.path} className="mt-1">
            Unmatched {i.unverified_numbers.join(", ")} in “{i.text.slice(0, 80)}…”
          </p>
        ))}
      </TooltipContent>
    </Tooltip>
  );
}

/** Instructions + generate button + provenance of the current output. */
export function GeneratePanel<T extends { _verification?: Verification }>({
  what,
  output,
  onGenerate,
  extra,
  disabled,
  disabledReason,
}: {
  what: string;
  output?: AIOutput<T>;
  onGenerate: (instructions: string, useAi: boolean) => Promise<void>;
  extra?: ReactNode;
  disabled?: boolean;
  disabledReason?: string;
}) {
  const { health } = useHealth();
  const aiAvailable = health.state === "ready" && health.data.ai.status === "ok";
  const [instructions, setInstructions] = useState(output?.user_instructions ?? "");
  const [useAi, setUseAi] = useState(true);
  const [busy, setBusy] = useState(false);

  async function go() {
    setBusy(true);
    try {
      await onGenerate(instructions, aiAvailable && useAi);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {output ? (
              <>
                <span className="font-medium">
                  {what} v{output.version}
                </span>
                <GeneratedByBadge by={output.generated_by} model={output.model} />
                <VerificationBadge v={output.content._verification} />
                <span className="text-xs text-muted-foreground">{dateTime(output.created_at)}</span>
              </>
            ) : (
              <span className="text-muted-foreground">No {what.toLowerCase()} generated yet.</span>
            )}
          </div>
          <Button onClick={go} disabled={busy || disabled} title={disabledReason}>
            {busy ? <Loader2 className="animate-spin" /> : <Sparkles />}
            {busy ? "Generating…" : output ? `Regenerate ${what.toLowerCase()}` : `Generate ${what.toLowerCase()}`}
          </Button>
        </div>
        <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
          <div className="space-y-1.5">
            <Label htmlFor={`instr-${what}`}>Custom instructions (optional)</Label>
            <Textarea
              id={`instr-${what}`}
              rows={2}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder='e.g. "Focus on generating leads", "Analyze our videos more deeply", "Do not recommend paid advertising"'
            />
          </div>
          <div className="space-y-2 pb-1">
            {extra}
            <Label className="flex items-center gap-2 text-sm font-normal">
              <Checkbox checked={aiAvailable && useAi} disabled={!aiAvailable} onCheckedChange={(v) => setUseAi(!!v)} />
              Use AI {aiAvailable ? "" : "(no API key - rule-based engine)"}
            </Label>
          </div>
        </div>
        {busy && aiAvailable && useAi && (
          <p className="text-xs text-muted-foreground">
            The AI is reading the verified analytics summary. This can take a minute or two.
          </p>
        )}
        {disabledReason && disabled && <p className="text-xs text-muted-foreground">{disabledReason}</p>}
      </CardContent>
    </Card>
  );
}
