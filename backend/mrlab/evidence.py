"""Registro de evidencias: solo inserción y encadenado con SHA-256 para
detectar alteraciones posteriores en la base de datos."""
from __future__ import annotations

import hashlib
import json

from . import db, settings
from .util.timeutil import now_iso

GENESIS = "0" * 64
RESULTS = {"success", "failure", "info", "warning", "cancelled", "confirmed"}

_FIELDS = (
    "timestamp", "technician", "case_id", "device_serial", "device_label",
    "operation", "result", "details", "files", "error", "confirmation",
)


def _hash(prev_hash: str, entry: dict) -> str:
    payload = json.dumps({k: entry.get(k) for k in _FIELDS}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((prev_hash + payload).encode("utf-8")).hexdigest()


def log(
    operation: str,
    result: str,
    *,
    details: str | dict | None = None,
    device_serial: str | None = None,
    device_label: str | None = None,
    case_id: int | None = None,
    files: list[str] | None = None,
    error: str | None = None,
    confirmation: str | None = None,
    technician: str | None = None,
) -> dict:
    if result not in RESULTS:
        result = "info"
    entry = {
        "timestamp": now_iso(),
        "technician": technician or settings.technician(),
        "case_id": case_id,
        "device_serial": device_serial,
        "device_label": device_label,
        "operation": operation,
        "result": result,
        "details": json.dumps(details, ensure_ascii=False) if isinstance(details, dict) else details,
        "files": json.dumps(files, ensure_ascii=False) if files else None,
        "error": error,
        "confirmation": confirmation,
    }
    with db.write() as conn:
        row = conn.execute("SELECT entry_hash FROM evidence_log ORDER BY id DESC LIMIT 1").fetchone()
        prev = row["entry_hash"] if row else GENESIS
        entry["prev_hash"] = prev
        entry["entry_hash"] = _hash(prev, entry)
        cols = list(entry.keys())
        cur = conn.execute(
            f"INSERT INTO evidence_log({', '.join(cols)}) VALUES({', '.join('?' for _ in cols)})",
            [entry[c] for c in cols],
        )
        entry["id"] = cur.lastrowid
    return to_api(entry)


def to_api(row: dict) -> dict:
    files = row.get("files")
    return {
        "id": row.get("id"),
        "timestamp": row["timestamp"],
        "technician": row["technician"],
        "caseId": row.get("case_id"),
        "deviceSerial": row.get("device_serial"),
        "deviceLabel": row.get("device_label"),
        "operation": row["operation"],
        "result": row["result"],
        "details": row.get("details"),
        "files": json.loads(files) if files else [],
        "error": row.get("error"),
        "confirmation": row.get("confirmation"),
        "entryHash": row.get("entry_hash"),
    }


def list_entries(limit: int = 200, offset: int = 0, case_id: int | None = None) -> dict:
    limit = max(1, min(int(limit), 1000))
    where, args = "", []
    if case_id is not None:
        where, args = "WHERE case_id = ?", [case_id]
    with db.read() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM evidence_log {where}", args).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM evidence_log {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*args, limit, int(offset)]
        ).fetchall()
    return {"total": total, "entries": [to_api(dict(r)) for r in rows]}


def verify_chain() -> dict:
    """Recalcula la cadena completa y reporta la primera entrada inconsistente."""
    prev = GENESIS
    count = 0
    with db.read() as conn:
        for row in conn.execute("SELECT * FROM evidence_log ORDER BY id ASC"):
            r = dict(row)
            if r["prev_hash"] != prev or _hash(prev, r) != r["entry_hash"]:
                return {"valid": False, "checked": count, "brokenAtId": r["id"]}
            prev = r["entry_hash"]
            count += 1
    return {"valid": True, "checked": count, "brokenAtId": None}
