import { RefreshCw, Save, Wrench } from "lucide-react";
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
      <PageHeader title="Settings" subtitle="Estación, rutas de herramientas y estado de los módulos." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Estación" actions={<Button variant="primary" onClick={save} disabled={!form}><Save className="h-4 w-4" /> {saved ? "Guardado" : "Guardar"}</Button>}>
          {form ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {text("technicianName", "Técnico responsable")}
              {text("labName", "Nombre del laboratorio")}
              {text("adbPath", "Ruta de adb (opcional)", "C:\\platform-tools\\adb.exe", true)}
              {text("fastbootPath", "Ruta de fastboot (opcional)", "C:\\platform-tools\\fastboot.exe", true)}
              <div className="md:col-span-2">{text("libimobiledeviceDir", "Carpeta de libimobiledevice (opcional)", "C:\\libimobiledevice", true)}</div>
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

        <Card title="Herramientas detectadas" icon={<Wrench className="h-3.5 w-3.5" />}
          actions={<Button onClick={tools.reload} disabled={tools.loading}>{tools.loading ? <Spinner /> : <RefreshCw className="h-4 w-4" />} Detectar</Button>}>
          <ErrorBox error={tools.error} onRetry={tools.reload} />
          {tools.data && (
            <div className="space-y-3">
              {tools.data.tools.map((t) => (
                <div key={t.id} className="flex items-start justify-between gap-3 border-b border-lab-line pb-2 last:border-0">
                  <div className="min-w-0">
                    <div className="text-sm text-white">{t.name}</div>
                    <div className="text-xs text-lab-mute">{t.purpose}</div>
                    {t.path && <div className="truncate font-mono text-[11px] text-cyan-200/70">{t.path}</div>}
                  </div>
                  <Badge tone={t.installed ? "ok" : "error"}>{t.installed ? (t.version ? `v${t.version}` : "Instalado") : "No encontrado"}</Badge>
                </div>
              ))}
              <div className="flex items-center justify-between text-sm">
                <span>{tools.data.appleService.name}</span>
                <Badge tone={tools.data.appleService.running ? "ok" : "warning"}>{tools.data.appleService.detail}</Badge>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span>Biblioteca de cifrado</span>
                <Badge tone={tools.data.encryption.available ? "ok" : "error"}>{tools.data.encryption.available ? `cryptography ${tools.data.encryption.version}` : "No instalada"}</Badge>
              </div>
            </div>
          )}
        </Card>

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
            ["Versión backend", health.data.version], ["Python", health.data.python], ["Esquema BD", String(health.data.schemaVersion)],
            ["Datos locales", health.data.dataDir], ["Base de datos", health.data.db],
          ]} /> : <ErrorBox error={health.error} />}
        </Card>
      </div>
    </>
  );
}
