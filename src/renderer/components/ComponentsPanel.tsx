import { PackageCheck, RefreshCw, ShieldAlert, ShieldCheck, Store } from "lucide-react";
import type { ToolInfo, ToolsReport } from "../../shared/types";
import { Badge, Button, Card, ErrorBox, Spinner } from "./ui";
import type { ApiError } from "../lib/api";
import { bridge } from "../lib/api";

export const SOURCE_LABEL: Record<string, string> = {
  integrated: "Integrado",
  custom: "Ruta personalizada",
  system: "Externo (sistema)",
};

const COMP_STATUS: Record<string, { label: string; tone: "ok" | "error" | "warning" }> = {
  ok: { label: "Verificado", tone: "ok" },
  altered: { label: "Alterado — bloqueado", tone: "error" },
  incomplete: { label: "Incompleto", tone: "warning" },
};

export function ToolSource({ t }: { t: ToolInfo }) {
  if (!t.installed) return <Badge tone="error">No disponible</Badge>;
  return <Badge tone={t.source === "integrated" ? "ok" : "warning"}>{SOURCE_LABEL[t.source ?? ""] ?? "—"}{t.version ? ` · v${t.version}` : ""}</Badge>;
}

export default function ComponentsPanel({ data, error, loading, onRefresh }: {
  data: ToolsReport | null; error: ApiError | null; loading: boolean; onRefresh: () => void;
}) {
  const a = data?.autonomy;
  return (
    <Card title="Componentes integrados" icon={<PackageCheck className="h-3.5 w-3.5" />}
      actions={<Button onClick={onRefresh} disabled={loading}>{loading ? <Spinner /> : <RefreshCw className="h-4 w-4" />} Verificar</Button>}>
      <ErrorBox error={error} onRetry={onRefresh} />
      {data && a && (
        <div className="space-y-4">
          <div className={`flex items-start gap-3 rounded-md border p-3 text-sm ${a.allIntegrated ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-100" : "border-amber-500/30 bg-amber-500/5 text-amber-100"}`}>
            {a.allIntegrated ? <ShieldCheck className="h-5 w-5 shrink-0 text-emerald-300" /> : <ShieldAlert className="h-5 w-5 shrink-0 text-amber-300" />}
            <div>
              <div className="font-medium">{a.allIntegrated ? "Estación autónoma: los motores Android y Apple son propios de MR Lab." : "La estación aún usa o necesita componentes externos."}</div>
              {!a.allIntegrated && (
                <div className="mt-1 text-xs opacity-80">
                  {a.external.length > 0 && <>Externos: {a.external.join(", ")}. </>}
                  {a.missing.length > 0 && <>Faltantes: {a.missing.join(", ")}. </>}
                  Integre los componentes al compilar el instalador (<span className="font-mono">scripts/fetch_components.py</span>).
                </div>
              )}
            </div>
          </div>

          <div>
            <div className="label">Paquetes integrados en el instalador</div>
            {!data.components.inventory ? (
              <div className="text-sm text-lab-mute">{data.components.error ?? "Esta compilación no incluye inventario de componentes."}</div>
            ) : (
              <ul className="space-y-2">
                {data.components.components.map((c) => (
                  <li key={c.id} className="flex items-start justify-between gap-3 text-sm">
                    <div className="min-w-0">
                      <div className="text-white">{c.name} {c.version && <span className="text-xs text-lab-mute">v{c.version}</span>}</div>
                      <div className="text-xs text-lab-mute">{c.kind === "driver" ? "Controlador" : "Motor"} · {c.fileCount} archivos · {c.license}</div>
                      {c.altered.length > 0 && <div className="text-xs text-rose-300">Modificados: {c.altered.join(", ")}</div>}
                      {c.missing.length > 0 && <div className="text-xs text-amber-300">Faltan: {c.missing.join(", ")}</div>}
                    </div>
                    <Badge tone={COMP_STATUS[c.status].tone}>{COMP_STATUS[c.status].label}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <div className="label">Herramientas en uso</div>
            <ul className="space-y-2">
              {data.tools.map((t) => (
                <li key={t.id} className="flex items-start justify-between gap-3 border-b border-lab-line pb-2 last:border-0">
                  <div className="min-w-0">
                    <div className="text-sm text-white">{t.name}</div>
                    <div className="text-xs text-lab-mute">{t.purpose}</div>
                    {t.path && <div className="truncate font-mono text-[11px] text-cyan-200/70">{t.path}</div>}
                  </div>
                  <ToolSource t={t} />
                </li>
              ))}
            </ul>
          </div>

          <div className="flex items-start justify-between gap-3 text-sm">
            <div>
              <div className="text-white">Servicio USB de Apple ({data.appleService.name})</div>
              <div className="text-xs text-lab-mute">{data.appleService.detail}</div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Badge tone={data.appleService.running ? "ok" : "warning"}>{data.appleService.running ? "Activo" : "Inactivo"}</Badge>
              {!data.appleService.installed && data.appleService.storeUrl && (
                <Button onClick={() => bridge().openAppleDevicesStore()}><Store className="h-4 w-4" /> Instalar</Button>
              )}
            </div>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span>Cifrado de respaldos (AES-256-GCM)</span>
            <Badge tone={data.encryption.available ? "ok" : "error"}>{data.encryption.available ? "Integrado" : "No disponible"}</Badge>
          </div>
        </div>
      )}
    </Card>
  );
}
