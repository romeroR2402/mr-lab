"""Sistema de plugins de ANÁLISIS para investigación de seguridad móvil.

Un plugin es un archivo .py con:
    MANIFEST = {"id", "name", "version", "author", "description",
                "capabilities": [...], "platforms": ["android", "apple"]}
    def analyze(ctx: dict) -> list[dict]   # cada dict: {title, severity, detail, data}

Barreras aplicadas:
  * El texto del archivo se revisa con la política antes de ejecutarlo.
  * Solo se aceptan capacidades de análisis (policy.ALLOWED_CAPABILITIES).
  * El plugin recibe una COPIA de solo lectura del contexto (sin conectores ni
    ejecución de comandos) y no puede alterar el dispositivo por esta vía.
  * Ejecución aislada con tiempo límite; un fallo no afecta al análisis.
  * Cada plugin externo debe habilitarse explícitamente.
"""
from __future__ import annotations

import copy
import importlib.util
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import config, db
from .model import PluginFinding
from .policy import PolicyViolation, scan_text, validate_capabilities

SEVERITIES = {"info", "low", "medium", "high"}
TIMEOUT_S = 10


@dataclass
class Plugin:
    id: str
    name: str
    version: str
    author: str
    description: str
    capabilities: list[str]
    platforms: list[str]
    builtin: bool
    path: str | None
    fn: Callable[[dict], list] | None
    error: str | None = None

    def to_api(self, enabled: bool) -> dict:
        return {"id": self.id, "name": self.name, "version": self.version, "author": self.author,
                "description": self.description, "capabilities": self.capabilities,
                "platforms": self.platforms, "builtin": self.builtin, "path": self.path,
                "enabled": enabled, "error": self.error, "loaded": self.fn is not None}


def plugins_dir() -> Path:
    return config.sub_dir("access_plugins")


def _from_manifest(m: dict, fn, builtin: bool, path: str | None) -> Plugin:
    for k in ("id", "name", "capabilities"):
        if k not in m:
            raise PolicyViolation(f"Manifiesto incompleto: falta '{k}'.")
    scan_text(str(m.get("id")), str(m.get("name")), str(m.get("description", "")))
    caps = validate_capabilities(list(m["capabilities"]))
    platforms = [p for p in m.get("platforms", ["android", "apple"]) if p in ("android", "apple")]
    return Plugin(str(m["id"]), str(m["name"]), str(m.get("version", "0.0.0")), str(m.get("author", "—")),
                  str(m.get("description", "")), caps, platforms or ["android", "apple"], builtin, path, fn)


def _load_external(path: Path) -> Plugin:
    try:
        src = path.read_text(encoding="utf-8")
    except OSError as e:
        return Plugin(path.stem, path.stem, "?", "?", "", [], [], False, str(path), None, f"No legible: {e}")
    try:
        scan_text(src)  # revisión antes de ejecutar cualquier código del plugin
        spec = importlib.util.spec_from_file_location(f"mrlab_access_plugin_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        manifest = getattr(mod, "MANIFEST", None)
        fn = getattr(mod, "analyze", None)
        if not isinstance(manifest, dict) or not callable(fn):
            raise PolicyViolation("El plugin debe definir MANIFEST (dict) y analyze(ctx).")
        return _from_manifest(manifest, fn, False, str(path))
    except PolicyViolation as e:
        return Plugin(path.stem, path.stem, "?", "?", "", [], [], False, str(path), None,
                      f"Rechazado por política: {e.message} {e.data.get('detail', '')}".strip())
    except Exception as e:
        return Plugin(path.stem, path.stem, "?", "?", "", [], [], False, str(path), None, f"Error al cargar: {e}")


def discover() -> list[Plugin]:
    from . import builtin_plugins
    found = [_from_manifest(m, fn, True, None) for m, fn in builtin_plugins.BUILTINS]
    for path in sorted(plugins_dir().glob("*.py")):
        found.append(_load_external(path))
    return found


def _enabled_map() -> dict[str, bool]:
    with db.read() as conn:
        return {r["plugin_id"]: bool(r["enabled"]) for r in conn.execute("SELECT plugin_id, enabled FROM access_plugin_state")}


def is_enabled(p: Plugin, state: dict[str, bool]) -> bool:
    # Los integrados vienen habilitados; los externos requieren habilitación explícita.
    return state.get(p.id, p.builtin)


def list_plugins() -> list[dict]:
    state = _enabled_map()
    return [p.to_api(is_enabled(p, state)) for p in discover()]


def set_enabled(plugin_id: str, enabled: bool) -> list[dict]:
    plugin = next((p for p in discover() if p.id == plugin_id), None)
    if plugin is None:
        from ..errors import RpcError
        raise RpcError("not_found", f"Plugin {plugin_id} no encontrado")
    if enabled and plugin.fn is None:
        from ..errors import RpcError
        raise RpcError("plugin_invalid", plugin.error or "El plugin no se pudo cargar.")
    with db.write() as conn:
        conn.execute("INSERT INTO access_plugin_state(plugin_id, enabled) VALUES(?, ?) "
                     "ON CONFLICT(plugin_id) DO UPDATE SET enabled = excluded.enabled", (plugin_id, int(enabled)))
    return list_plugins()


def _run_one(p: Plugin, snapshot: dict) -> list[PluginFinding]:
    result: dict = {}

    def target():
        try:
            result["value"] = p.fn(copy.deepcopy(snapshot))  # copia: el plugin no altera el contexto real
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(TIMEOUT_S)
    if t.is_alive():
        return [PluginFinding(p.id, p.name, "Tiempo límite excedido", "low", f"El plugin superó {TIMEOUT_S} s.")]
    if "error" in result:
        return [PluginFinding(p.id, p.name, "Error del plugin", "low", result["error"])]
    out = []
    for item in result.get("value") or []:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        sev = item.get("severity", "info")
        try:
            scan_text(str(item.get("title")), str(item.get("detail", "")))
        except PolicyViolation as e:
            out.append(PluginFinding(p.id, p.name, "Hallazgo descartado por política", "low", e.message))
            continue
        out.append(PluginFinding(p.id, p.name, str(item["title"])[:200], sev if sev in SEVERITIES else "info",
                                 str(item.get("detail", ""))[:2000] or None,
                                 item.get("data") if isinstance(item.get("data"), dict) else {}))
    return out


def run_all(snapshot: dict) -> list[PluginFinding]:
    state = _enabled_map()
    findings: list[PluginFinding] = []
    for p in discover():
        if p.fn is None or not is_enabled(p, state) or snapshot.get("platform") not in p.platforms:
            continue
        findings += _run_one(p, snapshot)
    return findings
