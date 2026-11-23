"""Fuentes de datos autorizadas.

* Android: almacenamiento compartido (/sdcard) con depuración USB autorizada
  por el titular, mediante `adb pull`. Las carpetas privadas de apps
  (Android/data, Android/obb) no son accesibles por diseño y se excluyen.
* Contactos Android: `content query` solo si el sistema lo permite al shell.
* Apple: respaldo oficial con `idevicebackup2` (dispositivo en el que el titular
  aceptó 'Confiar en este equipo'). Si el titular activó el cifrado de
  respaldos, el respaldo queda cifrado con su contraseña y MR Lab no la pide.
* Importación local: carpeta o .zip que el técnico tenga autorización para tratar.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path

from .. import config
from ..connectors.android import AdbConnector
from ..connectors.apple import AppleConnector
from ..errors import RpcError
from ..jobs import Job
from . import categories

ANDROID_FOLDERS = [
    {"id": "dcim", "path": "/sdcard/DCIM", "label": "Cámara (DCIM)"},
    {"id": "pictures", "path": "/sdcard/Pictures", "label": "Imágenes"},
    {"id": "movies", "path": "/sdcard/Movies", "label": "Películas"},
    {"id": "documents", "path": "/sdcard/Documents", "label": "Documentos"},
    {"id": "download", "path": "/sdcard/Download", "label": "Descargas"},
    {"id": "music", "path": "/sdcard/Music", "label": "Música"},
    {"id": "recordings", "path": "/sdcard/Recordings", "label": "Grabaciones"},
    {"id": "whatsapp", "path": "/sdcard/Android/media/com.whatsapp/WhatsApp/Media", "label": "WhatsApp (multimedia)"},
]
_BLOCKED = re.compile(r"^/sdcard/Android/(data|obb)(/|$)")
_SAFE_PATH = re.compile(r"^/sdcard(/[^\0'\"`$\;|&<>]+)*/?$")
WINFLAGS = 0x08000000 if config.IS_WINDOWS else 0


def _authorized_adb(device) -> AdbConnector:
    if device is None or device.platform != "android" or device.connector != "adb":
        raise RpcError("unsupported", "Seleccione un dispositivo Android conectado por ADB.")
    if device.comm_state != "online" or device.auth_state != "authorized":
        raise RpcError("not_authorized", "El dispositivo debe estar en línea y con la depuración USB autorizada por el titular.")
    adb = AdbConnector()
    if not adb.available:
        raise RpcError("tool_missing", "Motor Android no disponible.")
    return adb


def validate_remote(path: str) -> str:
    path = path.rstrip("/") or "/sdcard"
    if not _SAFE_PATH.match(path) or ".." in path.split("/"):
        raise RpcError("invalid_params", f"Ruta no válida: {path}. Debe estar dentro de /sdcard.")
    if _BLOCKED.match(path):
        raise RpcError("invalid_params", "Android/data y Android/obb son privados de cada app y no son accesibles por interfaces autorizadas.")
    return path


def android_scan(device, paths: list[str]) -> dict:
    """Inventario de los archivos de las carpetas indicadas (sin copiarlos)."""
    adb = _authorized_adb(device)
    totals = categories.empty_counts()
    folders = []
    for raw in paths:
        path = validate_remote(raw)
        r = adb.shell(device.serial, f"find '{path}' -type f -not -path '*/.thumbnails/*' -exec stat -c '%s|%Y|%n' {{}} + 2>/dev/null",
                      timeout=120)
        files = 0
        size = 0
        for line in r.stdout.splitlines():
            parts = line.split("|", 2)
            if len(parts) != 3 or not parts[0].isdigit():
                continue
            cat = categories.classify(parts[2])
            n = int(parts[0])
            totals[cat]["files"] += 1
            totals[cat]["bytes"] += n
            files += 1
            size += n
        folders.append({"path": path, "exists": files > 0 or r.ok, "files": files, "bytes": size})
    return {"folders": folders, "categories": totals,
            "totalFiles": sum(c["files"] for c in totals.values()),
            "totalBytes": sum(c["bytes"] for c in totals.values())}


def _dir_size(p: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def android_pull(job: Job, device, paths: list[str], dest: Path, expected_bytes: int) -> list[str]:
    """Copia carpetas con `adb pull`, informando progreso por tamaño copiado."""
    adb = _authorized_adb(device)
    warnings: list[str] = []
    for i, raw in enumerate(paths):
        job.check()
        path = validate_remote(raw)
        target = dest / "android" / path.lstrip("/").replace("sdcard/", "", 1)
        target.parent.mkdir(parents=True, exist_ok=True)
        job.update(phase=f"Copiando {path}", progress=None)
        proc = subprocess.Popen([adb.path, "-s", device.serial, "pull", "-a", path, str(target.parent)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace", creationflags=WINFLAGS)
        while proc.poll() is None:
            if job.cancelled():
                proc.kill()
                job.check()
            if expected_bytes:
                job.update(progress=min(0.99, _dir_size(dest) / expected_bytes) * 0.6,
                           detail=f"Carpeta {i + 1} de {len(paths)}")
            time.sleep(0.4)
        _out, err = proc.communicate()
        if proc.returncode != 0:
            warnings.append(f"{path}: {(err or '').strip()[:300] or 'adb pull terminó con error'}")
    return warnings


def _parse_content_rows(out: str) -> list[dict]:
    rows = []
    for line in out.splitlines():
        if not line.startswith("Row:"):
            continue
        body = line.split(" ", 2)[2] if line.count(" ") >= 2 else ""
        rows.append(dict(re.findall(r"(\w+)=(.*?)(?=, \w+=|$)", body)))
    return rows


def rows_to_vcf(rows: list[dict]) -> str:
    contacts: dict[str, dict] = {}
    for r in rows:
        name = (r.get("display_name") or "").strip()
        if not name or name == "NULL":
            continue
        c = contacts.setdefault(name, {"tel": [], "email": []})
        mt, val = r.get("mimetype", ""), (r.get("data1") or "").strip()
        if not val or val == "NULL":
            continue
        if mt.endswith("phone_v2"):
            c["tel"].append(val)
        elif mt.endswith("email_v2"):
            c["email"].append(val)
    out = []
    for name, c in sorted(contacts.items()):
        esc = name.replace(",", r"\,").replace(";", r"\;")
        out += ["BEGIN:VCARD", "VERSION:3.0", f"FN:{esc}"]
        out += [f"TEL:{t}" for t in dict.fromkeys(c["tel"])]
        out += [f"EMAIL:{e}" for e in dict.fromkeys(c["email"])]
        out.append("END:VCARD")
    return "\r\n".join(out) + ("\r\n" if out else "")


def android_contacts(device, dest: Path) -> tuple[int, str | None]:
    """Exporta contactos si el sistema permite consultarlos al shell. (n, aviso)."""
    adb = _authorized_adb(device)
    r = adb.shell(device.serial, "content query --uri content://com.android.contacts/data "
                                 "--projection display_name:mimetype:data1", timeout=60)
    text = r.output
    if "Permission Denial" in text or "SecurityException" in text or (not r.ok and "Row:" not in text):
        return 0, "El sistema no permite exportar contactos por esta interfaz; use la exportación del propio teléfono o la cuenta del titular."
    vcf = rows_to_vcf(_parse_content_rows(r.stdout))
    if not vcf:
        return 0, "No se encontraron contactos almacenados en el dispositivo (pueden estar solo en la nube)."
    target = dest / "contactos"
    target.mkdir(parents=True, exist_ok=True)
    (target / "contactos.vcf").write_text(vcf, encoding="utf-8")
    return vcf.count("BEGIN:VCARD"), None


def apple_backup(job: Job, device, dest: Path) -> list[str]:
    """Respaldo oficial completo con idevicebackup2."""
    if device is None or device.platform != "apple":
        raise RpcError("unsupported", "Seleccione un dispositivo Apple.")
    if device.auth_state != "authorized":
        raise RpcError("not_authorized", "El titular debe desbloquear el dispositivo y aceptar 'Confiar en este equipo'.")
    from .. import tools
    exe = tools.find("idevicebackup2")
    if not exe or not AppleConnector().available:
        raise RpcError("tool_missing", "Motor Apple (idevicebackup2) no disponible.")
    target = dest / "apple_backup"
    target.mkdir(parents=True, exist_ok=True)
    job.update(phase="Respaldo oficial de Apple", progress=0.0,
               detail="Si el dispositivo lo solicita, el titular debe introducir su código en la pantalla.")
    proc = subprocess.Popen([exe, "-u", device.serial, "backup", "--full", str(target)], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=WINFLAGS)
    tail: list[str] = []
    for line in iter(proc.stdout.readline, ""):  # type: ignore[union-attr]
        if job.cancelled():
            proc.kill()
            job.check()
        tail = (tail + [line.strip()])[-5:]
        m = re.search(r"(\d{1,3})%\s+Finished", line)
        if m:
            job.update(progress=int(m.group(1)) / 100 * 0.6)
    proc.wait()
    if proc.returncode != 0:
        raise RpcError("backup_failed", "idevicebackup2 falló: " + " | ".join(t for t in tail if t)[:400])
    return []


def local_import(job: Job, source: str, dest: Path) -> list[str]:
    src = Path(source).expanduser()
    if not src.exists():
        raise RpcError("not_found", f"No existe: {source}")
    data_root = config.data_dir().resolve()
    if str(src.resolve()).startswith(str(data_root)):
        raise RpcError("invalid_params", "No se puede importar desde la carpeta de datos de MR Lab.")
    target = dest / "importado"
    target.mkdir(parents=True, exist_ok=True)
    if src.is_file() and src.suffix.lower() == ".zip":
        job.update(phase="Extrayendo .zip", progress=None)
        with zipfile.ZipFile(src) as z:
            for info in z.infolist():
                job.check()
                out = (target / info.filename).resolve()
                if not str(out).startswith(str(target.resolve())):
                    raise RpcError("invalid_params", f"Ruta insegura en el .zip: {info.filename}")
                if info.is_dir():
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as fi, open(out, "wb") as fo:
                    shutil.copyfileobj(fi, fo)
    elif src.is_dir():
        total = _dir_size(src) or 1
        copied = 0
        for root, _dirs, files in os.walk(src):
            for f in files:
                job.check()
                s = Path(root) / f
                d = target / s.relative_to(src)
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s, d)
                copied += d.stat().st_size
                job.update(phase="Copiando archivos", progress=copied / total * 0.6)
    elif src.is_file():
        shutil.copy2(src, target / src.name)
    else:
        raise RpcError("invalid_params", "La ruta debe ser una carpeta, un archivo o un .zip.")
    return []
