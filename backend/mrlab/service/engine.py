"""Motor de reparación y restauración.

Flujo obligatorio para cualquier operación:
  1. plan(): método, comandos, advertencias, comprobaciones previas y la frase de
     confirmación exacta. Devuelve un planId válido 15 minutos.
  2. execute() / record_guided(): exige planId vigente, expediente, casillas de
     reconocimiento y la frase escrita. Registra solicitud y resultado en el
     Registro de evidencias y genera un reporte HTML adjunto al expediente.
"""
from __future__ import annotations

import json
import re
import secrets
import subprocess
import threading
import time

from .. import cases, config, db, evidence, jobs, scanner, settings, tools
from ..access import engine as access_engine
from ..connectors.android import AdbConnector, FastbootConnector
from ..diagnostics import engine as diag_engine
from ..errors import RpcError
from ..util.proc import run
from ..util.timeutil import now_iso
from . import report
from .operations import BY_ID, OPERATIONS, Operation

PLAN_TTL = 15 * 60
_plans: dict[str, dict] = {}
_plans_lock = threading.Lock()
_PKG = re.compile(r"^[a-zA-Z][\w]*(\.[a-zA-Z][\w]*)+$")
WINFLAGS = 0x08000000 if config.IS_WINDOWS else 0

IMPACT_LABEL = {"none": "Sin pérdida de datos", "app_data": "Borra los datos de una app", "full_wipe": "Borrado total"}


# ------------------------------------------------------------------ utilidades
def _device(device_key: str):
    dev = scanner.get_cached(device_key)
    if dev is None:
        raise RpcError("device_not_found", "El dispositivo no está conectado. Escanee de nuevo.")
    return dev


def _availability(op: Operation, dev) -> tuple[bool, str | None]:
    if op.platform != dev.platform:
        return False, "Otra plataforma"
    if op.kind == "guided":
        return True, None
    if dev.mode not in op.modes:
        need = ", ".join(op.modes)
        return False, f"Requiere el dispositivo en modo: {need} (ahora: {dev.mode})."
    if op.needs_auth and dev.auth_state != "authorized":
        return False, "Requiere el dispositivo autorizado por el titular."
    if op.tool == "adb" and (dev.connector != "adb" or not tools.find("adb")):
        return False, "Requiere conexión ADB."
    if op.tool == "fastboot" and (dev.connector != "fastboot" or not tools.find("fastboot")):
        return False, "Requiere el dispositivo en bootloader detectado por fastboot."
    if op.tool == "adb|fastboot" and not tools.find(dev.connector if dev.connector in ("adb", "fastboot") else "adb"):
        return False, "Motor Android no disponible."
    if op.tool == "ideviceenterrecovery" and not tools.find("ideviceenterrecovery"):
        return False, "Herramienta ideviceenterrecovery no disponible en este equipo."
    return True, None


def list_operations(device_key: str, group: str | None = None) -> dict:
    dev = _device(device_key)
    out = []
    for op in OPERATIONS:
        if op.platform != dev.platform or (group and op.group != group):
            continue
        ok, reason = _availability(op, dev)
        out.append({**op.to_api(), "available": ok, "unavailableReason": reason, "impactLabel": IMPACT_LABEL[op.impact]})
    return {"device": dev.to_api(), "operations": out}


def third_party_packages(device_key: str) -> list[str]:
    dev = _device(device_key)
    if dev.connector != "adb" or dev.auth_state != "authorized":
        raise RpcError("not_authorized", "Requiere el dispositivo autorizado por ADB.")
    r = AdbConnector().shell(dev.serial, "pm list packages -3", timeout=30)
    return sorted(line.split(":", 1)[1].strip() for line in r.stdout.splitlines() if line.startswith("package:"))


def _battery_pct(serial: str) -> int | None:
    d = diag_engine.latest_for(serial)
    if not d:
        return None
    b = next((c for c in d.get("checks", []) if c.get("id") == "battery"), None)
    m = re.match(r"(\d+)%", (b or {}).get("value") or "")
    return int(m.group(1)) if m else None


def _latest_backup(serial: str) -> dict | None:
    with db.read() as conn:
        r = conn.execute("SELECT id, created_at, file_count, verify_result FROM backups WHERE device_serial = ? "
                         "AND status = 'ok' ORDER BY id DESC LIMIT 1", (serial,)).fetchone()
    return dict(r) if r else None


