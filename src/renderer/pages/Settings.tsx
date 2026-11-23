import { Save } from "lucide-react";
import ComponentsPanel from "../components/ComponentsPanel";
import { useEffect, useState } from "react";
import type { Settings } from "../../shared/types";
import { Badge, Button, Card, ErrorBox, KV, PageHeader, Spinner } from "../components/ui";
import { ApiError, call } from "../lib/api";
import { useLab } from "../lib/context";
import { useRpc } from "../lib/hooks";

export default function SettingsPage() {
  const { settings, reloadSettings, backend, rescan } = useLab();
  const ready = backend.state === "ready";
  const tools = useRpc("tools.detect", { force: true }, { enabled: ready });
  const health = useRpc("system.health", undefined, { enabled: ready });
  const modules = useRpc("system.modules", undefined, { enabled: ready });
  const [form, setForm] = useState<Settings | null>(settings);
  const [error, setError] = useState<ApiError | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => setForm(settings), [settings]);

  const save = async () => {
    if (!form) return;
    try {
      await call("settings.update", { values: form });
      setError(null);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      await reloadSettings();
      tools.reload();
      rescan();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
    }
  };

  const text = (k: keyof Settings, label: string, placeholder = "", mono = false) => (
    <div>
      <label className="label">{label}</label>
      <input className={`input ${mono ? "font-mono" : ""}`} placeholder={placeholder} value={String(form?.[k] ?? "")}
        onChange={(e) => form && setForm({ ...form, [k]: e.target.value })} />
    </div>
  );

  return (
    <>
      <PageHeader title="Configuración" subtitle="Estación, componentes integrados y estado de los módulos." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Estación" actions={<Button variant="primary" onClick={save} disabled={!form}><Save className="h-4 w-4" /> {saved ? "Guardado" : "Guardar"}</Button>}>
          {form ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {text("technicianName", "Técnico responsable")}
              {text("labName", "Nombre del laboratorio")}
              <label className="flex items-start gap-2 rounded-md border border-lab-line bg-lab-bg p-3 text-sm md:col-span-2">
                <input type="checkbox" className="mt-1 accent-cyan-400" checked={form.autonomousMode}
                  onChange={(e) => setForm({ ...form, autonomousMode: e.target.checked })} />
                <span>
                  <span className="font-medium text-white">Modo autónomo</span>
                  <span className="block text-xs text-lab-mute">Usar exclusivamente los componentes integrados y verificados de MR Lab; ignora herramientas instaladas en el sistema.</span>
                </span>
              </label>
              <div className="label md:col-span-2 mt-2">Rutas personalizadas (avanzado, opcional)</div>
              {text("adbPath", "Ruta de adb", "C:\\platform-tools\\adb.exe", true)}
              {text("fastbootPath", "Ruta de fastboot", "C:\\platform-tools\\fastboot.exe", true)}
              <div className="md:col-span-2">{text("libimobiledeviceDir", "Carpeta de libimobiledevice", "C:\\libimobiledevice", true)}</div>
              <div>
                <label className="label">Escaneo automático (s)</label>
                <input type="number" min={2} max={300} className="input" value={form.autoScanSeconds}
                  onChange={(e) => setForm({ ...form, autoScanSeconds: Number(e.target.value) })} />
              </div>
              <label className="mt-5 flex items-center gap-2 text-sm">
                <input type="checkbox" className="accent-cyan-400" checked={form.maskIdentifiers}
                  onChange={(e) => setForm({ ...form, maskIdentifiers: e.target.checked })} />
                Enmascarar identificadores en pantalla
              </label>
              <div className="md:col-span-2"><ErrorBox error={error} /></div>
            </div>
          ) : <Spinner />}
        </Card>

        <ComponentsPanel data={tools.data} error={tools.error} loading={tools.loading} onRefresh={tools.reload} />

        <Card title="Estado de módulos">
          <ul className="space-y-2">
            {modules.data?.map((m) => (
              <li key={m.id} className="flex items-start justify-between gap-3 text-sm">
                <div><span className="text-white">{m.name}</span> <span className="text-xs text-lab-mute">· Etapa {m.stage}</span>
                  <div className="text-xs text-lab-mute">{m.description}</div></div>
                <Badge tone={m.status === "implemented" ? "ok" : m.status === "partial" ? "warning" : "muted"}>
                  {{ implemented: "Implementado", partial: "Parcial", planned: "Planificado" }[m.status]}
                </Badge>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Sistema">
          {health.data ? <KV items={[
            ["Versión de servicios", health.data.version], ["Python", health.data.python], ["Esquema BD", String(health.data.schemaVersion)],
            ["Datos locales", health.data.dataDir], ["Base de datos", health.data.db],
          ]} /> : <ErrorBox error={health.error} />}
        </Card>
      </div>
    </>
  );
}
