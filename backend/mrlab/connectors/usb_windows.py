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
    "12D1": ("Huawei / Honor (modelos anteriores a 2021)", None),
    "339B": ("Honor", None),
    "22D9": ("OPPO / realme", "https://developer.android.com/studio/run/oem-usb"),
    "2A70": ("OnePlus", "https://developer.android.com/studio/run/oem-usb"),
    "1004": ("LG", "https://developer.android.com/studio/run/oem-usb"),
    "0FCE": ("Sony", "https://developer.android.com/studio/run/oem-usb"),
    "2D95": ("vivo", "https://developer.android.com/studio/run/oem-usb"),
    "0BB4": ("HTC", "https://developer.android.com/studio/run/oem-usb"),
    "05AC": ("Apple", None),
}
# Indicaciones específicas por fabricante (controlador y ajustes del teléfono).
VENDOR_TIPS = {
    "Samsung": "Instale «Samsung Android USB Driver for Windows» desde la web de desarrolladores de Samsung.",
    "Honor": ("Instale HONOR Suite desde la web oficial de Honor (incluye el controlador USB). En el teléfono active "
              "«Permitir depuración ADB en modo Solo carga» o elija «Transferir archivos» al conectar."),
    "Huawei / Honor (modelos anteriores a 2021)": (
        "Instale HiSuite desde la web oficial de Huawei (incluye el controlador USB). En el teléfono active "
        "«Permitir depuración ADB en modo Solo carga» o elija «Transferir archivos» al conectar."),
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
                                    "adb": None, "adbOk": False, "missingDriver": False, "mtp": False, "storage": False})
        code = e.get("ConfigManagerErrorCode")
        p["interfaces"].append({"name": e.get("Name"), "class": e.get("PNPClass"), "errorCode": code})
        if code not in (0, None):
            p["missingDriver"] = True
        name_l = (e.get("Name") or "").lower()
        if (e.get("PNPClass") or "") == "WPD" or "mtp" in name_l:
            p["mtp"] = True
        if (e.get("PNPClass") or "") in ("DiskDrive", "CDROM") or "almacenamiento" in name_l or "mass storage" in name_l:
            p["storage"] = True
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
                            + VENDOR_TIPS.get(p["vendor"], f"Instale el controlador USB oficial de {p['vendor']}.")
                            + " Después vuelva a conectar el cable.")
        elif p["storage"] and not p["mtp"] and not p["adb"]:
            p["diagnosis"] = "charge_only"
            p["message"] = ("El teléfono está en modo «Solo carga»: se presenta como unidad de almacenamiento y no expone la "
                            "depuración USB. En el teléfono, toque el aviso de USB y elija «Transferir archivos», o active "
                            "«Permitir depuración ADB en modo Solo carga» en Opciones de desarrollador. Después acepte "
                            "«¿Permitir depuración USB?».")
        elif p["mtp"]:
            p["diagnosis"] = "no_adb_interface"
            p["message"] = ("El teléfono está conectado sin la interfaz de depuración. Active «Depuración USB» en Opciones de "
                            "desarrollador y vuelva a conectar el cable."
                            + (" " + VENDOR_TIPS[p["vendor"]] if p["vendor"] in VENDOR_TIPS else ""))
        else:
            p["diagnosis"] = "unknown"
            p["message"] = ("Windows detecta el teléfono pero sin interfaz de depuración. Revise la depuración USB y el cable."
                            + (" " + VENDOR_TIPS[p["vendor"]] if p["vendor"] in VENDOR_TIPS else ""))
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
