"use client";

import { Download, ExternalLink, FileText, Printer } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/project/states";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAnalytics, useAudit, useStrategy } from "@/hooks/use-api";
import { apiBlob, apiUrl, errorMessage } from "@/lib/api";

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const { data: analytics, isLoading } = useAnalytics(id);
  const { data: audit } = useAudit(id);
  const { data: strategy } = useStrategy(id);
  const [pdfBusy, setPdfBusy] = useState(false);
  const url = apiUrl(`/projects/${id}/report`);

  async function downloadPdf() {
    setPdfBusy(true);
    try {
      const blob = await apiBlob(`/projects/${id}/report?format=pdf`);
      const href = URL.createObjectURL(blob);
      Object.assign(document.createElement("a"), { href, download: "sociallens_audit.pdf" }).click();
      URL.revokeObjectURL(href);
    } catch (err) {
      // The report is served by the API (another origin), so the iframe can't be printed from here;
      // open it in a tab where the built-in "Print / Save as PDF" button works.
      toast.info("Server-side PDF unavailable", {
        description: `${errorMessage(err)} Use "Print / Save as PDF" in the report tab.`,
      });
      window.open(url, "_blank", "noopener");
    } finally {
      setPdfBusy(false);
    }
  }

  if (!isLoading && !analytics)
    return <EmptyState icon={FileText} title="No report yet" description="Run an analysis first; the report builds on it." />;

  return (
    <div className="space-y-4">
      <Card size="sm">
        <CardContent className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            Includes analytics{audit ? ", audit" : ""}
            {strategy ? ", strategy and content plan" : ""}.
            {!strategy && " Generate the audit and strategy for the complete report."}
          </p>
          <div className="flex flex-wrap gap-2">
            <a href={url} target="_blank" rel="noreferrer" className={buttonVariants({ variant: "outline", size: "sm" })}>
              <ExternalLink /> Open
            </a>
            <a href={`${url}?download=true`} className={buttonVariants({ variant: "outline", size: "sm" })}>
              <Download /> HTML
            </a>
            <Button size="sm" onClick={downloadPdf} disabled={pdfBusy}>
              <Printer /> PDF
            </Button>
          </div>
        </CardContent>
      </Card>
      <iframe
        src={url}
        title="Audit report"
        className="h-[80vh] w-full rounded-xl border bg-white"
      />
    </div>
  );
}
