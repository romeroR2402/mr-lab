import { DatabaseBackup, Download, FolderOpen, KeyRound, ListTree, ShieldCheck, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import type { BackupFile, BackupRecord, DataCategory } from "../../shared/types";
import { JobPanel, useJob } from "../components/JobPanel";
import { Badge, Button, Card, Empty, ErrorBox, KV, PageHeader, Spinner } from "../components/ui";
import { ApiError, bridge, call } from "../lib/api";
import { useLab } from "../lib/context";
import { CATEGORY_LABEL, CATEGORY_ORDER, fmtBytes } from "../lib/data";
import { fmtDate, maskId } from "../lib/format";
import { useRpc } from "../lib/hooks";

const VERIFY: Record<string, { label: string; tone: "ok" | "error" | "warning" | "muted" }> = {
  ok: { label: "Íntegro", tone: "ok" },
  sha_mismatch: { label: "Huella no coincide", tone: "error" },
  failed: { label: "Falló la verificación", tone: "error" },
};

function Detail({ b, onChanged }: { b: BackupRecord; onChanged: () => void }) {
  const { settings } = useLab();
  const mask = settings?.maskIdentifiers ?? false;
  const [pass, setPass] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [files, setFiles] = useState<BackupFile[] | null>(null);
  const [browsing, setBrowsing] = useState(false);
  const [filter, setFilter] = useState<DataCategory | "all">("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [cats, setCats] = useState<DataCategory[]>(CATEGORY_ORDER.filter((c) => b.categories[c].files > 0));
  const [confirm, setConfirm] = useState("");
  const { job, setJob } = useJob(() => onChanged());
  const fail = (e: unknown) => setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
  const busy = job?.status === "running";

  const shown = useMemo(() => (files ?? []).filter((f) =>
    (filter === "all" || f.category === filter) && (!search || f.path.toLowerCase().includes(search.toLowerCase()))), [files, filter, search]);

  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
    } catch (e) {
      fail(e);
    }
  };
  const browse = () => run(async () => {
    setBrowsing(true);
    try {
      const r = await call("backups.browse", { id: b.id, passphrase: pass });
      setFiles(r.files);
      setSelected(new Set());
    } finally {
      setBrowsing(false);
    }
  });
  const verify = () => run(async () => setJob(await call("backups.verify", { id: b.id, passphrase: pass })));
  const exportCats = () => run(async () => setJob(await call("backups.export", { id: b.id, passphrase: pass, categories: cats })));
  const exportSelected = () => run(async () => setJob(await call("backups.export", { id: b.id, passphrase: pass, paths: [...selected] })));
  const remove = () => run(async () => {
    await call("backups.delete", { id: b.id, confirmation: confirm });
    onChanged();
  });

  return (
    <div className="space-y-4">
      <Card title={`Respaldo #${b.id}`} icon={<DatabaseBackup className="h-3.5 w-3.5" />}
        actions={b.verifyResult ? <Badge tone={VERIFY[b.verifyResult].tone}>{VERIFY[b.verifyResult].label}</Badge> : <Badge tone="muted">Sin verificar</Badge>}>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <KV items={[
            ["Expediente", b.folio],
            ["Creado", fmtDate(b.createdAt)],
            ["Origen", b.sourceLabel],
            ["Dispositivo", b.deviceLabel ?? "—"],
            ["Identificador", maskId(b.deviceSerial, mask)],
            ["Archivos", `${b.fileCount} · ${fmtBytes(b.plainBytes)}`],
            ["Contenedor", `${b.fileName} · ${fmtBytes(b.containerBytes)}`],
            ["SHA-256", <span title={b.containerSha256}>{b.containerSha256.slice(0, 24)}…</span>],
            ["Verificado", b.verifiedAt ? fmtDate(b.verifiedAt) : "Nunca"],
          ]} />
          <div className="grid grid-cols-2 content-start gap-2">
            {CATEGORY_ORDER.map((c) => (
              <div key={c} className={`rounded-md border px-3 py-2 ${b.categories[c].files ? "border-lab-line" : "border-lab-line/40 opacity-50"}`}>
                <div className="text-xs text-lab-mute">{CATEGORY_LABEL[c]}</div>
                <div className="text-sm text-white tabular-nums">{b.categories[c].files} · {fmtBytes(b.categories[c].bytes)}</div>
              </div>
            ))}
          </div>
        </div>
        {b.warnings.length > 0 && (
          <div className="mt-3 space-y-0.5 rounded-md border border-amber-500/20 bg-amber-500/5 p-2 text-xs text-amber-200">
            {b.warnings.map((w) => <div key={w}>• {w}</div>)}
          </div>
        )}
      </Card>

      <Card title="Abrir con la frase de cifrado" icon={<KeyRound className="h-3.5 w-3.5" />}>
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[240px] flex-1">
            <label className="label" htmlFor="bm-pass">Frase del respaldo</label>
            <input id="bm-pass" type="password" className="input" autoComplete="off" value={pass} onChange={(e) => setPass(e.target.value)} />
          </div>
          <Button onClick={verify} disabled={!pass || busy}><ShieldCheck className="h-4 w-4" /> Verificar integridad</Button>
          <Button onClick={browse} disabled={!pass || busy || browsing}>{browsing ? <Spinner /> : <ListTree className="h-4 w-4" />} Explorar contenido</Button>
        </div>
        <div className="mt-2 text-[11px] text-lab-mute">La frase solo se usa en memoria para esta operación; no se guarda.</div>
        <div className="mt-3"><ErrorBox error={error} /></div>

        <div className="mt-4 border-t border-lab-line pt-4">
          <div className="label">Exportar por categoría al expediente</div>
          <div className="flex flex-wrap gap-2">
            {CATEGORY_ORDER.filter((c) => b.categories[c].files > 0).map((c) => (
              <label key={c} className="flex items-center gap-1.5 rounded-md border border-lab-line px-2 py-1 text-sm">
                <input type="checkbox" className="accent-cyan-400" checked={cats.includes(c)}
                  onChange={() => setCats(cats.includes(c) ? cats.filter((x) => x !== c) : [...cats, c])} />
                {CATEGORY_LABEL[c]} <span className="text-xs text-lab-mute">({b.categories[c].files})</span>
              </label>
            ))}
            <Button variant="primary" onClick={exportCats} disabled={!pass || busy || cats.length === 0}><Download className="h-4 w-4" /> Exportar</Button>
          </div>
          <div className="mt-1 text-[11px] text-lab-mute">Cada archivo exportado se compara con su huella SHA-256 y se genera un manifiesto de exportación.</div>
        </div>
      </Card>

      {job && (
        <JobPanel job={job}>
          {job.status === "done" && job.kind === "export" && job.result && (
            <div className="mt-3 space-y-2 text-sm">
              <div className="text-emerald-200">{String(job.result.files)} archivos exportados · {fmtBytes(Number(job.result.bytes))}</div>
              {(job.result.mismatches as string[]).length > 0 && (
                <div className="text-xs text-rose-300">Huella distinta en: {(job.result.mismatches as string[]).join(", ")}</div>
              )}
              <div className="break-all font-mono text-[11px] text-lab-mute">{String(job.result.path)}</div>
              <Button onClick={() => bridge().openPath(String(job.result!.path))}><FolderOpen className="h-4 w-4" /> Abrir carpeta</Button>
            </div>
          )}
          {job.status === "done" && job.kind === "verify" && job.result && (
            <div className="mt-3 text-sm text-emerald-200">
              {job.result.result === "ok" ? "Contenedor íntegro: todos los bloques se autenticaron y la huella coincide." : "La huella del contenedor no coincide con la registrada."}
            </div>
          )}
        </JobPanel>
      )}

      {files && (
        <Card title={`Contenido (${shown.length} de ${files.length})`} icon={<ListTree className="h-3.5 w-3.5" />}
          actions={<Button variant="primary" onClick={exportSelected} disabled={!pass || busy || selected.size === 0}><Download className="h-4 w-4" /> Exportar seleccionados ({selected.size})</Button>}>
          <div className="mb-3 flex flex-wrap gap-2">
            <select className="input max-w-[200px]" value={filter} onChange={(e) => setFilter(e.target.value as DataCategory | "all")}>
              <option value="all">Todas las categorías</option>
              {CATEGORY_ORDER.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
            </select>
            <input className="input max-w-[320px]" placeholder="Buscar por nombre o carpeta" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="max-h-[480px] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-lab-panel text-left text-[11px] uppercase tracking-wider text-lab-mute">
                <tr>
                  <th className="py-2 pr-2"><input type="checkbox" className="accent-cyan-400" aria-label="Seleccionar todo"
                    checked={shown.length > 0 && shown.every((f) => selected.has(f.path))}
                    onChange={(e) => setSelected(e.target.checked ? new Set(shown.map((f) => f.path)) : new Set())} /></th>
                  <th className="py-2 pr-3">Archivo</th><th className="py-2 pr-3">Categoría</th>
                  <th className="py-2 pr-3 text-right">Tamaño</th><th className="py-2 pr-3">Modificado</th><th className="py-2">SHA-256</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-lab-line">
                {shown.slice(0, 1000).map((f) => (
                  <tr key={f.path}>
                    <td className="py-1.5 pr-2"><input type="checkbox" className="accent-cyan-400" checked={selected.has(f.path)}
                      onChange={() => { const s = new Set(selected); s.has(f.path) ? s.delete(f.path) : s.add(f.path); setSelected(s); }} /></td>
                    <td className="max-w-[360px] break-all py-1.5 pr-3 font-mono text-xs">{f.path}</td>
                    <td className="py-1.5 pr-3"><Badge tone="muted">{CATEGORY_LABEL[f.category]}</Badge></td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{fmtBytes(f.size)}</td>
                    <td className="whitespace-nowrap py-1.5 pr-3 text-xs text-lab-mute">{fmtDate(f.mtime)}</td>
                    <td className="py-1.5 font-mono text-[11px] text-lab-mute" title={f.sha256}>{f.sha256.slice(0, 12)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {shown.length > 1000 && <div className="py-2 text-xs text-lab-mute">Se muestran los primeros 1000; use el buscador o los filtros.</div>}
          </div>
        </Card>
      )}

      <Card title="Eliminar respaldo" icon={<Trash2 className="h-3.5 w-3.5" />}>
        <div className="text-sm text-lab-mute">Borra el contenedor cifrado de este equipo. La eliminación queda en el Registro de evidencias y no se puede deshacer.</div>
        <div className="mt-2 flex flex-wrap gap-2">
          <input className="input max-w-[260px] font-mono" placeholder={`ELIMINAR ${b.id}`} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          <Button variant="danger" onClick={remove} disabled={confirm !== `ELIMINAR ${b.id}`}><Trash2 className="h-4 w-4" /> Eliminar</Button>
        </div>
      </Card>
    </div>
  );
}

export default function BackupManager() {
  const { backend, navigate } = useLab();
  const list = useRpc("backups.list", {}, { enabled: backend.state === "ready" });
  const [selected, setSelected] = useState<number | null>(null);
  const current = list.data?.find((b) => b.id === selected) ?? null;

  return (
    <>
      <PageHeader title="Administrador de respaldos" subtitle="Respaldos cifrados del laboratorio: verificar, explorar, exportar y eliminar."
        actions={<Button variant="primary" onClick={() => navigate("data-recovery")}><DatabaseBackup className="h-4 w-4" /> Nuevo respaldo</Button>} />
      <ErrorBox error={list.error} onRetry={list.reload} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[380px_1fr]">
        <Card title={`Respaldos (${list.data?.length ?? 0})`}>
          {list.data?.length ? (
            <ul className="space-y-1">
              {list.data.map((b) => (
                <li key={b.id}>
                  <button onClick={() => setSelected(b.id)}
                    className={`w-full rounded-md border px-3 py-2 text-left transition ${selected === b.id ? "border-cyan-500/50 bg-cyan-500/5" : "border-transparent hover:bg-white/5"}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm text-white">#{b.id} · {b.deviceLabel ?? b.sourceLabel}</span>
                      {b.verifyResult ? <Badge tone={VERIFY[b.verifyResult].tone}>{VERIFY[b.verifyResult].label}</Badge> : <Badge tone="muted">Sin verificar</Badge>}
                    </div>
                    <div className="mt-0.5 text-xs text-lab-mute">
                      <span className="font-mono text-cyan-200/80">{b.folio}</span> · {b.fileCount} archivos · {fmtBytes(b.plainBytes)} · {fmtDate(b.createdAt)}
                    </div>
                    {!b.present && <div className="text-xs text-rose-300">Archivo no encontrado en disco</div>}
                  </button>
                </li>
              ))}
            </ul>
          ) : list.loading ? <Spinner /> : (
            <Empty icon={<DatabaseBackup className="h-6 w-6" />} title="Sin respaldos">Cree el primero en Recuperación de datos.</Empty>
          )}
        </Card>
        <div>
          {current ? <Detail key={current.id} b={current} onChanged={() => { list.reload(); }} /> : (
            <Card><Empty icon={<DatabaseBackup className="h-8 w-8" />} title="Seleccione un respaldo">
              Para explorar, verificar o exportar se necesita la frase de cifrado con la que se creó.
            </Empty></Card>
          )}
        </div>
      </div>
    </>
  );
}
