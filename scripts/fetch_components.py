#!/usr/bin/env python3
"""Descarga, verifica e integra los componentes externos dentro de resources/
para que el instalador de MR Lab sea autosuficiente.

Uso:
  python scripts/fetch_components.py                      # todos los componentes con URL
  python scripts/fetch_components.py --local libimobiledevice=C:\\ruta\\carpeta_o_zip
  python scripts/fetch_components.py --only platform-tools
  python scripts/fetch_components.py --strict             # falla si falta algún componente

Solo usa la biblioteca estándar. Genera:
  resources/tools/components.json   inventario con SHA-256 por archivo (lo verifica la app)
  components/lock.json              hash de cada paquete descargado (fijado tras la 1.ª descarga)
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "components" / "manifest.json"
LOCK = ROOT / "components" / "lock.json"
RES = ROOT / "resources"
INVENTORY = RES / "tools" / "components.json"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mrlab-build"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def extract_zip(data: bytes, dest: Path, strip: str) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            name = info.filename
            if strip and name.startswith(strip):
                name = name[len(strip):]
            if not name or info.is_dir():
                continue
            target = (dest / name).resolve()
            if not str(target).startswith(str(dest.resolve())):  # protección zip-slip
                raise RuntimeError(f"Ruta insegura en el paquete: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            mode = (info.external_attr >> 16) & 0o777
            if mode:  # conservar permisos de ejecución (Linux/macOS)
                target.chmod(mode)


def integrate(comp: dict, local: str | None, lock: dict) -> dict:
    dest = RES / comp["dest"]
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    source = ""
    pkg_hash = None
    if local:
        lp = Path(local)
        if lp.is_dir():
            shutil.copytree(lp, dest, dirs_exist_ok=True)
        elif lp.suffix.lower() == ".zip":
            data = lp.read_bytes()
            pkg_hash = sha256_bytes(data)
            extract_zip(data, dest, comp.get("stripPrefix", ""))
        else:
            raise RuntimeError(f"--local debe ser carpeta o .zip: {lp}")
        source = f"local:{lp.name}"
    else:
        print(f"  descargando {comp['url']}")
        data = download(comp["url"])
        pkg_hash = sha256_bytes(data)
        expected = comp.get("sha256") or lock.get(comp["id"], {}).get("sha256")
        if expected and expected.lower() != pkg_hash:
            raise RuntimeError(f"SHA-256 no coincide para {comp['id']}: esperado {expected}, obtenido {pkg_hash}")
        if not expected:
            print(f"  hash fijado por primera vez: {pkg_hash}")
        lock[comp["id"]] = {"sha256": pkg_hash, "url": comp["url"],
                            "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        extract_zip(data, dest, comp.get("stripPrefix", ""))
        source = comp["url"]

    missing = [f for f in comp.get("required", []) if not (dest / f).exists()]
    if missing:
        raise RuntimeError(f"{comp['id']}: faltan archivos requeridos {missing}")
    files = {str(p.relative_to(RES)).replace("\\", "/"): sha256_file(p) for p in sorted(dest.rglob("*")) if p.is_file()}
    version = None
    props = dest / "source.properties"
    if props.exists():
        for line in props.read_text(errors="replace").splitlines():
            if line.startswith("Pkg.Revision="):
                version = line.split("=", 1)[1].strip()
    return {"id": comp["id"], "name": comp["name"], "kind": comp["kind"], "dest": comp["dest"],
            "version": version, "source": source, "packageSha256": pkg_hash, "license": comp.get("license"),
            "files": files}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="append", default=[], help="id=ruta (carpeta o .zip)")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    locals_ = dict(x.split("=", 1) for x in args.local)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
    previous = json.loads(INVENTORY.read_text(encoding="utf-8")) if INVENTORY.exists() else {"components": []}
    inventory = {c["id"]: c for c in previous.get("components", [])}
    failures = []
    for comp in manifest["components"]:
        if args.only and comp["id"] not in args.only:
            continue
        print(f"[{comp['id']}] {comp['name']}")
        if not comp.get("url") and comp["id"] not in locals_:
            msg = f"sin URL ni --local. {comp.get('note', '')}"
            print(f"  OMITIDO: {msg}")
            failures.append((comp["id"], msg))
            continue
        try:
            inventory[comp["id"]] = integrate(comp, locals_.get(comp["id"]), lock)
            print(f"  OK: {len(inventory[comp['id']]['files'])} archivos")
        except Exception as e:
            print(f"  ERROR: {e}")
            failures.append((comp["id"], str(e)))
    INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    INVENTORY.write_text(json.dumps({"generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                     "components": list(inventory.values())}, indent=2, ensure_ascii=False), encoding="utf-8")
    LOCK.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    print(f"Inventario: {INVENTORY}")
    if failures and args.strict:
        print("Componentes faltantes:", ", ".join(f for f, _ in failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
