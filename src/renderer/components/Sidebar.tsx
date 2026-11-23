import {
  Activity, Archive, ClipboardList, Cpu, DatabaseBackup, FolderKanban, KeyRound, LayoutDashboard,
  MonitorSmartphone, RotateCcw, Settings, Smartphone, Wrench,
} from "lucide-react";
import type { BackendStatus } from "../../shared/types";
import { Dot } from "./ui";

export type PageId =
  | "overview" | "devices" | "diagnostics" | "screen-recovery" | "data-recovery" | "access-recovery"
  | "backup-manager" | "system-repair" | "reset-center" | "case-files" | "settings";

export const NAV: { id: PageId; label: string; icon: typeof Activity; stage?: number }[] = [
  { id: "overview", label: "Resumen", icon: LayoutDashboard },
  { id: "devices", label: "Dispositivos", icon: Smartphone },
  { id: "diagnostics", label: "Diagnóstico", icon: Activity },
  { id: "screen-recovery", label: "Pantalla dañada", icon: MonitorSmartphone },
  { id: "data-recovery", label: "Recuperación de datos", icon: Archive },
  { id: "backup-manager", label: "Respaldos", icon: DatabaseBackup },
  { id: "access-recovery", label: "Recuperación de acceso", icon: KeyRound },
  { id: "system-repair", label: "Reparación de sistema", icon: Wrench, stage: 5 },
  { id: "reset-center", label: "Restauración de fábrica", icon: RotateCcw, stage: 5 },
  { id: "case-files", label: "Expedientes", icon: FolderKanban },
  { id: "settings", label: "Configuración", icon: Settings },
];

export function Sidebar({ page, onNavigate, backend, deviceCount }: {
  page: PageId; onNavigate: (p: PageId) => void; backend: BackendStatus; deviceCount: number;
}) {
  const tone = backend.state === "ready" ? "ok" : backend.state === "starting" ? "warning" : "error";
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-lab-line bg-lab-panel">
      <div className="flex items-center gap-3 border-b border-lab-line px-4 py-4">
        <div className="grid h-9 w-9 place-items-center rounded-md border border-cyan-500/40 bg-cyan-500/10">
          <Cpu className="h-5 w-5 text-cyan-300" />
        </div>
        <div>
          <div className="text-sm font-semibold tracking-wide text-white">MR LAB</div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-lab-mute">Laboratorio de recuperación móvil</div>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {NAV.map(({ id, label, icon: Icon, stage }) => {
          const active = page === id;
          return (
            <button key={id} onClick={() => onNavigate(id)}
              className={`group flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition ${
                active ? "bg-cyan-500/10 text-cyan-200 shadow-[inset_2px_0_0] shadow-cyan-400" : "text-lab-mute hover:bg-white/5 hover:text-lab-text"}`}>
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1">{label}</span>
              {id === "devices" && deviceCount > 0 && (
                <span className="rounded bg-cyan-500/20 px-1.5 text-[10px] font-semibold text-cyan-200">{deviceCount}</span>
              )}
              {stage && <span className="text-[9px] uppercase tracking-wider text-lab-mute/60">Et. {stage}</span>}
            </button>
          );
        })}
      </nav>
      <div className="border-t border-lab-line p-3 text-[11px] text-lab-mute">
        <div className="flex items-center gap-2">
          <Dot tone={tone} />
          <span>Servicios: {{ ready: "en línea", starting: "iniciando", crashed: "con error", stopped: "detenido" }[backend.state]}</span>
        </div>
        <div className="mt-1 flex items-center gap-2"><ClipboardList className="h-3 w-3" /> Datos almacenados localmente</div>
      </div>
    </aside>
  );
}
