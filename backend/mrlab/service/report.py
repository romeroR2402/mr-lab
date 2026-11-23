"""Reporte HTML autocontenido de cada operación de servicio (imprimible)."""
from __future__ import annotations

import hashlib
import html
from datetime import datetime
from pathlib import Path

from .. import config, settings

STATUS = {"success": ("Completada", "#047857"), "failure": ("Fallida", "#b91c1c")}
RESULT = {"pass": "Cumple", "warn": "Advertencia", "fail": "No cumple", "unknown": "Sin datos"}


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def write(op_db_id: int, p: dict, status: str, output: str, technician: str, started: str, finished: str,
          acks: list[str], confirmation: str, evidence_ids: list[int]) -> dict:
    op, dev = p["operation"], p["device"]
    lab = settings.get("labName") or "Mobile Recovery Lab"
    label, color = STATUS.get(status, (status, "#334155"))
    rows = lambda items: "".join(f"<tr><th>{_e(k)}</th><td>{v}</td></tr>" for k, v in items)
    checks = "".join(f"<tr><td>{_e(c['label'])}</td><td>{_e(RESULT.get(c['result'], c['result']))}</td><td>{_e(c['detail'])}</td></tr>"
                     for c in p["checks"]) or "<tr><td colspan='3'>Sin comprobaciones para esta operación.</td></tr>"
    steps = "".join(f"<li>{_e(s)}</li>" for s in op["steps"])
    warns = "".join(f"<li>{_e(w)}</li>" for w in op["warnings"])
    cmds = "".join(f"<li><code>{_e(c)}</code></li>" for c in p["commands"])
    doc = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Reporte de operación #{op_db_id} · {_e(p['folio'])}</title>
<style>
body{{font:14px/1.5 "Segoe UI",system-ui,sans-serif;color:#0f172a;max-width:860px;margin:32px auto;padding:0 20px}}
h1{{font-size:22px;margin:0}} h2{{font-size:15px;margin:28px 0 8px;border-bottom:1px solid #cbd5e1;padding-bottom:4px}}
.muted{{color:#64748b}} .status{{display:inline-block;padding:2px 10px;border-radius:4px;color:#fff;background:{color};font-weight:600}}
table{{border-collapse:collapse;width:100%}} th,td{{text-align:left;vertical-align:top;padding:5px 8px;border-bottom:1px solid #e2e8f0}}
th{{width:220px;color:#334155;font-weight:600}} code,pre{{font-family:Consolas,ui-monospace,monospace;font-size:12.5px}}
pre{{background:#f1f5f9;padding:10px;border-radius:4px;white-space:pre-wrap;word-break:break-all}}
.warn{{background:#fef3c7;border:1px solid #f59e0b;padding:8px 12px;border-radius:4px}}
@media print{{body{{margin:0}}}}
</style></head><body>
<div class="muted">{_e(lab)} · Reporte de operación de servicio</div>
<h1>{_e(op['title'])} <span class="status">{label}</span></h1>
<div class="muted">Operación #{op_db_id} · Expediente {_e(p['folio'])} · Generado {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</div>
<h2>Datos generales</h2>
<table>{rows([("Técnico", _e(technician)), ("Dispositivo", _e(dev['label'])), ("Identificador", _e(dev['serial'])),
              ("Sistema", _e(f"{dev.get('osName') or ''} {dev.get('osVersion') or ''}".strip() or '—')),
              ("Conexión / modo", _e(f"{dev['connection']} · {dev['mode']}")), ("Inicio", _e(started)), ("Fin", _e(finished))])}</table>
<h2>Método utilizado</h2>
<table>{rows([("Método oficial", _e(op['method'])), ("Tipo", "Ejecutada por MR Lab" if op['kind'] == 'auto' else "Guiada (realizada por el técnico)"),
              ("Impacto en los datos", _e(op['impactLabel']))])}</table>
{f"<p><b>Comandos</b></p><ul>{cmds}</ul>" if cmds else ""}
{f"<p><b>Pasos</b></p><ol>{steps}</ol>" if steps else ""}
<h2>Advertencias mostradas</h2>
{f"<div class='warn'><ul>{warns}</ul></div>" if warns else "<p class='muted'>Sin advertencias específicas.</p>"}
<h2>Comprobaciones previas</h2>
<table><tr><th>Comprobación</th><th>Resultado</th><th>Detalle</th></tr>{checks}</table>
<h2>Confirmación</h2>
<ul>{''.join(f"<li>☑ {_e(a)}</li>" for a in acks)}</ul>
<p>Frase escrita por el técnico: <code>{_e(confirmation)}</code></p>
<h2>Resultado</h2>
<pre>{_e(output) or 'Sin salida.'}</pre>
<p class="muted">Entradas del Registro de evidencias: {', '.join(f'#{i}' for i in evidence_ids)}. La integridad del registro puede
verificarse en MR Lab (Expedientes → Registro de evidencias → Verificar integridad).</p>
</body></html>"""
    out_dir = config.sub_dir("exports") / p["folio"] / "reportes"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"operacion-{op_db_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.html"
    data = doc.encode("utf-8")
    path.write_bytes(data)
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