def _protection(dev) -> str | None:
    """Estado de FRP / bloqueo de activación según el último análisis de acceso."""
    hist = access_engine.history(dev.serial, limit=1)
    if not hist:
        return None
    a = access_engine.get(hist[0]["id"])
    m = next((x for x in a["mechanisms"] if x["id"] in ("frp", "activation_lock")), None)
    return m["present"] if m else None


def _prechecks(op: Operation, dev, params: dict) -> tuple[list[dict], list[dict]]:
    """(comprobaciones, reconocimientos requeridos)."""
    checks: list[dict] = []
    acks: list[dict] = [{"id": "authorized", "label": "El titular autorizó esta operación y consta en el expediente."}]
    pct = _battery_pct(dev.serial)
    if op.impact == "full_wipe" or op.id in ("android_ota_sideload", "android_oem_reflash", "apple_update"):
        if pct is None:
            checks.append({"id": "battery", "label": "Batería", "result": "unknown",
                           "detail": "Sin diagnóstico reciente: verifique que la carga sea de al menos 50 %."})
        else:
            checks.append({"id": "battery", "label": "Batería", "result": "pass" if pct >= 50 else ("warn" if pct >= 20 else "fail"),
                           "detail": f"{pct} % (recomendado ≥ 50 %)"})
    if op.impact in ("full_wipe", "app_data"):
        b = _latest_backup(dev.serial)
        if b:
            checks.append({"id": "backup", "label": "Respaldo en MR Lab", "result": "pass",
                           "detail": f"Respaldo #{b['id']} ({b['file_count']} archivos, {b['created_at']})"
                                     + (" · verificado" if b["verify_result"] == "ok" else " · sin verificar")})
        else:
            checks.append({"id": "backup", "label": "Respaldo en MR Lab", "result": "warn",
                           "detail": "No hay respaldo de este dispositivo en MR Lab."})
            acks.append({"id": "no_backup", "label": "El titular sabe que no hay respaldo en MR Lab y acepta continuar."})
    if op.impact == "full_wipe":
        prot = _protection(dev)
        label = "Bloqueo de activación (Apple ID)" if dev.platform == "apple" else "FRP (cuenta Google)"
        checks.append({"id": "protection", "label": label,
                       "result": {"no": "pass", "yes": "warn"}.get(prot or "", "unknown"),
                       "detail": {"no": "No detectado en el último análisis de acceso.",
                                  "yes": "Activo: tras el borrado se pedirá la cuenta del titular."}.get(
                           prot or "", "Sin análisis de acceso: asuma que está activo.")})
        acks.append({"id": "account", "label": "El titular conoce (o puede recuperar) la cuenta Google / Apple ID del equipo."})
        acks.append({"id": "data_loss", "label": "Se advirtió al titular que se borrarán todos los datos de forma irreversible."})
    if op.id == "android_fastboot_wipe":
        v = FastbootConnector().getvar_all(dev.serial)
        unlocked = v.get("unlocked")
        checks.append({"id": "bootloader", "label": "Bootloader desbloqueado", "result": "pass" if unlocked == "yes" else "fail",
                       "detail": {"yes": "Desbloqueado: el fabricante permite borrar userdata.",
                                  "no": "Bloqueado: el fabricante no permite este método. Use recovery o Ajustes."}.get(
                           unlocked or "", "No reportado por el bootloader.")})
    if op.id == "android_ota_sideload":
        path = params.get("file") or ""
        from pathlib import Path
        p = Path(path)
        ok = p.is_file() and p.suffix.lower() == ".zip"
        checks.append({"id": "package", "label": "Paquete OTA", "result": "pass" if ok else "fail",
                       "detail": f"{p.name} · {p.stat().st_size // (1024 * 1024)} MB" if ok else "Seleccione un archivo .zip existente."})
        acks.append({"id": "official", "label": "El paquete es la OTA oficial del fabricante para este modelo exacto."})
    if op.id == "android_uninstall_app":
        pkg = params.get("package") or ""
        ok = bool(_PKG.match(pkg)) and pkg in third_party_packages(dev.key)
        checks.append({"id": "package", "label": "App de terceros", "result": "pass" if ok else "fail",
                       "detail": pkg if ok else "Seleccione una app instalada por el usuario."})
    if op.kind == "guided":
        acks.append({"id": "performed", "label": "Realicé el procedimiento siguiendo los pasos indicados y verifiqué el resultado."})
    return checks, acks


