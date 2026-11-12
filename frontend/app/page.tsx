import {
  ArrowRight,
  BarChart3,
  BrainCircuit,
  FileSpreadsheet,
  ShieldCheck,
  Sigma,
  Workflow,
} from "lucide-react";
import Link from "next/link";

import { Brand } from "@/components/brand";
import { DemoDialog } from "@/components/project/demo-dialog";
import { ThemeToggle } from "@/components/theme-toggle";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PIPELINE = [
  { icon: FileSpreadsheet, title: "Ingest", text: "CSV/XLSX exports from Instagram, Facebook, TikTok and LinkedIn, auto-mapped to one schema." },
  { icon: Sigma, title: "Analyze", text: "KPIs, format and pillar performance, timing, trends and statistical tests — computed in Python." },
  { icon: ShieldCheck, title: "Verify", text: "Every finding carries its sample size, evidence and a confidence level before AI sees it." },
  { icon: BrainCircuit, title: "Interpret", text: "An AI strategist turns verified findings into an audit, strategy and 30-day plan — no invented numbers." },
];

const PLATFORMS = ["Instagram", "Facebook", "TikTok", "LinkedIn"];

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-5 md:px-8">
        <Brand />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link href="/dashboard" className={buttonVariants({ variant: "outline" })}>
            Open app
          </Link>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-4xl px-4 pt-16 pb-20 text-center md:pt-24">
          <p className="mx-auto mb-5 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs text-muted-foreground">
            <Workflow className="size-3.5 text-primary" />
            Analytics first. AI second.
          </p>
          <h1 className="text-4xl font-semibold tracking-tight text-balance md:text-6xl">
            Social media audits backed by{" "}
            <span className="text-primary">evidence</span>, not guesswork.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-pretty text-muted-foreground">
            SocialLens AI analyses your content performance across platforms, surfaces statistically
            grounded findings, and turns them into a prioritized marketing strategy.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/dashboard" className={cn(buttonVariants({ size: "lg" }), "px-4")}>
              Get started <ArrowRight />
            </Link>
            <DemoDialog size="lg" />
          </div>
          <div className="mt-10 flex flex-wrap justify-center gap-2 text-xs text-muted-foreground">
            {PLATFORMS.map((p) => (
              <span key={p} className="rounded-md border px-2.5 py-1">
                {p}
              </span>
            ))}
          </div>
        </section>

        <section className="border-t bg-muted/30">
          <div className="mx-auto grid max-w-6xl gap-6 px-4 py-16 sm:grid-cols-2 md:px-8 lg:grid-cols-4">
            {PIPELINE.map(({ icon: Icon, title, text }, i) => (
              <div key={title} className="rounded-xl border bg-card p-5">
                <div className="mb-4 flex items-center justify-between">
                  <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="size-4" />
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">0{i + 1}</span>
                </div>
                <h3 className="font-medium">{title}</h3>
                <p className="mt-1.5 text-sm text-muted-foreground">{text}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-6 text-xs text-muted-foreground md:px-8">
          <span>SocialLens AI</span>
          <span className="flex items-center gap-1.5">
            <BarChart3 className="size-3.5" /> Recommendations are based on available historical data.
          </span>
        </div>
      </footer>
    </div>
  );
}
