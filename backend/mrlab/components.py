"""Componentes integrados en el instalador de MR Lab (motor Android, motor Apple,
controladores). Se verifican por SHA-256 contra el inventario generado en la
compilación; un componente alterado no se utiliza."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

from . import config

_lock = threading.Lock()
_cache: dict | None = None


def resources_dir() -> Path | None:
    env = os.environ.get("MRLAB_RESOURCES_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    tools = config.bundled_tools_dir()
    return tools.parent if tools else None


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_all() -> dict:
    res = resources_dir()
    inv_path = res / "tools" / "components.json" if res else None
    if not inv_path or not inv_path.exists():
        return {"inventory": False, "resourcesDir": str(res) if res else None, "components": []}
    try:
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"inventory": False, "error": f"Inventario ilegible: {e}", "resourcesDir": str(res), "components": []}
    out = []
    for c in inv.get("components", []):
        missing, altered = [], []
        for rel, digest in c.get("files", {}).items():
            p = res / rel
            if not p.is_file():
                missing.append(rel)
            elif _sha256(p) != digest:
                altered.append(rel)
        status = "altered" if altered else ("incomplete" if missing else "ok")
        out.append({
            "id": c["id"], "name": c["name"], "kind": c.get("kind", "tool"), "version": c.get("version"),
            "license": c.get("license"), "source": c.get("source"), "dest": c.get("dest"),
            "fileCount": len(c.get("files", {})), "status": status,
            "missing": missing[:10], "altered": altered[:10],
        })
    return {"inventory": True, "generatedAt": inv.get("generatedAt"), "resourcesDir": str(res), "components": out}


def status(force: bool = False) -> dict:
    global _cache
    with _lock:
        if _cache is None or force:
            _cache = _verify_all()
        return _cache


def integrated_tool(name: str) -> str | None:
    """Ruta del ejecutable `name` dentro de un componente integrado verificado."""
    st = status()
    res = resources_dir()
    if not res:
        return None
    exe = name + (".exe" if config.IS_WINDOWS else "")
    for c in st["components"]:
        if c["kind"] != "tool" or c["status"] != "ok" or not c.get("dest"):
            continue
        p = res / c["dest"] / exe
        if p.is_file():
            return str(p)
    return None


def reset_cache() -> None:
    global _cache
    with _lock:
        _cache = None
