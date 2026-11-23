import { Activity, Apple, RefreshCw, Smartphone, TriangleAlert, Usb, Wifi } from "lucide-react";
import type { DeviceInfo } from "../../shared/types";
import { Badge, Button, Card, Dot, Empty, ErrorBox, KV, PageHeader, Spinner } from "../components/ui";
import { useLab } from "../lib/context";
import { fmtDate, maskId } from "../lib/format";
import { bridge } from "../lib/api";
import { AUTH_LABEL, COMM_LABEL, CONN_LABEL, authTone, commTone } from "../lib/labels";

function DeviceCard({ d, selected, onSelect, onDiagnose, mask }: {
  d: DeviceInfo; selected: boolean; onSelect: () => void; onDiagnose: () => void; mask: boolean;
}) {
  const ConnIcon = d.connection === "network" ? Wifi : Usb;
  return (
    <div onClick={onSelect}
      className={`cursor-pointer rounded-lg border bg-lab-panel/90 p-4 transition ${selected ? "border-cyan-500/60 shadow-[0_0_24px_-12px] shadow-cyan-400" : "border-lab-line hover:border-cyan-500/30"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-md border border-lab-line bg-lab-bg">
            {d.platform === "apple" ? <Apple className="h-5 w-5 text-slate-200" /> : <Smartphone className="h-5 w-5 text-emerald-300" />}
          </div>
          <div>
            <div className="font-semibold text-white">{d.label}</div>
            <div className="text-xs text-lab-mute">{d.modelCode ?? "—"}</div>
          </div>
        </div>
        <Badge tone={commTone(d.commState)}><Dot tone={commTone(d.commState)} /> {COMM_LABEL[d.commState] ?? d.commState}</Badge>
      </div>
      <div className="mt-4">
        <KV items={[
          ["Fabricante", d.manufacturer ?? "No disponible"],
          ["Modelo", d.model ?? "No disponible"],
          ["Sistema", d.osName ? `${d.osName} ${d.osVersion ?? ""}` : "No disponible"],
          ["Identificador", maskId(d.serial, mask)],
          ["Conexión", <span className="inline-flex items-center gap-1"><ConnIcon className="h-3.5 w-3.5" />{CONN_LABEL[d.connection] ?? d.connection}</span>],
          ["Autorización", <Badge tone={authTone(d.authState)}>{AUTH_LABEL[d.authState] ?? d.authState}</Badge>],
          ["Conector", d.connector],
          ["Diagnóstico", d.diagnostics.length ? d.diagnostics.join(", ") : "No disponible"],
        ]} />
      </div>
      {d.notes.length > 0 && (
        <div className="mt-3 space-y-1 rounded-md border border-amber-500/20 bg-amber-500/5 p-2 text-xs text-amber-200">
          {d.notes.map((n) => <div key={n} className="flex gap-2"><TriangleAlert className="mt-0.5 h-3 w-3 shrink-0" />{n}</div>)}
        </div>
      )}
      <div className="mt-4 flex justify-end">
        <Button variant="primary" onClick={onDiagnose}><Activity className="h-4 w-4" /> Diagnosticar</Button>
      </div>
    </div>
  );
}

export default function Devices() {
  const { scan, scanError, scanning, rescan, selectedKey, setSelectedKey, navigate, settings } = useLab();
  return (
    <>
      <PageHeader title="Detección de dispositivos"
        subtitle={`Detección automática cada ${settings?.autoScanSeconds ?? 5} s · Último escaneo: ${fmtDate(scan?.scannedAt)}`}
        actions={<Button onClick={rescan} disabled={scanning}>{scanning ? <Spinner /> : <RefreshCw className="h-4 w-4" />} Escanear ahora</Button>} />
      <ErrorBox error={scanError} onRetry={rescan} />
      {scan && scan.errors.length > 0 && (
        <div className="mb-4 space-y-1 rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-200">
          {scan.errors.map((e) => <div key={e}>• {e}</div>)}
          <div className="pt-1 text-xs text-amber-200/70">Revise los componentes en <button className="underline" onClick={() => navigate("settings")}>Configuración</button>.</div>
        </div>
      )}
      {scan?.usbHints?.map((h) => (
        <div key={h.vid} className={`mb-4 rounded-lg border p-4 ${h.diagnosis === "missing_driver" ? "border-rose-500/40 bg-rose-500/5" : "border-amber-500/40 bg-amber-500/5"}`}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <TriangleAlert className={`mt-0.5 h-5 w-5 shrink-0 ${h.diagnosis === "missing_driver" ? "text-rose-300" : "text-amber-300"}`} />
              <div>
                <div className="font-medium text-white">Windows detecta un teléfono {h.vendor} que MR Lab no puede usar todavía</div>
                <div className="mt-1 text-sm text-lab-text">{h.message}</div>
                <ul className="mt-2 space-y-0.5 text-xs text-lab-mute">
                  {h.interfaces.map((i, n) => (
                    <li key={n}>• {i.name ?? "Interfaz"}{i.errorCode ? ` — sin controlador (código ${i.errorCode})` : " — correcto"}</li>
                  ))}
                </ul>
              </div>
            </div>
            {h.driverUrl && h.diagnosis === "missing_driver" && (
              <Button variant="primary" onClick={() => bridge().openDriverPage(h.driverUrl!)}>Descargar controlador oficial de {h.vendor}</Button>
            )}
          </div>
        </div>
      ))}
      {scan && (
        <div className="mb-4 flex flex-wrap gap-2 text-xs">
          {Object.entries(scan.connectors).map(([name, c]) => (
            <Badge key={name} tone={c.available ? "ok" : "muted"}>{name}: {c.available ? `${c.count} detectado(s)` : "no disponible"}</Badge>
          ))}
        </div>
      )}
      {!scan && scanning && <Spinner className="h-6 w-6" />}
      {scan && scan.devices.length === 0 && (
        <Card>
          <Empty icon={<Usb className="h-8 w-8" />} title="No hay dispositivos conectados">
            Android: active «Depuración USB» en Opciones de desarrollador y acepte «¿Permitir depuración USB?» en el teléfono.
            Apple: desbloquee el dispositivo y pulse «Confiar en este equipo». El escaneo continúa automáticamente.
          </Empty>
          <div className="mx-auto mt-2 max-w-xl text-left text-xs text-lab-mute">
            <div className="label">Si conectó un teléfono y no aparece</div>
            <ol className="list-inside list-decimal space-y-0.5">
              <li>Use un cable de datos (muchos cables solo cargan) y un puerto USB directo del PC, sin hub.</li>
              <li>Samsung, Xiaomi, Motorola y otras marcas necesitan su controlador USB oficial en Windows.</li>
              <li>En el teléfono: Opciones de desarrollador → «Revocar autorizaciones de depuración USB», desconecte y vuelva a conectar.</li>
              <li>Acepte el aviso del teléfono y marque «Permitir siempre desde este equipo».</li>
            </ol>
          </div>
        </Card>
      )}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3">
        {scan?.devices.map((d) => (
          <DeviceCard key={d.key} d={d} mask={settings?.maskIdentifiers ?? false} selected={d.key === selectedKey}
            onSelect={() => setSelectedKey(d.key)}
            onDiagnose={() => { setSelectedKey(d.key); navigate("diagnostics"); }} />
        ))}
      </div>
    </>
  );
}
