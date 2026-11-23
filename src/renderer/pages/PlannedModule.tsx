import { Construction, ShieldAlert } from "lucide-react";
import { Badge, Card, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { useLab } from "../lib/context";
import { useRpc } from "../lib/hooks";

const NOTES: Record<string, string> = {
  "access-recovery":
    "Este módulo solo guiará por mecanismos oficiales del fabricante (recuperación de cuenta Google/Apple ID, respaldos existentes, restauración y soporte técnico). " +
    "No incluye ni incluirá evasión de autenticación, bypass de cifrado, cracking de contraseñas ni extracción oculta.",
  "reset-center":
    "Antes de cualquier restauración se mostrará advertencia de pérdida de datos, se solicitará confirmación explícita, se registrará la operación con el método utilizado y se generará un reporte.",
  "data-recovery": "Solo se trabajará con datos accesibles mediante interfaces autorizadas por el titular (ADB autorizado, respaldos oficiales, fuentes importadas).",
};

export default function PlannedModule({ moduleId }: { moduleId: string }) {
  const { backend } = useLab();
  const mods = useRpc("system.modules", undefined, { enabled: backend.state === "ready" });
  const m = mods.data?.find((x) => x.id === moduleId);
  if (mods.error) return <ErrorBox error={mods.error} onRetry={mods.reload} />;
  if (!m) return <Spinner />;
  return (
    <>
      <PageHeader title={m.name} subtitle={m.description}
        actions={<Badge tone={m.status === "partial" ? "warning" : "muted"}>{m.status === "partial" ? "Parcial" : "Planificado"} · Etapa {m.stage}</Badge>} />
      <Card>
        <div className="flex items-start gap-4">
          <Construction className="h-8 w-8 shrink-0 text-amber-300" />
          <div className="space-y-3 text-sm">
            <p className="text-white">Este módulo aún no ejecuta operaciones. Ninguna acción ni resultado se simula.</p>
            {m.scope && (
              <div>
                <div className="label">Alcance planificado</div>
                <ul className="list-inside list-disc space-y-0.5 text-lab-mute">{m.scope.map((s) => <li key={s}>{s}</li>)}</ul>
              </div>
            )}
            {NOTES[moduleId] && (
              <div className="flex gap-2 rounded-md border border-cyan-500/20 bg-cyan-500/5 p-3 text-xs text-cyan-100/90">
                <ShieldAlert className="h-4 w-4 shrink-0" />{NOTES[moduleId]}
              </div>
            )}
          </div>
        </div>
      </Card>
    </>
  );
}
