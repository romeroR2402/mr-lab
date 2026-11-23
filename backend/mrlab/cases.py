"""Gestión de expedientes (Case Management)."""
from __future__ import annotations

from datetime import datetime

from . import db, evidence, settings
from .errors import RpcError
from .util.timeutil import now_iso

STATUSES = {
    "open": "Abierto",
    "in_progress": "En proceso",
    "waiting_client": "En espera del cliente",
    "completed": "Completado",
    "not_recoverable": "Sin recuperación posible",
    "closed": "Cerrado",
}
DEVICE_TYPES = {"android", "ios", "ipados", "other"}
AUTH_TYPES = {
    "owner": "Propietario del dispositivo",
    "legal_rep": "Representante legal",
    "company": "Empresa titular",
    "court_order": "Orden judicial",
}


def _text(params: dict, key: str, required: bool = True, max_len: int = 2000) -> str | None:
    val = params.get(key)
    if val is None or (isinstance(val, str) and not val.strip()):
        if required:
            raise RpcError("invalid_params", f"El campo '{key}' es obligatorio")
        return None
    if not isinstance(val, str):
        raise RpcError("invalid_params", f"El campo '{key}' debe ser texto")
    val = val.strip()
    if len(val) > max_len:
        raise RpcError("invalid_params", f"El campo '{key}' excede {max_len} caracteres")
    return val


def _next_folio(conn) -> str:
    prefix = datetime.now().strftime("MR-%Y%m%d-")
    row = conn.execute(
        "SELECT folio FROM cases WHERE folio LIKE ? ORDER BY folio DESC LIMIT 1", (prefix + "%",)
    ).fetchone()
    seq = int(row["folio"].rsplit("-", 1)[1]) + 1 if row else 1
    return f"{prefix}{seq:04d}"


def to_api(row: dict) -> dict:
    return {
        "id": row["id"],
        "folio": row["folio"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "technician": row["technician"],
        "deviceType": row["device_type"],
        "deviceModel": row["device_model"],
        "deviceSerial": row["device_serial"],
        "reason": row["reason"],
        "authorizationType": row["authorization_type"],
        "authorizedBy": row["authorized_by"],
        "authorizationRef": row["authorization_ref"],
        "status": row["status"],
        "results": row["results"],
    }


def create(params: dict) -> dict:
    device_type = _text(params, "deviceType")
    if device_type not in DEVICE_TYPES:
        raise RpcError("invalid_params", "Tipo de dispositivo no válido")
    auth_type = _text(params, "authorizationType")
    if auth_type not in AUTH_TYPES:
        raise RpcError("invalid_params", "Tipo de autorización no válido")
    if params.get("authorizationConfirmed") is not True:
        raise RpcError(
            "authorization_required",
            "Debe confirmar que cuenta con autorización documentada del titular para abrir el expediente.",
        )
    technician = _text(params, "technician", required=False, max_len=200) or settings.technician()
    now = now_iso()
    with db.write() as conn:
        folio = _next_folio(conn)
        cur = conn.execute(
            """INSERT INTO cases(folio, created_at, updated_at, technician, device_type, device_model,
                   device_serial, reason, authorization_type, authorized_by, authorization_ref, status)
               VALUES(?,?,?,?,?,?,?,?,?,?,?, 'open')""",
            (
                folio, now, now, technician, device_type,
                _text(params, "deviceModel", required=False, max_len=200),
                _text(params, "deviceSerial", required=False, max_len=200),
                _text(params, "reason"),
                auth_type,
                _text(params, "authorizedBy", max_len=200),
                _text(params, "authorizationRef", required=False, max_len=200),
            ),
        )
        case_id = cur.lastrowid
    evidence.log(
        "Apertura de expediente", "confirmed", case_id=case_id, technician=technician,
        details=f"Folio {folio}", confirmation=f"Autorización: {AUTH_TYPES[auth_type]}",
        device_serial=params.get("deviceSerial") or None, device_label=params.get("deviceModel") or None,
    )
    return get(case_id)


def get(case_id: int) -> dict:
    with db.read() as conn:
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not row:
            raise RpcError("not_found", f"Expediente {case_id} no encontrado")
        ops = conn.execute("SELECT * FROM case_operations WHERE case_id = ? ORDER BY id", (case_id,)).fetchall()
        files = conn.execute("SELECT * FROM case_files WHERE case_id = ? ORDER BY id", (case_id,)).fetchall()
    out = to_api(dict(row))
    out["operations"] = [
        {"id": o["id"], "timestamp": o["timestamp"], "operation": o["operation"], "method": o["method"],
         "result": o["result"], "details": o["details"]} for o in ops
    ]
    out["files"] = [
        {"id": f["id"], "createdAt": f["created_at"], "path": f["path"], "sha256": f["sha256"],
         "sizeBytes": f["size_bytes"], "description": f["description"]} for f in files
    ]
    return out


def list_cases(limit: int = 100, status: str | None = None, search: str | None = None) -> list[dict]:
    clauses, args = [], []
    if status:
        clauses.append("status = ?")
        args.append(status)
    if search:
        clauses.append("(folio LIKE ? OR device_model LIKE ? OR reason LIKE ? OR device_serial LIKE ?)")
        args += [f"%{search}%"] * 4
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with db.read() as conn:
        rows = conn.execute(
            f"SELECT * FROM cases {where} ORDER BY id DESC LIMIT ?", [*args, max(1, min(int(limit), 500))]
        ).fetchall()
    return [to_api(dict(r)) for r in rows]


def update_status(case_id: int, status: str, results: str | None = None) -> dict:
    if status not in STATUSES:
        raise RpcError("invalid_params", "Estado no válido")
    get(case_id)
    with db.write() as conn:
        conn.execute(
            "UPDATE cases SET status = ?, results = COALESCE(?, results), updated_at = ? WHERE id = ?",
            (status, results, now_iso(), case_id),
        )
    evidence.log("Cambio de estado de expediente", "info", case_id=case_id, details=f"Nuevo estado: {STATUSES[status]}")
    return get(case_id)


def add_operation(case_id: int, operation: str, result: str, method: str | None = None, details: str | None = None) -> None:
    with db.write() as conn:
        conn.execute(
            "INSERT INTO case_operations(case_id, timestamp, operation, method, result, details) VALUES(?,?,?,?,?,?)",
            (case_id, now_iso(), operation, method, result, details),
        )
        conn.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now_iso(), case_id))


def stats() -> dict:
    with db.read() as conn:
        rows = conn.execute("SELECT status, COUNT(*) c FROM cases GROUP BY status").fetchall()
    by = {r["status"]: r["c"] for r in rows}
    return {"total": sum(by.values()), "byStatus": by}
