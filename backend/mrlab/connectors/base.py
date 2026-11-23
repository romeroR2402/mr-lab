from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Device:
    platform: str               # android | apple
    serial: str                 # identificador disponible (serial ADB / UDID)
    connection: str             # usb | network | emulator | unknown
    comm_state: str             # online | offline | recovery | sideload | bootloader | unauthorized | no_permissions | ...
    auth_state: str             # authorized | unauthorized | pending | not_paired | locked | no_permissions | not_applicable | unknown
    mode: str = "normal"        # normal | recovery | sideload | bootloader | fastbootd
    manufacturer: str | None = None
    model: str | None = None
    model_code: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    connector: str = ""
    diagnostics: list[str] = field(default_factory=list)  # diagnósticos disponibles
    notes: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.platform}:{self.serial}"

    @property
    def label(self) -> str:
        parts = [p for p in (self.manufacturer, self.model) if p]
        return " ".join(parts) if parts else self.serial

    def to_api(self) -> dict:
        d = asdict(self)
        return {
            "key": self.key,
            "label": self.label,
            "platform": d["platform"],
            "serial": d["serial"],
            "connection": d["connection"],
            "commState": d["comm_state"],
            "authState": d["auth_state"],
            "mode": d["mode"],
            "manufacturer": d["manufacturer"],
            "model": d["model"],
            "modelCode": d["model_code"],
            "osName": d["os_name"],
            "osVersion": d["os_version"],
            "connector": d["connector"],
            "diagnostics": d["diagnostics"],
            "notes": d["notes"],
        }
