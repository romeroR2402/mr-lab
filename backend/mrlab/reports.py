"""Exportación y reportes del expediente.

El backend arma un informe HTML autocontenido (imprimible) y un JSON con los
mismos datos. Electron convierte el HTML a PDF (printToPDF) y el backend
registra el PDF resultante en el expediente con su SHA-256."""
from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime
from pathlib import Path

from . import backups, cases, config, db, evidence, settings
from .access import engine as access_engine
from .diagnostics import engine as diag_engine
from .errors import RpcError
from .recovery.categories import CATEGORIES
from .screen import engine as screen_engine
from .service import engine as service_engine
from .util.timeutil import now_iso

SECTIONS = {
    "case": "Datos del expediente y autorización",
    "diagnostics": "Diagnósticos",
    "screen": "Evaluaciones de pantalla",
    "access": "Análisis de acceso",
    "backups": "Respaldos",
    "service": "Operaciones de servicio",
    "files": "Archivos exportados",
    "evidence": "Registro de evidencias",
}
STATUS_TXT = {"ok": "Correcto", "warning": "Advertencia", "error": "Falla", "info": "Información", "unavailable": "No disponible"}
RECOV_TXT = {"likely": "Recuperación probable", "conditional": "Condicionada al titular", "unlikely": "Poco probable",
             "unknown": "Indeterminada"}
RESULT_TXT = {"success": "Correcto", "failure": "Falla", "info": "Información", "warning": "Advertencia",
              "cancelled": "Cancelado", "confirmed": "Confirmado"}


CASE_STATUS = {"open": "Abierto", "in_progress": "En proceso", "waiting_client": "En espera del cliente",
               "completed": "Completado", "not_recoverable": "Sin recuperación posible", "closed": "Cerrado"}
DEVICE_TYPE = {"android": "Android", "ios": "iPhone (iOS)", "ipados": "iPad (iPadOS)", "other": "Otro"}
AUTH_TYPE = {"owner": "Propietario del dispositivo", "legal_rep": "Representante legal", "company": "Empresa titular",
             "court_order": "Orden judicial"}
PRESENT = {"yes": "Presente", "no": "No configurado", "unknown": "No determinado"}
APPLIC = {"applicable": "Aplicable", "conditional": "Condicional", "not_applicable": "No aplica", "blocked": "Bloqueada",
          "unknown": "Indeterminada"}
LOSS = {"none": "Sin pérdida", "possible": "Posible", "full_wipe": "Borrado total", "unknown": "Desconocida"}
RSTATUS = {"active": "Activa", "inactive": "Inactiva", "partial": "Parcial", "unknown": "Desconocida"}
SEVERITY = {"blocker": "Bloqueante", "high": "Alta", "medium": "Media", "info": "Info"}


def _d(iso) -> str:
    """Fecha ISO → dd/mm/aaaa hh:mm."""
    try:
        return datetime.fromisoformat(str(iso)).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return "—" if not iso else str(iso)


def _t(mapping: dict, v) -> str:
    return mapping.get(v, v) if v is not None else None


def reports_dir(folio: str) -> Path:
    d = config.sub_dir("exports") / folio / "reportes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _e(v) -> str:
    return html.escape("—" if v is None or v == "" else str(v))


def _fmt_bytes(n) -> str:
    f = float(n or 0)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or u == "TB":
            return f"{f:.1f} {u}" if u != "B" else f"{int(f)} B"
        f /= 1024
    return str(n)


