from __future__ import annotations

from . import cases, evidence, scanner, tools
from .diagnostics import engine
from .screen import engine as screen_engine


def summary() -> dict:
    scan = scanner.last_scan()
    devices = scan.get("devices") or []
    primary = devices[0] if devices else None
    diag = engine.latest_for(primary["serial"]) if primary else None
    screen = None
    if diag:
        disp = next((c for c in diag["checks"] if c["id"] == "display"), None)
        touch = next((c for c in diag["checks"] if c["id"] == "touch"), None)
        screen = {"display": disp, "touch": touch}
    assessment = screen_engine.latest_for(primary["serial"]) if primary else None
    t = tools.detect()
    return {
        "primaryDevice": primary,
        "deviceCount": len(devices),
        "scannedAt": scan.get("scannedAt"),
        "scanErrors": scan.get("errors") or [],
        "lastDiagnostic": diag,
        "screen": screen,
        "screenAssessment": {"id": assessment["id"], "category": assessment["category"], "categoryLabel": assessment["categoryLabel"],
                             "timestamp": assessment["timestamp"]} if assessment else None,
        "recoveryChannels": engine.recovery_channels(primary) if primary else [],
        "recentCases": cases.list_cases(limit=6),
        "caseStats": cases.stats(),
        "evidenceCount": evidence.list_entries(limit=1)["total"],
        "tools": {x["id"]: x["installed"] for x in t["tools"]},
        "toolSources": {x["id"]: x["source"] for x in t["tools"]},
        "autonomy": t["autonomy"],
        "appleService": t["appleService"],
        "encryption": t["encryption"],
    }
