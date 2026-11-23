"""Conector Android basado en Android SDK Platform Tools (adb / fastboot).
Solo usa interfaces oficiales: requiere depuración USB autorizada por el usuario
del dispositivo para obtener información."""
from __future__ import annotations

import re

from .. import tools
from ..util.proc import ProcResult, run
from .base import Device

_PROP_RE = re.compile(r"^\[(?P<k>[^\]]+)\]: \[(?P<v>.*)\]$")

ADB_STATES = {
    "device": ("online", "authorized", "normal"),
    "unauthorized": ("unauthorized", "unauthorized", "normal"),
    "authorizing": ("connecting", "pending", "normal"),
    "offline": ("offline", "unknown", "normal"),
    "recovery": ("recovery", "authorized", "recovery"),
    "rescue": ("recovery", "authorized", "recovery"),
    "sideload": ("sideload", "not_applicable", "sideload"),
    "bootloader": ("bootloader", "not_applicable", "bootloader"),
    "connecting": ("connecting", "unknown", "normal"),
    "host": ("offline", "unknown", "normal"),
}


def parse_adb_devices(output: str) -> list[dict]:
    """Parsea `adb devices -l`."""
    result = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*") or line.startswith("adb "):
            continue
        m = re.match(r"^(\S+)\s+(no permissions.*?|\S+)(?:\s+(.*))?$", line)
        if not m:
            continue
        serial, state, rest = m.group(1), m.group(2), m.group(3) or ""
        props = dict(re.findall(r"(\w+):(\S+)", rest))
        if state.startswith("no permissions"):
            # en Linux el mensaje incluye la causa (reglas udev / grupo plugdev)
            props = dict(re.findall(r"(\w+):(\S+)", line.split("]", 1)[-1])) if "]" in line else props
            state = "no permissions"
        result.append({"serial": serial, "state": state, "props": props})
    return result


def parse_getprop(output: str) -> dict:
    props = {}
    for line in output.splitlines():
        m = _PROP_RE.match(line.strip())
        if m:
            props[m.group("k")] = m.group("v")
    return props


def connection_type(serial: str, props: dict) -> str:
    if serial.startswith("emulator-"):
        return "emulator"
    if "usb" in props:
        return "usb"
    if re.match(r"^[\w.\-]+:\d+$", serial) or "._adb-tls-connect._tcp" in serial:
        return "network"
    return "usb"


class AdbConnector:
    name = "adb"

    def __init__(self) -> None:
        self.path = tools.find("adb")

    @property
    def available(self) -> bool:
        return bool(self.path)

    def _cmd(self, *args: str, serial: str | None = None, timeout: float = 15) -> ProcResult:
        if not self.path:
            return ProcResult(None, "", "", error="adb no está instalado o no se encontró su ruta")
        cmd = [self.path]
        if serial:
            cmd += ["-s", serial]
        return run([*cmd, *args], timeout=timeout)

    def shell(self, serial: str, command: str, timeout: float = 15) -> ProcResult:
        return self._cmd("shell", command, serial=serial, timeout=timeout)

    def getprops(self, serial: str) -> dict:
        r = self.shell(serial, "getprop", timeout=10)
        return parse_getprop(r.stdout) if r.ok else {}

    def list_devices(self) -> tuple[list[Device], list[str]]:
        errors: list[str] = []
        if not self.path:
            return [], ["adb no disponible: instale Android SDK Platform Tools o configure su ruta en Settings."]
        r = self._cmd("devices", "-l", timeout=20)
        if not r.ok:
            errors.append(f"adb devices falló: {r.error or r.stderr.strip() or r.code}")
            return [], errors
        devices: list[Device] = []
        for entry in parse_adb_devices(r.stdout):
            serial, state, props = entry["serial"], entry["state"], entry["props"]
            if state == "no permissions":
                comm, auth, mode = "no_permissions", "no_permissions", "normal"
            else:
                comm, auth, mode = ADB_STATES.get(state, ("unknown", "unknown", "normal"))
            dev = Device(
                platform="android", serial=serial, connection=connection_type(serial, props),
                comm_state=comm, auth_state=auth, mode=mode, connector="adb",
                model=props.get("model", "").replace("_", " ") or None,
                model_code=props.get("device"), os_name="Android", raw={"adbState": state, **props},
            )
            if state == "device":
                gp = self.getprops(serial)
                if gp:
                    dev.manufacturer = gp.get("ro.product.manufacturer") or gp.get("ro.product.brand")
                    dev.model = gp.get("ro.product.model") or dev.model
                    dev.model_code = gp.get("ro.product.device") or dev.model_code
                    dev.os_version = gp.get("ro.build.version.release")
                    dev.raw["sdk"] = gp.get("ro.build.version.sdk")
                else:
                    dev.notes.append("No fue posible leer propiedades del sistema (getprop).")
                dev.diagnostics = ["identidad", "batería", "almacenamiento", "memoria", "pantalla",
                                   "táctil", "cifrado", "arranque verificado", "conectividad"]
            elif state == "unauthorized":
                dev.notes.append("Acepte el diálogo 'Permitir depuración USB' en la pantalla del dispositivo.")
                dev.diagnostics = ["comunicación USB"]
            elif state == "no permissions":
                dev.notes.append("El sistema operativo no concede acceso USB (revise controlador / reglas udev).")
            elif state == "offline":
                dev.notes.append("Dispositivo fuera de línea: reconecte el cable o reinicie el servidor adb.")
            elif state in ("recovery", "rescue", "sideload"):
                dev.notes.append(f"Dispositivo en modo {state}.")
                dev.diagnostics = ["comunicación USB", "modo de arranque"]
            devices.append(dev)
        return devices, errors


def parse_fastboot_vars(output: str) -> dict:
    out = {}
    for line in output.splitlines():
        m = re.match(r"^\(bootloader\)\s+([\w\-.:]+?):\s*(.*)$", line.strip())
        if m:
            key, val = m.group(1), m.group(2).strip()
            out.setdefault(key, val)
    return out


class FastbootConnector:
    name = "fastboot"

    def __init__(self) -> None:
        self.path = tools.find("fastboot")

    @property
    def available(self) -> bool:
        return bool(self.path)

    def getvar_all(self, serial: str) -> dict:
        if not self.path:
            return {}
        r = run([self.path, "-s", serial, "getvar", "all"], timeout=20)
        return parse_fastboot_vars(r.output)

    def list_devices(self) -> tuple[list[Device], list[str]]:
        if not self.path:
            return [], []
        r = run([self.path, "devices", "-l"], timeout=15)
        if r.error:
            return [], [f"fastboot devices falló: {r.error}"]
        devices = []
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2 or parts[1] not in ("fastboot", "fastbootd", "bootloader"):
                if len(parts) >= 2 and parts[1] == "no" and "permissions" in line:
                    devices.append(Device("android", parts[0], "usb", "no_permissions", "no_permissions",
                                          mode="bootloader", connector="fastboot", os_name="Android"))
                continue
            serial = parts[0]
            dev = Device("android", serial, "usb", "bootloader", "not_applicable",
                         mode="fastbootd" if parts[1] == "fastbootd" else "bootloader",
                         connector="fastboot", os_name="Android (bootloader)")
            dev.diagnostics = ["variables de bootloader", "estado de desbloqueo"]
            dev.notes.append("Dispositivo en modo bootloader/fastboot.")
            devices.append(dev)
        return devices, []
