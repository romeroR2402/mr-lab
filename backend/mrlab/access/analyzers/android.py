"""Analizador Android: lee por interfaces oficiales (adb/fastboot) los
mecanismos de autenticación presentes y las restricciones del sistema.
Nunca lee ni intenta obtener el valor de un PIN/patrón/contraseña."""
from __future__ import annotations

from ...connectors.android import AdbConnector, FastbootConnector
from ..model import AccessContext, AuthMechanism, Restriction


def collect_properties(device: dict) -> dict:
    """Propiedades de solo lectura útiles para el análisis (si el equipo está autorizado)."""
    if device.get("connector") == "adb" and device.get("commState") == "online" and device.get("authState") == "authorized":
        adb = AdbConnector()
        serial = device["serial"]
        props = adb.getprops(serial)
        # Señales adicionales de bloqueo de pantalla vía dumpsys (presencia, no valor).
        lock = adb.shell(serial, "dumpsys trust", timeout=8)
        props["_trust"] = lock.stdout if lock.ok else ""
        dev_pol = adb.shell(serial, "dumpsys device_policy", timeout=8)
        props["_device_policy"] = dev_pol.stdout if dev_pol.ok else ""
        lockset = adb.shell(serial, "locksettings get-disabled", timeout=6)
        props["_lock_disabled"] = lockset.stdout.strip() if lockset.ok else ""
        return props
    if device.get("connector") == "fastboot":
        return FastbootConnector().getvar_all(device["serial"])
    return {}


def mechanisms(ctx: AccessContext) -> list[AuthMechanism]:
    p = ctx.properties
    out: list[AuthMechanism] = []
    if ctx.device.get("connector") == "fastboot":
        unlocked = p.get("unlocked")
        out.append(AuthMechanism("bootloader", "Bloqueo de bootloader",
                                 "yes" if unlocked == "no" else ("no" if unlocked == "yes" else "unknown"),
                                 kind="bootloader",
                                 detail={"yes": "Bootloader desbloqueado", "no": "Bootloader bloqueado"}.get(unlocked or "", "Estado no reportado"),
                                 source="fastboot getvar"))
        return out

    if not p:
        out.append(AuthMechanism("screen_lock", "Bloqueo de pantalla", "unknown",
                                 detail="Requiere dispositivo en línea y autorizado para analizar.", source="adb"))
        return out

    # Bloqueo de pantalla: 'locksettings get-disabled' == false sugiere que hay credencial configurada.
    disabled = p.get("_lock_disabled", "").lower()
    if disabled in ("true", "false"):
        present = "no" if disabled == "true" else "yes"
        out.append(AuthMechanism("screen_lock", "Bloqueo de pantalla (PIN/patrón/contraseña)", present,
                                 kind="pin", detail="Se detecta la presencia de una credencial, no su valor.", source="adb locksettings"))
    else:
        out.append(AuthMechanism("screen_lock", "Bloqueo de pantalla", "unknown",
                                 detail="No se pudo determinar con las interfaces disponibles.", source="adb"))

    # Cuenta Google / FRP: presencia de cuentas gestionadas tras un reset exige la cuenta previa.
    has_google = "com.google" in (p.get("_trust", "") + p.get("_device_policy", ""))
    out.append(AuthMechanism("frp", "Protección de restablecimiento de fábrica (FRP / cuenta Google)",
                             "yes" if has_google else "unknown", kind="account",
                             detail="Tras un restablecimiento, Android puede exigir la cuenta Google previamente sincronizada.",
                             source="dumpsys"))

    # Administración (MDM / Device Owner / perfil de trabajo).
    dp = p.get("_device_policy", "")
    mdm_present = "Device Owner" in dp or "Profile Owner" in dp or "active-admin" in dp.lower()
    out.append(AuthMechanism("mdm", "Administración de dispositivo (MDM / Device Owner)",
                             "yes" if mdm_present else "no" if dp else "unknown", kind="mdm",
                             detail="Una política de empresa puede impedir restablecer o requerir desenrolamiento por el administrador.",
                             source="dumpsys device_policy"))

    # Biometría (capacidad de hardware; no credencial).
    fp = p.get("sys.fingerprint") or p.get("ro.hardware.fingerprint")
    if fp:
        out.append(AuthMechanism("biometric", "Biometría (huella/rostro)", "yes", kind="biometric",
                                 detail="La biometría respalda la credencial, no la sustituye para recuperación.", source="getprop"))
    return out


def restrictions(ctx: AccessContext) -> list[Restriction]:
    p = ctx.properties
    out: list[Restriction] = []
    if ctx.device.get("connector") == "fastboot":
        secure = p.get("secure")
        out.append(Restriction("verified_boot", "Arranque verificado / secure boot",
                               "active" if secure == "yes" else "inactive" if secure == "no" else "unknown",
                               severity="high",
                               detail="Con arranque verificado activo, modificar particiones del sistema invalida el arranque."))
        return out
    if not p:
        return [Restriction("analysis", "Análisis de restricciones", "unknown", "info",
                            "Requiere dispositivo autorizado.")]

    crypto = p.get("ro.crypto.state")
    ctype = p.get("ro.crypto.type")
    out.append(Restriction("encryption", "Cifrado del almacenamiento de usuario",
                           "active" if crypto == "encrypted" else "inactive" if crypto == "unencrypted" else "unknown",
                           severity="blocker" if crypto == "encrypted" else "info",
                           detail=("Datos cifrados ligados a la credencial del usuario (" +
                                   {"file": "FBE por archivo", "block": "FDE disco completo"}.get(ctype or "", "tipo desconocido") +
                                   "). Sin la credencial del titular, los datos de usuario no son legibles por diseño.")
                                  if crypto == "encrypted" else "Sin cifrado reportado."))

    vb = p.get("ro.boot.verifiedbootstate")
    locked = p.get("ro.boot.flash.locked")
    out.append(Restriction("verified_boot", "Arranque verificado (AVB)",
                           "active" if vb == "green" else "partial" if vb in ("yellow", "orange") else "inactive" if vb == "red" else "unknown",
                           severity="high",
                           detail=f"Estado AVB: {vb or 'no reportado'}; bootloader {'bloqueado' if locked == '1' else 'desbloqueado' if locked == '0' else 'desconocido'}."))

    patch = p.get("ro.build.version.security_patch")
    out.append(Restriction("security_patch", "Nivel de parche de seguridad", "active" if patch else "unknown",
                           severity="info", detail=f"Parche: {patch or 'no reportado'}. Relevante para compatibilidad de procedimientos oficiales."))
    return out
