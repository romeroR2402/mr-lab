"""Clasificación de archivos por categoría (extensión y firma del contenido)."""
from __future__ import annotations

from pathlib import PurePosixPath

CATEGORIES = {
    "photos": "Fotografías",
    "videos": "Videos",
    "documents": "Documentos",
    "contacts": "Contactos",
    "backups": "Respaldos locales",
    "files": "Archivos",
}

_EXT = {
    "photos": {"jpg", "jpeg", "png", "heic", "heif", "webp", "gif", "bmp", "dng", "raw", "cr2", "nef", "arw", "tif", "tiff"},
    "videos": {"mp4", "mov", "m4v", "3gp", "mkv", "avi", "webm", "hevc", "mts"},
    "documents": {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp", "txt", "rtf", "csv",
                  "md", "pages", "numbers", "key", "epub"},
    "contacts": {"vcf", "vcard"},
    "backups": {"ab", "mrlb", "bak", "mbdb"},
}
_MAGIC = [
    (b"\xff\xd8\xff", "photos"), (b"\x89PNG", "photos"), (b"GIF8", "photos"),
    (b"%PDF", "documents"), (b"BEGIN:VCARD", "contacts"), (b"ANDROID BACKUP", "backups"), (b"MRLB1", "backups"),
]
_APPLE_BACKUP_MARKERS = {"Manifest.db", "Manifest.plist", "Info.plist", "Status.plist"}


def classify(relpath: str, head: bytes | None = None) -> str:
    name = PurePosixPath(relpath.replace("\\", "/")).name
    if name in _APPLE_BACKUP_MARKERS:
        return "backups"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    for cat, exts in _EXT.items():
        if ext in exts:
            return cat
    if head:
        for sig, cat in _MAGIC:
            if head.startswith(sig):
                return cat
        if head[4:8] == b"ftyp":
            return "videos"
    return "files"


def empty_counts() -> dict:
    return {c: {"files": 0, "bytes": 0} for c in CATEGORIES}
