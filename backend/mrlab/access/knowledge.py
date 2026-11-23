"""Catálogo de vías de recuperación OFICIALES. Cada entrada es un procedimiento
del fabricante o un apoyo técnico legítimo; ninguna evade autenticación.
El motor selecciona y evalúa cuáles aplican según el análisis del dispositivo."""
from __future__ import annotations

from .model import AccessContext, RecoveryOption


def _android_options(ctx: AccessContext, mech: dict, restr: dict) -> list[RecoveryOption]:
    opts: list[RecoveryOption] = []
    screen_locked = mech.get("screen_lock") == "yes"
    frp = mech.get("frp") in ("yes", "unknown")
    diag = ctx.diagnostic or {}
    display_ok = any(c.get("id") == "display" and c.get("status") in ("ok", "info") for c in diag.get("checks", []))
    touch_ok = any(c.get("id") == "touch" and c.get("status") == "ok" for c in diag.get("checks", []))

    opts.append(RecoveryOption(
        "google_account_recovery", "Recuperación de cuenta Google del titular", "manufacturer_account",
        applicability="applicable" if frp else "conditional", data_loss="none",
        requirements=["El titular conoce o puede recuperar su cuenta Google", "Acceso a correo/teléfono de recuperación"],
        steps=["Guiar al titular a g.co/recover desde otro equipo",
               "Recuperar la contraseña de la cuenta Google vinculada",
               "Usar esa cuenta para pasar la verificación tras un restablecimiento"],
        warnings=["No sustituye al código de pantalla", "Debe ser la cuenta sincronizada antes del bloqueo"],
        reason="Vía oficial cuando el equipo tiene FRP. La ejecuta el titular con sus credenciales.",
        official_url="https://g.co/recover"))

    opts.append(RecoveryOption(
        "find_my_device", "Borrado remoto con Find My Device (si se busca reutilizar)", "manufacturer_account",
        applicability="conditional", data_loss="full_wipe",
        requirements=["Sesión de la cuenta Google del titular", "Dispositivo con conexión"],
        steps=["El titular accede a android.com/find", "Selecciona el equipo y 'Borrar dispositivo'"],
        warnings=["Borra todos los datos", "Tras el borrado puede pedir la cuenta por FRP"],
        reason="Útil solo si el objetivo es reutilizar el equipo, no recuperar datos.",
        official_url="https://www.google.com/android/find"))

    if mech.get("mdm") == "yes":
        opts.append(RecoveryOption(
            "mdm_unenroll", "Desenrolamiento por el administrador (MDM)", "vendor_support",
            applicability="applicable", data_loss="possible",
            requirements=["Contactar al administrador de la organización propietaria"],
            steps=["Identificar al administrador/EMM", "Solicitar liberación o restablecimiento desde la consola"],
            warnings=["Solo el administrador puede liberar el equipo"],
            reason="El equipo está gestionado por una organización."))

    # Respaldo previo del propio MR Lab o del fabricante.
    opts.append(RecoveryOption(
        "existing_backup", "Restaurar desde un respaldo previo autorizado", "backup",
        applicability="conditional", data_loss="none",
        requirements=["Existe un respaldo previo (MR Lab, Google One u OEM)"],
        steps=["Verificar respaldos disponibles", "Restaurar tras recuperar el acceso oficial"],
        reason="Depende de que exista un respaldo anterior."))

    opts.append(RecoveryOption(
        "oem_support", "Soporte oficial del fabricante / prueba de propiedad", "vendor_support",
        applicability="applicable", data_loss="unknown",
        requirements=["Factura o prueba de propiedad", "IMEI/serie del equipo"],
        steps=["Abrir caso con el soporte del fabricante", "Acreditar propiedad", "Seguir su procedimiento"],
        reason="Vía válida cuando el titular puede acreditar propiedad ante el OEM."))

    if screen_locked and (not display_ok or not touch_ok):
        opts.append(RecoveryOption(
            "hardware_assist_input", "Asistencia de entrada por pantalla dañada", "hardware_assist",
            applicability="conditional", data_loss="none",
            requirements=["Comunicación USB disponible", "El titular conoce su credencial",
                          "Depuración USB previamente autorizada o adaptador OTG"],
            steps=["Conectar ratón/teclado por OTG para introducir la credencial del titular",
                   "O usar salida de video/duplicación para ver la pantalla",
                   "El titular introduce su propia credencial"],
            warnings=["No revela ni evade la credencial: la introduce el titular"],
            reason="La pantalla/táctil está dañada pero el titular conoce su clave.",
            official_url=None))
    return opts


