import { FilePlus2, FolderKanban, FolderOpen, ScrollText, ShieldCheck, X } from "lucide-react";
import CaseReport from "../components/CaseReport";
import { FormEvent, useState } from "react";
import type { CaseRecord } from "../../shared/types";
import { Badge, Button, Card, Empty, ErrorBox, KV, PageHeader, Spinner } from "../components/ui";
import { ApiError, bridge, call } from "../lib/api";
import { useLab } from "../lib/context";
import { fmtDate } from "../lib/format";
import { useRpc } from "../lib/hooks";
import { AUTH_TYPES, CASE_STATUS, DEVICE_TYPES, RESULT_LABEL, STATUS_LABEL } from "../lib/labels";

const RESULT_TONE: Record<string, "ok" | "error" | "warning" | "info" | "accent" | "muted"> = {
  success: "ok", failure: "error", warning: "warning", info: "info", confirmed: "accent", cancelled: "muted",
};

function NewCaseForm({ onCreated, onCancel }: { onCreated: (c: CaseRecord) => void; onCancel: () => void }) {
  const { scan, settings } = useLab();
  const dev = scan?.devices[0];
  const [f, setF] = useState({
    technician: settings?.technicianName ?? "",
    deviceType: dev ? (dev.platform === "apple" ? (dev.osName === "iPadOS" ? "ipados" : "ios") : "android") : "android",
    deviceModel: dev?.label ?? "",
    deviceSerial: dev?.serial ?? "",
    reason: "",
    authorizationType: "owner",
    authorizedBy: "",
    authorizationRef: "",
    authorizationConfirmed: false,
  });
  const [error, setError] = useState<ApiError | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      onCreated(await call("cases.create", f));
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("unknown", String(err)));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card title="Nuevo expediente" icon={<FilePlus2 className="h-3.5 w-3.5" />}
      actions={<Button variant="ghost" onClick={onCancel}><X className="h-4 w-4" /></Button>}>
      <form onSubmit={submit} className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div><label className="label">Técnico</label><input className="input" value={f.technician} onChange={set("technician")} placeholder="Nombre del técnico" /></div>
        <div><label className="label">Tipo de dispositivo</label>
          <select className="input" value={f.deviceType} onChange={set("deviceType")}>
            {Object.entries(DEVICE_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select></div>
        <div><label className="label">Modelo</label><input className="input" value={f.deviceModel} onChange={set("deviceModel")} /></div>
        <div><label className="label">Identificador / serie</label><input className="input font-mono" value={f.deviceSerial} onChange={set("deviceSerial")} /></div>
        <div className="md:col-span-2"><label className="label">Motivo del servicio *</label>
          <textarea className="input min-h-[70px]" required value={f.reason} onChange={set("reason")}
            placeholder="Ej.: pantalla rota sin imagen, el cliente solicita respaldo de fotografías." /></div>
        <div><label className="label">Tipo de autorización *</label>
          <select className="input" value={f.authorizationType} onChange={set("authorizationType")}>
            {Object.entries(AUTH_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select></div>
        <div><label className="label">Autorizado por *</label><input className="input" required value={f.authorizedBy} onChange={set("authorizedBy")} placeholder="Nombre del titular / representante" /></div>
        <div className="md:col-span-2"><label className="label">Referencia del documento de autorización</label>
          <input className="input" value={f.authorizationRef} onChange={set("authorizationRef")} placeholder="Nº de orden de servicio, identificación, oficio…" /></div>
        <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200 md:col-span-2">
          No registre códigos de desbloqueo, PIN, patrones ni contraseñas del dispositivo o de cuentas. MR Lab no los almacena.
        </div>
        <label className="flex items-start gap-2 text-sm md:col-span-2">
          <input type="checkbox" className="mt-1 accent-cyan-400" checked={f.authorizationConfirmed}
            onChange={(e) => setF({ ...f, authorizationConfirmed: e.target.checked })} />
          Confirmo que cuento con autorización documentada del titular o de autoridad competente para intervenir este dispositivo.
        </label>
        <div className="md:col-span-2"><ErrorBox error={error} /></div>
        <div className="flex justify-end gap-2 md:col-span-2">
          <Button onClick={onCancel}>Cancelar</Button>
          <Button type="submit" variant="primary" disabled={saving || !f.authorizationConfirmed}>{saving && <Spinner />} Abrir expediente</Button>
        </div>
      </form>
    </Card>
  );
}

function CaseDetail({ id, onChanged }: { id: number; onChanged: () => void }) {
  const c = useRpc("cases.get", { id });
  const ev = useRpc("evidence.list", { caseId: id, limit: 100 });
  const [status, setStatus] = useState("");
  const [results, setResults] = useState("");
  if (!c.data) return c.error ? <ErrorBox error={c.error} /> : <Spinner />;
  const d = c.data;
  const save = async () => {
    await call("cases.updateStatus", { id, status: status || d.status, results: results || undefined });
    setResults("");
    c.reload();
    ev.reload();
    onChanged();
  };
  return (
    <div className="space-y-4">
      <Card title={`Expediente ${d.folio}`} icon={<FolderKanban className="h-3.5 w-3.5" />}
        actions={<Badge tone="accent">{CASE_STATUS[d.status] ?? d.status}</Badge>}>
        <KV items={[
          ["Folio", d.folio], ["Fecha de ingreso", fmtDate(d.createdAt)], ["Técnico", d.technician],
          ["Tipo", DEVICE_TYPES[d.deviceType] ?? d.deviceType], ["Modelo", d.deviceModel], ["Identificador", d.deviceSerial],
          ["Motivo", d.reason], ["Autorización", `${AUTH_TYPES[d.authorizationType] ?? d.authorizationType} · ${d.authorizedBy}`],
          ["Referencia", d.authorizationRef], ["Resultados", d.results], ["Actualizado", fmtDate(d.updatedAt)],
        ]} />
        <div className="mt-4 grid grid-cols-1 gap-2 border-t border-lab-line pt-4 md:grid-cols-[200px_1fr_auto]">
          <select className="input" value={status || d.status} onChange={(e) => setStatus(e.target.value)}>
            {Object.entries(CASE_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <input className="input" placeholder="Resultados / observaciones" value={results} onChange={(e) => setResults(e.target.value)} />
          <Button variant="primary" onClick={save}>Guardar</Button>
        </div>
      </Card>
      <Card title="Operaciones realizadas">
        {d.operations?.length ? (
          <ul className="space-y-1 text-sm">{d.operations.map((o) => (
            <li key={o.id} className="flex justify-between gap-2"><span>{o.operation} {o.method && <span className="text-lab-mute">({o.method})</span>} · {o.details}</span>
              <span className="text-lab-mute">{STATUS_LABEL[o.result as keyof typeof STATUS_LABEL] ?? RESULT_LABEL[o.result] ?? o.result} · {fmtDate(o.timestamp)}</span></li>
          ))}</ul>
        ) : <div className="text-sm text-lab-mute">Sin operaciones registradas.</div>}
      </Card>
      <CaseReport caseId={id} onGenerated={() => { c.reload(); ev.reload(); onChanged(); }} />
      <Card title={`Archivos exportados (${d.files?.length ?? 0})`}>
        {d.files?.length ? (
          <ul className="divide-y divide-lab-line">
            {d.files.map((f) => (
              <li key={f.id} className="flex items-start justify-between gap-3 py-2 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <div className="text-sm text-white">{f.description ?? "Archivo"}</div>
                  <div className="break-all font-mono text-[11px] text-lab-mute">{f.path}</div>
                  <div className="font-mono text-[10px] text-lab-mute/70" title={f.sha256 ?? ""}>{fmtDate(f.createdAt)} · SHA-256 {f.sha256?.slice(0, 16)}…</div>
                </div>
                <Button variant="ghost" onClick={() => bridge().openPath(f.path)}><FolderOpen className="h-4 w-4" /> Abrir</Button>
              </li>
            ))}
          </ul>
        ) : <div className="text-sm text-lab-mute">Sin archivos. Aquí aparecen las exportaciones de respaldos, los reportes de operaciones y el reporte del expediente.</div>}
      </Card>
      <Card title="Evidencias del expediente">
        <EvidenceTable entries={ev.data?.entries ?? []} />
      </Card>
    </div>
  );
}

function EvidenceTable({ entries }: { entries: { id: number; timestamp: string; technician: string; deviceLabel: string | null; deviceSerial: string | null; operation: string; result: string; details: string | null; error: string | null; confirmation: string | null; entryHash: string }[] }) {
  if (!entries.length) return <div className="text-sm text-lab-mute">Sin registros.</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-[11px] uppercase tracking-wider text-lab-mute">
          <tr><th className="pb-2 pr-3">#</th><th className="pb-2 pr-3">Fecha y hora</th><th className="pb-2 pr-3">Técnico</th><th className="pb-2 pr-3">Dispositivo</th>
            <th className="pb-2 pr-3">Operación</th><th className="pb-2 pr-3">Resultado</th><th className="pb-2 pr-3">Detalle</th><th className="pb-2">Hash</th></tr>
        </thead>
        <tbody className="divide-y divide-lab-line">
          {entries.map((e) => (
            <tr key={e.id} className="align-top">
              <td className="py-2 pr-3 font-mono text-lab-mute">{e.id}</td>
              <td className="whitespace-nowrap py-2 pr-3">{fmtDate(e.timestamp)}</td>
              <td className="py-2 pr-3">{e.technician}</td>
              <td className="py-2 pr-3">{e.deviceLabel ?? e.deviceSerial ?? "—"}</td>
              <td className="py-2 pr-3">{e.operation}</td>
              <td className="py-2 pr-3"><Badge tone={RESULT_TONE[e.result] ?? "muted"}>{RESULT_LABEL[e.result] ?? e.result}</Badge></td>
              <td className="max-w-[320px] py-2 pr-3 text-xs text-lab-mute">
                {e.details}{e.confirmation && <div className="text-cyan-200/80">{e.confirmation}</div>}{e.error && <div className="text-rose-300">{e.error}</div>}
              </td>
              <td className="py-2 font-mono text-[11px] text-lab-mute" title={e.entryHash}>{e.entryHash.slice(0, 10)}…</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CaseFiles() {
  const [tab, setTab] = useState<"cases" | "evidence">("cases");
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const list = useRpc("cases.list", { search: search || undefined });
  const ev = useRpc("evidence.list", { limit: 300 }, { enabled: tab === "evidence" });
  const [verify, setVerify] = useState<{ valid: boolean; checked: number; brokenAtId: number | null } | null>(null);

  return (
    <>
      <PageHeader title="Expedientes" subtitle="Expedientes de servicio y registro de evidencias."
        actions={<>
          <Button variant={tab === "cases" ? "primary" : "default"} onClick={() => setTab("cases")}><FolderKanban className="h-4 w-4" /> Expedientes</Button>
          <Button variant={tab === "evidence" ? "primary" : "default"} onClick={() => setTab("evidence")}><ScrollText className="h-4 w-4" /> Registro de evidencias</Button>
        </>} />
      {tab === "cases" ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[380px_1fr]">
          <Card title="Expedientes" actions={<Button variant="primary" onClick={() => { setCreating(true); setSelected(null); }}><FilePlus2 className="h-4 w-4" /> Nuevo</Button>}>
            <input className="input mb-3" placeholder="Buscar folio, modelo, motivo…" value={search} onChange={(e) => setSearch(e.target.value)} />
            <ErrorBox error={list.error} onRetry={list.reload} />
            {list.data?.length ? (
              <ul className="space-y-1">
                {list.data.map((c) => (
                  <li key={c.id}>
                    <button onClick={() => { setSelected(c.id); setCreating(false); }}
                      className={`w-full rounded-md border px-3 py-2 text-left transition ${selected === c.id ? "border-cyan-500/50 bg-cyan-500/5" : "border-transparent hover:bg-white/5"}`}>
                      <div className="flex items-center justify-between"><span className="font-mono text-sm text-cyan-200">{c.folio}</span><Badge tone="accent">{CASE_STATUS[c.status]}</Badge></div>
                      <div className="mt-0.5 truncate text-xs text-lab-mute">{c.deviceModel || DEVICE_TYPES[c.deviceType]} · {c.reason}</div>
                    </button>
                  </li>
                ))}
              </ul>
            ) : <Empty icon={<FolderKanban className="h-6 w-6" />} title="Sin expedientes" />}
          </Card>
          <div>
            {creating && <NewCaseForm onCancel={() => setCreating(false)} onCreated={(c) => { setCreating(false); setSelected(c.id); list.reload(); }} />}
            {!creating && selected && <CaseDetail key={selected} id={selected} onChanged={list.reload} />}
            {!creating && !selected && <Card><Empty icon={<FolderKanban className="h-8 w-8" />} title="Seleccione o cree un expediente">
              Cada expediente requiere la confirmación de autorización del titular.</Empty></Card>}
          </div>
        </div>
      ) : (
        <Card title={`Registro de evidencias · ${ev.data?.total ?? 0} registros`} icon={<ScrollText className="h-3.5 w-3.5" />}
          actions={<>
            {verify && <Badge tone={verify.valid ? "ok" : "error"}>{verify.valid ? `Cadena íntegra (${verify.checked})` : `Alteración detectada en #${verify.brokenAtId}`}</Badge>}
            <Button onClick={async () => setVerify(await call("evidence.verify"))}><ShieldCheck className="h-4 w-4" /> Verificar integridad</Button>
          </>}>
          <ErrorBox error={ev.error} onRetry={ev.reload} />
          <EvidenceTable entries={ev.data?.entries ?? []} />
        </Card>
      )}
    </>
  );
}
