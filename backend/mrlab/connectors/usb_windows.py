"""Diagnóstico de conexión USB en Windows.

Cuando adb no ve un teléfono, la causa suele estar en Windows: falta el
controlador del fabricante, el cable solo carga o la depuración USB no está
activa. Este módulo pregunta a Windows (PnP) qué teléfonos hay conectados por
USB y en qué estado está su controlador, para explicar al técnico qué hacer.
Solo lectura: no instala ni modifica nada."""
from __future__ import annotations

import json
import re
import time

from .. import config
from ..util.proc import run

VENDORS = {
    "04E8": ("Samsung", "https://developer.samsung.com/android-usb-driver"),
    "18D1": ("Google / genérico Android", None),
    "2717": ("Xiaomi", "https://developer.android.com/studio/run/oem-usb"),
    "22B8": ("Motorola", "https://developer.android.com/studio/run/oem-usb"),
    "12D1": ("Huawei", "https://developer.android.com/studio/run/oem-usb"),
    "22D9": ("OPPO / realme", "https://developer.android.com/studio/run/oem-usb"),
    "2A70": ("OnePlus", "https://developer.android.com/studio/run/oem-usb"),
    "1004": ("LG", "https://developer.android.com/studio/run/oem-usb"),
    "0FCE": ("Sony", "https://developer.android.com/studio/run/oem-usb"),
    "2D95": ("vivo", "https://developer.android.com/studio/run/oem-usb"),
    "0BB4": ("HTC", "https://developer.android.com/studio/run/oem-usb"),
    "05AC": ("Apple", None),
}
_VID = re.compile(r"VID_([0-9A-F]{4})", re.I)
_cache: dict = {"at": 0.0, "value": None}

PS_QUERY = (
    "Get-CimInstance Win32_PnPEntity | Where-Object { $_.DeviceID -like 'USB\\VID_*' } | "
    "Select-Object Name, DeviceID, PNPClass, ConfigManagerErrorCode, Status | ConvertTo-Json -Compress"
)


def _is_adb(e: dict) -> bool:
    name = (e.get("Name") or "").lower()
    return "adb" in name or (e.get("PNPClass") or "") in ("AndroidUsbDeviceClass", "ADB Interface") or "&mi_01" in (e.get("DeviceID") or "").lower() and "android" in name


def analyze(entries: list[dict]) -> list[dict]:
    """Agrupa las entradas PnP por teléfono y genera un diagnóstico por cada uno."""
    phones: dict[str, dict] = {}
    for e in entries:
        dev_id = e.get("DeviceID") or ""
        m = _VID.search(dev_id)
        if not m or m.group(1).upper() not in VENDORS:
            continue
        vid = m.group(1).upper()
        vendor, driver_url = VENDORS[vid]
        # Windows registra cada interfaz (MTP, ADB…) con su propio ID: se agrupan por fabricante.
        p = phones.setdefault(vid, {"vendor": vendor, "vid": vid, "driverUrl": driver_url, "interfaces": [],
                                    "adb": None, "adbOk": False, "missingDriver": False, "mtp": False})
        code = e.get("ConfigManagerErrorCode")
        p["interfaces"].append({"name": e.get("Name"), "class": e.get("PNPClass"), "errorCode": code})
        if code not in (0, None):
            p["missingDriver"] = True
        if (e.get("PNPClass") or "") == "WPD" or "mtp" in (e.get("Name") or "").lower():
            p["mtp"] = True
        if _is_adb(e):
            p["adb"] = e.get("Name")
            p["adbOk"] = code == 0
    out = []
    for p in phones.values():
        if p["vendor"] == "Apple":
            p["diagnosis"] = "apple"
            p["message"] = "Windows ve un dispositivo Apple. MR Lab necesita el motor Apple y la app Apple Devices para comunicarse con él."
        elif p["adbOk"]:
            p["diagnosis"] = "adb_ready"
            p["message"] = ("La interfaz de depuración tiene controlador. Si MR Lab no lo muestra, acepte «¿Permitir depuración USB?» "
                            "en la pantalla del teléfono o reconecte el cable.")
        elif p["missingDriver"]:
            p["diagnosis"] = "missing_driver"
            p["message"] = (f"Windows detecta el teléfono {p['vendor']}, pero una de sus interfaces no tiene controlador. "
                            f"Instale el controlador USB oficial de {p['vendor']} y vuelva a conectar el cable.")
        elif p["mtp"]:
            p["diagnosis"] = "no_adb_interface"
            p["message"] = ("El teléfono está conectado solo para transferir archivos: no expone la interfaz de depuración. "
                            "Active «Depuración USB» en Opciones de desarrollador y vuelva a conectar el cable.")
        else:
            p["diagnosis"] = "unknown"
            p["message"] = "Windows detecta el teléfono pero sin interfaz de depuración. Revise la depuración USB y el cable."
        out.append(p)
    return out


def scan(force: bool = False) -> list[dict]:
    if not config.IS_WINDOWS:
        return []
    if not force and _cache["value"] is not None and time.monotonic() - _cache["at"] < 15:
        return _cache["value"]
    r = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_QUERY], timeout=20)
    result: list[dict] = []
    if r.ok and r.stdout.strip():
        try:
            data = json.loads(r.stdout)
            result = analyze(data if isinstance(data, list) else [data])
        except json.JSONDecodeError:
            result = []
    _cache.update(at=time.monotonic(), value=result)
    return result
