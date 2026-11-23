"""Creación de respaldos: adquisición desde una fuente autorizada, inventario
con SHA-256 por archivo, clasificación y empaquetado en un contenedor cifrado
AES-256-GCM. El texto plano solo existe temporalmente en la carpeta de
preparación y se elimina al terminar (o al iniciar, si quedó un trabajo interrumpido)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from .. import cases, config, crypto, db, evidence, jobs, scanner
from ..errors import RpcError
from ..util.timeutil import now_iso
from . import categories, sources

SOURCES = {"android_adb": "Android por ADB autorizado", "apple_backup": "Respaldo oficial de Apple",
           "local_import": "Importación local"}


def staging_root() -> Path:
    return config.sub_dir("staging")


def backups_dir() -> Path:
    return config.sub_dir("backups")


def cleanup_staging() -> int:
    """Borra restos de trabajos interrumpidos (contienen texto plano)."""
    n = 0
    for p in staging_root().iterdir():
        shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
        n += 1
    return n


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _inventory(job: jobs.Job, root: Path) -> tuple[list[dict], dict]:
    files = [p for p in sorted(root.rglob("*")) if p.is_file()]
    totals = categories.empty_counts()
    entries = []
    for i, p in enumerate(files):
        job.check()
        with open(p, "rb") as f:
            head = f.read(16)
        rel = p.relative_to(root).as_posix()
        cat = categories.classify(rel, head)
        if rel.startswith("apple_backup/"):
            cat = "backups"  # el respaldo de Apple se conserva íntegro como respaldo local
        st = p.stat()
        entries.append({"path": rel, "category": cat, "size": st.st_size,
                        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                        "sha256": _sha256(p)})
        totals[cat]["files"] += 1
        totals[cat]["bytes"] += st.st_size
        if i % 20 == 0:
            job.update(phase="Inventario y huellas SHA-256", progress=0.6 + 0.15 * (i / max(1, len(files))),
                       detail=f"{i + 1} de {len(files)} archivos")
    return entries, totals


def _validate_passphrase(p: str) -> str:
    if not isinstance(p, str) or len(p) < 10:
        raise RpcError("weak_passphrase", "La frase de cifrado debe tener al menos 10 caracteres.")
    return p


def create(params: dict) -> dict:
    source = params.get("source")
    if source not in SOURCES:
        raise RpcError("invalid_params", "Fuente no válida.")
    case_id = params.get("caseId")
    if not isinstance(case_id, int):
        raise RpcError("case_required", "Vincule un expediente: los respaldos requieren autorización documentada del titular.")
    case = cases.get(case_id)
    if case["status"] in ("closed",):
        raise RpcError("invalid_params", "El expediente está cerrado.")
    passphrase = _validate_passphrase(params.get("passphrase", ""))
    if params.get("passphrase") != params.get("passphraseConfirm"):
        raise RpcError("invalid_params", "La confirmación de la frase no coincide.")
    device = None
    paths: list[str] = []
    if source in ("android_adb", "apple_backup"):
        device = scanner.get_cached(params.get("deviceKey") or "")
        if device is None:
            raise RpcError("device_not_found", "El dispositivo no está conectado.")
    if source == "android_adb":
        paths = [sources.validate_remote(p) for p in params.get("paths") or []]
        if not paths and not params.get("includeContacts"):
            raise RpcError("invalid_params", "Seleccione al menos una carpeta o los contactos.")
    if source == "local_import" and not params.get("localPath"):
        raise RpcError("invalid_params", "Indique la carpeta o el .zip a importar.")
    expected = int(params.get("expectedBytes") or 0)
    label = device.label if device else Path(params.get("localPath", "")).name or "Importación"
    serial = device.serial if device else None

    def run(job: jobs.Job) -> dict:
        stage = staging_root() / f"job-{job.id}"
        data = stage / "datos"
        data.mkdir(parents=True)
        warnings: list[str] = []
        try:
            evidence.log("Respaldo iniciado", "info", case_id=case_id, device_serial=serial, device_label=label,
                         details={"fuente": SOURCES[source], "carpetas": paths or None, "trabajo": job.id})
            if source == "android_adb":
                if paths:
                    warnings += sources.android_pull(job, device, paths, data, expected)
                if params.get("includeContacts"):
                    job.update(phase="Exportando contactos", progress=None)
                    n, warn = sources.android_contacts(device, data)
                    if warn:
                        warnings.append(warn)
            elif source == "apple_backup":
                warnings += sources.apple_backup(job, device, data)
            else:
                warnings += sources.local_import(job, params["localPath"], data)
            job.check()
            entries, totals = _inventory(job, data)
            if not entries:
                raise RpcError("empty", "No se obtuvo ningún archivo de la fuente seleccionada." +
                               (" " + " ".join(warnings) if warnings else ""))
            manifest = {"version": 1, "createdAt": now_iso(), "caseId": case_id, "folio": case["folio"],
                        "source": source, "device": {"label": label, "serial": serial}, "files": entries,
                        "categories": totals, "warnings": warnings}
            # Empaquetado
            zpath = stage / "contenedor.zip"
            with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
                z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
                for i, e in enumerate(entries):
                    job.check()
                    z.write(data / e["path"], "datos/" + e["path"])
                    if i % 20 == 0:
                        job.update(phase="Empaquetando", progress=0.75 + 0.1 * (i / len(entries)))
            plain = zpath.stat().st_size
            name = f"respaldo-{case['folio']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{job.id}"
            out = backups_dir() / f"{name}.mrlb"
            job.update(phase="Cifrando (AES-256-GCM)", progress=0.85)
            enc = crypto.encrypt_file(zpath, out, passphrase, cancelled=job.cancelled,
                                      progress=lambda d: job.update(progress=0.85 + 0.15 * d / max(1, plain)))
            man_path = backups_dir() / f"{name}.manifest.mrlb"
            crypto.encrypt_bytes(json.dumps(manifest, ensure_ascii=False).encode("utf-8"), man_path, passphrase)
            total_bytes = sum(e["size"] for e in entries)
            with db.write() as conn:
                cur = conn.execute(
                    """INSERT INTO backups(created_at, case_id, source, device_serial, device_label, path, manifest_path,
                           container_bytes, plain_bytes, file_count, categories_json, container_sha256, warnings_json, status)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?, 'ok')""",
                    (now_iso(), case_id, source, serial, label, str(out), str(man_path), out.stat().st_size,
                     total_bytes, len(entries), json.dumps(totals), enc["sha256"], json.dumps(warnings, ensure_ascii=False)))
                backup_id = cur.lastrowid
            evidence.log("Respaldo cifrado creado", "success", case_id=case_id, device_serial=serial, device_label=label,
                         files=[out.name], details={"respaldo": backup_id, "archivos": len(entries), "bytes": total_bytes,
                                                    "sha256_contenedor": enc["sha256"], "avisos": len(warnings)})
            cases.add_operation(case_id, "Respaldo cifrado", "success", SOURCES[source],
                                f"Respaldo #{backup_id}: {len(entries)} archivos")
            return {"backupId": backup_id, "files": len(entries), "bytes": total_bytes, "warnings": warnings}
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    def on_error(job: jobs.Job, message: str) -> None:
        evidence.log("Respaldo", "cancelled" if job.status == "cancelled" else "failure", case_id=case_id,
                     device_serial=serial, device_label=label, error=message)

    return jobs.start("backup", f"Respaldo · {label}", run, on_error)
