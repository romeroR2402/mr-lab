import { Activity, ClipboardCheck, History, MonitorSmartphone, Play, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import type { ScreenAssessment, ScreenCategory, ScreenRecommendation, ScreenSignals } from "../../shared/types";
import { Badge, Button, Card, Empty, ErrorBox, KV, PageHeader, Spinner } from "../components/ui";
import { ApiError, call } from "../lib/api";
import { useLab } from "../lib/context";
import { fmtDate, maskId } from "../lib/format";
import { useRpc } from "../lib/hooks";
import type { Tone } from "../lib/labels";
import { COMM_LABEL, MODULE_LABEL } from "../lib/labels";

export const CATEGORY_TONE: Record<ScreenCategory, Tone> = {
  visible_touch_ok: "ok",
  visible_touch_faulty: "warning",
  partial_display: "warning",
  black_screen: "error",
  no_response: "error",
  undetermined: "muted",
};
const FLAG_STATE: Record<string, { label: string; tone: Tone }> = {
  yes: { label: "Sí", tone: "ok" },
  probable: { label: "Probable", tone: "info" },
  no: { label: "No", tone: "error" },
  unknown: { label: "Desconocido", tone: "muted" },
};
const PRIORITY: Record<number, { label: string; tone: Tone }> = {
  1: { label: "Inmediata", tone: "error" },
  2: { label: "Alta", tone: "warning" },
  3: { label: "Media", tone: "info" },
  4: { label: "Baja", tone: "muted" },
};
const MODULE_PAGE: Record<string, string> = {
  devices: "Detección de dispositivos",
  "access-recovery": "Recuperación de acceso",
  ...MODULE_LABEL,
};

function SignalsPanel({ s }: { s: ScreenSignals }) {
  const v = (x: boolean | null, yes: string, no: string) => (x === null ? "No disponible" : x ? yes : no);
  return (
    <KV items={[
      ["Conectado", s.deviceConnected ? "Sí" : "No (evaluación solo por cuestionario)"],
      ["Comunicación USB", s.commState ? COMM_LABEL[s.commState] ?? s.commState : "No disponible"],
      ["Autorizado", v(s.authorized, "Sí", "No")],
      ["Display (sistema)", s.displayPower ?? "No disponible"],
      ["Controlador táctil", v(s.touchDriver, "Registrado", "No registrado")],
      ["Batería", s.battery ?? "No disponible"],
      ["Diagnóstico usado", s.diagnosticId ? `#${s.diagnosticId}` : "Ninguno"],
    ]} />
  );
}

function RecCard({ r }: { r: ScreenRecommendation }) {
  return (
    <div className="rounded-lg border border-lab-line bg-lab-panel2 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-medium text-white">{r.title}</div>
          <div className="text-xs text-lab-mute">{r.category}</div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge tone={PRIORITY[r.priority].tone}>Prioridad {PRIORITY[r.priority].label.toLowerCase()}</Badge>
          {r.module && (
            <Badge tone={r.implemented ? "accent" : "muted"}>
              {MODULE_PAGE[r.module] ?? r.module}{r.implemented === false ? " · pendiente" : ""}
            </Badge>
          )}
        </div>
      </div>
      <ol className="mt-3 list-inside list-decimal space-y-1 text-sm text-lab-text">{r.steps.map((s) => <li key={s}>{s}</li>)}</ol>
      {r.requirements.length > 0 && (
        <div className="mt-2 text-xs text-lab-mute"><span className="text-lab-text">Requisitos:</span> {r.requirements.join(" · ")}</div>
      )}
      {r.risks.length > 0 && (
        <div className="mt-2 space-y-0.5 rounded-md border border-amber-500/20 bg-amber-500/5 p-2 text-xs text-amber-200">
          {r.risks.map((x) => <div key={x}>• {x}</div>)}
        </div>
      )}
    </div>
  );
}

function ResultView({ a, mask }: { a: ScreenAssessment; mask: boolean }) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-lab-line bg-lab-panel2 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <MonitorSmartphone className="h-6 w-6 text-cyan-300" />
          <div className="flex-1">
            <div className="font-semibold text-white">{a.deviceLabel}</div>
            <div className="text-xs text-lab-mute">
              Evaluación #{a.id} · {fmtDate(a.timestamp)}{a.deviceSerial ? ` · ${maskId(a.deviceSerial, mask)}` : ""}{a.caseId ? ` · Expediente #${a.caseId}` : ""}
            </div>
          </div>
          <Badge tone={CATEGORY_TONE[a.category]}>{a.categoryLabel}</Badge>
        </div>
        <p className="mt-3 text-sm text-lab-text">{a.summary}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {a.flags.map((f) => (
            <span key={f.id} className="inline-flex items-center gap-1.5 text-xs text-lab-mute" title={f.detail ?? ""}>
              {f.label}: <Badge tone={FLAG_STATE[f.state]?.tone ?? "muted"}>{FLAG_STATE[f.state]?.label ?? f.state}</Badge>
            </span>
          ))}
        </div>
      </div>
      {a.notes.length > 0 && (
        <Card title="Observación vs. sistema" icon={<TriangleAlert className="h-3.5 w-3.5" />}>
          <ul className="space-y-2 text-sm">
            {a.notes.map((n) => (
              <li key={n.text} className={n.level === "warning" ? "text-amber-200" : "text-lab-mute"}>• {n.text}</li>
            ))}
          </ul>
        </Card>
      )}
      <Card title={`Recomendaciones técnicas (${a.recommendations.length})`} icon={<ClipboardCheck className="h-3.5 w-3.5" />}>
        <div className="space-y-3">{a.recommendations.map((r) => <RecCard key={r.id} r={r} />)}</div>
      </Card>
      <Card title="Señales del sistema usadas" icon={<Activity className="h-3.5 w-3.5" />}>
        <SignalsPanel s={a.signals} />
      </Card>
    </div>
  );
}

