"""Diagnóstico Android vía adb shell (solo lectura) y fastboot getvar."""
from __future__ import annotations

import re

from ..connectors.android import AdbConnector, FastbootConnector
from ..connectors.base import Device
from .model import Check, unavailable

BATTERY_HEALTH = {"1": "Desconocida", "2": "Buena", "3": "Sobrecalentada", "4": "Agotada",
                  "5": "Sobrevoltaje", "6": "Falla", "7": "Fría"}
BATTERY_STATUS = {"1": "Desconocido", "2": "Cargando", "3": "Descargando", "4": "Sin carga", "5": "Completa"}


def parse_dumpsys_battery(out: str) -> dict:
    data = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip()
    return data


def parse_df(out: str) -> dict | None:
    """Parsea `df -k /data` (toybox). Devuelve bytes."""
    lines = [line for line in out.splitlines() if line.strip()]
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 6 and parts[1].isdigit():
            total, used, avail = int(parts[1]) * 1024, int(parts[2]) * 1024, int(parts[3]) * 1024
            return {"total": total, "used": used, "available": avail, "mount": parts[-1]}
    return None


def parse_meminfo(out: str) -> dict:
    vals = {}
    for line in out.splitlines():
        m = re.match(r"^(\w+):\s+(\d+)\s*kB", line)
        if m:
            vals[m.group(1)] = int(m.group(2)) * 1024
    return vals


def parse_touch_devices(dumpsys_input: str) -> list[str]:
    """Nombres de dispositivos de entrada táctiles en `dumpsys input`.
    Reconoce 'Classes: TOUCH...' (Event Hub) y 'Sources: ...TOUCHSCREEN' (Input Reader)."""
    names = []
    current = None
    for line in dumpsys_input.splitlines():
        m = re.match(r"^\s+(?:Device\s+)?-?\d+:\s+(.+)$", line)
        if m:
            current = m.group(1).strip()
            continue
        if current and (re.search(r"Classes:.*\bTOUCH", line) or re.search(r"Sources:.*TOUCHSCREEN", line)):
            names.append(current)
    return sorted(set(names))


def fmt_bytes(n: int | None) -> str:
    if n is None:
        return "—"
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f} {unit}"
        f /= 1024
    return str(n)


