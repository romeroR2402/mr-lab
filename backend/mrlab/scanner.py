"""Device Scanner: agrega todos los conectores y registra hallazgos."""
from __future__ import annotations

import threading

from . import db, evidence
from .connectors.android import AdbConnector, FastbootConnector
from .connectors.apple import AppleConnector
from .connectors.base import Device
from .util.timeutil import now_iso

_lock = threading.Lock()
_session_seen: set[str] = set()
_last: dict = {"devices": [], "errors": [], "scannedAt": None, "connectors": {}}
_cache: dict[str, Device] = {}


def _persist(dev: Device) -> None:
    now = now_iso()
    with db.write() as conn:
        conn.execute(
            """INSERT INTO devices(platform, serial, manufacturer, model, os_name, os_version, first_seen, last_seen)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(platform, serial) DO UPDATE SET
                 manufacturer = COALESCE(excluded.manufacturer, devices.manufacturer),
                 model = COALESCE(excluded.model, devices.model),
                 os_name = COALESCE(excluded.os_name, devices.os_name),
                 os_version = COALESCE(excluded.os_version, devices.os_version),
                 last_seen = excluded.last_seen""",
            (dev.platform, dev.serial, dev.manufacturer, dev.model, dev.os_name, dev.os_version, now, now),
        )


def scan() -> dict:
    with _lock:
        connectors = [AdbConnector(), FastbootConnector(), AppleConnector()]
        devices: list[Device] = []
        errors: list[str] = []
        status = {}
        for c in connectors:
            found, errs = c.list_devices()
            status[c.name] = {"available": c.available, "count": len(found)}
            devices += found
            errors += errs
        current_keys = set()
        for dev in devices:
            current_keys.add(dev.key)
            _cache[dev.key] = dev
            try:
                _persist(dev)
            except Exception as e:  # la detección no debe fallar por la base
                errors.append(f"No se pudo registrar {dev.serial}: {e}")
            if dev.key not in _session_seen:
                _session_seen.add(dev.key)
                evidence.log(
                    "Dispositivo detectado", "info", device_serial=dev.serial, device_label=dev.label,
                    details={"conexión": dev.connection, "comunicación": dev.comm_state,
                             "autorización": dev.auth_state, "conector": dev.connector},
                )
        for gone in list(_session_seen - current_keys):
            _session_seen.discard(gone)
            old = _cache.pop(gone, None)
            evidence.log("Dispositivo desconectado", "info",
                         device_serial=old.serial if old else gone, device_label=old.label if old else None)
        _last.update({
            "devices": [d.to_api() for d in devices],
            "errors": errors,
            "scannedAt": now_iso(),
            "connectors": status,
        })
        return dict(_last)


def last_scan() -> dict:
    return dict(_last)


def get_cached(key: str) -> Device | None:
    return _cache.get(key)


def known_devices(limit: int = 50) -> list[dict]:
    with db.read() as conn:
        rows = conn.execute("SELECT * FROM devices ORDER BY last_seen DESC LIMIT ?", (limit,)).fetchall()
    return [{"platform": r["platform"], "serial": r["serial"], "manufacturer": r["manufacturer"],
             "model": r["model"], "osName": r["os_name"], "osVersion": r["os_version"],
             "firstSeen": r["first_seen"], "lastSeen": r["last_seen"]} for r in rows]
