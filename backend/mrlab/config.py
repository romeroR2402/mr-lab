"""Configuración de rutas y constantes del backend."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import __version__

VERSION = __version__
IS_WINDOWS = sys.platform.startswith("win")


def data_dir() -> Path:
    """Directorio de datos local. Electron lo define con MRLAB_DATA_DIR (userData)."""
    env = os.environ.get("MRLAB_DATA_DIR")
    if env:
        base = Path(env)
    elif IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home())) / "MobileRecoveryLab"
    else:
        base = Path.home() / ".mrlab"
    base.mkdir(parents=True, exist_ok=True)
    return base


def sub_dir(name: str) -> Path:
    p = data_dir() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return data_dir() / "mrlab.sqlite3"


def bundled_tools_dir() -> Path | None:
    """Herramientas empaquetadas junto al instalador (resources/tools)."""
    env = os.environ.get("MRLAB_TOOLS_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    return None