def run_adb(dev: Device) -> list[Check]:
    adb = AdbConnector()
    checks: list[Check] = []
    s = dev.serial

    comm = Check("comm", "Comunicación", "Comunicación ADB")
    comm.value = dev.comm_state
    comm.status = "ok" if dev.comm_state == "online" else ("warning" if dev.comm_state in ("recovery", "sideload") else "error")
    comm.detail = f"Conexión {dev.connection} mediante adb ({adb.path or 'no encontrado'})"
    checks.append(comm)

    auth = Check("auth", "Comunicación", "Autorización de depuración USB", value=dev.auth_state)
    auth.status = "ok" if dev.auth_state == "authorized" else "error"
    if dev.auth_state != "authorized":
        auth.detail = "Sin autorización no se pueden ejecutar diagnósticos. Acepte la huella RSA en el dispositivo."
    checks.append(auth)

    if dev.comm_state != "online" or dev.auth_state != "authorized":
        for cid, cat, label in (("identity", "Sistema", "Identidad del dispositivo"),
                                ("battery", "Energía", "Batería"), ("storage", "Almacenamiento", "Almacenamiento /data"),
                                ("display", "Pantalla", "Pantalla"), ("touch", "Pantalla", "Panel táctil")):
            checks.append(unavailable(cid, cat, label, "Requiere dispositivo en línea y autorizado."))
        return checks

    props = adb.getprops(s)
    ident = Check("identity", "Sistema", "Identidad del dispositivo")
    if props:
        ident.status = "info"
        ident.value = f"{props.get('ro.product.manufacturer', '?')} {props.get('ro.product.model', '?')}"
        ident.data = {
            "Fabricante": props.get("ro.product.manufacturer"), "Marca": props.get("ro.product.brand"),
            "Modelo": props.get("ro.product.model"), "Dispositivo": props.get("ro.product.device"),
            "Android": props.get("ro.build.version.release"), "SDK": props.get("ro.build.version.sdk"),
            "Parche de seguridad": props.get("ro.build.version.security_patch"),
            "Compilación": props.get("ro.build.display.id"), "ABI": props.get("ro.product.cpu.abi"),
            "Plataforma": props.get("ro.board.platform") or props.get("ro.hardware"),
        }
    else:
        ident = unavailable("identity", "Sistema", "Identidad del dispositivo", "getprop no respondió.")
    checks.append(ident)

    # Batería
    r = adb.shell(s, "dumpsys battery")
    bat = Check("battery", "Energía", "Batería")
    if r.ok and "level" in r.stdout:
        b = parse_dumpsys_battery(r.stdout)
        level = int(b.get("level", "0") or 0)
        scale = int(b.get("scale", "100") or 100)
        pct = round(level * 100 / scale) if scale else level
        temp = int(b.get("temperature", "0") or 0) / 10
        health = BATTERY_HEALTH.get(b.get("health", "1"), b.get("health"))
        bat.value = f"{pct}%"
        bat.data = {"Nivel": f"{pct}%", "Salud": health, "Estado": BATTERY_STATUS.get(b.get("status", "1")),
                    "Temperatura": f"{temp:.1f} °C", "Voltaje": f"{b.get('voltage', '?')} mV",
                    "Tecnología": b.get("technology"),
                    "Fuente": ", ".join(k.replace(" powered", "") for k, v in b.items() if k.endswith("powered") and v == "true") or "Ninguna"}
        problems = []
        if b.get("health") not in ("2", None):
            problems.append(f"salud: {health}")
        if temp >= 45:
            problems.append("temperatura elevada")
        if pct <= 15:
            problems.append("nivel bajo")
        bat.status = "error" if b.get("health") in ("4", "6") else ("warning" if problems else "ok")
        bat.detail = ("Atención: " + ", ".join(problems)) if problems else "Parámetros dentro de rango."
    else:
        bat = unavailable("battery", "Energía", "Batería", r.error or "dumpsys battery no disponible")
    checks.append(bat)

    # Almacenamiento
    r = adb.shell(s, "df -k /data")
    st = parse_df(r.stdout) if r.ok else None
    if st:
        pct = st["used"] * 100 / st["total"] if st["total"] else 0
        checks.append(Check("storage", "Almacenamiento", "Almacenamiento /data",
                            "warning" if pct >= 90 else "ok", f"{pct:.0f}% usado",
                            f"{fmt_bytes(st['available'])} libres de {fmt_bytes(st['total'])}",
                            {"Total": fmt_bytes(st["total"]), "Usado": fmt_bytes(st["used"]),
                             "Libre": fmt_bytes(st["available"])}))
    else:
        checks.append(unavailable("storage", "Almacenamiento", "Almacenamiento /data", "df no disponible"))

    # Memoria
    r = adb.shell(s, "cat /proc/meminfo")
    mem = parse_meminfo(r.stdout) if r.ok else {}
    if "MemTotal" in mem:
        checks.append(Check("memory", "Sistema", "Memoria RAM", "info", fmt_bytes(mem["MemTotal"]),
                            f"Disponible: {fmt_bytes(mem.get('MemAvailable'))}",
                            {"Total": fmt_bytes(mem["MemTotal"]), "Disponible": fmt_bytes(mem.get("MemAvailable"))}))

    # Pantalla
    size = adb.shell(s, "wm size")
    dens = adb.shell(s, "wm density")
    power = adb.shell(s, "dumpsys power")
    disp = Check("display", "Pantalla", "Pantalla")
    m_size = re.findall(r"(Physical|Override) size: (\d+x\d+)", size.stdout)
    m_dens = re.findall(r"(Physical|Override) density: (\d+)", dens.stdout)
    wake = re.search(r"mWakefulness=(\w+)", power.stdout)
    disp_state = re.search(r"Display Power: state=(\w+)", power.stdout)
    if m_size:
        disp.status = "info"
        disp.value = dict(m_size).get("Override") or dict(m_size).get("Physical")
        disp.data = {"Resolución física": dict(m_size).get("Physical"), "Resolución activa": disp.value,
                     "Densidad": (dict(m_dens).get("Override") or dict(m_dens).get("Physical")) if m_dens else None,
                     "Estado de energía": wake.group(1) if wake else None,
                     "Estado del display": disp_state.group(1) if disp_state else None}
        disp.detail = ("El sistema reporta el display encendido. Confirme visualmente si hay imagen."
                       if disp_state and disp_state.group(1) == "ON" else
                       "El display está apagado según el sistema (puede estar en reposo).")
    else:
        disp = unavailable("display", "Pantalla", "Pantalla", size.error or "wm size no respondió")
    checks.append(disp)

    # Táctil
    r = adb.shell(s, "dumpsys input", timeout=20)
    if r.ok and r.stdout:
        touch = parse_touch_devices(r.stdout)
        checks.append(Check("touch", "Pantalla", "Panel táctil",
                            "ok" if touch else "warning",
                            "Controlador detectado" if touch else "Sin controlador táctil",
                            ("El controlador táctil está registrado; su presencia no garantiza respuesta física correcta."
                             if touch else "No se registró ningún dispositivo de entrada táctil: posible falla de flex/digitalizador."),
                            {"Dispositivos": ", ".join(touch) or "—"}))
    else:
        checks.append(unavailable("touch", "Pantalla", "Panel táctil", "dumpsys input no disponible"))

    # Cifrado
    if props:
        state, ctype = props.get("ro.crypto.state"), props.get("ro.crypto.type")
        checks.append(Check("encryption", "Seguridad", "Cifrado del almacenamiento",
                            "info" if state else "unavailable",
                            {"encrypted": "Cifrado", "unencrypted": "Sin cifrar"}.get(state or "", state or "Desconocido"),
                            {"file": "Cifrado por archivo (FBE)", "block": "Cifrado de disco completo (FDE)"}.get(ctype or "", ctype),
                            {"Estado": state, "Tipo": ctype}))
        vb = props.get("ro.boot.verifiedbootstate")
        locked = props.get("ro.boot.flash.locked")
        vb_status = {"green": "ok", "yellow": "warning", "orange": "warning", "red": "error"}.get(vb or "", "unavailable")
        checks.append(Check("verified_boot", "Seguridad", "Arranque verificado", vb_status,
                            vb or "No reportado",
                            "Bootloader bloqueado" if locked == "1" else ("Bootloader desbloqueado" if locked == "0" else None),
                            {"Estado AVB": vb, "flash.locked": locked,
                             "vbmeta": props.get("ro.boot.vbmeta.device_state")}))

    # Conectividad y tiempo activo
    up = adb.shell(s, "cat /proc/uptime")
    if up.ok and up.stdout.strip():
        secs = float(up.stdout.split()[0])
        checks.append(Check("uptime", "Sistema", "Tiempo encendido", "info", f"{int(secs // 3600)} h {int(secs % 3600 // 60)} min"))
    wifi = adb.shell(s, "settings get global wifi_on")
    if wifi.ok and wifi.stdout.strip() in ("0", "1", "2"):
        checks.append(Check("wifi", "Conectividad", "Wi-Fi", "info",
                            "Activado" if wifi.stdout.strip() != "0" else "Desactivado"))
    return checks


def run_fastboot(dev: Device) -> list[Check]:
    fb = FastbootConnector()
    checks = [Check("comm", "Comunicación", "Comunicación fastboot",
                    "ok" if dev.comm_state == "bootloader" else "error", dev.mode,
                    f"Conectado mediante {fb.path or 'fastboot no encontrado'}")]
    if dev.comm_state != "bootloader":
        return checks
    v = fb.getvar_all(dev.serial)
    if not v:
        checks.append(unavailable("bootloader_vars", "Bootloader", "Variables de bootloader", "getvar all no respondió"))
        return checks
    unlocked = v.get("unlocked")
    checks.append(Check("bootloader_vars", "Bootloader", "Variables de bootloader", "info",
                        v.get("product"), None,
                        {k: v.get(k) for k in ("product", "version-bootloader", "version-baseband", "secure",
                                                "current-slot", "is-userspace", "battery-voltage", "battery-soc-ok")}))
    checks.append(Check("unlock", "Seguridad", "Estado de desbloqueo",
                        "info" if unlocked else "unavailable",
                        {"yes": "Desbloqueado", "no": "Bloqueado"}.get(unlocked or "", unlocked or "No reportado")))
    return checks
