import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { BackendStatus, ScanResult, Settings } from "../shared/types";
import { PageId, Sidebar } from "./components/Sidebar";
import { ApiError, call } from "./lib/api";
import { Ctx, LabContext } from "./lib/context";
import AccessRecovery from "./pages/AccessRecovery";
import CaseFiles from "./pages/CaseFiles";
import Dashboard from "./pages/Dashboard";
import Devices from "./pages/Devices";
import Diagnostics from "./pages/Diagnostics";
import PlannedModule from "./pages/PlannedModule";
import ScreenRecovery from "./pages/ScreenRecovery";
import SettingsPage from "./pages/Settings";

export default function App() {
  const [page, setPage] = useState<PageId>("overview");
  const [backend, setBackend] = useState<BackendStatus>({ state: "starting", restarts: 0 });
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [scanError, setScanError] = useState<ApiError | null>(null);
  const [scanning, setScanning] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const scanBusy = useRef(false);

  useEffect(() => {
    if (!window.mrlab) {
      setBackend({ state: "crashed", restarts: 0, detail: "La interfaz no se está ejecutando dentro de Electron." });
      return;
    }
    window.mrlab.backendStatus().then(setBackend);
    return window.mrlab.onBackendStatus(setBackend);
  }, []);

  const reloadSettings = useCallback(async () => {
    try {
      setSettings(await call("settings.get"));
    } catch {
      /* se mostrará en Settings */
    }
  }, []);

  const rescan = useCallback(async () => {
    if (scanBusy.current) return;
    scanBusy.current = true;
    setScanning(true);
    try {
      const r = await call("devices.scan");
      setScan(r);
      setScanError(null);
      setSelectedKey((k) => (k && r.devices.some((d) => d.key === k) ? k : r.devices[0]?.key ?? null));
    } catch (e) {
      setScanError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
    } finally {
      scanBusy.current = false;
      setScanning(false);
    }
  }, []);

  useEffect(() => {
    if (backend.state !== "ready") return;
    reloadSettings();
    rescan();
  }, [backend.state, reloadSettings, rescan]);

  const interval = (settings?.autoScanSeconds ?? 5) * 1000;
  useEffect(() => {
    if (backend.state !== "ready") return;
    const t = setInterval(rescan, interval);
    return () => clearInterval(t);
  }, [backend.state, interval, rescan]);

  const ctx: LabContext = useMemo(() => ({
    backend, scan, scanError, scanning, rescan, settings, reloadSettings, selectedKey, setSelectedKey, navigate: setPage,
  }), [backend, scan, scanError, scanning, rescan, settings, reloadSettings, selectedKey]);

  return (
    <Ctx.Provider value={ctx}>
      <div className="flex h-full">
        <Sidebar page={page} onNavigate={setPage} backend={backend} deviceCount={scan?.devices.length ?? 0} />
        <main className="grid-bg flex-1 overflow-y-auto">
          {backend.state !== "ready" && (
            <div className={`border-b px-6 py-2 text-sm ${backend.state === "starting" ? "border-amber-500/30 bg-amber-500/5 text-amber-200" : "border-rose-500/30 bg-rose-500/10 text-rose-200"}`}>
              {backend.state === "starting" ? "Iniciando servicios locales…" : `Servicios locales no disponibles. ${backend.detail ?? ""}`}
            </div>
          )}
          <div className="mx-auto max-w-[1400px] p-6">
            {page === "overview" && <Dashboard />}
            {page === "devices" && <Devices />}
            {page === "diagnostics" && <Diagnostics />}
            {page === "screen-recovery" && <ScreenRecovery />}
            {page === "access-recovery" && <AccessRecovery />}
            {page === "case-files" && <CaseFiles />}
            {page === "settings" && <SettingsPage />}
            {["data-recovery", "backup-manager", "system-repair", "reset-center"].includes(page) && (
              <PlannedModule moduleId={page} />
            )}
          </div>
        </main>
      </div>
    </Ctx.Provider>
  );
}
