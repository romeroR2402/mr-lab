import { FileDown, FileText, FolderOpen } from "lucide-react";
import { useState } from "react";
import { ApiError, bridge, call } from "../lib/api";
import { useRpc } from "../lib/hooks";
import { Button, Card, ErrorBox, Spinner } from "./ui";

/** Genera el reporte final del expediente en PDF (y JSON) y lo adjunta. */
export default function CaseReport({ caseId, onGenerated }: { caseId: number; onGenerated: () => void }) {
  const sections = useRpc("reports.sections");
  const [selected, setSelected] = useState<string[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [last, setLast] = useState<{ pdf: string; folder: string } | null>(null);
  const chosen = selected ?? sections.data?.map((s) => s.id) ?? [];

  const generate = async () => {
    setError(null);
    setLast(null);
    try {
      setBusy("Reuniendo datos del expediente…");
      const built = await call("reports.build", { caseId, sections: chosen });
      setBusy("Generando PDF…");
      const pdf = await bridge().reportToPdf(built.html);
      setBusy("Registrando en el expediente…");
      await call("reports.register", { caseId, paths: [pdf, built.json] });
      setLast({ pdf, folder: pdf.replace(/[\\/][^\\/]+$/, "") });
      onGenerated();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("report_failed", e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card title="Reporte del expediente" icon={<FileText className="h-3.5 w-3.5" />}>
      <div className="text-sm text-lab-mute">Documento PDF (A4) con firma de técnico y titular, más un JSON con los mismos datos. Ambos se adjuntan con su huella SHA-256.</div>
      <div className="mt-3 grid grid-cols-1 gap-1 md:grid-cols-2">
        {sections.data?.map((s) => (
          <label key={s.id} className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="accent-cyan-400" checked={chosen.includes(s.id)}
              onChange={() => setSelected(chosen.includes(s.id) ? chosen.filter((x) => x !== s.id) : [...chosen, s.id])} />
            {s.label}
          </label>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button variant="primary" onClick={generate} disabled={!!busy || chosen.length === 0}>
          {busy ? <Spinner /> : <FileDown className="h-4 w-4" />} Generar PDF
        </Button>
        {busy && <span className="text-xs text-lab-mute">{busy}</span>}
        {last && (
          <>
            <Button onClick={() => bridge().openPath(last.pdf)}><FileText className="h-4 w-4" /> Abrir PDF</Button>
            <Button variant="ghost" onClick={() => bridge().openPath(last.folder)}><FolderOpen className="h-4 w-4" /> Carpeta</Button>
          </>
        )}
      </div>
      <div className="mt-2"><ErrorBox error={error} /></div>
    </Card>
  );
}
