"""Trabajos de larga duración (respaldos, verificaciones, exportaciones) con
progreso y cancelación. Se ejecutan en hilos propios para no bloquear el RPC."""
from __future__ import annotations

import itertools
import threading
import traceback
import sys
from dataclasses import dataclass, field
from typing import Callable

from .errors import RpcError
from .util.timeutil import now_iso

_ids = itertools.count(1)
_lock = threading.Lock()
_jobs: dict[int, "Job"] = {}


@dataclass
class Job:
    id: int
    kind: str
    title: str
    status: str = "running"          # running | done | failed | cancelled
    phase: str = "Preparando"
    progress: float | None = None     # 0..1 o None si es indeterminado
    detail: str | None = None
    result: dict | None = None
    error: str | None = None
    started_at: str = field(default_factory=now_iso)
    finished_at: str | None = None
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    # API para el código del trabajo
    def update(self, phase: str | None = None, progress: float | None = None, detail: str | None = None) -> None:
        if phase is not None:
            self.phase = phase
        self.progress = None if progress is None else max(0.0, min(1.0, progress))
        if detail is not None:
            self.detail = detail

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def check(self) -> None:
        if self._cancel.is_set():
            raise RpcError("cancelled", "Operación cancelada por el técnico.")

    def to_api(self) -> dict:
        return {"id": self.id, "kind": self.kind, "title": self.title, "status": self.status, "phase": self.phase,
                "progress": self.progress, "detail": self.detail, "result": self.result, "error": self.error,
                "startedAt": self.started_at, "finishedAt": self.finished_at}


def start(kind: str, title: str, fn: Callable[[Job], dict], on_error: Callable[[Job, str], None] | None = None) -> dict:
    job = Job(next(_ids), kind, title)
    with _lock:
        _jobs[job.id] = job

    def run():
        try:
            job.result = fn(job)
            job.status = "done"
            job.phase = "Completado"
            job.detail = None
            job.progress = 1.0
        except RpcError as e:
            job.status = "cancelled" if e.code == "cancelled" else "failed"
            job.error = e.message
            if on_error:
                on_error(job, e.message)
        except Exception as e:  # pragma: no cover - errores inesperados
            traceback.print_exc(file=sys.stderr)
            job.status = "failed"
            job.error = f"Error interno: {e}"
            if on_error:
                on_error(job, job.error)
        finally:
            job.finished_at = now_iso()

    threading.Thread(target=run, name=f"job-{job.id}", daemon=True).start()
    return job.to_api()


def get(job_id: int) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise RpcError("not_found", f"Trabajo {job_id} no encontrado")
    return job.to_api()


def list_jobs(limit: int = 30) -> list[dict]:
    with _lock:
        items = sorted(_jobs.values(), key=lambda j: j.id, reverse=True)[:limit]
    return [j.to_api() for j in items]


def cancel(job_id: int) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise RpcError("not_found", f"Trabajo {job_id} no encontrado")
    job._cancel.set()
    return job.to_api()


def wait(job_id: int, timeout: float = 60) -> dict:
    """Solo para pruebas: espera a que termine un trabajo."""
    import time
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        j = _jobs[job_id]
        if j.status != "running":
            return j.to_api()
        time.sleep(0.05)
    raise TimeoutError(f"job {job_id}")
