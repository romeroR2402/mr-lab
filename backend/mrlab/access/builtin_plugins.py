"""Plugins de análisis integrados. Sirven también como referencia para
escribir plugins externos (misma interfaz: MANIFEST + analyze(ctx))."""
from __future__ import annotations

from datetime import date


def _check(ctx: dict, cid: str) -> dict | None:
    d = ctx.get("diagnostic") or {}
    return next((c for c in d.get("checks", []) if c.get("id") == cid), None)


# ---------------------------------------------------------------------------
DAMAGE_MANIFEST = {
    "id": "damaged-interaction",
    "name": "Escenarios con interacción comprometida",
    "version": "1.0.0",
    "author": "MR Lab",
    "description": "Clasifica el escenario cuando pantalla o táctil están dañados y propone apoyos de entrada/visualización para que el titular use su propia credencial.",
    "capabilities": ["read_diagnostics", "evaluate_recovery", "document"],
    "platforms": ["android", "apple"],
}


def damage_analyze(ctx: dict) -> list[dict]:
    dev = ctx["device"]
    display, touch = _check(ctx, "display"), _check(ctx, "touch")
    comm = dev.get("commState")
    auth = dev.get("authState")
    usb = comm in ("online", "recovery", "sideload", "bootloader", "unauthorized", "no_permissions", "connecting")
    display_on = bool(display and display.get("status") in ("ok", "info") and (display.get("data") or {}).get("Estado del display") == "ON")
    touch_ok = bool(touch and touch.get("status") == "ok")

    if not usb:
        scenario, sev = "Sin comunicación USB", "high"
        detail = ("El equipo no responde por USB. Revisar cable/puerto, carga de batería y modo de arranque. "
                  "Si no enciende, el caso pasa a diagnóstico de hardware.")
    elif auth == "not_applicable":
        scenario, sev = "Dispositivo en modo de servicio", "info"
        detail = ("El equipo está en bootloader/recovery: no hay interacción de usuario que evaluar. "
                  "Solo proceden operaciones oficiales del fabricante en ese modo.")
    elif auth != "authorized":
        scenario, sev = "Comunicación USB sin autorización", "high"
        detail = ("Hay comunicación pero el dispositivo no ha autorizado este equipo. La autorización la debe aceptar "
                  "el titular en pantalla; si la pantalla no funciona, usar OTG/salida de video para que pueda hacerlo.")
    elif display is None and touch is None:
        scenario, sev = "Sin diagnóstico de pantalla", "low"
        detail = "Ejecute un diagnóstico para clasificar el estado de pantalla y táctil."
    elif display_on and touch_ok:
        scenario, sev = "Pantalla visible y táctil funcional", "info"
        detail = "El titular puede desbloquear normalmente. No se requiere asistencia de entrada."
    elif display_on and not touch_ok:
        scenario, sev = "Pantalla visible, táctil defectuoso", "medium"
        detail = ("Conectar ratón/teclado por OTG (Android) para que el titular introduzca su credencial, "
                  "o reemplazar el digitalizador.")
    else:
        scenario, sev = "Pantalla negra o sin imagen", "medium"
        detail = ("El sistema responde por USB. Usar salida de video/duplicación (si la depuración ya estaba autorizada) "
                  "o reemplazo temporal de pantalla para que el titular desbloquee el equipo.")
    return [{"title": scenario, "severity": sev, "detail": detail,
             "data": {"Comunicación": comm, "Autorización": auth,
                      "Display": (display or {}).get("value"), "Táctil": (touch or {}).get("value")}}]


# ---------------------------------------------------------------------------
CRYPTO_MANIFEST = {
    "id": "data-protection-limits",
    "name": "Límites de protección de datos",
    "version": "1.0.0",
    "author": "MR Lab",
    "description": "Resume las limitaciones de cifrado y protección de datos para fijar expectativas realistas del caso.",
    "capabilities": ["inspect_encryption", "inspect_restrictions", "document"],
    "platforms": ["android", "apple"],
}


def crypto_analyze(ctx: dict) -> list[dict]:
    restr = {r["id"]: r for r in ctx.get("restrictions", [])}
    mech = {m["id"]: m for m in ctx.get("mechanisms", [])}
    out = []
    enc = restr.get("encryption") or restr.get("data_encryption")
    lock = mech.get("screen_lock") or mech.get("passcode")
    if enc and enc["status"] == "active" and lock and lock["present"] == "yes":
        out.append({"title": "Datos de usuario cifrados y protegidos por credencial", "severity": "high",
                    "detail": "Los datos solo son accesibles con la credencial del titular. Si el titular no la recuerda, "
                              "las únicas vías son respaldos previos o restauración (con pérdida de datos)."})
    elif enc and enc["status"] == "active":
        out.append({"title": "Almacenamiento cifrado", "severity": "medium",
                    "detail": "Cifrado activo. La recuperación de datos depende de que el titular desbloquee el equipo."})
    act = mech.get("activation_lock") or mech.get("frp")
    if act and act["present"] in ("yes", "unknown"):
        out.append({"title": "Protección tras restablecimiento", "severity": "medium",
                    "detail": "Tras restaurar, el equipo pedirá la cuenta del titular (FRP/Bloqueo de activación). "
                              "Verifique que el titular puede recuperar su cuenta ANTES de restaurar."})
    return out


# ---------------------------------------------------------------------------
FW_MANIFEST = {
    "id": "firmware-context",
    "name": "Contexto de firmware",
    "version": "1.0.0",
    "author": "MR Lab",
    "description": "Evalúa versión del sistema y antigüedad del parche de seguridad para la compatibilidad de procedimientos oficiales.",
    "capabilities": ["inspect_restrictions", "evaluate_compat", "document"],
    "platforms": ["android", "apple"],
}


def fw_analyze(ctx: dict) -> list[dict]:
    p = ctx.get("properties", {})
    dev = ctx["device"]
    out = []
    patch = p.get("ro.build.version.security_patch")
    if patch:
        try:
            y, m, d = (int(x) for x in patch.split("-"))
            months = (date.today().year - y) * 12 + date.today().month - m
            sev = "medium" if months > 12 else "info"
            out.append({"title": f"Parche de seguridad de hace {months} meses", "severity": sev,
                        "detail": "Actualizar por OTA oficial tras recuperar el acceso." if months > 12 else "Parche reciente.",
                        "data": {"Parche": patch}})
        except ValueError:
            pass
    ver = dev.get("osVersion")
    if ver:
        out.append({"title": f"{dev.get('osName') or 'Sistema'} {ver}", "severity": "info",
                    "detail": "Las vías oficiales listadas son compatibles con versiones vigentes del fabricante.",
                    "data": {"Versión": ver, "Compilación": p.get("ro.build.display.id") or p.get("BuildVersion")}})
    return out


BUILTINS = [
    (DAMAGE_MANIFEST, damage_analyze),
    (CRYPTO_MANIFEST, crypto_analyze),
    (FW_MANIFEST, fw_analyze),
]
