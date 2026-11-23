"""Conector Apple basado en libimobiledevice. En Windows requiere el servicio
'Apple Mobile Device Service' (app Apple Devices o iTunes). Solo opera con
dispositivos que el usuario haya marcado como 'Confiar en este equipo'."""
from __future__ import annotations

import plistlib
import re

from .. import tools
from ..util.proc import ProcResult, run
from .base import Device

PRODUCT_NAMES = {
    "iPhone12,1": "iPhone 11", "iPhone12,3": "iPhone 11 Pro", "iPhone12,5": "iPhone 11 Pro Max",
    "iPhone12,8": "iPhone SE (2.ª gen.)", "iPhone13,1": "iPhone 12 mini", "iPhone13,2": "iPhone 12",
    "iPhone13,3": "iPhone 12 Pro", "iPhone13,4": "iPhone 12 Pro Max", "iPhone14,4": "iPhone 13 mini",
    "iPhone14,5": "iPhone 13", "iPhone14,2": "iPhone 13 Pro", "iPhone14,3": "iPhone 13 Pro Max",
    "iPhone14,6": "iPhone SE (3.ª gen.)", "iPhone14,7": "iPhone 14", "iPhone14,8": "iPhone 14 Plus",
    "iPhone15,2": "iPhone 14 Pro", "iPhone15,3": "iPhone 14 Pro Max", "iPhone15,4": "iPhone 15",
    "iPhone15,5": "iPhone 15 Plus", "iPhone16,1": "iPhone 15 Pro", "iPhone16,2": "iPhone 15 Pro Max",
    "iPhone17,3": "iPhone 16", "iPhone17,4": "iPhone 16 Plus", "iPhone17,1": "iPhone 16 Pro",
    "iPhone17,2": "iPhone 16 Pro Max", "iPhone17,5": "iPhone 16e",
}


def parse_kv(output: str) -> dict:
    out = {}
    for line in output.splitlines():
        if ": " in line and not line.startswith(" "):
            k, v = line.split(": ", 1)
            out[k.strip()] = v.strip()
    return out


def classify_lockdown_error(text: str) -> tuple[str, str]:
    """Traduce errores de lockdownd a (auth_state, nota)."""
    t = text.lower()
    if "pairing dialog response pending" in t:
        return "pending", "Pulse 'Confiar' en el dispositivo y, si se solicita, introduzca su código en el propio dispositivo."
    if "user denied pairing" in t:
        return "unauthorized", "El usuario rechazó la confianza con este equipo."
    if "password protected" in t or "passcode" in t:
        return "locked", "El dispositivo está bloqueado: el titular debe desbloquearlo para autorizar la conexión."
    if "invalid hostid" in t or "not paired" in t or "pairing" in t:
        return "not_paired", "Equipo no emparejado: desbloquee el dispositivo y acepte 'Confiar en este equipo'."
    return "unknown", text.strip()[:300] or "Error de comunicación con lockdownd."


class AppleConnector:
    name = "libimobiledevice"

    def __init__(self) -> None:
        self.idevice_id = tools.find("idevice_id")
        self.ideviceinfo = tools.find("ideviceinfo")
        self.idevicediagnostics = tools.find("idevicediagnostics")

    @property
    def available(self) -> bool:
        return bool(self.idevice_id and self.ideviceinfo)

    def info(self, udid: str, domain: str | None = None, simple: bool = False, network: bool = False) -> ProcResult:
        cmd = [self.ideviceinfo, "-u", udid]
        if network:
            cmd.append("-n")
        if simple:
            cmd.append("-s")
        if domain:
            cmd += ["-q", domain]
        return run(cmd, timeout=15)

    def battery_registry(self, udid: str) -> dict:
        if not self.idevicediagnostics:
            return {}
        r = run([self.idevicediagnostics, "-u", udid, "ioregentry", "AppleSmartBattery"], timeout=15)
        if not r.ok or "<plist" not in r.stdout:
            return {}
        try:
            data = plistlib.loads(r.stdout[r.stdout.index("<?xml") if "<?xml" in r.stdout else r.stdout.index("<plist"):].encode())
            return data.get("IORegistry", data) if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _udids(self, flag: str) -> list[str]:
        r = run([self.idevice_id, flag], timeout=10)
        if not r.ok:
            return []
        return [u.strip() for u in r.stdout.splitlines() if re.match(r"^[0-9A-Fa-f\-]{24,}$", u.strip())]

    def list_devices(self) -> tuple[list[Device], list[str]]:
        if not self.available:
            return [], ["Motor Apple no disponible: el componente integrado falta o no superó la verificación de integridad (Configuración → Componentes)."]
        errors: list[str] = []
        seen: dict[str, str] = {}
        for udid in self._udids("-l"):
            seen[udid] = "usb"
        for udid in self._udids("-n"):
            seen.setdefault(udid, "network")
        devices = []
        for udid, conn in seen.items():
            net = conn == "network"
            full = self.info(udid, network=net)
            dev = Device("apple", udid, conn, "online", "authorized", connector=self.name, manufacturer="Apple")
            if full.ok and full.stdout.strip():
                kv = parse_kv(full.stdout)
                dev.raw = {k: kv.get(k) for k in ("ProductType", "DeviceName", "ActivationState", "BuildVersion", "HardwareModel")}
            else:
                auth, note = classify_lockdown_error(full.output or full.error or "")
                dev.auth_state = auth
                dev.notes.append(note)
                kv = parse_kv(self.info(udid, simple=True, network=net).stdout)
            ptype = kv.get("ProductType")
            dev.model = PRODUCT_NAMES.get(ptype or "", ptype)
            dev.model_code = ptype
            dev.os_name = "iPadOS" if (ptype or "").startswith("iPad") else "iOS"
            dev.os_version = kv.get("ProductVersion")
            dev.diagnostics = (["identidad", "batería", "almacenamiento", "activación", "cifrado de respaldo"]
                               if dev.auth_state == "authorized" else ["comunicación USB"])
            devices.append(dev)
        return devices, errors