def collect(case_id: int) -> dict:
    case = cases.get(case_id)
    with db.read() as conn:
        diag_ids = [r["id"] for r in conn.execute("SELECT id FROM diagnostic_reports WHERE case_id = ? ORDER BY id", (case_id,))]
        if not diag_ids and case.get("deviceSerial"):
            diag_ids = [r["id"] for r in conn.execute(
                "SELECT id FROM diagnostic_reports WHERE device_serial = ? ORDER BY id DESC LIMIT 1", (case["deviceSerial"],))]
        screen_ids = [r["id"] for r in conn.execute("SELECT id FROM screen_assessments WHERE case_id = ? ORDER BY id", (case_id,))]
        access_ids = [r["id"] for r in conn.execute("SELECT id FROM access_analyses WHERE case_id = ? ORDER BY id", (case_id,))]
    ev = evidence.list_entries(limit=1000, case_id=case_id)
    return {
        "generatedAt": now_iso(),
        "lab": settings.get("labName") or "Mobile Recovery Lab",
        "technician": settings.technician(),
        "case": case,
        "diagnostics": [diag_engine.get_report(i) for i in diag_ids],
        "screen": [screen_engine.get(i) for i in screen_ids],
        "access": [access_engine.get(i) for i in access_ids],
        "backups": backups.list_backups(case_id),
        "service": service_engine.history(case_id=case_id),
        "evidence": list(reversed(ev["entries"])),
        "evidenceTotal": ev["total"],
        "chain": evidence.verify_chain(),
    }


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "<p class='muted'>Sin registros.</p>"
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table class='grid'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(d: dict, sections: list[str]) -> str:
    c = d["case"]
    parts: list[str] = []
    n = 0

    def sec(key: str, body: str) -> None:
        nonlocal n
        if key in sections:
            n += 1
            parts.append(f"<section><h2>{n}. {SECTIONS[key]}</h2>{body}</section>")

    kv = lambda items: "<table class='kv'>" + "".join(f"<tr><th>{_e(k)}</th><td>{v}</td></tr>" for k, v in items) + "</table>"
    sec("case", kv([
        ("Folio", _e(c["folio"])), ("Fecha de ingreso", _e(_d(c["createdAt"]))), ("Técnico", _e(c["technician"])),
        ("Tipo de dispositivo", _e(_t(DEVICE_TYPE, c["deviceType"]))), ("Modelo", _e(c["deviceModel"])), ("Identificador", _e(c["deviceSerial"])),
        ("Motivo del servicio", _e(c["reason"])), ("Autorización", _e(f"{_t(AUTH_TYPE, c['authorizationType'])} · {c['authorizedBy']}")),
        ("Referencia de autorización", _e(c["authorizationRef"])), ("Estado", _e(_t(CASE_STATUS, c["status"]))),
        ("Resultados", _e(c["results"])), ("Última actualización", _e(_d(c["updatedAt"]))),
    ]) + "<h3>Operaciones registradas</h3>" + _table(
        ["Fecha", "Operación", "Método", "Resultado", "Detalle"],
        [[_e(_d(o["timestamp"])), _e(o["operation"]), _e(o["method"]), _e(_t({**RESULT_TXT, **STATUS_TXT}, o["result"])), _e(o["details"])] for o in c.get("operations", [])]))

    diag_html = ""
    for r in d["diagnostics"]:
        rows = [[_e(x["category"]), _e(x["label"]), _e(STATUS_TXT.get(x["status"], x["status"])), _e(x["value"]), _e(x["detail"])]
                for x in r["checks"]]
        diag_html += (f"<h3>Reporte #{r['id']} · {_e(r['device']['label'])} · {_e(_d(r['timestamp']))} · "
                      f"resultado: {_e(STATUS_TXT.get(r['summaryStatus'], r['summaryStatus']))}</h3>"
                      + _table(["Categoría", "Prueba", "Estado", "Valor", "Detalle"], rows))
    sec("diagnostics", diag_html or "<p class='muted'>Sin diagnósticos vinculados.</p>")

    scr = ""
    for a in d["screen"]:
        recs = "".join(f"<li><b>{_e(x['title'])}</b> ({_e(x['category'])})</li>" for x in a["recommendations"])
        notes = "".join(f"<li>{_e(x['text'])}</li>" for x in a["notes"])
        flags = ", ".join(f"{_e(f['label'])}: {_e(f['state'])}" for f in a["flags"])
        scr += (f"<h3>Evaluación #{a['id']} · {_e(a['deviceLabel'])} · {_e(_d(a['timestamp']))}</h3>"
                f"<p><b>Clasificación:</b> {_e(a['categoryLabel'])}. {_e(a['summary'])}<br><span class='muted'>{flags}</span></p>"
                + (f"<p><b>Observación vs. sistema</b></p><ul>{notes}</ul>" if notes else "")
                + f"<p><b>Recomendaciones</b></p><ol>{recs}</ol>")
    sec("screen", scr or "<p class='muted'>Sin evaluaciones vinculadas.</p>")

    acc = ""
    for a in d["access"]:
        mech = _table(["Mecanismo", "Estado", "Detalle"], [[_e(m["label"]), _e(_t(PRESENT, m["present"])), _e(m["detail"])] for m in a["mechanisms"]])
        restr = _table(["Restricción", "Estado", "Severidad", "Detalle"],
                       [[_e(r["label"]), _e(_t(RSTATUS, r["status"])), _e(_t(SEVERITY, r["severity"])), _e(r["detail"])] for r in a["restrictions"]])
        opts = _table(["Vía oficial", "Aplicabilidad", "Pérdida de datos"],
                      [[_e(o["title"]), _e(_t(APPLIC, o["applicability"])), _e(_t(LOSS, o["dataLoss"]))] for o in a["options"]])
        acc += (f"<h3>Análisis #{a['id']} · {_e(a['deviceLabel'])} · {_e(_d(a['timestamp']))} · "
                f"{_e(RECOV_TXT.get(a['recoverability'], a['recoverability']))}</h3><p>{_e(a['summary'])}</p>"
                f"{mech}{restr}{opts}<p class='muted'>{_e(a['disclaimer'])}</p>")
    sec("access", acc or "<p class='muted'>Sin análisis vinculados.</p>")

    sec("backups", _table(
        ["#", "Creado", "Origen", "Archivos", "Tamaño", "Categorías", "Verificación", "SHA-256 del contenedor"],
        [[str(b["id"]), _e(_d(b["createdAt"])), _e(b["sourceLabel"]), str(b["fileCount"]), _fmt_bytes(b["plainBytes"]),
          _e(", ".join(f"{CATEGORIES[k]}: {v['files']}" for k, v in b["categories"].items() if v["files"])),
          _e({"ok": "Íntegro", "sha_mismatch": "Huella distinta", "failed": "Falló"}.get(b["verifyResult"] or "", "Sin verificar")),
          f"<code>{_e(b['containerSha256'])}</code>"] for b in d["backups"]])
        + "<p class='muted'>Los respaldos están cifrados con AES-256-GCM; la frase de cifrado no se almacena en MR Lab.</p>")

    sec("service", _table(
        ["#", "Fecha", "Operación", "Método", "Tipo", "Impacto", "Resultado", "Técnico"],
        [[str(s["id"]), _e(_d(s["startedAt"])), _e(s["title"]), _e(s["method"]), "Ejecutada" if s["kind"] == "auto" else "Guiada",
          _e(service_engine.IMPACT_LABEL.get(s["impact"], s["impact"])), _e(RESULT_TXT.get(s["status"], s["status"])),
          _e(s["technician"])] for s in d["service"]]))

    sec("files", _table(["Fecha", "Descripción", "Ruta", "Tamaño", "SHA-256"],
                        [[_e(_d(f["createdAt"])), _e(f["description"]), f"<code>{_e(f['path'])}</code>", _fmt_bytes(f["sizeBytes"]),
                          f"<code>{_e(f['sha256'])}</code>"] for f in c.get("files", [])]))

    chain = d["chain"]
    chain_txt = (f"Cadena íntegra: {chain['checked']} entradas verificadas." if chain["valid"]
                 else f"ALTERACIÓN DETECTADA en la entrada #{chain['brokenAtId']}.")
    sec("evidence", f"<p class='{'ok' if chain['valid'] else 'bad'}'>{_e(chain_txt)}</p>" + _table(
        ["#", "Fecha y hora", "Técnico", "Dispositivo", "Operación", "Resultado", "Detalle", "Hash"],
        [[str(e["id"]), _e(_d(e["timestamp"])), _e(e["technician"]), _e(e["deviceLabel"] or e["deviceSerial"]), _e(e["operation"]),
          _e(RESULT_TXT.get(e["result"], e["result"])),
          _e(" · ".join(x for x in (e["details"], e["confirmation"], e["error"]) if x)), f"<code>{_e(e['entryHash'][:16])}…</code>"]
         for e in d["evidence"]]))

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Reporte del expediente {_e(c['folio'])}</title>
<style>
@page {{ size: A4; margin: 16mm 14mm 18mm; }}
body {{ font: 10.5pt/1.45 "Segoe UI", Arial, sans-serif; color: #0f172a; margin: 0; }}
header {{ border-bottom: 2px solid #0e7490; padding-bottom: 8px; margin-bottom: 14px; }}
header .lab {{ font-size: 9pt; letter-spacing: .12em; text-transform: uppercase; color: #0e7490; }}
h1 {{ font-size: 18pt; margin: 2px 0; }} h2 {{ font-size: 13pt; margin: 18px 0 6px; color: #0e7490; break-after: avoid; }}
h3 {{ font-size: 10.5pt; margin: 12px 0 4px; break-after: avoid; }}
.muted {{ color: #64748b; }} .ok {{ color: #047857; font-weight: 600; }} .bad {{ color: #b91c1c; font-weight: 600; }}
table {{ border-collapse: collapse; width: 100%; margin: 4px 0 8px; }}
.kv th {{ width: 34%; text-align: left; font-weight: 600; color: #334155; }}
th, td {{ padding: 3px 6px; border-bottom: 1px solid #e2e8f0; vertical-align: top; text-align: left; }}
.grid th {{ background: #f1f5f9; font-size: 9pt; }} .grid td {{ font-size: 9pt; }}
tr {{ break-inside: avoid; }} code {{ font: 8pt Consolas, monospace; word-break: break-all; }}
.sign {{ display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin-top: 46px; break-inside: avoid; }}
.sign div {{ border-top: 1px solid #0f172a; padding-top: 4px; font-size: 9pt; text-align: center; }}
footer {{ margin-top: 20px; font-size: 8pt; color: #64748b; }}
</style></head><body>
<header><div class="lab">{_e(d['lab'])}</div><h1>Reporte del expediente {_e(c['folio'])}</h1>
<div class="muted">Generado {_e(_d(d['generatedAt']))} por {_e(d['technician'])} · Dispositivo: {_e(c['deviceModel'])} · Estado: {_e(_t(CASE_STATUS, c['status']))}</div></header>
{''.join(parts)}
<div class="sign"><div>Técnico responsable<br>{_e(c['technician'])}</div><div>Titular / autorizante<br>{_e(c['authorizedBy'])}</div></div>
<footer>Documento generado por Mobile Recovery Lab. Todas las operaciones se realizaron mediante interfaces oficiales y autorizadas por el
titular. La integridad del registro de evidencias puede comprobarse en la aplicación. No contiene códigos de acceso ni contraseñas.</footer>
</body></html>"""


def build(case_id: int, sections: list[str] | None = None) -> dict:
    secs = [s for s in (sections or list(SECTIONS)) if s in SECTIONS]
    if not secs:
        raise RpcError("invalid_params", "Seleccione al menos una sección.")
    d = collect(case_id)
    folio = d["case"]["folio"]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = reports_dir(folio)
    html_path = out / f"expediente-{folio}-{stamp}.html"
    html_path.write_text(render_html(d, secs), encoding="utf-8")
    json_path = out / f"expediente-{folio}-{stamp}.json"
    json_path.write_text(json.dumps({k: v for k, v in d.items()}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return {"html": str(html_path), "json": str(json_path), "pdf": str(html_path.with_suffix(".pdf")), "folio": folio,
            "sections": secs}


def register(case_id: int, paths: list[str]) -> dict:
    """Registra en el expediente los archivos de reporte generados (PDF/JSON/HTML)."""
    case = cases.get(case_id)
    base = (config.sub_dir("exports") / case["folio"] / "reportes").resolve()
    registered = []
    for p in paths:
        path = Path(p).resolve()
        if not str(path).startswith(str(base)) or not path.is_file():
            raise RpcError("invalid_params", f"Ruta de reporte no válida: {p}")
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        kind = {"pdf": "PDF", "json": "JSON", "html": "HTML"}.get(path.suffix.lstrip(".").lower(), path.suffix)
        with db.write() as conn:
            conn.execute("INSERT INTO case_files(case_id, created_at, path, sha256, size_bytes, description) VALUES(?,?,?,?,?,?)",
                         (case_id, now_iso(), str(path), sha, len(data), f"Reporte del expediente ({kind})"))
        registered.append({"path": str(path), "sha256": sha, "size": len(data), "kind": kind})
    evidence.log("Reporte del expediente generado", "success", case_id=case_id, files=[r["path"] for r in registered],
                 details={r["kind"]: r["sha256"] for r in registered})
    cases.add_operation(case_id, "Reporte del expediente", "success", "Exportación PDF/JSON",
                        ", ".join(Path(r["path"]).name for r in registered))
    return {"files": registered}


def list_reports(case_id: int) -> list[dict]:
    case = cases.get(case_id)
    return [f for f in case.get("files", []) if (f.get("description") or "").startswith("Reporte del expediente")]
