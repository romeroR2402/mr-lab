from __future__ import annotations

from dataclasses import dataclass, field

ORDER = {"error": 3, "warning": 2, "ok": 1, "info": 0, "unavailable": 0}


@dataclass
class Check:
    id: str
    category: str
    label: str
    status: str = "unavailable"   # ok | warning | error | info | unavailable
    value: str | None = None
    detail: str | None = None
    data: dict = field(default_factory=dict)

    def to_api(self) -> dict:
        return {"id": self.id, "category": self.category, "label": self.label, "status": self.status,
                "value": self.value, "detail": self.detail, "data": self.data}


def summarize(checks: list[Check]) -> str:
    worst = "unavailable"
    for c in checks:
        if ORDER.get(c.status, 0) > ORDER.get(worst, 0) or (worst == "unavailable" and c.status in ("ok", "info")):
            worst = c.status
    return "ok" if worst == "info" else worst


def unavailable(cid: str, category: str, label: str, reason: str) -> Check:
    return Check(cid, category, label, "unavailable", None, reason)