def _phrase(op: Operation, dev, params: dict) -> str:
    tail = dev.serial[-4:].upper()
    if op.impact == "full_wipe":
        return f"RESTABLECER {tail}"
    if op.impact == "app_data":
        return f"DESINSTALAR {params.get('package', '')}"
    if op.id == "android_ota_sideload":
        return f"INSTALAR OTA {tail}"
    return f"CONFIRMAR {tail}"


# -------------------------------------------------------------------- plan
def plan(device_key: str, op_id: str, case_id: int, params: dict | None = None) -> dict:
    params = params or {}
    op = BY_ID.get(op_id)
    if not op:
        raise RpcError("not_found", f"Operación desconocida: {op_id}")
    if not isinstance(case_id, int):
        raise RpcError("case_required", "Vincule un expediente: toda operación de servicio debe quedar documentada.")
    case = cases.get(case_id)
    if case["status"] == "closed":
        raise RpcError("invalid_params", "El expediente está cerrado.")
    dev = _device(device_key)
    ok, reason = _availability(op, dev)
    if not ok:
        raise RpcError("unavailable", reason or "Operación no disponible.")
    checks, acks = _prechecks(op, dev, params)
    blocked = [c for c in checks if c["result"] == "fail"]
    plan_id = secrets.token_hex(8)
    commands = [c.replace("<serie>", dev.serial).replace("<UDID>", dev.serial)
                 .replace("<paquete>", params.get("package", "<paquete>"))
                 .replace("<paquete_ota.zip>", params.get("file", "<paquete_ota.zip>")) for c in op.commands]
    out = {"planId": plan_id, "operation": {**op.to_api(), "impactLabel": IMPACT_LABEL[op.impact]},
           "device": dev.to_api(), "caseId": case_id, "folio": case["folio"], "params": params, "commands": commands,
           "checks": checks, "acknowledgements": acks, "confirmationPhrase": _phrase(op, dev, params),
           "blocked": bool(blocked), "blockedReason": "; ".join(c["detail"] for c in blocked) or None,
           "createdAt": now_iso(), "expiresInSeconds": PLAN_TTL}
    with _plans_lock:
        now = time.monotonic()
        for k in [k for k, v in _plans.items() if v["_t"] + PLAN_TTL < now]:
            _plans.pop(k)
        _plans[plan_id] = {**out, "_t": now}
    evidence.log("Plan de operación de servicio", "info", case_id=case_id, device_serial=dev.serial, device_label=dev.label,
                 details={"operación": op.title, "método": op.method, "impacto": IMPACT_LABEL[op.impact],
                          "bloqueado": bool(blocked)})
    return out


def _consume(plan_id: str, confirmation: str, acknowledged: list[str]) -> dict:
    with _plans_lock:
        p = _plans.get(plan_id)
        if not p or p["_t"] + PLAN_TTL < time.monotonic():
            raise RpcError("plan_expired", "El plan caducó o no existe. Vuelva a prepararlo para revisar las advertencias.")
        if p["blocked"]:
            raise RpcError("blocked", f"La operación está bloqueada: {p['blockedReason']}")
        missing = [a["label"] for a in p["acknowledgements"] if a["id"] not in set(acknowledged or [])]
        if missing:
            raise RpcError("ack_required", "Faltan confirmaciones: " + " / ".join(missing))
        if (confirmation or "").strip() != p["confirmationPhrase"]:
            raise RpcError("confirmation_required", f"Escriba exactamente «{p['confirmationPhrase']}» para confirmar.")
        return _plans.pop(plan_id)


