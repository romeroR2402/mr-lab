"""Orquestador del análisis de acceso: detección de mecanismos, restricciones,
vías oficiales, compatibilidad, plugins y persistencia/registro."""
from __future__ import annotations

import json

from .. import cases, db, evidence, scanner
from ..diagnostics import engine as diag_engine
from ..errors import RpcError
from ..util.timeutil import now_iso
from . import compat, knowledge, plugins
from .analyzers import android as an_android, apple as an_apple
from .model import AccessAnalysis, AccessContext
from .policy import DISCLAIMER

# Claves internas con volcados crudos que no se persisten ni se entregan a plugins.
_RAW = ("_trust", "_device_policy")


def _limitations(ctx: AccessContext, analysis: AccessAnalysis) -> list[str]:
    lim = ["MR Lab no obtiene, descifra ni evade códigos, patrones, contraseñas o cuentas: "
           "toda recuperación de acceso requiere al titular o al fabricante."]
    if not ctx.properties:
        lim.append("Análisis parcial: el dispositivo no está autorizado; varias señales no se pudieron leer.")
    if any(r.severity == "blocker" and r.status == "active" for r in analysis.restrictions):
        lim.append("Existe al menos una restricción bloqueante por diseño del fabricante (cifrado / bloqueo de activación).")
    return lim


def _recoverability(analysis: AccessAnalysis, ctx: AccessContext) -> tuple[str, str]:
    applicable = [o for o in analysis.options if o.applicability == "applicable" and o.data_loss == "none"]
    blockers = [r for r in analysis.restrictions if r.severity == "blocker" and r.status == "active"]
    lock = next((m for m in analysis.mechanisms if m.id in ("screen_lock", "passcode")), None)
    if not ctx.properties:
        return "unknown", "Sin autorización del dispositivo no es posible un análisis completo."
    if lock and lock.present == "no":
        return "likely", "No hay credencial de pantalla configurada: el acceso es directo."
    if blockers and lock and lock.present == "yes":
        return "conditional", ("El acceso a los datos depende de que el titular conozca o recupere su credencial "
                               "por vías oficiales. Sin ella, solo procede restaurar con pérdida de datos.")
    if applicable:
        return "likely", "Existen vías oficiales aplicables sin pérdida de datos."
    return "unknown", "No se pudo determinar la recuperabilidad con la información disponible."


def analyze(device_key: str, case_id: int | None = None) -> dict:
    dev = scanner.get_cached(device_key)
    if dev is None:
        raise RpcError("device_not_found", "El dispositivo no está conectado. Ejecute un escaneo nuevamente.")
    api_dev = dev.to_api()
    analyzer = an_apple if dev.platform == "apple" else an_android
    try:
        props = analyzer.collect_properties(api_dev)
    except Exception as e:
        props = {}
        evidence.log("Análisis de acceso: lectura de propiedades", "warning",
                     device_serial=dev.serial, device_label=dev.label, case_id=case_id, error=str(e))
    ctx = AccessContext(dev.platform, api_dev, props, diag_engine.latest_for(dev.serial))

    analysis = AccessAnalysis(device_key=device_key, device_label=dev.label, platform=dev.platform,
                              timestamp=now_iso(), summary="", recoverability="unknown",
                              disclaimer=DISCLAIMER, case_id=case_id)
    analysis.mechanisms = analyzer.mechanisms(ctx)
    analysis.restrictions = analyzer.restrictions(ctx)
    analysis.options = knowledge.recovery_options(ctx, analysis.mechanisms, analysis.restrictions)
    compat_results = compat.evaluate(ctx)

    snapshot = {
        "platform": ctx.platform, "device": api_dev,
        "properties": {k: v for k, v in props.items() if k not in _RAW},
        "diagnostic": ctx.diagnostic,
        "mechanisms": [m.to_api() for m in analysis.mechanisms],
        "restrictions": [r.to_api() for r in analysis.restrictions],
    }
    analysis.findings = plugins.run_all(snapshot)
    analysis.recoverability, analysis.summary = _recoverability(analysis, ctx)
    analysis.limitations = _limitations(ctx, analysis)

    out = analysis.to_api()
    out["compatibility"] = compat_results
    with db.write() as conn:
        cur = conn.execute(
            "INSERT INTO access_analyses(timestamp, platform, device_serial, device_label, case_id, recoverability, report_json)"
            " VALUES(?,?,?,?,?,?,?)",
            (analysis.timestamp, dev.platform, dev.serial, dev.label, case_id, analysis.recoverability,
             json.dumps(out, ensure_ascii=False)),
        )
        out["id"] = cur.lastrowid
    evidence.log("Análisis de acceso", "success", device_serial=dev.serial, device_label=dev.label, case_id=case_id,
                 details={"análisis": out["id"], "recuperabilidad": analysis.recoverability,
                          "mecanismos": [m.id for m in analysis.mechanisms if m.present == "yes"],
                          "plugins": sorted({f.plugin_id for f in analysis.findings})})
    if case_id:
        cases.add_operation(case_id, "Análisis de acceso", analysis.recoverability, "lectura oficial",
                            f"Análisis #{out['id']}")
    return out


def history(device_serial: str | None = None, limit: int = 50) -> list[dict]:
    q = "SELECT id, timestamp, platform, device_serial, device_label, case_id, recoverability FROM access_analyses"
    args: list = []
    if device_serial:
        q += " WHERE device_serial = ?"
        args.append(device_serial)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(max(1, min(int(limit), 500)))
    with db.read() as conn:
        rows = conn.execute(q, args).fetchall()
    return [{"id": r["id"], "timestamp": r["timestamp"], "platform": r["platform"], "deviceSerial": r["device_serial"],
             "deviceLabel": r["device_label"], "caseId": r["case_id"], "recoverability": r["recoverability"]} for r in rows]


def get(analysis_id: int) -> dict:
    with db.read() as conn:
        row = conn.execute("SELECT report_json FROM access_analyses WHERE id = ?", (analysis_id,)).fetchone()
    if not row:
        raise RpcError("not_found", f"Análisis {analysis_id} no encontrado")
    out = json.loads(row["report_json"])
    out["id"] = analysis_id
    return out


def procedures() -> list[dict]:
    return [{"id": p.id, "title": p.title, "platforms": p.platforms,
             "checks": [label for _, label, _ in p.checks]} for p in compat.procedures()]
