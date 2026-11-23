"""Ejecución segura de procesos externos (adb, fastboot, libimobiledevice)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass

from ..config import IS_WINDOWS


@dataclass
class ProcResult:
    code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    error: str | None = None  # error al lanzar el proceso (no encontrado, permisos...)

    @property
    def ok(self) -> bool:
        return self.error is None and not self.timed_out and self.code == 0

    @property
    def output(self) -> str:
        return (self.stdout or "") + (self.stderr or "")


def run(cmd: list[str], timeout: float = 15.0, input_text: str | None = None) -> ProcResult:
    """Ejecuta un comando sin shell; nunca lanza excepción, devuelve ProcResult."""
    kwargs: dict = {}
    if IS_WINDOWS:
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        cp = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            input=input_text,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=None if input_text is not None else subprocess.DEVNULL,
            **kwargs,
        )
        return ProcResult(cp.returncode, cp.stdout or "", cp.stderr or "")
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return ProcResult(None, out, err, timed_out=True, error=f"Tiempo de espera agotado ({timeout}s)")
    except FileNotFoundError:
        return ProcResult(None, "", "", error=f"Ejecutable no encontrado: {cmd[0]}")
    except PermissionError:
        return ProcResult(None, "", "", error=f"Permiso denegado al ejecutar: {cmd[0]}")
    except OSError as e:
        return ProcResult(None, "", "", error=f"Error del sistema al ejecutar {cmd[0]}: {e}")