export default function ScreenRecovery() {
  const { scan, selectedKey, setSelectedKey, settings, backend, navigate } = useLab();
  const ready = backend.state === "ready";
  const mask = settings?.maskIdentifiers ?? false;
  const questions = useRpc("screen.questionnaire", undefined, { enabled: ready });
  const cases = useRpc("cases.list", {}, { enabled: ready });
  const history = useRpc("screen.history", {}, { enabled: ready });
  const [mode, setMode] = useState<"device" | "offline">("device");
  const [offlineLabel, setOfflineLabel] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [caseId, setCaseId] = useState<number | "">("");
  const [result, setResult] = useState<ScreenAssessment | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const device = scan?.devices.find((d) => d.key === selectedKey) ?? null;

  useEffect(() => {
    if (questions.data && Object.keys(answers).length === 0) {
      setAnswers(Object.fromEntries(questions.data.map((q) => [q.id, q.default])));
    }
  }, [questions.data, answers]);

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await call("screen.assess", {
        answers,
        deviceKey: mode === "device" ? device?.key ?? null : null,
        deviceLabel: mode === "offline" ? offlineLabel || undefined : undefined,
        caseId: caseId === "" ? null : caseId,
      });
      setResult(res);
      document.querySelector("main")?.scrollTo({ top: 0, behavior: "smooth" });
      history.reload();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
    } finally {
      setRunning(false);
    }
  };
  const open = async (id: number) => {
    try {
      setResult(await call("screen.get", { id }));
      document.querySelector("main")?.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
    }
  };

  return (
    <>
      <PageHeader title="Asistente de pantalla dañada"
        subtitle="Clasifica el caso combinando lo que observa el técnico con lo que reporta el sistema, y propone el plan técnico." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[420px_1fr]">
        <div className="space-y-4">
          <Card title="Dispositivo" icon={<MonitorSmartphone className="h-3.5 w-3.5" />}>
            <div className="space-y-3">
              <div className="flex gap-2">
                <Button variant={mode === "device" ? "primary" : "default"} onClick={() => setMode("device")}>Conectado</Button>
                <Button variant={mode === "offline" ? "primary" : "default"} onClick={() => setMode("offline")}>Sin conexión</Button>
              </div>
              {mode === "device" ? (
                <>
                  <select className="input" value={selectedKey ?? ""} onChange={(e) => setSelectedKey(e.target.value || null)}>
                    <option value="">— Seleccione —</option>
                    {scan?.devices.map((d) => <option key={d.key} value={d.key}>{d.label} ({maskId(d.serial, mask)})</option>)}
                  </select>
                  <div className="text-[11px] text-lab-mute">
                    Se usarán la comunicación USB y el último diagnóstico.{" "}
                    <button className="underline" onClick={() => navigate("diagnostics")}>Ejecutar diagnóstico</button> mejora la clasificación.
                  </div>
                </>
              ) : (
                <>
                  <input className="input" placeholder="Ej.: Galaxy A52 del cliente" value={offlineLabel} onChange={(e) => setOfflineLabel(e.target.value)} />
                  <div className="text-[11px] text-lab-mute">Para equipos que no se detectan (sin respuesta o sin cable de datos).</div>
                </>
              )}
              <div>
                <label className="label">Expediente (recomendado)</label>
                <select className="input" value={caseId} onChange={(e) => setCaseId(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">Sin vincular</option>
                  {cases.data?.filter((c) => !["closed", "completed"].includes(c.status)).map((c) => (
                    <option key={c.id} value={c.id}>{c.folio} · {c.deviceModel || c.deviceType}</option>
                  ))}
                </select>
              </div>
            </div>
          </Card>

          <Card title="Síntomas observados" icon={<ClipboardCheck className="h-3.5 w-3.5" />}>
            <ErrorBox error={questions.error} onRetry={questions.reload} />
            {questions.data ? (
              <div className="space-y-4">
                {questions.data.map((q) => (
                  <fieldset key={q.id}>
                    <legend className="text-sm text-white">{q.label}</legend>
                    {q.help && <div className="text-[11px] text-lab-mute">{q.help}</div>}
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {q.options.map((o) => {
                        const active = answers[q.id] === o.value;
                        return (
                          <button key={o.value} type="button" onClick={() => setAnswers({ ...answers, [q.id]: o.value })}
                            className={`rounded-md border px-2.5 py-1 text-xs transition ${active ? "border-cyan-500/60 bg-cyan-500/15 text-cyan-100" : "border-lab-line text-lab-mute hover:border-cyan-500/30 hover:text-lab-text"}`}>
                            {o.label}
                          </button>
                        );
                      })}
                    </div>
                  </fieldset>
                ))}
                <Button variant="primary" onClick={run} disabled={running || (mode === "device" && !device)}>
                  {running ? <Spinner /> : <Play className="h-4 w-4" />} Evaluar caso
                </Button>
                {mode === "device" && !device && <div className="text-[11px] text-lab-mute">Seleccione un dispositivo o use «Sin conexión».</div>}
              </div>
            ) : <Spinner />}
          </Card>

          <Card title="Historial" icon={<History className="h-3.5 w-3.5" />}>
            {history.data?.length ? (
              <ul className="max-h-[360px] space-y-1 overflow-y-auto">
                {history.data.map((h) => (
                  <li key={h.id}>
                    <button onClick={() => open(h.id)}
                      className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-white/5 ${result?.id === h.id ? "bg-white/5" : ""}`}>
                      <span className="flex-1 truncate">{h.deviceLabel ?? "—"}</span>
                      <Badge tone={CATEGORY_TONE[h.category]}>{h.categoryLabel}</Badge>
                    </button>
                    <div className="px-2 text-[10px] text-lab-mute">{fmtDate(h.timestamp)}</div>
                  </li>
                ))}
              </ul>
            ) : <div className="text-sm text-lab-mute">Sin evaluaciones guardadas.</div>}
          </Card>
        </div>
        <div className="space-y-4">
          <ErrorBox error={error} />
          {result ? <ResultView a={result} mask={mask} /> : (
            <Card><Empty icon={<MonitorSmartphone className="h-8 w-8" />} title="Sin evaluación">
              Responda el cuestionario y pulse «Evaluar caso». La evaluación queda en el Registro de evidencias y en el expediente vinculado.
            </Empty></Card>
          )}
        </div>
      </div>
    </>
  );
}
