"""Cuestionario de síntomas observados por el técnico. El esquema se sirve
al frontend para renderizar el formulario, de modo que añadir una pregunta
solo requiere tocar este archivo."""
from __future__ import annotations

from ..errors import RpcError

QUESTIONS: list[dict] = [
    {"id": "powers_on", "label": "¿El equipo da señales de encendido?",
     "help": "Vibración, sonido, LED, calor, logotipo o reconocimiento por el PC.",
     "options": [["yes", "Sí"], ["no", "No"], ["unknown", "No se sabe"]]},
    {"id": "display", "label": "Estado de la imagen",
     "options": [["normal", "Imagen completa"], ["partial", "Parcial (zonas negras, líneas, manchas)"],
                 ["black", "Negra / sin imagen"], ["unknown", "No se sabe"]]},
    {"id": "backlight", "label": "¿Se aprecia retroiluminación o brillo con la pantalla negra?",
     "help": "Mirar con linterna en ángulo: a veces la imagen está pero sin luz.",
     "options": [["yes", "Sí, hay brillo / imagen tenue"], ["no", "No"], ["na", "No aplica"]]},
    {"id": "touch", "label": "Respuesta táctil",
     "options": [["ok", "Responde bien"], ["partial", "Responde en zonas / toques fantasma"],
                 ["none", "No responde"], ["unknown", "No se puede comprobar"]]},
    {"id": "damage", "label": "Daño físico visible",
     "options": [["none", "Ninguno"], ["glass", "Cristal roto"], ["panel", "Panel dañado (fugas de tinta, manchas)"],
                 ["liquid", "Contacto con líquido"], ["bent", "Chasis doblado / impacto fuerte"]]},
    {"id": "usb_debug_before", "label": "¿La depuración USB / 'Confiar en este equipo' estaba autorizada antes del daño?",
     "options": [["yes", "Sí"], ["no", "No"], ["unknown", "No se sabe"]]},
    {"id": "backup", "label": "¿El titular tiene un respaldo previo?",
     "help": "Google One, iCloud, respaldo del fabricante, PC o respaldo de MR Lab.",
     "options": [["yes", "Sí, confirmado"], ["maybe", "Posiblemente (sincronización automática)"],
                 ["no", "No"], ["unknown", "No se sabe"]]},
    {"id": "owner_credential", "label": "¿El titular conoce su PIN / patrón / código?",
     "options": [["yes", "Sí"], ["no", "No"], ["unknown", "No se sabe"]]},
    {"id": "goal", "label": "Objetivo del cliente",
     "options": [["data", "Recuperar datos"], ["repair", "Reparar y seguir usando el equipo"], ["both", "Ambos"]]},
]

_VALID = {q["id"]: {o[0] for o in q["options"]} for q in QUESTIONS}
DEFAULTS = {"powers_on": "unknown", "display": "unknown", "backlight": "na", "touch": "unknown",
            "damage": "none", "usb_debug_before": "unknown", "backup": "unknown",
            "owner_credential": "unknown", "goal": "data"}


def validate(answers: dict) -> dict:
    if not isinstance(answers, dict):
        raise RpcError("invalid_params", "answers debe ser un objeto")
    out = dict(DEFAULTS)
    for k, v in answers.items():
        if k not in _VALID:
            raise RpcError("invalid_params", f"Pregunta desconocida: {k}")
        if v not in _VALID[k]:
            raise RpcError("invalid_params", f"Respuesta inválida para '{k}': {v}")
        out[k] = v
    return out


def schema() -> list[dict]:
    return [{**q, "options": [{"value": v, "label": l} for v, l in q["options"]], "default": DEFAULTS[q["id"]]}
            for q in QUESTIONS]
