"""Administrador de respaldos: listado, verificación de integridad,
exploración del contenido, exportación por categorías y eliminación."""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from . import cases, config, crypto, db, evidence, jobs
from .errors import RpcError
from .recovery import categories
from .recovery.engine import SOURCES, staging_root
from .util.timeutil import now_iso


def _row(r) -> dict:
    return {"id": r["id"], "createdAt": r["created_at"], "caseId": r["case_id"], "folio": r["folio"],
            "source": r["source"], "sourceLabel": SOURCES.get(r["source"], r["source"]),
            "deviceSerial": r["device_serial"], "deviceLabel": r["device_label"], "fileName": Path(r["path"]).name,
            "containerBytes": r["container_bytes"], "plainBytes": r["plain_bytes"], "fileCount": r["file_count"],
            "categories": json.loads(r["categories_json"]), "containerSha256": r["container_sha256"],
            "warnings": json.loads(r["warnings_json"] or "[]"), "verifiedAt": r["verified_at"],
            "verifyResult": r["verify_result"], "status": r["status"],
            "present": Path(r["path"]).exists()}


def list_backups(case_id: int | None = None) -> list[dict]:
    q = ("SELECT b.*, c.folio FROM backups b JOIN cases c ON c.id = b.case_id WHERE b.status = 'ok'")
    args: list = []
    if case_id is not None:
        q += " AND b.case_id = ?"
        args.append(case_id)
    with db.read() as conn:
        return [_row(r) for r in conn.execute(q + " ORDER BY b.id DESC", args)]


def _get(backup_id: int) -> dict:
    with db.read() as conn:
        r = conn.execute("SELECT b.*, c.folio FROM backups b JOIN cases c ON c.id = b.case_id WHERE b.id = ?",
                         (backup_id,)).fetchone()
    if not r or r["status"] != "ok":
        raise RpcError("not_found", f"Respaldo {backup_id} no encontrado")
    out = _row(r)
    out["_path"], out["_manifest"] = r["path"], r["manifest_path"]
    if not out["present"]:
        raise RpcError("missing_file", "El archivo del respaldo no existe en disco.")
    return out


def get(backup_id: int) -> dict:
    b = _get(backup_id)
    return {k: v for k, v in b.items() if not k.startswith("_")}


def browse(backup_id: int, passphrase: str) -> dict:
    """Descifra solo el manifiesto (pequeño) para listar el contenido."""
    b = _get(backup_id)
    manifest = json.loads(crypto.decrypt_bytes(Path(b["_manifest"]), passphrase))
    evidence.log("Exploración de respaldo", "info", case_id=b["caseId"], device_serial=b["deviceSerial"],
                 device_label=b["deviceLabel"], details={"respaldo": backup_id})
    return {"backup": get(backup_id), "files": manifest["files"], "warnings": manifest.get("warnings", [])}


def verify(backup_id: int, passphrase: str) -> dict:
    b = _get(backup_id)
    path = Path(b["_path"])

    def run(job: jobs.Job) -> dict:
        job.update(phase="Comprobando huella del contenedor", progress=0.02)
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                job.check()
                h.update(chunk)
        sha_ok = h.hexdigest() == b["containerSha256"]
        size = path.stat().st_size
        job.update(phase="Descifrando y autenticando cada bloque", progress=0.1)
        crypto.verify_file(path, passphrase, cancelled=job.cancelled,
                           progress=lambda d: job.update(progress=0.1 + 0.9 * min(1, d / max(1, size))))
        result = "ok" if sha_ok else "sha_mismatch"
        with db.write() as conn:
            conn.execute("UPDATE backups SET verified_at = ?, verify_result = ? WHERE id = ?", (now_iso(), result, backup_id))
        evidence.log("Verificación de respaldo", "success" if sha_ok else "warning", case_id=b["caseId"],
                     device_serial=b["deviceSerial"], device_label=b["deviceLabel"],
                     details={"respaldo": backup_id, "sha256": "coincide" if sha_ok else "NO coincide", "autenticación": "correcta"})
        return {"backupId": backup_id, "result": result}

    def on_error(job: jobs.Job, message: str) -> None:
        if job.final == "failed":
            with db.write() as conn:
                conn.execute("UPDATE backups SET verified_at = ?, verify_result = ? WHERE id = ?", (now_iso(), "failed", backup_id))
        evidence.log("Verificación de respaldo", "failure" if job.final == "failed" else "cancelled",
                     case_id=b["caseId"], device_serial=b["deviceSerial"], error=message, details={"respaldo": backup_id})

    return jobs.start("verify", f"Verificación · respaldo #{backup_id}", run, on_error)


def exports_dir() -> Path:
    return config.sub_dir("exports")