# --------------------------------------------------------------- ejecución
def _run_auto(job: jobs.Job, op: Operation, dev, params: dict) -> tuple[bool, str]:
    adb, fb = tools.find("adb"), tools.find("fastboot")
    s = dev.serial
    if op.id == "android_reboot_system":
        r = run([fb, "-s", s, "reboot"] if dev.connector == "fastboot" else [adb, "-s", s, "reboot"], timeout=30)
    elif op.id == "android_reboot_recovery":
        r = run([adb, "-s", s, "reboot", "recovery"], timeout=30)
    elif op.id == "android_reboot_bootloader":
        r = run([adb, "-s", s, "reboot", "bootloader"], timeout=30)
    elif op.id == "android_reboot_sideload":
        r = run([adb, "-s", s, "reboot", "sideload"], timeout=30)
    elif op.id == "android_trim_caches":
        r = run([adb, "-s", s, "shell", "pm trim-caches 999G"], timeout=120)
    elif op.id == "android_uninstall_app":
        r = run([adb, "-s", s, "shell", f"pm uninstall --user 0 {params['package']}"], timeout=60)
        return r.ok and "Success" in r.stdout, r.output.strip()
    elif op.id == "apple_enter_recovery":
        r = run([tools.find("ideviceenterrecovery"), s], timeout=60)
    elif op.id == "android_fastboot_wipe":
        job.update(phase="Borrando userdata (fastboot -w)", progress=0.3)
        r = run([fb, "-s", s, "-w"], timeout=600)
        if not r.ok:
            return False, r.output.strip()
        job.update(phase="Reiniciando", progress=0.8)
        r2 = run([fb, "-s", s, "reboot"], timeout=60)
        return r2.ok, (r.output + r2.output).strip()
    elif op.id == "android_ota_sideload":
        job.update(phase="Enviando paquete OTA al dispositivo", progress=0.0)
        proc = subprocess.Popen([adb, "-s", s, "sideload", params["file"]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", creationflags=WINFLAGS)
        buf, tail = "", []
        while True:
            ch = proc.stdout.read(1)  # type: ignore[union-attr]
            if not ch:
                break
            if ch in "\r\n":
                if buf.strip():
                    tail = (tail + [buf.strip()])[-6:]
                    m = re.search(r"~(\d{1,3})%", buf)
                    if m:
                        job.update(progress=int(m.group(1)) / 100)
                buf = ""
            else:
                buf += ch
            if job.cancelled():
                proc.kill()
                job.check()
        proc.wait()
        proc.stdout.close()  # type: ignore[union-attr]
        text = "\n".join(tail)
        return proc.returncode == 0 and "error" not in text.lower(), text
    else:
        raise RpcError("not_implemented", f"Operación sin ejecutor: {op.id}")
    return r.ok, (r.output or r.error or "").strip()


def _persist(p: dict, status: str, output: str, technician: str, started: str, finished: str,
             ack_labels: list[str], confirmation: str, evidence_ids: list[int]) -> dict:
    op, dev = p["operation"], p["device"]
    with db.write() as conn:
        cur = conn.execute(
            """INSERT INTO service_operations(case_id, device_serial, device_label, op_id, title, grp, kind, method, impact,
                   status, started_at, finished_at, technician, plan_json, output)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p["caseId"], dev["serial"], dev["label"], op["id"], op["title"], op["group"], op["kind"], op["method"],
             op["impact"], status, started, finished, technician,
             json.dumps({k: v for k, v in p.items() if not k.startswith("_")}, ensure_ascii=False), output[-4000:]))
        op_db_id = cur.lastrowid
    rep = report.write(op_db_id, p, status, output, technician, started, finished, ack_labels, confirmation, evidence_ids)
    with db.write() as conn:
        conn.execute("UPDATE service_operations SET report_path = ?, report_sha256 = ? WHERE id = ?",
                     (rep["path"], rep["sha256"], op_db_id))
        conn.execute("INSERT INTO case_files(case_id, created_at, path, sha256, size_bytes, description) VALUES(?,?,?,?,?,?)",
                     (p["caseId"], now_iso(), rep["path"], rep["sha256"], rep["size"], f"Reporte de operación: {op['title']}"))
    evidence.log("Reporte de operación generado", "info", case_id=p["caseId"], device_serial=dev["serial"],
                 device_label=dev["label"], files=[rep["path"]], details={"operación": op_db_id, "sha256": rep["sha256"]})
    cases.add_operation(p["caseId"], op["title"], status, op["method"], f"Operación #{op_db_id} · reporte adjunto")
    return {"operationId": op_db_id, "status": status, "report": rep["path"], "output": output[-2000:]}


def execute(plan_id: str, confirmation: str, acknowledged: list[str]) -> dict:
    p = _consume(plan_id, confirmation, acknowledged)
    op = BY_ID[p["operation"]["id"]]
    if op.kind != "auto":
        raise RpcError("invalid_params", "Esta operación es guiada: regístrela como realizada.")
    dev = scanner.get_cached(p["device"]["key"])
    if dev is None:
        raise RpcError("device_not_found", "El dispositivo se desconectó. Prepare el plan de nuevo.")
    ack_labels = [a["label"] for a in p["acknowledgements"]]
    technician = settings.technician()
    started = now_iso()
    e1 = evidence.log("Operación de servicio confirmada", "confirmed", case_id=p["caseId"], device_serial=dev.serial,
                      device_label=dev.label, confirmation=confirmation,
                      details={"operación": op.title, "método": op.method, "comandos": p["commands"],
                               "impacto": IMPACT_LABEL[op.impact], "reconocimientos": ack_labels})

    def work(job: jobs.Job) -> dict:
        job.update(phase=op.title, progress=None)
        ok, output = _run_auto(job, op, dev, p["params"])
        status = "success" if ok else "failure"
        e2 = evidence.log(f"Operación de servicio: {op.title}", status, case_id=p["caseId"], device_serial=dev.serial,
                          device_label=dev.label, details={"método": op.method, "salida": output[-800:]},
                          error=None if ok else (output[-500:] or "Falló sin salida"))
        res = _persist(p, status, output, technician, started, now_iso(), ack_labels, confirmation, [e1["id"], e2["id"]])
        if not ok:
            raise RpcError("operation_failed", f"La operación falló. Reporte #{res['operationId']} generado. {output[-300:]}")
        return res

    return jobs.start("service", f"{op.title} · {dev.label}", work)


def record_guided(plan_id: str, confirmation: str, acknowledged: list[str], result: str, notes: str | None) -> dict:
    if result not in ("success", "failure"):
        raise RpcError("invalid_params", "Indique si el procedimiento terminó correctamente o falló.")
    p = _consume(plan_id, confirmation, acknowledged)
    op = BY_ID[p["operation"]["id"]]
    if op.kind != "guided":
        raise RpcError("invalid_params", "Esta operación se ejecuta desde MR Lab.")
    dev = p["device"]
    ack_labels = [a["label"] for a in p["acknowledgements"]]
    technician = settings.technician()
    now = now_iso()
    notes = (notes or "").strip()[:2000]
    e = evidence.log(f"Operación guiada registrada: {op.title}", "confirmed" if result == "success" else "failure",
                     case_id=p["caseId"], device_serial=dev["serial"], device_label=dev["label"], confirmation=confirmation,
                     details={"método": op.method, "resultado": result, "notas": notes or None, "reconocimientos": ack_labels})
    output = f"Procedimiento guiado realizado por el técnico. Resultado declarado: {'correcto' if result == 'success' else 'fallido'}."
    if notes:
        output += f"\nNotas del técnico: {notes}"
    return _persist(p, result, output, technician, p["createdAt"], now, ack_labels, confirmation, [e["id"]])


def history(case_id: int | None = None, device_serial: str | None = None, limit: int = 100) -> list[dict]:
    q, args = "SELECT * FROM service_operations WHERE 1=1", []
    if case_id is not None:
        q += " AND case_id = ?"
        args.append(case_id)
    if device_serial:
        q += " AND device_serial = ?"
        args.append(device_serial)
    with db.read() as conn:
        rows = conn.execute(q + " ORDER BY id DESC LIMIT ?", [*args, limit]).fetchall()
    return [{"id": r["id"], "caseId": r["case_id"], "deviceSerial": r["device_serial"], "deviceLabel": r["device_label"],
             "opId": r["op_id"], "title": r["title"], "group": r["grp"], "kind": r["kind"], "method": r["method"],
             "impact": r["impact"], "status": r["status"], "startedAt": r["started_at"], "finishedAt": r["finished_at"],
             "technician": r["technician"], "reportPath": r["report_path"], "reportSha256": r["report_sha256"]} for r in rows]
