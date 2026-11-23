import { Activity, Archive, FolderKanban, KeyRound, MonitorSmartphone, Plug, RefreshCw, ShieldCheck, Smartphone, Wrench } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { SOURCE_LABEL } from "../components/ComponentsPanel";
import { CATEGORY_TONE } from "./ScreenRecovery";
import { Badge, Button, Card, Dot, Empty, ErrorBox, KV, PageHeader, Spinner, StatusBadge, StatusIcon } from "../components/ui";
import { useLab } from "../lib/context";
import { fmtDate, maskId } from "../lib/format";
import { useRpc } from "../lib/hooks";
import { AUTH_LABEL, CASE_STATUS, COMM_LABEL, CONN_LABEL, MODE_LABEL, MODULE_LABEL, STATUS_LABEL, authTone, commTone } from "../lib/labels";

function Tile({ label, icon, children, footer }: { label: string; icon: ReactNode; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="rounded-lg border border-lab-line bg-lab-panel/90 p-4">
      <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-lab-mute">
        {icon}{label}
      </div>
      <div className="min-h-[52px]">{children}</div>
      {footer && <div className="mt-3 border-t border-lab-line pt-2 text-xs text-lab-mute">{footer}</div>}
    </div>
  );
}

export default function Dashboard() {
  const { scan, scanning, rescan, navigate, settings, backend, setSelectedKey } = useLab();
  const summary = useRpc("dashboard.summary", undefined, { enabled: backend.state === "ready" });
  const s = summary.data;
  const reloadSummary = summary.reload;
  useEffect(() => {
    if (scan?.scannedAt) reloadSummary();
  }, [scan?.scannedAt, reloadSummary]);
  const dev = scan?.devices[0] ?? s?.primaryDevice ?? null;
  const diag = s?.lastDiagnostic && dev && s.lastDiagnostic.device.serial === dev.serial ? s.lastDiagnostic : null;
  const mask = settings?.maskIdentifiers ?? false;
  const display = diag?.checks.find((c) => c.id === "display");
  const touch = diag?.checks.find((c) => c.id === "touch");

  const refresh = async () => {
    await rescan();
    summary.reload();
  };

  return (
    <>
      <PageHeader
        title="Resumen"
        subtitle={`Estación ${settings?.labName || "MR Lab"} · Técnico: ${settings?.technicianName || "sin asignar"}`}
        actions={<Button onClick={refresh} disabled={scanning}>{scanning ? <Spinner /> : <RefreshCw className="h-4 w-4" />} Escanear</Button>}
      />
      <ErrorBox error={summary.error} onRetry={summary.reload} />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Tile label="Dispositivo conectado" icon={<Smartphone className="h-3.5 w-3.5" />}
          footer={scan ? `${scan.devices.length} dispositivo(s) · último escaneo ${fmtDate(scan.scannedAt)}` : "Sin escaneo"}>
          {dev ? (
            <div>
              <div className="text-lg font-semibold text-white">{dev.label}</div>
              <div className="mt-0.5 text-sm text-lab-mute">{dev.osName} {dev.osVersion ?? ""} · <span className="font-mono">{maskId(dev.serial, mask)}</span></div>
            </div>
          ) : <div className="text-sm text-lab-mute">Ningún dispositivo detectado. Conecte un equipo por USB.</div>}
        </Tile>

        <Tile label="Estado de conexión" icon={<Plug className="h-3.5 w-3.5" />}
          footer={dev ? `Conector: ${dev.connector}` : undefined}>
          {dev ? (
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2"><Dot tone={commTone(dev.commState)} /> {COMM_LABEL[dev.commState] ?? dev.commState}</div>
              <div className="text-lab-mute">Vía {CONN_LABEL[dev.connection] ?? dev.connection} · modo {MODE_LABEL[dev.mode] ?? dev.mode}</div>
            </div>
          ) : <div className="text-sm text-lab-mute">—</div>}
        </Tile>

        <Tile label="Diagnóstico" icon={<Activity className="h-3.5 w-3.5" />}
          footer={diag ? <>Reporte #{diag.id} · {fmtDate(diag.timestamp)}</> : undefined}>
          {diag ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2"><StatusIcon status={diag.summaryStatus} className="h-6 w-6" /><StatusBadge status={diag.summaryStatus} /></div>
              <div className="text-right text-xs text-lab-mute">
                {(["ok", "warning", "error", "unavailable"] as const).map((st) => (
                  <div key={st}>{STATUS_LABEL[st]}: {diag.checks.filter((c) => c.status === st).length}</div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between gap-2 text-sm text-lab-mute">
              <span>Sin diagnóstico para este dispositivo.</span>
              {dev && <Button variant="primary" onClick={() => { setSelectedKey(dev.key); navigate("diagnostics"); }}>Diagnosticar</Button>}
            </div>
          )}
        </Tile>

        <Tile label="Tipo de pantalla" icon={<MonitorSmartphone className="h-3.5 w-3.5" />}
          footer={s?.screenAssessment ? <>Evaluación #{s.screenAssessment.id} · {fmtDate(s.screenAssessment.timestamp)}</> : <button className="underline" onClick={() => navigate("screen-recovery")}>Evaluar daño de pantalla</button>}>
          {s?.screenAssessment && (
            <div className="mb-2"><Badge tone={CATEGORY_TONE[s.screenAssessment.category]}>{s.screenAssessment.categoryLabel}</Badge></div>
          )}
          {display && display.status !== "unavailable" ? (
            <KV items={[
              ["Resolución", display.value],
              ["Densidad", String(display.data["Densidad"] ?? "—")],
              ["Display", String(display.data["Estado del display"] ?? "—")],
              ["Táctil", touch ? touch.value : "—"],
            ]} />
          ) : <div className="text-sm text-lab-mute">Requiere un diagnóstico con dispositivo autorizado.</div>}
        </Tile>

        <Tile label="Estado de acceso" icon={<KeyRound className="h-3.5 w-3.5" />}>
          {dev ? (
            <div className="space-y-2 text-sm">
              <Badge tone={authTone(dev.authState)}>{AUTH_LABEL[dev.authState] ?? dev.authState}</Badge>
              {dev.notes.map((n) => <div key={n} className="text-xs text-lab-mute">{n}</div>)}
            </div>
          ) : <div className="text-sm text-lab-mute">—</div>}
        </Tile>

        <Tile label="Recuperación disponible" icon={<Archive className="h-3.5 w-3.5" />}
          footer="Solo se listan vías por interfaces autorizadas.">
          {s && dev ? (
            (diag?.recoveryChannels ?? s.recoveryChannels).length ? (
              <ul className="space-y-1.5 text-sm">
                {(diag?.recoveryChannels ?? s.recoveryChannels).map((c) => (
                  <li key={c.id} className="flex items-start justify-between gap-2">
                    <span>{c.label}</span>
                    <Badge tone={c.implemented ? "ok" : "muted"}>{c.implemented ? "Disponible" : `Pendiente: ${MODULE_LABEL[c.module] ?? c.module}`}</Badge>
                  </li>
                ))}
              </ul>
            ) : <div className="text-sm text-lab-mute">No hay vías disponibles con el estado actual de comunicación/autorización.</div>
          ) : <div className="text-sm text-lab-mute">—</div>}
        </Tile>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" title="Últimos casos" icon={<FolderKanban className="h-3.5 w-3.5" />}
          actions={<Button variant="ghost" onClick={() => navigate("case-files")}>Ver todos</Button>}>
          {s?.recentCases.length ? (
            <table className="w-full text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wider text-lab-mute">
                <tr><th className="pb-2">Folio</th><th className="pb-2">Ingreso</th><th className="pb-2">Dispositivo</th><th className="pb-2">Motivo</th><th className="pb-2">Estado</th></tr>
              </thead>
              <tbody className="divide-y divide-lab-line">
                {s.recentCases.map((c) => (
                  <tr key={c.id}>
                    <td className="py-2 font-mono text-cyan-200">{c.folio}</td>
                    <td className="py-2 text-lab-mute">{fmtDate(c.createdAt)}</td>
                    <td className="py-2">{c.deviceModel || c.deviceType}</td>
                    <td className="max-w-[240px] truncate py-2 text-lab-mute">{c.reason}</td>
                    <td className="py-2"><Badge tone="accent">{CASE_STATUS[c.status] ?? c.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : summary.loading && !s ? <Spinner /> : (
            <Empty icon={<FolderKanban className="h-6 w-6" />} title="Sin expedientes">Abra un expediente en Expedientes antes de operar un dispositivo.</Empty>
          )}
        </Card>

        <Card title="Estación" icon={<Wrench className="h-3.5 w-3.5" />}
          actions={<Button variant="ghost" onClick={() => navigate("settings")}>Componentes</Button>}>
          {s ? (
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span>Autonomía</span>
                <Badge tone={s.autonomy.allIntegrated ? "ok" : "warning"}>{s.autonomy.allIntegrated ? "Motores propios" : "Depende de externos"}</Badge>
              </div>
              {[["adb", "Motor Android"], ["fastboot", "Bootloader Android"], ["ideviceinfo", "Motor Apple"]].map(([id, name]) => (
                <div key={id} className="flex items-center justify-between">
                  <span>{name}</span>
                  <Badge tone={!s.tools[id] ? "error" : s.toolSources[id] === "integrated" ? "ok" : "warning"}>
                    {!s.tools[id] ? "No disponible" : SOURCE_LABEL[s.toolSources[id] ?? ""] ?? "Disponible"}
                  </Badge>
                </div>
              ))}
              <div className="flex items-center justify-between">
                <span>Servicio USB de Apple</span>
                <Badge tone={s.appleService.running ? "ok" : "warning"}>{s.appleService.running ? "Activo" : "Inactivo"}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1"><ShieldCheck className="h-3.5 w-3.5" /> Cifrado AES-256</span>
                <Badge tone={s.encryption.available ? "ok" : "error"}>{s.encryption.available ? "Disponible" : "No disponible"}</Badge>
              </div>
              <div className="flex items-center justify-between text-lab-mute">
                <span>Registros de evidencia</span><span className="font-mono">{s.evidenceCount}</span>
              </div>
            </div>
          ) : <Spinner />}
        </Card>
      </div>
    </>
  );
}
