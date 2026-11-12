"use client";

import { FileSpreadsheet, Loader2, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

const ACCEPT = [".csv", ".xlsx"];

export function Dropzone({ onFiles, busy }: { onFiles: (files: File[]) => void; busy?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [rejected, setRejected] = useState<string[]>([]);

  function handle(list: FileList | null) {
    if (!list) return;
    const files = Array.from(list);
    const ok = files.filter((f) => ACCEPT.some((ext) => f.name.toLowerCase().endsWith(ext)));
    setRejected(files.filter((f) => !ok.includes(f)).map((f) => f.name));
    if (ok.length) onFiles(ok);
  }

  return (
    <div>
      <button
        type="button"
        disabled={busy}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          handle(e.dataTransfer.files);
        }}
        className={cn(
          "flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
          drag ? "border-primary bg-primary/5" : "hover:border-primary/50 hover:bg-muted/40",
          busy && "pointer-events-none opacity-70",
        )}
      >
        {busy ? (
          <Loader2 className="size-8 animate-spin text-primary" />
        ) : (
          <UploadCloud className="size-8 text-muted-foreground" />
        )}
        <p className="font-medium">{busy ? "Uploading & profiling…" : "Drop CSV / XLSX exports here"}</p>
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <FileSpreadsheet className="size-4" /> One or many files - different platforms are detected automatically
        </p>
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPT.join(",")}
        className="hidden"
        onChange={(e) => {
          handle(e.target.files);
          e.target.value = "";
        }}
      />
      {rejected.length > 0 && (
        <p className="mt-2 text-sm text-destructive">Unsupported file type: {rejected.join(", ")} (CSV or XLSX only)</p>
      )}
    </div>
  );
}
