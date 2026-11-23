"""Detección de herramientas externas instaladas."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from . import components, config, settings
from .util.proc import run

EXE = ".exe" if config.IS_WINDOWS else ""


def _android_sdk_dirs() -> list[Path]:
    dirs = []
    for env in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        if os.environ.get(env):
            dirs.append(Path(os.environ[env]) / "platform-tools")
    if config.IS_WINDOWS and os.environ.get("LOCALAPPDATA"):
        dirs.append(Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk" / "platform-tools")
    dirs += [Path.home() / "Android" / "Sdk" / "platform-tools", Path.home() / "Library/Android/sdk/platform-tools"]
    if config.IS_WINDOWS:
        dirs.append(Path("C:/platform-tools"))
    return dirs


def locate(name: str) -> tuple[str | None, str | None]:
    """Devuelve (ruta, origen). Orden: ruta personalizada → componente integrado
    verificado → sistema (solo si el modo autónomo está desactivado)."""
    s = settings.get_all()
    override = {"adb": s["adbPath"], "fastboot": s["fastbootPath"]}.get(name, s["libimobiledeviceDir"])
    if override:
        p = Path(override)
        p = p / f"{name}{EXE}" if p.is_dir() else p
        if p.is_file():
            return str(p), "custom"
    integrated = components.integrated_tool(name)
    if integrated:
        return integrated, "integrated"
    if s["autonomousMode"]:
        return None, None
    cands = []
    found = shutil.which(name)
    if found:
        cands.append(Path(found))
    if name in ("adb", "fastboot"):
        cands += [d / f"{name}{EXE}" for d in _android_sdk_dirs()]
    for c in cands:
        if c.is_file():
            return str(c), "system"
    return None, None


def find(name: str) -> str | None:
    return locate(name)[0]


def _version(path: str | None, args: list[str], pattern: str) -> str | None:
    if not path:
        return None
    r = run([path, *args], timeout=8)
    m = re.search(pattern, r.output)
    return m.group(1) if m else None


def apple_service_status() -> dict:
    """En Windows libimobiledevice requiere el servicio de Apple (iTunes o app Apple Devices)."""
    if config.IS_WINDOWS:
        for svc in ("Apple Mobile Device Service", "AppleMobileDeviceService"):
            r = run(["sc", "query", svc], timeout=6)
            if r.code == 0:
                running = "RUNNING" in r.stdout
                return {"name": svc, "installed": True, "running": running,
                        "detail": "En ejecución" if running else "Instalado pero detenido"}
        return {"name": "Apple Mobile Device Service", "installed": False, "running": False,
                "detail": "No instalado. Windows lo requiere para comunicarse por USB con iPhone/iPad.", "storeUrl": "ms-windows-store://pdp/?productid=9NP83LWLPZ9K"}
    usbmuxd = shutil.which("usbmuxd")
    sock = Path("/var/run/usbmuxd").exists()
    return {"name": "usbmuxd", "installed": bool(usbmuxd) or sock, "running": sock,
            "detail": "Socket activo" if sock else ("Instalado, sin socket activo" if usbmuxd else "No instalado")}


_cache: dict = {"at": 0.0, "value": None}


def detect(force: bool = False) -> dict:
    """Resultado cacheado 30 s: cada detección lanza varios procesos."""
    import time
    if not force and _cache["value"] and time.monotonic() - _cache["at"] < 30:
        return _cache["value"]
    _cache["value"] = _detect()
    _cache["at"] = time.monotonic()
    return _cache["value"]


def invalidate() -> None:
    _cache["value"] = None


def _detect() -> dict:
    loc = {n: locate(n) for n in ("adb", "fastboot", "idevice_id", "ideviceinfo", "idevicebackup2",
                                   "idevicediagnostics", "idevicepair")}
    adb, fastboot = loc["adb"][0], loc["fastboot"][0]
    idevice_id, ideviceinfo = loc["idevice_id"][0], loc["ideviceinfo"][0]
    backup2, diag, pair = loc["idevicebackup2"][0], loc["idevicediagnostics"][0], loc["idevicepair"][0]
    try:
        import cryptography  # noqa: F401
        crypto = {"available": True, "version": cryptography.__version__}
    except Exception:  # pragma: no cover
        crypto = {"available": False, "version": None}

    def tool(tid, name, path, version, purpose, required_for):
        return {"id": tid, "name": name, "path": path, "installed": bool(path), "version": version,
                "purpose": purpose, "requiredFor": required_for, "source": loc[tid][1]}

    comp = components.status()
    tool_list = [
            tool("adb", "Android Debug Bridge (adb)", adb,
                 _version(adb, ["version"], r"Android Debug Bridge version ([\d.]+)"),
                 "Comunicación con dispositivos Android con depuración USB autorizada",
                 ["Detección", "Diagnóstico Android", "Recuperación de datos"]),
            tool("fastboot", "fastboot", fastboot, _version(fastboot, ["--version"], r"fastboot version ([\w.\-]+)"),
                 "Detección y diagnóstico en modo bootloader", ["Detección", "Reparación de sistema", "Restauración"]),
            tool("idevice_id", "libimobiledevice: idevice_id", idevice_id,
                 _version(idevice_id, ["--version"], r"idevice_id ([\d.]+)"),
                 "Enumeración de dispositivos Apple", ["Detección"]),
            tool("ideviceinfo", "libimobiledevice: ideviceinfo", ideviceinfo,
                 _version(ideviceinfo, ["--version"], r"ideviceinfo ([\d.]+)"),
                 "Información y diagnóstico de dispositivos Apple emparejados", ["Diagnóstico Apple"]),
            tool("idevicepair", "libimobiledevice: idevicepair", pair, None,
                 "Validación de confianza (pairing) con el equipo", ["Detección"]),
            tool("idevicediagnostics", "libimobiledevice: idevicediagnostics", diag, None,
                 "Lectura de salud de batería en dispositivos Apple", ["Diagnóstico Apple"]),
            tool("idevicebackup2", "libimobiledevice: idevicebackup2", backup2, None,
                 "Respaldos oficiales de dispositivos Apple", ["Respaldos"]),
    ]
    core = [t for t in tool_list if t["id"] in ("adb", "fastboot", "idevice_id", "ideviceinfo")]
    return {
        "tools": tool_list,
        "components": comp,
        "autonomy": {
            "autonomousMode": settings.get("autonomousMode"),
            "allIntegrated": all(t["source"] == "integrated" for t in core),
            "external": [t["id"] for t in tool_list if t["source"] in ("system", "custom")],
            "missing": [t["id"] for t in tool_list if not t["installed"]],
        },
        "appleService": apple_service_status(),
        "encryption": crypto,
        "platform": "windows" if config.IS_WINDOWS else os.name,
    }
