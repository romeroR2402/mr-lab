import { ClipboardList, FileText, FolderOpen, Hand, History, Play, RotateCcw, ShieldAlert, TriangleAlert, Wrench, X } from "lucide-react";
import { useEffect, useState } from "react";
import type { Job, ServiceOperation, ServicePlan, ServiceResult } from "../../shared/types";
import { JobPanel, useJob } from "../components/JobPanel";
import { Badge, Button, Card, Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { ApiError, bridge, call } from "../lib/api";
import { useLab } from "../lib/context";
import { fmtDate, maskId } from "../lib/format";
import { useRpc } from "../lib/hooks";
import type { Tone } from "../lib/labels";
import { AUTH_LABEL, COMM_LABEL } from "../lib/labels";

const IMPACT_TONE: Record<string, Tone> = { none: "ok", app_data: "warning", full_wipe: "error" };
const CHECK: Record<string, { label: string; tone: Tone }> = {
  pass: { label: "Cumple", tone: "ok" },
  warn: { label: "Advertencia", tone: "warning" },
  fail: { label: "No cumple", tone: "error" },
  unknown: { label: "Sin datos", tone: "muted" },
};

function OperationCard({ op, onPrepare }: { op: ServiceOperation; onPrepare: () => void }) {
  return (
    <div className={`flex flex-col rounded-lg border p-4 ${op.available ? "border-lab-line bg-lab-panel2" : "border-lab-line/50 bg-lab-panel/60"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="font-medium text-white">{op.title}</div>
        <Badge tone={op.kind === "auto" ? "accent" : "info"}>{op.kind === "auto" ? "MR Lab ejecuta" : "Guiada"}</Badge>
      </div>
      <p className="mt-1 flex-1 text-sm text-lab-mute">{op.summary}</p>
      <div className="mt-2 font-mono text-[11px] text-cyan-200/70">{op.method}</div>
      <div className="mt-3 flex items-center justify-between gap-2">
        <Badge tone={IMPACT_TONE[op.impact]}>{op.impactLabel}</Badge>
        <Button variant={op.impact === "full_wipe" ? "danger" : "primary"} onClick={onPrepare} disabled={!op.available}>Preparar</Button>
      </div>
      {!op.available && op.unavailableReason && <div className="mt-2 text-xs text-amber-200/80">{op.unavailableReason}</div>}
    </div>
  );
}

function PlanView({ plan, onClose, onFinished }: { plan: ServicePlan; onClose: () => void; onFinished: () => void }) {
  const op = plan.operation;
  const [acks, setAcks] = useState<string[]>([]);
  const [phrase, setPhrase] = useState("");
  const [guidedResult, setGuidedResult] = useState<"success" | "failure">("success");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<ServiceResult | null>(null);
  const [sending, setSending] = useState(false);
  const { job, setJob } = useJob(() => onFinished());
  const allAcks = plan.acknowledgements.every((a) => acks.includes(a.id));
  const ready = !plan.blocked && allAcks && phrase.trim() === plan.confirmationPhrase && !job && !result;
  const wipe = op.impact === "full_wipe";

  const submit = async () => {
    setError(null);
    setSending(true);
    try {
      if (op.kind === "auto") {
        const j: Job = await call("service.execute", { planId: plan.planId, confirmation: phrase, acknowledged: acks });
        setJob(j);
      } else {
        setResult(await call("service.recordGuided", { planId: plan.planId, confirmation: phrase, acknowledged: acks, result: guidedResult, notes }));
        onFinished();
      }
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
    } finally {
      setSending(false);
    }
  };
  const report = result?.report ?? (job?.result?.report as string | undefined);

  return (
    <Card title={`Plan · ${op.title}`} icon={<ClipboardList className="h-3.5 w-3.5" />}
      actions={<Button variant="ghost" onClick={onClose} title="Cerrar"><X className="h-4 w-4" /></Button>}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge tone={IMPACT_TONE[op.impact]}>{op.impactLabel}</Badge>
          <Badge tone={op.kind === "auto" ? "accent" : "info"}>{op.kind === "auto" ? "Ejecutada por MR Lab" : "Guiada por el técnico"}</Badge>
          <span className="text-lab-mute">{plan.device.label} · <span className="font-mono">{plan.folio}</span></span>
        </div>

        {wipe && (
          <div className="flex gap-3 rounded-lg border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-100">
            <TriangleAlert className="h-6 w-6 shrink-0 text-rose-300" />
            <div>
              <div className="font-semibold text-rose-200">Advertencia de pérdida de datos</div>
              <div className="mt-1">Esta operación borra de forma irreversible todos los datos del usuario. Confirme que existe respaldo o que el titular renuncia a él.</div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div>
            <div className="label">Método oficial</div>
            <div className="text-sm text-white">{op.method}</div>
            {plan.commands.length > 0 && (
              <div className="mt-2 space-y-1">{plan.commands.map((c) => (
                <code key={c} className="block overflow-x-auto rounded bg-lab-bg px-2 py-1 font-mono text-xs text-cyan-200">{c}</code>
              ))}</div>
            )}
            {op.steps.length > 0 && (
              <ol className="mt-3 list-inside list-decimal space-y-1 text-sm text-lab-text">{op.steps.map((s) => <li key={s}>{s}</li>)}</ol>
            )}
          </div>
          <div>
            <div className="label">Comprobaciones previas</div>
            {plan.checks.length ? (
              <ul className="space-y-2">{plan.checks.map((c) => (
                <li key={c.id} className="text-sm">
                  <div className="flex items-center justify-between gap-2"><span className="text-white">{c.label}</span><Badge tone={CHECK[c.result].tone}>{CHECK[c.result].label}</Badge></div>
                  <div className="text-xs text-lab-mute">{c.detail}</div>
                </li>
              ))}</ul>
            ) : <div className="text-sm text-lab-mute">No requiere comprobaciones.</div>}
          </div>
        </div>

        {op.warnings.length > 0 && (
          <div className="space-y-1 rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">
            {op.warnings.map((w) => <div key={w}>• {w}</div>)}
          </div>
        )}

        {plan.blocked ? (
          <div className="rounded-md border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200">
            Operación bloqueada: {plan.blockedReason}
          </div>
        ) : !job && !result && (
          <div className="space-y-3 border-t border-lab-line pt-4">
            <div className="label">Confirmación</div>
            {plan.acknowledgements.map((a) => (
              <label key={a.id} className="flex items-start gap-2 text-sm">
                <input type="checkbox" className="mt-1 accent-cyan-400" checked={acks.includes(a.id)}
                  onChange={() => setAcks(acks.includes(a.id) ? acks.filter((x) => x !== a.id) : [...acks, a.id])} />
                {a.label}
              </label>
            ))}
            {op.kind === "guided" && (
              <div className="grid grid-cols-1 gap-2 md:grid-cols-[200px_1fr]">
                <select className="input" value={guidedResult} onChange={(e) => setGuidedResult(e.target.value as "success" | "failure")}>
                  <option value="success">Terminó correctamente</option>
                  <option value="failure">Falló / no se completó</option>
                </select>
                <input className="input" placeholder="Observaciones del técnico (opcional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
              </div>
            )}
            <div>
              <label className="text-sm text-lab-text" htmlFor="svc-phrase">Escriba <span className="rounded bg-lab-bg px-1.5 py-0.5 font-mono text-cyan-200">{plan.confirmationPhrase}</span> para confirmar</label>
              <input id="svc-phrase" className="input mt-1 font-mono" autoComplete="off" value={phrase} onChange={(e) => setPhrase(e.target.value)} />
            </div>
            <ErrorBox error={error} />
            <Button variant={wipe ? "danger" : "primary"} onClick={submit} disabled={!ready || sending}>
              {sending ? <Spinner /> : op.kind === "auto" ? <Play className="h-4 w-4" /> : <Hand className="h-4 w-4" />}
              {op.kind === "auto" ? (wipe ? "Ejecutar borrado" : "Ejecutar") : "Registrar operación realizada"}
            </Button>
          </div>
        )}

        {job && <JobPanel job={job} />}
        {(result || (job && job.status !== "running")) && (
          <div className={`rounded-md border p-3 text-sm ${result?.status === "failure" || job?.status === "failed" ? "border-rose-500/30 bg-rose-500/5 text-rose-100" : "border-emerald-500/30 bg-emerald-500/5 text-emerald-100"}`}>
            {result ? (result.status === "success" ? "Operación registrada." : "Operación registrada como fallida.") :
              job?.status === "done" ? "Operación completada." : job?.error}
            <div className="mt-1 text-xs opacity-80">Quedó en el Registro de evidencias y en el expediente. El reporte se generó incluso si la operación falló.</div>
            {report && <Button onClick={() => bridge().openPath(report)}><FileText className="h-4 w-4" /> Abrir reporte</Button>}
          </div>
        )}
      </div>
    </Card>
  );
}

export default function ServiceCenter({ group }: { group: "repair" | "reset" }) {
  const { scan, selectedKey, setSelectedKey, settings, backend, navigate } = useLab();
  const ready = backend.state === "ready";
  const mask = settings?.maskIdentifiers ?? false;
  const device = scan?.devices.find((d) => d.key === selectedKey) ?? null;
  const cases = useRpc("cases.list", {}, { enabled: ready });
  const [caseId, setCaseId] = useState<number | "">("");
  const [ops, setOps] = useState<ServiceOperation[] | null>(null);
  const [packages, setPackages] = useState<string[] | null>(null);
  const [pendingOp, setPendingOp] = useState<ServiceOperation | null>(null);
  const [param, setParam] = useState("");
  const [plan, setPlan] = useState<ServicePlan | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const history = useRpc("service.history", caseId === "" ? {} : { caseId }, { enabled: ready });
  const reset = group === "reset";

  useEffect(() => {
    setOps(null);
    setPlan(null);
    setPendingOp(null);
    if (!device) return;
    call("service.operations", { deviceKey: device.key, group }).then((r) => setOps(r.operations)).catch((e) => setError(e));
  }, [device?.key, device?.mode, device?.authState, group]); // eslint-disable-line react-hooks/exhaustive-deps

  const prepare = async (op: ServiceOperation, value?: string) => {
    setError(null);
    if (caseId === "") {
      setError(new ApiError("case_required", "Seleccione el expediente antes de preparar la operación."));
      return;
    }
    if (op.param && value === undefined) {
      setPendingOp(op);
      setParam("");
      if (op.param === "package" && device) {
        try {
          setPackages(await call("service.packages", { deviceKey: device.key }));
        } catch (e) {
          setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
        }
      }
      return;
    }
    setLoading(true);
    try {
      const params = op.param && value ? { [op.param]: value } : {};
      setPlan(await call("service.plan", { deviceKey: device!.key, opId: op.id, caseId: caseId as number, params }));
      setPendingOp(null);
      document.querySelector("main")?.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
    } finally {
      setLoading(false);
    }
  };

  const pickOta = async () => {
    const p = await bridge().pickSource("zip");
    if (p) setParam(p);
  };

  return (
    <>
      <PageHeader
        title={reset ? "Asistente de restauración de fábrica" : "Reparación de sistema"}
        subtitle={reset ? "Restablece el dispositivo solo por métodos del fabricante, con advertencia, confirmación, registro y reporte."
          : "Reinicios de servicio, OTA oficial, limpieza y reinstalación con herramientas oficiales."} />
      {reset && (
        <div className="mb-4 flex gap-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-100">
          <ShieldAlert className="h-5 w-5 shrink-0 text-amber-300" />
          Antes de restablecer: respalde los datos (Recuperación de datos) y confirme que el titular puede acceder a su cuenta Google o Apple ID.
          La protección del fabricante seguirá activa después del borrado.
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[340px_1fr]">
        <div className="space-y-4">
          <Card title="Objetivo" icon={reset ? <RotateCcw className="h-3.5 w-3.5" /> : <Wrench className="h-3.5 w-3.5" />}>
            <div className="space-y-3">
              <div>
                <label className="label" htmlFor="svc-device">Dispositivo</label>
                <select id="svc-device" className="input" value={selectedKey ?? ""} onChange={(e) => setSelectedKey(e.target.value || null)}>
                  <option value="">— Seleccione —</option>
                  {scan?.devices.map((d) => <option key={d.key} value={d.key}>{d.label} ({maskId(d.serial, mask)}) · {d.mode}</option>)}
                </select>
                {device && <div className="mt-1 text-xs text-lab-mute">{COMM_LABEL[device.commState] ?? device.commState} · {AUTH_LABEL[device.authState] ?? device.authState} · modo {device.mode}</div>}
              </div>
              <div>
                <label className="label" htmlFor="svc-case">Expediente (obligatorio)</label>
                <select id="svc-case" className="input" value={caseId} onChange={(e) => setCaseId(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">— Seleccione —</option>
                  {cases.data?.filter((c) => c.status !== "closed").map((c) => <option key={c.id} value={c.id}>{c.folio} · {c.deviceModel || c.deviceType}</option>)}
                </select>
              </div>
              {reset && <Button onClick={() => navigate("data-recovery")}>Respaldar primero</Button>}
            </div>
          </Card>
          <Card title="Operaciones registradas" icon={<History className="h-3.5 w-3.5" />}>
            {history.data?.length ? (
              <ul className="max-h-[420px] space-y-2 overflow-y-auto">
                {history.data.map((h) => (
                  <li key={h.id} className="rounded-md border border-lab-line p-2 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-white">{h.title}</span>
                      <Badge tone={h.status === "success" ? "ok" : "error"}>{h.status === "success" ? "Correcta" : "Fallida"}</Badge>
                    </div>
                    <div className="text-xs text-lab-mute">{h.deviceLabel} · {fmtDate(h.startedAt)} · {h.kind === "auto" ? "ejecutada" : "guiada"}</div>
                    {h.reportPath && (
                      <button className="mt-1 inline-flex items-center gap-1 text-xs text-cyan-300 hover:underline" onClick={() => bridge().openPath(h.reportPath!)}>
                        <FolderOpen className="h-3 w-3" /> Abrir reporte
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            ) : <div className="text-sm text-lab-mute">Sin operaciones{caseId !== "" ? " en este expediente" : ""}.</div>}
          </Card>
        </div>

        <div className="space-y-4">
          <ErrorBox error={error} />
          {plan && <PlanView key={plan.planId} plan={plan} onClose={() => setPlan(null)} onFinished={() => {
            history.reload();
            if (device) call("service.operations", { deviceKey: device.key, group }).then((r) => setOps(r.operations)).catch(() => undefined);
          }} />}

          {pendingOp && (
            <Card title={`Datos para: ${pendingOp.title}`} actions={<Button variant="ghost" onClick={() => setPendingOp(null)}><X className="h-4 w-4" /></Button>}>
              {pendingOp.param === "file" ? (
                <div className="space-y-2">
                  <label className="label" htmlFor="svc-ota">Paquete OTA oficial (.zip)</label>
                  <div className="flex gap-2">
                    <input id="svc-ota" className="input font-mono" value={param} onChange={(e) => setParam(e.target.value)} placeholder="C:\Descargas\ota.zip" />
                    <Button onClick={pickOta}><FolderOpen className="h-4 w-4" /> Elegir</Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <label className="label" htmlFor="svc-pkg">App de terceros</label>
                  {packages ? (
                    <select id="svc-pkg" className="input font-mono" value={param} onChange={(e) => setParam(e.target.value)}>
                      <option value="">— Seleccione —</option>
                      {packages.map((p) => <option key={p} value={p}>{p}</option>)}
                    </select>
                  ) : <Spinner />}
                </div>
              )}
              <div className="mt-3"><Button variant="primary" disabled={!param || loading} onClick={() => prepare(pendingOp, param)}>{loading && <Spinner />} Preparar plan</Button></div>
            </Card>
          )}

          {!device ? (
            <Card><Empty icon={reset ? <RotateCcw className="h-8 w-8" /> : <Wrench className="h-8 w-8" />} title="Seleccione un dispositivo">
              Las operaciones disponibles dependen del modo del dispositivo (normal, recovery, sideload o bootloader) y de su autorización.
            </Empty></Card>
          ) : !ops ? <Spinner /> : (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
              {ops.map((op) => <OperationCard key={op.id} op={op} onPrepare={() => prepare(op)} />)}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
