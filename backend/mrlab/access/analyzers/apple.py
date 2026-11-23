"""Analizador Apple: lee por lockdownd (ideviceinfo) la presencia de código,
estado de activación (Activation Lock), supervisión/MDM y cifrado de respaldo.
No lee ni intenta obtener el código del dispositivo."""
from __future__ import annotations

from ...connectors.apple import AppleConnector, parse_kv
from ..model import AccessContext, AuthMechanism, Restriction


def collect_properties(device: dict) -> dict:
    if device.get("platform") != "apple" or device.get("authState") != "authorized":
        return {}
    ac = AppleConnector()
    if not ac.available:
        return {}
    net = device.get("connection") == "network"
    props = parse_kv(ac.info(device["serial"], network=net).stdout)
    for domain in ("com.apple.mobile.backup", "com.apple.mobile.chaperone"):
        props.update({f"{domain}:{k}": v for k, v in parse_kv(ac.info(device["serial"], domain, network=net).stdout).items()})
    return props


def mechanisms(ctx: AccessContext) -> list[AuthMechanism]:
    p = ctx.properties
    out: list[AuthMechanism] = []
    if not p:
        return [AuthMechanism("passcode", "Código del dispositivo", "unknown",
                              detail="Requiere dispositivo emparejado (Confiar en este equipo).", source="lockdownd")]

    pwd = p.get("PasswordProtected")
    out.append(AuthMechanism("passcode", "Código del dispositivo",
                             "yes" if pwd == "true" else "no" if pwd == "false" else "unknown", kind="password",
                             detail="Se detecta si hay código configurado, nunca su valor. El código cifra el llavero y los datos.",
                             source="lockdownd"))

    act = p.get("ActivationState")
    out.append(AuthMechanism("activation_lock", "Bloqueo de activación (Find My / Apple ID)",
                             "yes" if act and act != "Unactivated" else "unknown", kind="activation",
                             detail="Si 'Buscar' está activo, tras borrar el dispositivo Apple exige el Apple ID del titular para reactivarlo.",
                             source="lockdownd ActivationState"))

    supervised = p.get("com.apple.mobile.chaperone:IsSupervised") or p.get("IsSupervised")
    if supervised is not None:
        out.append(AuthMechanism("mdm", "Supervisión / MDM", "yes" if supervised == "true" else "no", kind="mdm",
                                 detail="Un dispositivo supervisado puede estar inscrito en MDM; el desenrolamiento lo hace el administrador.",
                                 source="lockdownd"))
    return out


def restrictions(ctx: AccessContext) -> list[Restriction]:
    p = ctx.properties
    out: list[Restriction] = []
    if not p:
        return [Restriction("analysis", "Análisis de restricciones", "unknown", "info",
                            "Requiere dispositivo emparejado.")]

    out.append(Restriction("data_encryption", "Cifrado de datos (Secure Enclave)", "active", "blocker",
                           detail="En iOS los datos de usuario están cifrados por hardware y ligados al código. "
                                  "Sin el código del titular, los datos no son recuperables por diseño."))

    will_enc = p.get("com.apple.mobile.backup:WillEncrypt")
    if will_enc is not None:
        out.append(Restriction("backup_encryption", "Cifrado de respaldos locales",
                               "active" if will_enc == "true" else "inactive", "medium",
                               detail="Los respaldos cifrados requieren la contraseña de respaldo del titular; incluyen más datos (llavero, salud)."))

    act = p.get("ActivationState")
    out.append(Restriction("activation_lock", "Bloqueo de activación", "active" if act and act != "Unactivated" else "unknown",
                           "blocker", detail="Impide reutilizar el dispositivo tras un borrado sin el Apple ID del titular."))
    return out
