"""Servidor JSON-RPC por stdio (una línea JSON por mensaje).
Petición:  {"id": 1, "method": "devices.scan", "params": {...}}
Respuesta: {"id": 1, "result": ...} | {"id": 1, "error": {"code", "message", "data"}}"""
from __future__ import annotations

import json
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from . import cases, components, config, dashboard, db, evidence, modules, scanner, settings, tools
from .access import engine as access_engine, plugins as access_plugins, policy as access_policy
from .diagnostics import engine
from .screen import engine as screen_engine, questionnaire as screen_questions
from .errors import NotImplementedOperation, RpcError


def _p(params: dict, key: str, typ=None, default=...):
    if key not in params or params[key] is None:
        if default is ...:
            raise RpcError("invalid_params", f"Falta el parámetro '{key}'")
        return default
    val = params[key]
    if typ is not None and not isinstance(val, typ):
        raise RpcError("invalid_params", f"Parámetro '{key}' con tipo inválido")
    return val


def _health(_):
    return {"version": config.VERSION, "dataDir": str(config.data_dir()), "db": str(db.current_path()),
            "schemaVersion": db.migrate(), "python": sys.version.split()[0]}


def _update_settings(p: dict) -> dict:
    out = settings.update(_p(p, "values", dict))
    tools.invalidate()  # las rutas de herramientas pueden haber cambiado
    return out


def _not_impl(name: str, stage: str):
    def handler(_):
        raise NotImplementedOperation(name, stage)
    return handler


METHODS: dict[str, Callable[[dict], object]] = {
    "system.health": _health,
    "system.modules": lambda p: modules.list_modules(),
    "tools.detect": lambda p: tools.detect(force=bool(p.get("force"))),
    "components.status": lambda p: components.status(force=bool(p.get("force"))),
    "settings.get": lambda p: settings.get_all(),
    "settings.update": lambda p: _update_settings(p),
    "devices.scan": lambda p: scanner.scan(),
    "devices.last": lambda p: scanner.last_scan(),
    "devices.known": lambda p: scanner.known_devices(),
    "diagnostics.run": lambda p: engine.run(_p(p, "deviceKey", str), _p(p, "caseId", int, None)),
    "diagnostics.history": lambda p: engine.history(_p(p, "deviceSerial", str, None)),
    "diagnostics.get": lambda p: engine.get_report(_p(p, "id", int)),
    "dashboard.summary": lambda p: dashboard.summary(),
    "cases.list": lambda p: cases.list_cases(status=_p(p, "status", str, None), search=_p(p, "search", str, None)),
    "cases.get": lambda p: cases.get(_p(p, "id", int)),
    "cases.create": lambda p: cases.create(p),
    "cases.updateStatus": lambda p: cases.update_status(_p(p, "id", int), _p(p, "status", str), _p(p, "results", str, None)),
    "evidence.list": lambda p: evidence.list_entries(_p(p, "limit", int, 200), _p(p, "offset", int, 0), _p(p, "caseId", int, None)),
    "evidence.verify": lambda p: evidence.verify_chain(),
    "access.analyze": lambda p: access_engine.analyze(_p(p, "deviceKey", str), _p(p, "caseId", int, None)),
    "access.history": lambda p: access_engine.history(_p(p, "deviceSerial", str, None)),
    "access.get": lambda p: access_engine.get(_p(p, "id", int)),
    "access.procedures": lambda p: access_engine.procedures(),
    "access.plugins": lambda p: {"plugins": access_plugins.list_plugins(), "directory": str(access_plugins.plugins_dir()),
                                 "allowedCapabilities": sorted(access_policy.ALLOWED_CAPABILITIES)},
    "access.setPlugin": lambda p: access_plugins.set_enabled(_p(p, "id", str), _p(p, "enabled", bool)),
    "screen.questionnaire": lambda p: screen_questions.schema(),
    "screen.assess": lambda p: screen_engine.assess(_p(p, "answers", dict), _p(p, "deviceKey", str, None),
                                                    _p(p, "caseId", int, None), _p(p, "deviceLabel", str, None)),
    "screen.history": lambda p: screen_engine.history(_p(p, "deviceSerial", str, None)),
    "screen.get": lambda p: screen_engine.get(_p(p, "id", int)),
    # Operaciones de etapas posteriores: responden explícitamente "no implementado".
    "recovery.start": _not_impl("Recuperación de datos", "Etapa 3"),
    "backup.create": _not_impl("Creación de respaldo", "Etapa 3"),
    "repair.start": _not_impl("Reparación de sistema", "Etapa 5"),
    "reset.prepare": _not_impl("Restauración de fábrica", "Etapa 5"),
    "reports.export": _not_impl("Exportación de reportes", "Etapa 6"),
}


class Server:
    def __init__(self, inp=sys.stdin, out=sys.stdout, workers: int = 4):
        self.inp, self.out = inp, out
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=workers)

    def send(self, msg: dict) -> None:
        line = json.dumps(msg, ensure_ascii=False, default=str)
        with self.lock:
            self.out.write(line + "\n")
            self.out.flush()

    def handle(self, req: dict) -> dict:
        rid = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}
        fn = METHODS.get(method) if isinstance(method, str) else None
        if fn is None:
            return {"id": rid, "error": {"code": "method_not_found", "message": f"Método desconocido: {method}"}}
        if not isinstance(params, dict):
            return {"id": rid, "error": {"code": "invalid_params", "message": "params debe ser un objeto"}}
        try:
            return {"id": rid, "result": fn(params)}
        except RpcError as e:
            return {"id": rid, "error": {"code": e.code, "message": e.message, "data": e.data}}
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            return {"id": rid, "error": {"code": "internal_error", "message": f"Error interno: {e}"}}

    def serve(self) -> None:
        db.migrate()
        self.send({"event": "ready", "data": {"version": config.VERSION}})
        for line in self.inp:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                self.send({"id": None, "error": {"code": "parse_error", "message": "JSON inválido"}})
                continue
            if req.get("method") == "system.shutdown":
                self.send({"id": req.get("id"), "result": True})
                break
            self.pool.submit(lambda r=req: self.send(self.handle(r)))
        self.pool.shutdown(wait=True)
