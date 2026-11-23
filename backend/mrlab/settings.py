"""Ajustes locales. Sólo se aceptan claves conocidas: nunca se guardan
códigos de acceso, PIN, patrones ni contraseñas de dispositivos."""
from __future__ import annotations

import json
import re

from . import db
from .errors import RpcError

DEFAULTS: dict = {
    "technicianName": "",
    "labName": "",
    "adbPath": "",
    "fastbootPath": "",
    "libimobiledeviceDir": "",
    "autoScanSeconds": 5,
    "maskIdentifiers": False,
    # Modo autónomo: usar exclusivamente los componentes integrados en MR Lab.
    "autonomousMode": False,
}

_FORBIDDEN = re.compile(r"(pass|pwd|pin|passcode|patron|pattern|secret|clave|codigo)", re.I)


def _validate(key: str, value):
    if key not in DEFAULTS:
        if _FORBIDDEN.search(key):
            raise RpcError("forbidden_setting", "MR Lab no almacena credenciales ni códigos de acceso de dispositivos.")
        raise RpcError("unknown_setting", f"Ajuste desconocido: {key}")
    default = DEFAULTS[key]
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise RpcError("invalid_setting", f"{key} debe ser booleano")
    elif isinstance(default, int):
        if not isinstance(value, int) or isinstance(value, bool) or not (2 <= value <= 300):
            raise RpcError("invalid_setting", f"{key} debe ser un entero entre 2 y 300")
    elif isinstance(default, str):
        if not isinstance(value, str) or len(value) > 1024:
            raise RpcError("invalid_setting", f"{key} debe ser texto (máx. 1024)")
    return value


def get_all() -> dict:
    out = dict(DEFAULTS)
    with db.read() as conn:
        for row in conn.execute("SELECT key, value FROM settings"):
            if row["key"] in DEFAULTS:
                try:
                    out[row["key"]] = json.loads(row["value"])
                except json.JSONDecodeError:
                    pass
    return out


def get(key: str):
    return get_all().get(key)


def update(values: dict) -> dict:
    if not isinstance(values, dict):
        raise RpcError("invalid_params", "Se esperaba un objeto de ajustes")
    clean = {k: _validate(k, v) for k, v in values.items()}
    with db.write() as conn:
        for k, v in clean.items():
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (k, json.dumps(v)),
            )
    return get_all()


def technician() -> str:
    name = (get("technicianName") or "").strip()
    return name or "Sin asignar"
