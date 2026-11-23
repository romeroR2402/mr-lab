"""Orquestador de diagnósticos y persistencia de reportes."""
from __future__ import annotations

import json

from .. import db, evidence, scanner
from ..errors import RpcError
from ..util.timeutil import now_iso
from .android import run_adb, run_fastboot
from .apple import run_apple
from .model import summarize


def recovery_channels(dev: dict) -> list[dict]:
    """Vías de recuperación realmente disponibles según el estado de comunicación,
    con el estado de implementación del módulo que las ejecutará."""
    ch = []
    if dev["platform"] == "android" and dev["commState"] == "online" and dev["authState"] == "authorized":
        ch.append({"id": "adb_pull", "label": "Copia de almacenamiento compartido vía ADB (interfaz autorizada)",
                   "module": "data-recovery", "implemented": False})
    if dev["platform"] == "apple" and dev["authState"] == "authorized":
        ch.append({"id": "apple_backup", "label": "Respaldo local oficial (idevicebackup2)",
                   "module": "backup-manager", "implemented": False})
    if dev["mode"] in ("recovery", "sideload"):
        ch.append({"id": "sideload", "label": "Actualización OTA oficial por sideload",
                   "module": "system-repair", "implemented": False})
    return ch


def run(device_key: str, case_id: int | None = None) -> dict:
    dev = scanner.get_cached(device_key)
    if dev is None:
        raise RpcError("device_not_found", "El dispositivo no está conectado. Ejecute un escaneo nuevamente.")
    try:
        if dev.connector == "fastboot":
            checks = run_fastboot(dev)
        elif dev.platform == "android":
            checks = run_adb(dev)
        elif dev.platform == "apple":
            checks = run_apple(dev)
        else:
            raise RpcError("unsupported", f"Plataforma no soportada: {dev.platform}")
    except RpcError:
        raise
    except Exception as e:
        evidence.log("Diagnóstico", "failure", device_serial=dev.serial, device_label=dev.label,
                     case_id=case_id, error=str(e))
        raise RpcError("diagnostic_failed", f"El diagnóstico falló: {e}") from e

    api_dev = dev.to_api()
    report = {
        "device": api_dev,
        "timestamp": now_iso(),
        "summaryStatus": summarize(checks),
        "checks": [c.to_api() for c in checks],
        "recoveryChannels": recovery_channels(api_dev),
        "caseId": case_id,
    }
    with db.write() as conn:
        cur = conn.execute(
            "INSERT INTO diagnostic_reports(timestamp, platform, device_serial, device_label, case_id, summary_status, report_json)"
            " VALUES(?,?,?,?,?,?,?)",
            (report["timestamp"], dev.platform, dev.serial, dev.label, case_id, report["summaryStatus"],
             json.dumps(report, ensure_ascii=False)),
        )
        report["id"] = cur.lastrowid
    counts = {s: sum(1 for c in checks if c.status == s) for s in ("ok", "warning", "error", "unavailable")}
    evidence.log("Diagnóstico", "success", device_serial=dev.serial, device_label=dev.label, case_id=case_id,
                 details={"reporte": report["id"], "resultado": report["summaryStatus"], **counts})
    if case_id:
        from .. import cases
        cases.add_operation(case_id, "Diagnóstico", report["summaryStatus"], dev.connector, f"Reporte #{report['id']}")
    return report


def history(device_serial: str | None = None, limit: int = 50) -> list[dict]:
    q = "SELECT id, timestamp, platform, device_serial, device_label, case_id, summary_status FROM diagnostic_reports"
    args: list = []
    if device_serial:
        q += " WHERE device_serial = ?"
        args.append(device_serial)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(max(1, min(int(limit), 500)))
    with db.read() as conn:
        rows = conn.execute(q, args).fetchall()
    return [{"id": r["id"], "timestamp": r["timestamp"], "platform": r["platform"], "deviceSerial": r["device_serial"],
             "deviceLabel": r["device_label"], "caseId": r["case_id"], "summaryStatus": r["summary_status"]} for r in rows]


def get_report(report_id: int) -> dict:
    with db.read() as conn:
        row = conn.execute("SELECT report_json FROM diagnostic_reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        raise RpcError("not_found", f"Reporte {report_id} no encontrado")
    out = json.loads(row["report_json"])
    out["id"] = report_id
    return out


def latest_for(serial: str) -> dict | None:
    with db.read() as conn:
        row = conn.execute("SELECT id, report_json FROM diagnostic_reports WHERE device_serial = ? ORDER BY id DESC LIMIT 1",
                           (serial,)).fetchone()
    if not row:
        return None
    out = json.loads(row["report_json"])
    out["id"] = row["id"]
    return out