def export(backup_id: int, passphrase: str, cats: list[str] | None, paths: list[str] | None = None) -> dict:
    b = _get(backup_id)
    if cats:
        bad = [c for c in cats if c not in categories.CATEGORIES]
        if bad:
            raise RpcError("invalid_params", f"Categorías no válidas: {bad}")
    case = cases.get(b["caseId"])

    def run(job: jobs.Job) -> dict:
        stage = staging_root() / f"export-{job.id}"
        stage.mkdir(parents=True)
        try:
            zpath = stage / "contenedor.zip"
            size = Path(b["_path"]).stat().st_size
            job.update(phase="Descifrando respaldo", progress=0.0)
            crypto.decrypt_file(Path(b["_path"]), zpath, passphrase, cancelled=job.cancelled,
                                progress=lambda d: job.update(progress=0.5 * min(1, d / max(1, size))))
            out = exports_dir() / case["folio"] / f"respaldo-{backup_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            out.mkdir(parents=True)
            with zipfile.ZipFile(zpath) as z:
                manifest = json.loads(z.read("manifest.json"))
                selected = [e for e in manifest["files"]
                            if (not cats or e["category"] in cats) and (not paths or e["path"] in paths)]
                if not selected:
                    raise RpcError("empty", "La selección no contiene archivos.")
                mismatches = []
                for i, e in enumerate(selected):
                    job.check()
                    dest = (out / categories.CATEGORIES[e["category"]] / e["path"]).resolve()
                    if not str(dest).startswith(str(out.resolve())):
                        raise RpcError("integrity_error", f"Ruta insegura en el manifiesto: {e['path']}")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    h = hashlib.sha256()
                    with z.open("datos/" + e["path"]) as fi, open(dest, "wb") as fo:
                        for chunk in iter(lambda: fi.read(1 << 20), b""):
                            h.update(chunk)
                            fo.write(chunk)
                    if h.hexdigest() != e["sha256"]:
                        mismatches.append(e["path"])
                    if i % 10 == 0:
                        job.update(phase="Exportando y verificando SHA-256", progress=0.5 + 0.5 * i / len(selected),
                                   detail=f"{i + 1} de {len(selected)}")
            report = {"exportedAt": now_iso(), "backupId": backup_id, "folio": case["folio"],
                      "categories": cats or "todas", "files": selected, "hashMismatches": mismatches}
            report_path = out / "manifiesto-exportacion.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
            rsha = hashlib.sha256(report_path.read_bytes()).hexdigest()
            total = sum(e["size"] for e in selected)
            with db.write() as conn:
                conn.execute("INSERT INTO case_files(case_id, created_at, path, sha256, size_bytes, description) VALUES(?,?,?,?,?,?)",
                             (case["id"], now_iso(), str(out), rsha, total,
                              f"Exportación del respaldo #{backup_id}: {len(selected)} archivos"))
            evidence.log("Exportación de datos", "success" if not mismatches else "warning", case_id=case["id"],
                         device_serial=b["deviceSerial"], device_label=b["deviceLabel"], files=[str(out)],
                         details={"respaldo": backup_id, "archivos": len(selected), "bytes": total,
                                  "categorías": cats or "todas", "sha256_manifiesto": rsha,
                                  "discrepancias": len(mismatches)})
            cases.add_operation(case["id"], "Exportación de datos", "success" if not mismatches else "warning",
                                "descifrado + verificación SHA-256", f"{len(selected)} archivos → {out.name}")
            return {"path": str(out), "files": len(selected), "bytes": total, "mismatches": mismatches}
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    def on_error(job: jobs.Job, message: str) -> None:
        evidence.log("Exportación de datos", "cancelled" if job.final == "cancelled" else "failure",
                     case_id=b["caseId"], device_serial=b["deviceSerial"], error=message, details={"respaldo": backup_id})

    return jobs.start("export", f"Exportación · respaldo #{backup_id}", run, on_error)


def delete(backup_id: int, confirmation: str) -> dict:
    b = _get(backup_id)
    if confirmation != f"ELIMINAR {backup_id}":
        raise RpcError("confirmation_required", f"Escriba exactamente «ELIMINAR {backup_id}» para confirmar.")
    for p in (b["_path"], b["_manifest"]):
        Path(p).unlink(missing_ok=True)
    with db.write() as conn:
        conn.execute("UPDATE backups SET status = 'deleted' WHERE id = ?", (backup_id,))
    evidence.log("Eliminación de respaldo", "confirmed", case_id=b["caseId"], device_serial=b["deviceSerial"],
                 device_label=b["deviceLabel"], confirmation=confirmation,
                 details={"respaldo": backup_id, "sha256_contenedor": b["containerSha256"]})
    return {"deleted": backup_id}
