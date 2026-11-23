"""Barrera de cumplimiento del módulo de acceso.

Define qué está permitido (análisis, evaluación, documentación de métodos
oficiales) y qué está prohibido de forma terminante. Se aplica al registrar
plugins y antes de ejecutar cualquier procedimiento, de modo que la prohibición
no sea solo una norma escrita sino una restricción efectiva del código.
"""
from __future__ import annotations

import re

from ..errors import RpcError

# Capacidades que un plugin o procedimiento puede declarar. Solo análisis.
ALLOWED_CAPABILITIES = {
    "inspect_auth",         # leer el tipo de autenticación configurado (no su valor)
    "inspect_restrictions", # leer restricciones del SO / hardware
    "inspect_encryption",   # leer estado de cifrado (no claves)
    "evaluate_recovery",    # evaluar si una vía oficial aplica
    "evaluate_compat",      # evaluar precondiciones de un procedimiento
    "document",             # producir documentación/hallazgos
    "read_diagnostics",     # reutilizar un diagnóstico de solo lectura ya hecho
}

# Capacidades terminantemente prohibidas. Un plugin que declare cualquiera de
# estas (o cuyo texto las insinúe) es rechazado al registrarse.
PROHIBITED_CAPABILITIES = {
    "bypass_auth", "bypass", "unlock_bypass", "frp_bypass", "icloud_bypass",
    "activation_bypass", "mdm_bypass", "crack_password", "bruteforce",
    "decrypt", "defeat_encryption", "exploit", "jailbreak", "root_exploit",
    "covert_extraction", "silent_extraction", "keylogger", "capture_credentials",
    "disable_security", "evade_detection", "spoof",
}

_PROHIBITED_RE = re.compile(
    r"(by-?pass|frp\s*bypass|icloud\s*bypass|crack|brute\s*force|bruteforce|"
    r"defeat\s+(the\s+)?(lock|encryption|passcode)|unlock\s+without|remove\s+(the\s+)?(lock|frp|passcode)\s+without|"
    r"descifrar\s+sin|evadir|evasi[oó]n|saltarse|romper\s+(la\s+|el\s+|los\s+)?(contrase|cifrado|bloqueo)|"
    r"extracci[oó]n\s+(oculta|encubierta|sin\s+autoriz)|keylogger|exploit|0day|zero-?day)",
    re.IGNORECASE,
)


class PolicyViolation(RpcError):
    def __init__(self, message: str, detail: str | None = None):
        super().__init__("policy_violation", message, {"detail": detail} if detail else {})


def validate_capabilities(capabilities: list[str]) -> list[str]:
    caps = []
    for c in capabilities:
        c = str(c).strip().lower()
        if c in PROHIBITED_CAPABILITIES or c not in ALLOWED_CAPABILITIES:
            raise PolicyViolation(
                "El plugin declara una capacidad no permitida.",
                f"Capacidad rechazada: '{c}'. MR Lab solo admite capacidades de análisis "
                f"({', '.join(sorted(ALLOWED_CAPABILITIES))}).",
            )
        caps.append(c)
    return caps


def scan_text(*parts: str) -> None:
    """Rechaza metadatos/manifiestos cuyo texto describa una función prohibida."""
    blob = " ".join(p for p in parts if p)
    m = _PROHIBITED_RE.search(blob)
    if m:
        raise PolicyViolation(
            "El contenido describe una operación prohibida (evasión, descifrado o extracción no autorizada).",
            f"Coincidencia: '{m.group(0)}'.",
        )


# Nota legal/ética que acompaña a cada análisis.
DISCLAIMER = (
    "Este análisis es informativo. MR Lab no evade autenticación ni cifrado. "
    "Las vías mostradas son procedimientos oficiales que requieren que el titular "
    "acredite su identidad ante el fabricante. Operar sin autorización del titular "
    "puede ser ilícito."
)
