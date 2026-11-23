"""Persistencia local en SQLite con migraciones versionadas (PRAGMA user_version)."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import config

_write_lock = threading.RLock()
_db_path_override: Path | None = None

MIGRATIONS: list[str] = [
    # v1: esquema inicial
    """
    CREATE TABLE settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE devices (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        platform     TEXT NOT NULL,
        serial       TEXT NOT NULL,
        manufacturer TEXT,
        model        TEXT,
        os_name      TEXT,
        os_version   TEXT,
        first_seen   TEXT NOT NULL,
        last_seen    TEXT NOT NULL,
        UNIQUE(platform, serial)
    );

    CREATE TABLE cases (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        folio              TEXT NOT NULL UNIQUE,
        created_at         TEXT NOT NULL,
        updated_at         TEXT NOT NULL,
        technician         TEXT NOT NULL,
        device_type        TEXT NOT NULL,
        device_model       TEXT,
        device_serial      TEXT,
        reason             TEXT NOT NULL,
        authorization_type TEXT NOT NULL,
        authorized_by      TEXT NOT NULL,
        authorization_ref  TEXT,
        status             TEXT NOT NULL DEFAULT 'open',
        results            TEXT
    );

    CREATE TABLE case_operations (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id   INTEGER NOT NULL REFERENCES cases(id),
        timestamp TEXT NOT NULL,
        operation TEXT NOT NULL,
        method    TEXT,
        result    TEXT NOT NULL,
        details   TEXT
    );

    CREATE TABLE case_files (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id     INTEGER NOT NULL REFERENCES cases(id),
        created_at  TEXT NOT NULL,
        path        TEXT NOT NULL,
        sha256      TEXT,
        size_bytes  INTEGER,
        description TEXT
    );

    CREATE TABLE evidence_log (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp     TEXT NOT NULL,
        technician    TEXT NOT NULL,
        case_id       INTEGER REFERENCES cases(id),
        device_serial TEXT,
        device_label  TEXT,
        operation     TEXT NOT NULL,
        result        TEXT NOT NULL,
        details       TEXT,
        files         TEXT,
        error         TEXT,
        confirmation  TEXT,
        prev_hash     TEXT NOT NULL,
        entry_hash    TEXT NOT NULL
    );

    -- El registro de evidencias es de solo inserción.
    CREATE TRIGGER evidence_log_no_update BEFORE UPDATE ON evidence_log
    BEGIN SELECT RAISE(ABORT, 'evidence_log es de solo inserción'); END;
    CREATE TRIGGER evidence_log_no_delete BEFORE DELETE ON evidence_log
    BEGIN SELECT RAISE(ABORT, 'evidence_log es de solo inserción'); END;

    CREATE TABLE diagnostic_reports (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp      TEXT NOT NULL,
        platform       TEXT NOT NULL,
        device_serial  TEXT NOT NULL,
        device_label   TEXT,
        case_id        INTEGER REFERENCES cases(id),
        summary_status TEXT NOT NULL,
        report_json    TEXT NOT NULL
    );

    CREATE INDEX idx_evidence_case ON evidence_log(case_id);
    CREATE INDEX idx_diag_serial ON diagnostic_reports(device_serial);
    """,
    # v2: módulo de análisis y recuperación de acceso
    """
    CREATE TABLE access_analyses (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp      TEXT NOT NULL,
        platform       TEXT NOT NULL,
        device_serial  TEXT NOT NULL,
        device_label   TEXT,
        case_id        INTEGER REFERENCES cases(id),
        recoverability TEXT NOT NULL,
        report_json    TEXT NOT NULL
    );
    CREATE INDEX idx_access_serial ON access_analyses(device_serial);

    CREATE TABLE access_plugin_state (
        plugin_id TEXT PRIMARY KEY,
        enabled   INTEGER NOT NULL
    );
    """,
    # v3: asistente de pantalla dañada
    """
    CREATE TABLE screen_assessments (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp     TEXT NOT NULL,
        device_serial TEXT,
        device_label  TEXT,
        case_id       INTEGER REFERENCES cases(id),
        category      TEXT NOT NULL,
        report_json   TEXT NOT NULL
    );
    CREATE INDEX idx_screen_serial ON screen_assessments(device_serial);
    """,
    # v4: centro de recuperación de datos y administrador de respaldos
    """
    CREATE TABLE backups (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at       TEXT NOT NULL,
        case_id          INTEGER NOT NULL REFERENCES cases(id),
        source           TEXT NOT NULL,
        device_serial    TEXT,
        device_label     TEXT,
        path             TEXT NOT NULL,
        manifest_path    TEXT NOT NULL,
        container_bytes  INTEGER NOT NULL,
        plain_bytes      INTEGER NOT NULL,
        file_count       INTEGER NOT NULL,
        categories_json  TEXT NOT NULL,
        container_sha256 TEXT NOT NULL,
        warnings_json    TEXT,
        verified_at      TEXT,
        verify_result    TEXT,
        status           TEXT NOT NULL DEFAULT 'ok'
    );
    CREATE INDEX idx_backups_case ON backups(case_id);
    """,
]


def set_db_path(path: Path | None) -> None:
    """Usado por pruebas para apuntar a una base temporal."""
    global _db_path_override
    _db_path_override = path


def current_path() -> Path:
    return _db_path_override or config.db_path()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(current_path(), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def read() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def write() -> Iterator[sqlite3.Connection]:
    """Transacción de escritura serializada (BEGIN IMMEDIATE)."""
    with _write_lock:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()


def migrate() -> int:
    with _write_lock:
        conn = _connect()
        try:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            for idx in range(version, len(MIGRATIONS)):
                conn.execute("BEGIN IMMEDIATE")
                for stmt in _split_sql(MIGRATIONS[idx]):
                    conn.execute(stmt)
                conn.execute(f"PRAGMA user_version = {idx + 1}")
                conn.execute("COMMIT")
            return conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()


def _split_sql(script: str) -> list[str]:
    """Divide un script respetando bloques BEGIN ... END de triggers."""
    stmts: list[str] = []
    buf: list[str] = []
    depth = 0
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        upper = stripped.upper()
        if " BEGIN " in f" {upper} ":
            depth += 1
        if upper.startswith("END") or upper.endswith(" END;"):
            depth = max(0, depth - 1)
        if stripped.endswith(";") and depth == 0:
            stmts.append("\n".join(buf))
            buf = []
    if buf:
        stmts.append("\n".join(buf))
    return stmts


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None
