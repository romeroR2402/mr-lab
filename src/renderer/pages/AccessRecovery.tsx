import { Blocks, FlaskConical, History, KeyRound, ListChecks, Lock, Play, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";
import type { AccessAnalysis, AccessPlugin, CompatResult, RecoveryOption } from "../../shared/types";
import { Badge, Button, Card, Empty, ErrorBox, KV, PageHeader, Spinner } from "../components/ui";
import { ApiError, call } from "../lib/api";
import { useLab } from "../lib/context";
import { fmtDate, maskId } from "../lib/format";
import { useRpc } from "../lib/hooks";
import type { Tone } from "../lib/labels";
import { AUTH_LABEL, COMM_LABEL } from "../lib/labels";

const RECOV: Record<string, { label: string; tone: Tone }> = {
  likely: { label: "Recuperación probable", tone: "ok" },
  conditional: { label: "Condicionada al titular", tone: "warning" },
  unlikely: { label: "Poco probable", tone: "error" },
  unknown: { label: "Indeterminada", tone: "muted" },
};
const PRESENT: Record<string, { label: string; tone: Tone }> = {
  yes: { label: "Presente", tone: "warning" },
  no: { label: "No configurado", tone: "ok" },
  unknown: { label: "No determinado", tone: "muted" },
};
const RESTR_STATUS: Record<string, string> = { active: "Activa", inactive: "Inactiva", partial: "Parcial", unknown: "Desconocida" };
const SEVERITY: Record<string, { label: string; tone: Tone }> = {
  blocker: { label: "Bloqueante", tone: "error" },
  high: { label: "Alta", tone: "warning" },
  medium: { label: "Media", tone: "info" },
  low: { label: "Baja", tone: "muted" },
  info: { label: "Info", tone: "muted" },
};
const APPLIC: Record<string, { label: string; tone: Tone }> = {
  applicable: { label: "Aplicable", tone: "ok" },
  conditional: { label: "Condicional", tone: "warning" },
  not_applicable: { label: "No aplica", tone: "muted" },
  blocked: { label: "Bloqueada", tone: "error" },
  unknown: { label: "Indeterminada", tone: "muted" },
};
const DATA_LOSS: Record<string, { label: string; tone: Tone }> = {
  none: { label: "Sin pérdida de datos", tone: "ok" },
  possible: { label: "Posible pérdida", tone: "warning" },
  full_wipe: { label: "Borrado total", tone: "error" },
  unknown: { label: "Pérdida desconocida", tone: "muted" },
};
const CHANNEL: Record<string, string> = {
  manufacturer_account: "Cuenta del fabricante",
  device_settings: "Ajustes del dispositivo",
  official_restore: "Restauración oficial",
  backup: "Respaldo",
  vendor_support: "Soporte del fabricante",
  hardware_assist: "Asistencia de hardware",
};
const VERDICT: Record<string, { label: string; tone: Tone }> = {
  compatible: { label: "Compatible", tone: "ok" },
  incompatible: { label: "Incompatible", tone: "error" },
  undetermined: { label: "Sin determinar", tone: "muted" },
};
const CHECK: Record<string, { label: string; tone: Tone }> = {
  pass: { label: "Cumple", tone: "ok" },
  fail: { label: "No cumple", tone: "error" },
  unknown: { label: "Desconocido", tone: "muted" },
  not_applicable: { label: "No aplica", tone: "muted" },
};
const CAPABILITY: Record<string, string> = {
  inspect_auth: "Leer tipo de autenticación",
  inspect_restrictions: "Leer restricciones",
  inspect_encryption: "Leer estado de cifrado",
  evaluate_recovery: "Evaluar vías de recuperación",
  evaluate_compat: "Evaluar compatibilidad",
  document: "Documentar",
  read_diagnostics: "Leer diagnóstico",
};

function OptionCard({ o }: { o: RecoveryOption }) {
  return (
    <div className="rounded-lg border border-lab-line bg-lab-panel2 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-medium text-white">{o.title}</div>
          <div className="text-xs text-lab-mute">{CHANNEL[o.channel] ?? o.channel}</div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge tone={APPLIC[o.applicability].tone}>{APPLIC[o.applicability].label}</Badge>
          <Badge tone={DATA_LOSS[o.dataLoss].tone}>{DATA_LOSS[o.dataLoss].label}</Badge>
        </div>
      </div>
      {o.reason && <p className="mt-2 text-sm text-lab-mute">{o.reason}</p>}
      <div className="mt-3 grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
        {o.requirements.length > 0 && (
          <div>
            <div className="label">Requisitos</div>
            <ul className="list-inside list-disc space-y-0.5 text-lab-text">{o.requirements.map((r) => <li key={r}>{r}</li>)}</ul>
          </div>
        )}
        {o.steps.length > 0 && (
          <div>
            <div className="label">Pasos</div>
            <ol className="list-inside list-decimal space-y-0.5 text-lab-text">{o.steps.map((s) => <li key={s}>{s}</li>)}</ol>
          </div>
        )}
      </div>
      {o.warnings.length > 0 && (
        <div className="mt-3 space-y-0.5 rounded-md border border-amber-500/20 bg-amber-500/5 p-2 text-xs text-amber-200">
          {o.warnings.map((w) => <div key={w}>• {w}</div>)}
        </div>
      )}
      {o.officialUrl && <div className="mt-2 font-mono text-[11px] text-cyan-200/70">Fuente oficial: {o.officialUrl}</div>}
    </div>
  );
}

function CompatCard({ c }: { c: CompatResult }) {
  return (
    <div className="rounded-md border border-lab-line p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="text-sm text-white">{c.title}</div>
        <Badge tone={VERDICT[c.verdict].tone}>{VERDICT[c.verdict].label}</Badge>
      </div>
      <ul className="mt-2 space-y-1 text-xs">
        {c.checks.map((k) => (
          <li key={k.id} className="flex items-center justify-between gap-2">
            <span className="text-lab-mute">{k.label}{k.detail ? ` — ${k.detail}` : ""}</span>
            <Badge tone={CHECK[k.result].tone}>{CHECK[k.result].label}</Badge>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AnalysisView({ a, mask }: { a: AccessAnalysis; mask: boolean }) {
  const r = RECOV[a.recoverability];
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-lab-line bg-lab-panel2 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <KeyRound className="h-6 w-6 text-cyan-300" />
          <div className="flex-1">
            <div className="font-semibold text-white">{a.deviceLabel}</div>
            <div className="text-xs text-lab-mute">Análisis #{a.id} · {fmtDate(a.timestamp)} · {maskId(a.deviceKey.split(":").slice(1).join(":"), mask)}{a.caseId ? ` · Expediente #${a.caseId}` : ""}</div>
          </div>
          <Badge tone={r.tone}>{r.label}</Badge>
        </div>
        <p className="mt-3 text-sm text-lab-text">{a.summary}</p>
      </div>

      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
        <Card title="Mecanismos de autenticación" icon={<Lock className="h-3.5 w-3.5" />}>
          <ul className="divide-y divide-lab-line">
            {a.mechanisms.map((m) => (
              <li key={m.id} className="py-2.5 first:pt-0 last:pb-0">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm text-white">{m.label}</span>
                  <Badge tone={PRESENT[m.present].tone}>{PRESENT[m.present].label}</Badge>
                </div>
                {m.detail && <div className="mt-0.5 text-xs text-lab-mute">{m.detail}</div>}
                {m.source && <div className="mt-0.5 font-mono text-[10px] text-lab-mute/70">Fuente: {m.source}</div>}
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Restricciones del sistema y hardware" icon={<ShieldAlert className="h-3.5 w-3.5" />}>
          <ul className="divide-y divide-lab-line">
            {a.restrictions.map((x) => (
              <li key={x.id} className="py-2.5 first:pt-0 last:pb-0">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm text-white">{x.label}</span>
                  <div className="flex gap-1.5">
                    <Badge tone="muted">{RESTR_STATUS[x.status]}</Badge>
                    <Badge tone={SEVERITY[x.severity].tone}>{SEVERITY[x.severity].label}</Badge>
                  </div>
                </div>
                {x.detail && <div className="mt-0.5 text-xs text-lab-mute">{x.detail}</div>}
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="Vías oficiales de recuperación evaluadas" icon={<ShieldCheck className="h-3.5 w-3.5" />}>
        <div className="grid grid-cols-1 gap-3 2xl:grid-cols-2">{a.options.map((o) => <OptionCard key={o.id} o={o} />)}</div>
      </Card>

      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
        <Card title="Compatibilidad de procedimientos" icon={<ListChecks className="h-3.5 w-3.5" />}>
          {a.compatibility.length ? (
            <div className="space-y-2">{a.compatibility.map((c) => <CompatCard key={c.procedureId} c={c} />)}</div>
          ) : <div className="text-sm text-lab-mute">No hay procedimientos registrados para esta plataforma.</div>}
        </Card>
        <Card title="Hallazgos de módulos de análisis" icon={<FlaskConical className="h-3.5 w-3.5" />}>
          {a.findings.length ? (
            <ul className="space-y-3">
              {a.findings.map((f, i) => (
                <li key={`${f.pluginId}-${i}`}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-sm text-white">{f.title}</span>
                    <Badge tone={SEVERITY[f.severity]?.tone ?? "muted"}>{SEVERITY[f.severity]?.label ?? f.severity}</Badge>
                  </div>
                  <div className="text-[11px] text-cyan-200/70">{f.pluginName}</div>
                  {f.detail && <div className="mt-0.5 text-xs text-lab-mute">{f.detail}</div>}
                  {Object.keys(f.data).length > 0 && (
                    <div className="mt-1.5"><KV items={Object.entries(f.data).filter(([, v]) => v !== null && v !== "").map(([k, v]) => [k, String(v)])} /></div>
                  )}
                </li>
              ))}
            </ul>
          ) : <div className="text-sm text-lab-mute">Sin hallazgos.</div>}
        </Card>
      </div>

      <Card title="Limitaciones y alcance">
        <ul className="list-inside list-disc space-y-1 text-sm text-lab-mute">{a.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        <div className="mt-3 rounded-md border border-cyan-500/20 bg-cyan-500/5 p-3 text-xs text-cyan-100/90">{a.disclaimer}</div>
      </Card>
    </div>
  );
}

function PluginsPanel() {
  const data = useRpc("access.plugins");
  const procs = useRpc("access.procedures");
  const [error, setError] = useState<ApiError | null>(null);
  const toggle = async (p: AccessPlugin) => {
    try {
      await call("access.setPlugin", { id: p.id, enabled: !p.enabled });
      setError(null);
      data.reload();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
    }
  };
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_380px]">
      <Card title="Módulos de análisis (plugins)" icon={<Blocks className="h-3.5 w-3.5" />}
        actions={<Button onClick={data.reload}>Recargar</Button>}>
        <ErrorBox error={error ?? data.error} />
        {data.data ? (
          <ul className="divide-y divide-lab-line">
            {data.data.plugins.map((p) => (
              <li key={p.id} className="py-3 first:pt-0">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm text-white">{p.name} <span className="text-xs text-lab-mute">v{p.version} · {p.author}</span></div>
                    <div className="text-xs text-lab-mute">{p.description}</div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      <Badge tone={p.builtin ? "accent" : "info"}>{p.builtin ? "Integrado" : "Externo"}</Badge>
                      {p.capabilities.map((c) => <Badge key={c} tone="muted">{CAPABILITY[c] ?? c}</Badge>)}
                    </div>
                    {p.error && <div className="mt-1 text-xs text-rose-300">{p.error}</div>}
                  </div>
                  <Button variant={p.enabled ? "primary" : "default"} disabled={!p.loaded} onClick={() => toggle(p)}>
                    {p.enabled ? "Habilitado" : "Deshabilitado"}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        ) : <Spinner />}
      </Card>
      <div className="space-y-4">
        <Card title="Política de módulos">
          <div className="space-y-2 text-xs text-lab-mute">
            <p>Los módulos son de <span className="text-white">solo análisis</span>: reciben una copia de solo lectura del contexto, sin conectores ni ejecución de comandos.</p>
            <p>Un módulo se rechaza si declara capacidades fuera de la lista permitida o si su código describe evasión, descifrado o extracción no autorizada. Los externos inician deshabilitados.</p>
            {data.data && (
              <>
                <div className="label pt-1">Capacidades permitidas</div>
                <div className="flex flex-wrap gap-1">{data.data.allowedCapabilities.map((c) => <Badge key={c} tone="muted">{CAPABILITY[c] ?? c}</Badge>)}</div>
                <div className="label pt-1">Carpeta de módulos externos</div>
                <div className="break-all font-mono text-[11px] text-cyan-200/70">{data.data.directory}</div>
              </>
            )}
          </div>
        </Card>
        <Card title="Procedimientos registrados">
          <ul className="space-y-2 text-sm">
            {procs.data?.map((p) => (
              <li key={p.id}>
                <div className="text-white">{p.title}</div>
                <div className="text-xs text-lab-mute">{p.platforms.join(", ")} · {p.checks.length} precondiciones</div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}

export default function AccessRecovery() {
  const { scan, selectedKey, setSelectedKey, settings, backend } = useLab();
  const mask = settings?.maskIdentifiers ?? false;
  const ready = backend.state === "ready";
  const device = scan?.devices.find((d) => d.key === selectedKey) ?? null;
  const [tab, setTab] = useState<"analysis" | "plugins">("analysis");
  const [caseId, setCaseId] = useState<number | "">("");
  const [analysis, setAnalysis] = useState<AccessAnalysis | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const cases = useRpc("cases.list", {}, { enabled: ready });
  const history = useRpc("access.history", {}, { enabled: ready });

  const run = async () => {
    if (!device) return;
    setRunning(true);
    setError(null);
    try {
      setAnalysis(await call("access.analyze", { deviceKey: device.key, caseId: caseId === "" ? null : caseId }));
      history.reload();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
    } finally {
      setRunning(false);
    }
  };
  const open = async (id: number) => {
    try {
      setAnalysis(await call("access.get", { id }));
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
    }
  };

  return (
    <>
      <PageHeader title="Análisis y recuperación de acceso"
        subtitle="Mecanismos de autenticación, restricciones y vías oficiales de recuperación. Sin evasión."
        actions={<>
          <Button variant={tab === "analysis" ? "primary" : "default"} onClick={() => setTab("analysis")}><KeyRound className="h-4 w-4" /> Análisis</Button>
          <Button variant={tab === "plugins" ? "primary" : "default"} onClick={() => setTab("plugins")}><Blocks className="h-4 w-4" /> Módulos</Button>
        </>} />
      {tab === "plugins" ? <PluginsPanel /> : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[340px_1fr]">
          <div className="space-y-4">
            <Card title="Objetivo" icon={<KeyRound className="h-3.5 w-3.5" />}>
              <div className="space-y-3">
                <div>
                  <label className="label">Dispositivo</label>
                  <select className="input" value={selectedKey ?? ""} onChange={(e) => setSelectedKey(e.target.value || null)}>
                    <option value="">— Seleccione —</option>
                    {scan?.devices.map((d) => <option key={d.key} value={d.key}>{d.label} ({maskId(d.serial, mask)})</option>)}
                  </select>
                </div>
                {device && <div className="text-xs text-lab-mute">{COMM_LABEL[device.commState] ?? device.commState} · {AUTH_LABEL[device.authState] ?? device.authState}</div>}
                <div>
                  <label className="label">Expediente (recomendado)</label>
                  <select className="input" value={caseId} onChange={(e) => setCaseId(e.target.value ? Number(e.target.value) : "")}>
                    <option value="">Sin vincular</option>
                    {cases.data?.filter((c) => !["closed", "completed"].includes(c.status)).map((c) => (
                      <option key={c.id} value={c.id}>{c.folio} · {c.deviceModel || c.deviceType}</option>
                    ))}
                  </select>
                </div>
                <Button variant="primary" onClick={run} disabled={!device || running}>
                  {running ? <Spinner /> : <Play className="h-4 w-4" />} {running ? "Analizando…" : "Analizar acceso"}
                </Button>
                <div className="text-[11px] text-lab-mute">Solo lectura. Se recomienda ejecutar antes un diagnóstico para evaluar pantalla y táctil.</div>
              </div>
            </Card>
            <Card title="Historial" icon={<History className="h-3.5 w-3.5" />}>
              {history.data?.length ? (
                <ul className="max-h-[420px] space-y-1 overflow-y-auto">
                  {history.data.map((h) => (
                    <li key={h.id}>
                      <button onClick={() => open(h.id)}
                        className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-white/5 ${analysis?.id === h.id ? "bg-white/5" : ""}`}>
                        <span className="flex-1 truncate">{h.deviceLabel ?? h.deviceSerial}</span>
                        <Badge tone={RECOV[h.recoverability].tone}>{RECOV[h.recoverability].label}</Badge>
                      </button>
                      <div className="px-2 text-[10px] text-lab-mute">{fmtDate(h.timestamp)}</div>
                    </li>
                  ))}
                </ul>
              ) : <div className="text-sm text-lab-mute">Sin análisis guardados.</div>}
            </Card>
          </div>
          <div className="space-y-4">
            <ErrorBox error={error} />
            {running && !analysis && <Card><div className="flex items-center gap-3 text-sm"><Spinner /> Leyendo mecanismos por interfaces oficiales…</div></Card>}
            {analysis ? <AnalysisView a={analysis} mask={mask} /> : !running && (
              <Card><Empty icon={<KeyRound className="h-8 w-8" />} title="Sin análisis seleccionado">
                Seleccione un dispositivo y ejecute el análisis. Cada ejecución queda en el Registro de evidencias y en el expediente vinculado.
              </Empty></Card>
            )}
          </div>
        </div>
      )}
    </>
  );
}
