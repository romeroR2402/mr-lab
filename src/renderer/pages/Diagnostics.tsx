import { Activity, History, Play } from "lucide-react";
import { useState } from "react";
import type { DiagnosticReport } from "../../shared/types";
import { Badge, Button, Card, Empty, ErrorBox, KV, PageHeader, Spinner, StatusBadge, StatusIcon } from "../components/ui";
import { ApiError, call } from "../lib/api";
import { useLab } from "../lib/context";
import { fmtDate, maskId } from "../lib/format";
import { useRpc } from "../lib/hooks";
import { AUTH_LABEL, COMM_LABEL } from "../lib/labels";

function ReportView({ report, mask }: { report: DiagnosticReport; mask: boolean }) {
  const groups = report.checks.reduce<Record<string, typeof report.checks>>((acc, c) => {
    (acc[c.category] ??= []).push(c);
    return acc;
  }, {});
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-lab-line bg-lab-panel2 p-4">
        <StatusIcon status={report.summaryStatus} className="h-7 w-7" />
        <div className="flex-1">
          <div className="font-semibold text-white">{report.device.label}</div>
          <div className="text-xs text-lab-mute">
            Reporte #{report.id} · {fmtDate(report.timestamp)} · {maskId(report.device.serial, mask)}
            {report.caseId ? ` · Expediente ${report.caseId}` : ""}
          </div>
        </div>
        <StatusBadge status={report.summaryStatus} />
      </div>
      {Object.entries(groups).map(([cat, checks]) => (
        <Card key={cat} title={cat}>
          <div className="divide-y divide-lab-line">
            {checks.map((c) => (
              <div key={c.id} className="grid grid-cols-1 gap-3 py-3 first:pt-0 last:pb-0 lg:grid-cols-[260px_1fr]">
                <div className="flex items-start gap-2">
                  <StatusIcon status={c.status} className="mt-0.5 h-4 w-4" />
                  <div>
                    <div className="text-sm font-medium text-white">{c.label}</div>
                    <div className="mt-0.5 font-mono text-[13px] text-cyan-200">{(c.id === "comm" && c.value ? COMM_LABEL[c.value] : c.id === "auth" && c.value ? AUTH_LABEL[c.value] : null) ?? c.value ?? "—"}</div>
                  </div>
                </div>
                <div className="space-y-2">
                  {c.detail && <div className="text-sm text-lab-mute">{c.detail}</div>}
                  {Object.keys(c.data).length > 0 && (
                    <KV items={Object.entries(c.data).filter(([, v]) => v !== null && v !== "").map(([k, v]) => [k, String(v)])} />
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      ))}
      <Card title="Vías de recuperación por interfaces autorizadas">
        {report.recoveryChannels.length ? (
          <ul className="space-y-2 text-sm">
            {report.recoveryChannels.map((ch) => (
              <li key={ch.id} className="flex items-center justify-between">
                <span>{ch.label}</span>
                <Badge tone={ch.implemented ? "ok" : "muted"}>{ch.implemented ? "Disponible" : `Pendiente (${ch.module})`}</Badge>
              </li>
            ))}
          </ul>
        ) : <div className="text-sm text-lab-mute">Ninguna con el estado actual del dispositivo.</div>}
      </Card>
    </div>
  );
}

export default function Diagnostics() {
  const { scan, selectedKey, setSelectedKey, settings, backend } = useLab();
  const mask = settings?.maskIdentifiers ?? false;
  const device = scan?.devices.find((d) => d.key === selectedKey) ?? null;
  const [caseId, setCaseId] = useState<number | "">("");
  const [report, setReport] = useState<DiagnosticReport | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const ready = backend.state === "ready";
  const openCases = useRpc("cases.list", {}, { enabled: ready });
  const history = useRpc("diagnostics.history", {}, { enabled: ready });

  const run = async () => {
    if (!device) return;
    setRunning(true);
    setError(null);
    try {
      setReport(await call("diagnostics.run", { deviceKey: device.key, caseId: caseId === "" ? null : caseId }));
      history.reload();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
    } finally {
      setRunning(false);
    }
  };

  const openReport = async (id: number) => {
    try {
      setReport(await call("diagnostics.get", { id }));
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
    }
  };

  return (
    <>
      <PageHeader title="Device Diagnostic" subtitle="Diagnóstico de solo lectura mediante interfaces oficiales (adb, fastboot, lockdownd)." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[340px_1fr]">
        <div className="space-y-4">
          <Card title="Objetivo" icon={<Activity className="h-3.5 w-3.5" />}>
            <div className="space-y-3">
              <div>
                <label className="label">Dispositivo</label>
                <select className="input" value={selectedKey ?? ""} onChange={(e) => setSelectedKey(e.target.value || null)}>
                  <option value="">— Seleccione —</option>
                  {scan?.devices.map((d) => <option key={d.key} value={d.key}>{d.label} ({maskId(d.serial, mask)})</option>)}
                </select>
              </div>
              {device && (
                <div className="text-xs text-lab-mute">
                  {COMM_LABEL[device.commState] ?? device.commState} · {AUTH_LABEL[device.authState] ?? device.authState} · {device.connector}
                </div>
              )}
              <div>
                <label className="label">Expediente (opcional)</label>
                <select className="input" value={caseId} onChange={(e) => setCaseId(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">Sin vincular</option>
                  {openCases.data?.filter((c) => !["closed", "completed"].includes(c.status)).map((c) => (
                    <option key={c.id} value={c.id}>{c.folio} · {c.deviceModel || c.deviceType}</option>
                  ))}
                </select>
              </div>
              <Button variant="primary" onClick={run} disabled={!device || running}>
                {running ? <Spinner /> : <Play className="h-4 w-4" />} {running ? "Ejecutando…" : "Ejecutar diagnóstico"}
              </Button>
              {!scan?.devices.length && <div className="text-xs text-lab-mute">Conecte un dispositivo para diagnosticar.</div>}
            </div>
          </Card>
          <Card title="Historial" icon={<History className="h-3.5 w-3.5" />}>
            {history.data?.length ? (
              <ul className="max-h-[420px] space-y-1 overflow-y-auto">
                {history.data.map((h) => (
                  <li key={h.id}>
                    <button onClick={() => openReport(h.id)}
                      className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-white/5 ${report?.id === h.id ? "bg-white/5" : ""}`}>
                      <StatusIcon status={h.summaryStatus} />
                      <span className="flex-1 truncate">{h.deviceLabel ?? h.deviceSerial}</span>
                      <span className="text-[11px] text-lab-mute">{fmtDate(h.timestamp)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : <div className="text-sm text-lab-mute">Sin reportes guardados.</div>}
          </Card>
        </div>
        <div className="space-y-4">
          <ErrorBox error={error} />
          {running && !report && <Card><div className="flex items-center gap-3 text-sm"><Spinner /> Consultando al dispositivo…</div></Card>}
          {report ? <ReportView report={report} mask={mask} /> : !running && (
            <Card><Empty icon={<Activity className="h-8 w-8" />} title="Sin reporte seleccionado">
              Ejecute un diagnóstico o abra uno del historial. Cada ejecución queda registrada en el Evidence Log.
            </Empty></Card>
          )}
        </div>
      </div>
    </>
  );
}
