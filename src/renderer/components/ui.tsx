import { AlertTriangle, CircleCheck, CircleDashed, CircleX, Info, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import type { CheckStatus } from "../../shared/types";
import type { Tone } from "../lib/labels";
import { STATUS_LABEL } from "../lib/labels";

const TONE: Record<Tone, string> = {
  ok: "text-emerald-300 bg-emerald-500/10 ring-emerald-500/30",
  warning: "text-amber-300 bg-amber-500/10 ring-amber-500/30",
  error: "text-rose-300 bg-rose-500/10 ring-rose-500/30",
  info: "text-sky-300 bg-sky-500/10 ring-sky-500/30",
  accent: "text-cyan-300 bg-cyan-500/10 ring-cyan-500/30",
  muted: "text-lab-mute bg-white/5 ring-white/10",
};

export function Badge({ tone = "muted", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${TONE[tone]}`}>
      {children}
    </span>
  );
}

export function Dot({ tone }: { tone: Tone }) {
  const c = { ok: "bg-emerald-400", warning: "bg-amber-400", error: "bg-rose-400", info: "bg-sky-400", accent: "bg-cyan-400", muted: "bg-slate-500" }[tone];
  return <span className={`inline-block h-2 w-2 rounded-full ${c} ${tone === "ok" ? "shadow-[0_0_8px] shadow-emerald-400/70" : ""}`} />;
}

export function statusTone(s: CheckStatus): Tone {
  return s === "unavailable" ? "muted" : s;
}

export function StatusIcon({ status, className = "h-4 w-4" }: { status: CheckStatus; className?: string }) {
  switch (status) {
    case "ok": return <CircleCheck className={`${className} text-emerald-400`} />;
    case "warning": return <AlertTriangle className={`${className} text-amber-400`} />;
    case "error": return <CircleX className={`${className} text-rose-400`} />;
    case "info": return <Info className={`${className} text-sky-400`} />;
    default: return <CircleDashed className={`${className} text-lab-mute`} />;
  }
}

export function StatusBadge({ status }: { status: CheckStatus }) {
  return <Badge tone={statusTone(status)}>{STATUS_LABEL[status]}</Badge>;
}

export function Card({ title, icon, actions, children, className = "" }: {
  title?: ReactNode; icon?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-lg border border-lab-line bg-lab-panel/90 shadow-[0_0_0_1px_rgba(0,0,0,0.3)] ${className}`}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-lab-line px-4 py-2.5">
          <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-lab-mute">
            {icon}
            {title}
          </h2>
          <div className="flex items-center gap-2">{actions}</div>
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Button({ children, onClick, variant = "default", disabled, type = "button", title }: {
  children: ReactNode; onClick?: () => void; variant?: "default" | "primary" | "danger" | "ghost";
  disabled?: boolean; type?: "button" | "submit"; title?: string;
}) {
  const v = {
    default: "border-lab-line bg-lab-panel2 hover:border-cyan-500/40 text-lab-text",
    primary: "border-cyan-500/50 bg-cyan-500/15 text-cyan-200 hover:bg-cyan-500/25",
    danger: "border-rose-500/50 bg-rose-500/10 text-rose-200 hover:bg-rose-500/20",
    ghost: "border-transparent text-lab-mute hover:text-lab-text hover:bg-white/5",
  }[variant];
  return (
    <button type={type} title={title} onClick={onClick} disabled={disabled}
      className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition disabled:cursor-not-allowed disabled:opacity-40 ${v}`}>
      {children}
    </button>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return <Loader2 className={`${className} animate-spin text-cyan-400`} />;
}

export function ErrorBox({ error, onRetry }: { error: { code?: string; message: string } | null; onRetry?: () => void }) {
  if (!error) return null;
  return (
    <div className="flex items-start gap-3 rounded-md border border-rose-500/30 bg-rose-500/5 p-3 text-sm text-rose-200">
      <CircleX className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">
        <div>{error.message}</div>
        {error.code && <div className="mt-0.5 font-mono text-[11px] text-rose-300/60">{error.code}</div>}
      </div>
      {onRetry && <Button variant="ghost" onClick={onRetry}>Reintentar</Button>}
    </div>
  );
}

export function Empty({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
      <div className="text-lab-mute/70">{icon}</div>
      <div className="text-sm font-medium text-lab-text">{title}</div>
      {children && <div className="max-w-md text-xs text-lab-mute">{children}</div>}
    </div>
  );
}

export function KV({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[minmax(110px,auto)_1fr] gap-x-4 gap-y-1.5 text-sm">
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-lab-mute">{k}</dt>
          <dd className="min-w-0 break-words font-mono text-[13px] text-lab-text">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-white">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-lab-mute">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2">{actions}</div>
    </div>
  );
}
