"""Estructuras de datos del análisis de acceso."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class AuthMechanism:
    """Mecanismo de autenticación detectado (se lee su presencia/tipo, nunca su valor)."""
    id: str
    label: str
    present: str              # yes | no | unknown
    kind: str | None = None   # pin | password | pattern | biometric | account | activation | mdm | bootloader
    detail: str | None = None
    source: str | None = None

    def to_api(self) -> dict:
        return {"id": self.id, "label": self.label, "present": self.present, "kind": self.kind,
                "detail": self.detail, "source": self.source}


@dataclass
class Restriction:
    """Restricción del SO/hardware que condiciona la recuperación."""
    id: str
    label: str
    status: str               # active | inactive | partial | unknown
    severity: str = "info"    # info | medium | high | blocker
    detail: str | None = None

    def to_api(self) -> dict:
        return {"id": self.id, "label": self.label, "status": self.status,
                "severity": self.severity, "detail": self.detail}


@dataclass
class RecoveryOption:
    """Vía de recuperación OFICIAL evaluada para este dispositivo."""
    id: str
    title: str
    channel: str              # manufacturer_account | device_settings | official_restore | backup | vendor_support | hardware_assist
    applicability: str        # applicable | conditional | not_applicable | blocked | unknown
    data_loss: str            # none | possible | full_wipe | unknown
    requirements: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reason: str | None = None  # por qué aplica / no aplica / está bloqueada
    official_url: str | None = None

    def to_api(self) -> dict:
        return {"id": self.id, "title": self.title, "channel": self.channel,
                "applicability": self.applicability, "dataLoss": self.data_loss,
                "requirements": self.requirements, "steps": self.steps,
                "warnings": self.warnings, "reason": self.reason, "officialUrl": self.official_url}


@dataclass
class CompatibilityCheck:
    """Resultado de evaluar una precondición de un procedimiento (sin ejecutarlo)."""
    id: str
    label: str
    result: str               # pass | fail | unknown | not_applicable
    detail: str | None = None

    def to_api(self) -> dict:
        return {"id": self.id, "label": self.label, "result": self.result, "detail": self.detail}


@dataclass
class PluginFinding:
    plugin_id: str
    plugin_name: str
    title: str
    severity: str = "info"
    detail: str | None = None
    data: dict = field(default_factory=dict)

    def to_api(self) -> dict:
        return {"pluginId": self.plugin_id, "pluginName": self.plugin_name, "title": self.title,
                "severity": self.severity, "detail": self.detail, "data": self.data}


@dataclass
class AccessContext:
    """Contexto de SOLO LECTURA entregado a analizadores y plugins.
    No expone ejecución de comandos arbitrarios ni valores de credenciales."""
    platform: str
    device: dict                      # Device.to_api()
    properties: dict = field(default_factory=dict)   # getprop / lockdown (filtrado)
    diagnostic: dict | None = None    # último reporte de diagnóstico (solo lectura)

    def prop(self, key: str, default=None):
        return self.properties.get(key, default)


@dataclass
class AccessAnalysis:
    device_key: str
    device_label: str
    platform: str
    timestamp: str
    summary: str                      # evaluación general en texto
    recoverability: str               # likely | conditional | unlikely | unknown
    mechanisms: list[AuthMechanism] = field(default_factory=list)
    restrictions: list[Restriction] = field(default_factory=list)
    options: list[RecoveryOption] = field(default_factory=list)
    compatibility: list[CompatibilityCheck] = field(default_factory=list)
    findings: list[PluginFinding] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    disclaimer: str = ""
    case_id: int | None = None
    id: int | None = None

    def to_api(self) -> dict:
        return {
            "id": self.id, "deviceKey": self.device_key, "deviceLabel": self.device_label,
            "platform": self.platform, "timestamp": self.timestamp, "summary": self.summary,
            "recoverability": self.recoverability, "caseId": self.case_id,
            "mechanisms": [m.to_api() for m in self.mechanisms],
            "restrictions": [r.to_api() for r in self.restrictions],
            "options": [o.to_api() for o in self.options],
            "compatibility": [c.to_api() for c in self.compatibility],
            "findings": [f.to_api() for f in self.findings],
            "limitations": self.limitations, "disclaimer": self.disclaimer,
        }
