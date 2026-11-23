"""Motor de pruebas de compatibilidad. Evalúa precondiciones de un procedimiento
de recuperación sobre el estado del dispositivo SIN ejecutarlo. Cada
procedimiento es una definición declarativa extensible."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .model import AccessContext, CompatibilityCheck
from .policy import scan_text

Predicate = Callable[[AccessContext], "tuple[str, str | None]"]


@dataclass
class Procedure:
    id: str
    title: str
    platforms: list[str]
    checks: list[tuple[str, str, Predicate]] = field(default_factory=list)  # (id, etiqueta, predicado)


_REGISTRY: dict[str, Procedure] = {}


def register(proc: Procedure) -> None:
    scan_text(proc.id, proc.title, *[label for _, label, _ in proc.checks])
    _REGISTRY[proc.id] = proc


def procedures() -> list[Procedure]:
    return list(_REGISTRY.values())


def _comm(ctx: AccessContext):
    s = ctx.device.get("commState")
    return ("pass", "Comunicación USB activa") if s in ("online", "recovery", "sideload", "bootloader", "unauthorized") \
        else ("fail", f"Comunicación: {s}")


def _authorized(ctx: AccessContext):
    a = ctx.device.get("authState")
    if a == "authorized":
        return "pass", "Equipo autorizado por el titular"
    if a in ("not_applicable",):
        return "not_applicable", "No aplica en este modo"
    return "fail", f"Autorización: {a}"


def _platform(name: str):
    def f(ctx: AccessContext):
        return ("pass", None) if ctx.platform == name else ("not_applicable", f"Solo {name}")
    return f


def _diag(check_id: str, ok_states=("ok", "info")):
    def f(ctx: AccessContext):
        d = ctx.diagnostic
        if not d:
            return "unknown", "Sin diagnóstico previo"
        c = next((c for c in d.get("checks", []) if c.get("id") == check_id), None)
        if not c or c.get("status") == "unavailable":
            return "unknown", "No disponible en el diagnóstico"
        return ("pass", c.get("value")) if c.get("status") in ok_states else ("fail", c.get("value"))
    return f


def _bootloader_reachable(ctx: AccessContext):
    mode = ctx.device.get("mode")
    if mode in ("bootloader", "fastbootd", "recovery", "sideload"):
        return "pass", f"Modo {mode}"
    return "unknown", "El dispositivo no está en modo de servicio"


# --- Procedimientos de base (todos oficiales / no destructivos para la autenticación) ---
register(Procedure("otg_input", "Entrada por OTG para que el titular introduzca su credencial", ["android"], [
    ("platform", "Plataforma Android", _platform("android")),
    ("comm", "Comunicación USB", _comm),
    ("display", "Display funcional para ver la entrada", _diag("display")),
]))
register(Procedure("screen_mirror", "Duplicación de pantalla con depuración previamente autorizada", ["android"], [
    ("platform", "Plataforma Android", _platform("android")),
    ("comm", "Comunicación USB", _comm),
    ("auth", "Depuración USB ya autorizada", _authorized),
]))
register(Procedure("official_ota_sideload", "Actualización OTA oficial por sideload", ["android"], [
    ("platform", "Plataforma Android", _platform("android")),
    ("mode", "Acceso a modo recovery/sideload", _bootloader_reachable),
]))
register(Procedure("apple_official_restore", "Restauración oficial iOS (modo recuperación)", ["apple"], [
    ("platform", "Plataforma Apple", _platform("apple")),
    ("comm", "Comunicación USB", _comm),
]))
register(Procedure("apple_backup", "Respaldo local oficial (idevicebackup2)", ["apple"], [
    ("platform", "Plataforma Apple", _platform("apple")),
    ("auth", "Dispositivo emparejado (Confiar)", _authorized),
]))


def evaluate(ctx: AccessContext, procedure_id: str | None = None) -> list[dict]:
    """Evalúa uno o todos los procedimientos aplicables a la plataforma."""
    out = []
    for proc in procedures():
        if procedure_id and proc.id != procedure_id:
            continue
        if ctx.platform not in proc.platforms:
            continue
        checks = []
        for cid, label, pred in proc.checks:
            try:
                result, detail = pred(ctx)
            except Exception as e:  # una precondición defectuosa no rompe el análisis
                result, detail = "unknown", f"Error al evaluar: {e}"
            checks.append(CompatibilityCheck(cid, label, result, detail))
        results = {c.result for c in checks}
        verdict = "compatible" if results <= {"pass", "not_applicable"} else \
                  "incompatible" if "fail" in results else "undetermined"
        out.append({"procedureId": proc.id, "title": proc.title, "verdict": verdict,
                    "checks": [c.to_api() for c in checks]})
    return out
