import { Apple, Archive, FolderOpen, FileArchive, Play, Search, ShieldCheck, Smartphone, Upload } from "lucide-react";
import { useState } from "react";
import type { Job, RecoveryScan } from "../../shared/types";
import { JobPanel, useJob } from "../components/JobPanel";
import { Badge, Button, Card, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { ApiError, bridge, call } from "../lib/api";
import { useLab } from "../lib/context";
import { CATEGORY_LABEL, CATEGORY_ORDER, fmtBytes } from "../lib/data";
import { maskId } from "../lib/format";
import { useRpc } from "../lib/hooks";
import { AUTH_LABEL } from "../lib/labels";

type Source = "android_adb" | "apple_backup" | "local_import";

const SOURCES: { id: Source; label: string; icon: typeof Smartphone; text: string }[] = [
  { id: "android_adb", label: "Android", icon: Smartphone, text: "Almacenamiento compartido por depuración USB autorizada." },
  { id: "apple_backup", label: "iPhone / iPad", icon: Apple, text: "Respaldo oficial completo del dispositivo emparejado." },
  { id: "local_import", label: "Importar", icon: Upload, text: "Carpeta o .zip de otra fuente autorizada." },
];

export default function DataRecovery() {
  const { scan, selectedKey, setSelectedKey, settings, backend, navigate } = useLab();
  const ready = backend.state === "ready";
  const mask = settings?.maskIdentifiers ?? false;
  const folders = useRpc("recovery.folders", undefined, { enabled: ready });
  const cases = useRpc("cases.list", {}, { enabled: ready });
  const [source, setSource] = useState<Source>("android_adb");
  const [paths, setPaths] = useState<string[]>(["/sdcard/DCIM", "/sdcard/Pictures", "/sdcard/Documents", "/sdcard/Download"]);
  const [custom, setCustom] = useState("");
  const [contacts, setContacts] = useState(true);
  const [localPath, setLocalPath] = useState("");
  const [inventory, setInventory] = useState<RecoveryScan | null>(null);
  const [scanning, setScanning] = useState(false);
  const [caseId, setCaseId] = useState<number | "">("");
  const [pass, setPass] = useState("");
  const [pass2, setPass2] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const { job, setJob } = useJob();

  const platform = source === "apple_backup" ? "apple" : "android";
  const devices = scan?.devices.filter((d) => d.platform === platform && (platform === "apple" || d.connector === "adb")) ?? [];
  const device = devices.find((d) => d.key === selectedKey) ?? null;
  const authorized = device?.authState === "authorized";
  const openCases = cases.data?.filter((c) => !["closed"].includes(c.status)) ?? [];
  const passOk = pass.length >= 10 && pass === pass2;
  const canStart =
    caseId !== "" && passOk && !(job?.status === "running") &&
    (source === "local_import" ? localPath.trim() !== "" : authorized && (source === "apple_backup" || paths.length > 0 || contacts));

  const toggle = (p: string) => {
    setInventory(null);
    setPaths(paths.includes(p) ? paths.filter((x) => x !== p) : [...paths, p]);
  };
  const addCustom = () => {
    const p = custom.trim();
    if (p && !paths.includes(p)) toggle(p);
    setCustom("");
  };
  const fail = (e: unknown) => setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));

  const analyze = async () => {
    if (!device) return;
    setScanning(true);
    setError(null);
    try {
      setInventory(await call("recovery.scan", { deviceKey: device.key, paths }));
    } catch (e) {
      fail(e);
    } finally {
      setScanning(false);
    }
  };
  const pick = async (kind: "folder" | "zip") => {
    try {
      const p = await bridge().pickSource(kind);
      if (p) setLocalPath(p);
    } catch (e) {
      fail(e);
    }
  };
  const start = async () => {
    setError(null);
    try {
      const j: Job = await call("recovery.start", {
        source, caseId, passphrase: pass, passphraseConfirm: pass2,
        deviceKey: device?.key, paths: source === "android_adb" ? paths : undefined,
        includeContacts: source === "android_adb" ? contacts : undefined,
        localPath: source === "local_import" ? localPath : undefined,
        expectedBytes: inventory?.totalBytes,
      });
      setJob(j);
      setPass("");
      setPass2("");
    } catch (e) {
      fail(e);
    }
  };

  return (
    <>
      <PageHeader title="Centro de recuperación de datos"
        subtitle="Respalda, importa y clasifica los datos accesibles por interfaces autorizadas. Todo respaldo queda cifrado." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_400px]">
        <div className="space-y-4">
          <Card title="1 · Origen de los datos" icon={<Archive className="h-3.5 w-3.5" />}>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
              {SOURCES.map(({ id, label, icon: Icon, text }) => (
                <button key={id} onClick={() => { setSource(id); setInventory(null); setError(null); }}
                  className={`rounded-lg border p-3 text-left transition ${source === id ? "border-cyan-500/60 bg-cyan-500/10" : "border-lab-line hover:border-cyan-500/30"}`}>
                  <div className="flex items-center gap-2 text-sm font-medium text-white"><Icon className="h-4 w-4" />{label}</div>
                  <div className="mt-1 text-xs text-lab-mute">{text}</div>
                </button>
              ))}
            </div>

            {source !== "local_import" && (
              <div className="mt-4 space-y-2">
                <label className="label" htmlFor="dr-device">Dispositivo</label>
                <select id="dr-device" className="input" value={device?.key ?? ""} onChange={(e) => { setSelectedKey(e.target.value || null); setInventory(null); }}>
                  <option value="">— Seleccione —</option>
                  {devices.map((d) => <option key={d.key} value={d.key}>{d.label} ({maskId(d.serial, mask)}) · {AUTH_LABEL[d.authState] ?? d.authState}</option>)}
                </select>
                {devices.length === 0 && <div className="text-xs text-lab-mute">No hay dispositivos {platform === "apple" ? "Apple" : "Android por ADB"} conectados.</div>}
                {device && !authorized && (
                  <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-xs text-amber-200">
                    El dispositivo no está autorizado. {platform === "apple" ? "El titular debe desbloquearlo y pulsar «Confiar»." : "El titular debe aceptar la depuración USB."}{" "}
                    Si la pantalla no funciona, use el <button className="underline" onClick={() => navigate("screen-recovery")}>Asistente de pantalla dañada</button>.
                  </div>
                )}
              </div>
            )}

            {source === "apple_backup" && (
              <div className="mt-3 rounded-md border border-lab-line bg-lab-bg p-3 text-xs text-lab-mute">
                Se crea un respaldo oficial completo con el motor Apple. Si el titular tiene activado el cifrado de respaldos, el respaldo
                queda protegido con su contraseña: MR Lab no la solicita ni la almacena, y lo guarda íntegro como «Respaldo local».
                El dispositivo puede pedir que el titular introduzca su código en pantalla.
              </div>
            )}

            {source === "local_import" && (
              <div className="mt-4 space-y-2">
                <label className="label" htmlFor="dr-local">Carpeta o archivo .zip</label>
                <input id="dr-local" className="input font-mono" placeholder="C:\Usuarios\...\Exportación" value={localPath} onChange={(e) => setLocalPath(e.target.value)} />
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => pick("folder")}><FolderOpen className="h-4 w-4" /> Elegir carpeta</Button>
                  <Button onClick={() => pick("zip")}><FileArchive className="h-4 w-4" /> Elegir .zip</Button>
                </div>
                <div className="text-xs text-lab-mute">Por ejemplo, una exportación de Google Takeout, una tarjeta SD o un respaldo entregado por el titular.</div>
              </div>
            )}
          </Card>

          {source === "android_adb" && (
            <Card title="2 · Qué respaldar" icon={<Search className="h-3.5 w-3.5" />}
              actions={<Button onClick={analyze} disabled={!authorized || scanning || paths.length === 0}>{scanning ? <Spinner /> : <Search className="h-4 w-4" />} Analizar contenido</Button>}>
              <div className="grid grid-cols-1 gap-1.5 md:grid-cols-2">
                {folders.data?.map((f) => (
                  <label key={f.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-white/5">
                    <input type="checkbox" className="accent-cyan-400" checked={paths.includes(f.path)} onChange={() => toggle(f.path)} />
                    <span className="flex-1">{f.label}</span>
                    <span className="font-mono text-[10px] text-lab-mute">{f.path.replace("/sdcard/", "")}</span>
                  </label>
                ))}
                {paths.filter((p) => !folders.data?.some((f) => f.path === p)).map((p) => (
                  <label key={p} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-white/5">
                    <input type="checkbox" className="accent-cyan-400" checked onChange={() => toggle(p)} />
                    <span className="flex-1 font-mono text-xs">{p}</span>
                  </label>
                ))}
              </div>
              <div className="mt-2 flex gap-2">
                <input className="input font-mono" placeholder="/sdcard/otra/carpeta" value={custom} onChange={(e) => setCustom(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addCustom()} />
                <Button onClick={addCustom}>Añadir</Button>
              </div>
              <label className="mt-3 flex items-start gap-2 text-sm">
                <input type="checkbox" className="mt-1 accent-cyan-400" checked={contacts} onChange={(e) => setContacts(e.target.checked)} />
                <span>Contactos del dispositivo <span className="block text-xs text-lab-mute">Solo si el sistema permite consultarlos por esta interfaz; si no, se indicará en el resultado.</span></span>
              </label>
              <div className="mt-2 text-[11px] text-lab-mute">Las carpetas privadas de las apps (Android/data, Android/obb) no son accesibles por interfaces autorizadas.</div>

              {inventory && (
                <div className="mt-4 border-t border-lab-line pt-4">
                  <div className="mb-2 flex items-baseline justify-between">
                    <div className="label">Contenido encontrado</div>
                    <div className="text-sm text-white tabular-nums">{inventory.totalFiles} archivos · {fmtBytes(inventory.totalBytes)}</div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                    {CATEGORY_ORDER.filter((c) => c !== "contacts").map((c) => (
                      <div key={c} className="rounded-md border border-lab-line px-3 py-2">
                        <div className="text-xs text-lab-mute">{CATEGORY_LABEL[c]}</div>
                        <div className="text-sm text-white tabular-nums">{inventory.categories[c].files} · {fmtBytes(inventory.categories[c].bytes)}</div>
                      </div>
                    ))}
                  </div>
                  <ul className="mt-3 space-y-1 text-xs">
                    {inventory.folders.map((f) => (
                      <li key={f.path} className="flex justify-between gap-2">
                        <span className="font-mono text-lab-mute">{f.path}</span>
                        <span className="tabular-nums">{f.files ? `${f.files} archivos · ${fmtBytes(f.bytes)}` : "vacía o inexistente"}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Card title={`${source === "android_adb" ? "3" : "2"} · Expediente y cifrado`} icon={<ShieldCheck className="h-3.5 w-3.5" />}>
            <div className="space-y-3">
              <div>
                <label className="label" htmlFor="dr-case">Expediente (obligatorio)</label>
                <select id="dr-case" className="input" value={caseId} onChange={(e) => setCaseId(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">— Seleccione —</option>
                  {openCases.map((c) => <option key={c.id} value={c.id}>{c.folio} · {c.deviceModel || c.deviceType}</option>)}
                </select>
                {openCases.length === 0 && (
                  <div className="mt-1 text-xs text-lab-mute">No hay expedientes abiertos. <button className="underline" onClick={() => navigate("case-files")}>Crear uno</button>.</div>
                )}
              </div>
              <div>
                <label className="label" htmlFor="dr-pass">Frase de cifrado</label>
                <input id="dr-pass" type="password" className="input" autoComplete="new-password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="Mínimo 10 caracteres" />
              </div>
              <div>
                <label className="label" htmlFor="dr-pass2">Confirmar frase</label>
                <input id="dr-pass2" type="password" className="input" autoComplete="new-password" value={pass2} onChange={(e) => setPass2(e.target.value)} />
                {pass2 && pass !== pass2 && <div className="mt-1 text-xs text-rose-300">Las frases no coinciden.</div>}
              </div>
              <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-xs text-amber-200">
                MR Lab no guarda esta frase. Sin ella el respaldo no se puede abrir. Entréguela al titular por un medio seguro.
              </div>
              <ErrorBox error={error} />
              <Button variant="primary" onClick={start} disabled={!canStart}><Play className="h-4 w-4" /> Iniciar respaldo cifrado</Button>
            </div>
          </Card>

          {job && (
            <JobPanel job={job}>
              {job.status === "done" && job.result && (
                <div className="mt-3 space-y-2 text-sm">
                  <div className="text-emerald-200">
                    Respaldo #{String(job.result.backupId)}: {String(job.result.files)} archivos · {fmtBytes(Number(job.result.bytes))}
                  </div>
                  {(job.result.warnings as string[]).map((w) => <div key={w} className="text-xs text-amber-200">• {w}</div>)}
                  <Button onClick={() => navigate("backup-manager")}>Ver en Respaldos</Button>
                </div>
              )}
            </JobPanel>
          )}
          <Card title="Qué se guarda">
            <ul className="space-y-1.5 text-xs text-lab-mute">
              <li><Badge tone="accent">AES-256-GCM</Badge> Contenedor cifrado con clave derivada de la frase (scrypt).</li>
              <li><Badge tone="accent">SHA-256</Badge> Huella de cada archivo y del contenedor para verificar integridad.</li>
              <li><Badge tone="accent">Evidencias</Badge> Inicio, resultado, avisos y huellas quedan en el expediente.</li>
              <li><Badge tone="muted">Temporal</Badge> Los archivos sin cifrar solo existen durante el proceso y se eliminan al terminar.</li>
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
