"""Diagnóstico Apple mediante lockdownd (ideviceinfo) e idevicediagnostics.
Requiere que el dispositivo confíe en el equipo."""
from __future__ import annotations

from ..connectors.apple import AppleConnector, parse_kv
from ..connectors.base import Device
from .android import fmt_bytes
from .model import Check, unavailable


def run_apple(dev: Device) -> list[Check]:
    ac = AppleConnector()
    checks = [Check("comm", "Comunicación", "Comunicación usbmux/lockdownd",
                    "ok" if dev.comm_state == "online" else "error", dev.connection,
                    f"ideviceinfo: {ac.ideviceinfo or 'no encontrado'}")]
    auth = Check("auth", "Comunicación", "Confianza (pairing)", value=dev.auth_state,
                 status="ok" if dev.auth_state == "authorized" else "error")
    if dev.auth_state != "authorized":
        auth.detail = (dev.notes[0] if dev.notes else
                       "El titular debe desbloquear el dispositivo y aceptar 'Confiar en este equipo'.")
    checks.append(auth)
    if not ac.available or dev.auth_state != "authorized":
        for cid, cat, label in (("identity", "Sistema", "Identidad"), ("battery", "Energía", "Batería"),
                                ("storage", "Almacenamiento", "Almacenamiento")):
            checks.append(unavailable(cid, cat, label, "Requiere libimobiledevice y dispositivo emparejado."))
        return checks

    net = dev.connection == "network"
    kv = parse_kv(ac.info(dev.serial, network=net).stdout)
    checks.append(Check("identity", "Sistema", "Identidad", "info", dev.model or kv.get("ProductType"), None, {
        "Nombre": kv.get("DeviceName"), "Modelo": kv.get("ProductType"), "Modelo de hardware": kv.get("HardwareModel"),
        "Versión": kv.get("ProductVersion"), "Compilación": kv.get("BuildVersion"),
        "Arquitectura": kv.get("CPUArchitecture"), "Región": kv.get("RegionInfo"),
    }))
    act = kv.get("ActivationState")
    checks.append(Check("activation", "Seguridad", "Estado de activación",
                        "ok" if act == "Activated" else ("warning" if act else "unavailable"), act or "No reportado",
                        None if act == "Activated" else "Si el dispositivo no está activado, el titular debe completar la activación con su Apple ID."))

    bat = parse_kv(ac.info(dev.serial, "com.apple.mobile.battery", network=net).stdout)
    reg = ac.battery_registry(dev.serial)
    if bat.get("BatteryCurrentCapacity"):
        data = {"Nivel": f"{bat['BatteryCurrentCapacity']}%", "Cargando": bat.get("BatteryIsCharging"),
                "Cargador externo": bat.get("ExternalConnected")}
        status, detail = "ok", None
        if reg.get("DesignCapacity") and (reg.get("AppleRawMaxCapacity") or reg.get("NominalChargeCapacity")):
            full = reg.get("AppleRawMaxCapacity") or reg.get("NominalChargeCapacity")
            health = round(full * 100 / reg["DesignCapacity"])
            data.update({"Capacidad de diseño": f"{reg['DesignCapacity']} mAh", "Capacidad máxima": f"{full} mAh",
                         "Salud estimada": f"{health}%", "Ciclos": reg.get("CycleCount")})
            if health < 80:
                status, detail = "warning", "Salud de batería inferior a 80%."
        if reg.get("Temperature"):
            data["Temperatura"] = f"{reg['Temperature'] / 100:.1f} °C"
        checks.append(Check("battery", "Energía", "Batería", status, data["Nivel"], detail, data))
    else:
        checks.append(unavailable("battery", "Energía", "Batería", "El dominio de batería no respondió."))

    disk = parse_kv(ac.info(dev.serial, "com.apple.disk_usage", network=net).stdout)
    try:
        total = int(disk.get("TotalDiskCapacity") or disk.get("TotalDataCapacity"))
        free = int(disk.get("TotalDataAvailable"))
        used_pct = (total - free) * 100 / total
        checks.append(Check("storage", "Almacenamiento", "Almacenamiento", "warning" if used_pct >= 90 else "ok",
                            f"{used_pct:.0f}% usado", f"{fmt_bytes(free)} libres de {fmt_bytes(total)}",
                            {"Total": fmt_bytes(total), "Libre": fmt_bytes(free)}))
    except (TypeError, ValueError, ZeroDivisionError):
        checks.append(unavailable("storage", "Almacenamiento", "Almacenamiento", "com.apple.disk_usage no disponible"))

    bk = parse_kv(ac.info(dev.serial, "com.apple.mobile.backup", network=net).stdout)
    if "WillEncrypt" in bk:
        enc = bk["WillEncrypt"].lower() == "true"
        checks.append(Check("backup_encryption", "Respaldo", "Cifrado de respaldos locales", "info",
                            "Activado" if enc else "Desactivado",
                            "Los respaldos requerirán la contraseña de respaldo que define el titular." if enc else
                            "Los respaldos locales no están cifrados; algunos datos (salud, llavero) no se incluirán."))
    return checks