def _apple_options(ctx: AccessContext, mech: dict, restr: dict) -> list[RecoveryOption]:
    opts: list[RecoveryOption] = []
    activation = mech.get("activation_lock") == "yes"

    opts.append(RecoveryOption(
        "apple_id_recovery", "Recuperación del Apple ID del titular", "manufacturer_account",
        applicability="applicable", data_loss="none",
        requirements=["El titular puede recuperar su Apple ID", "Acceso a correo/teléfono de confianza"],
        steps=["Guiar al titular a iforgot.apple.com", "Recuperar el Apple ID/contraseña",
               "Usarlo para el bloqueo de activación tras una restauración"],
        warnings=["No sustituye el código del dispositivo"],
        reason="Vía oficial para el bloqueo de activación. La ejecuta el titular.",
        official_url="https://iforgot.apple.com"))

    opts.append(RecoveryOption(
        "recovery_mode_restore", "Restauración oficial (modo recuperación / DFU con Apple Devices/Finder)", "official_restore",
        applicability="conditional" if activation else "applicable", data_loss="full_wipe",
        requirements=["Equipo con Apple Devices o Finder", "Si 'Buscar' está activo, Apple ID del titular tras restaurar"],
        steps=["Poner el dispositivo en modo recuperación", "Restaurar iOS con la herramienta oficial de Apple",
               "Completar la activación con el Apple ID del titular"],
        warnings=["Borra todos los datos", "El bloqueo de activación persiste tras restaurar"],
        reason="Reinstala iOS por vía oficial; no recupera datos ni evade el Apple ID.",
        official_url="https://support.apple.com/es-es/HT201263"))

    opts.append(RecoveryOption(
        "icloud_backup", "Restaurar desde respaldo de iCloud/iTunes del titular", "backup",
        applicability="conditional", data_loss="none",
        requirements=["Existe un respaldo del titular", "Credenciales del titular"],
        steps=["Tras restaurar, elegir 'Restaurar desde copia'", "El titular autentica con su Apple ID"],
        reason="Depende de que exista un respaldo del titular."))

    if mech.get("mdm") == "yes":
        opts.append(RecoveryOption(
            "apple_mdm_unenroll", "Liberación por el administrador (MDM/ABM)", "vendor_support",
            applicability="applicable", data_loss="possible",
            requirements=["Organización propietaria y su administrador MDM"],
            steps=["Identificar al administrador", "Solicitar liberación desde Apple Business Manager/MDM"],
            reason="El dispositivo está supervisado/gestionado."))

    opts.append(RecoveryOption(
        "apple_support_proof", "Soporte de Apple con prueba de compra", "vendor_support",
        applicability="conditional", data_loss="unknown",
        requirements=["Prueba de compra original a nombre del titular"],
        steps=["Abrir caso con Apple", "Presentar prueba de compra para el bloqueo de activación"],
        warnings=["Apple exige comprobante válido; no siempre procede"],
        reason="Única vía oficial para activation lock sin el Apple ID, a criterio de Apple.",
        official_url="https://support.apple.com/es-es/HT201441"))
    return opts


def recovery_options(ctx: AccessContext, mechanisms: list, restrictions: list) -> list[RecoveryOption]:
    mech = {m.id: m.present for m in mechanisms}
    restr = {r.id: r.status for r in restrictions}
    if ctx.platform == "apple":
        return _apple_options(ctx, mech, restr)
    return _android_options(ctx, mech, restr)
