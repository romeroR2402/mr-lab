import { CircleCheck, CircleX, Loader2, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Job } from "../../shared/types";
import { call } from "../lib/api";
import { Badge, Button } from "./ui";

/** Sigue un trabajo de larga duración hasta que termina. */
export function useJob(onFinish?: (j: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  const cb = useRef(onFinish);
  cb.current = onFinish;
  useEffect(() => {
    if (!job || job.status !== "running") return;
    const t = setInterval(async () => {
      try {
        const j = await call("jobs.get", { id: job.id });
        setJob(j);
        if (j.status !== "running") cb.current?.(j);
      } catch {
        /* reintento en el siguiente ciclo */
      }
    }, 700);
    return () => clearInterval(t);
  }, [job]);
  return { job, setJob };
}

const STATUS = {
  running: { label: "En curso", tone: "accent" as const },
  done: { label: "Completado", tone: "ok" as const },
  failed: { label: "Falló", tone: "error" as const },
  cancelled: { label: "Cancelado", tone: "muted" as const },
};

export function JobPanel({ job, children }: { job: Job; children?: React.ReactNode }) {
  const pct = job.progress === null ? null : Math.round(job.progress * 100);
  return (
    <div className="rounded-lg border border-lab-line bg-lab-panel2 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm text-white">
          {job.status === "running" ? <Loader2 className="h-4 w-4 animate-spin text-cyan-400" /> :
            job.status === "done" ? <CircleCheck className="h-4 w-4 text-emerald-400" /> : <CircleX className="h-4 w-4 text-rose-400" />}
          {job.title}
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={STATUS[job.status].tone}>{STATUS[job.status].label}</Badge>
          {job.status === "running" && (
            <Button variant="danger" onClick={() => call("jobs.cancel", { id: job.id })}><Square className="h-3.5 w-3.5" /> Cancelar</Button>
          )}
        </div>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded bg-lab-bg">
        <div className={`h-full bg-cyan-400/80 transition-all ${pct === null && job.status === "running" ? "w-1/3 animate-pulse" : ""}`}
          style={pct !== null ? { width: `${pct}%` } : job.status !== "running" ? { width: "100%" } : undefined} />
      </div>
      <div className="mt-2 flex justify-between gap-2 text-xs text-lab-mute">
        <span>{job.phase}{job.detail ? ` · ${job.detail}` : ""}</span>
        {pct !== null && <span className="tabular-nums">{pct}%</span>}
      </div>
      {job.error && <div className="mt-2 text-sm text-rose-300">{job.error}</div>}
      {children}
    </div>
  );
}
