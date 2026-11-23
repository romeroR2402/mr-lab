"""Catálogo de operaciones de servicio.

Tipos:
  * "auto": MR Lab ejecuta el comando oficial (adb, fastboot, libimobiledevice).
  * "guided": el procedimiento lo realiza el técnico en el dispositivo o en la
    herramienta oficial del fabricante; MR Lab muestra los pasos, exige la misma
    confirmación y registra la operación.

Niveles de impacto: none | app_data | full_wipe.
Ninguna operación evade FRP, bloqueo de activación ni cifrado: tras un
restablecimiento, esas protecciones siguen exigiendo la cuenta del titular.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Operation:
    id: str
    group: str                    # repair | reset
    platform: str                 # android | apple
    kind: str                     # auto | guided
    title: str
    summary: str
    method: str                   # descripción del método oficial
    impact: str = "none"          # none | app_data | full_wipe
    modes: list[str] = field(default_factory=lambda: ["normal"])   # modos en que aplica (auto)
    needs_auth: bool = True
    tool: str | None = None       # adb | fastboot | ideviceenterrecovery
    commands: list[str] = field(default_factory=list)  # comandos mostrados en el plan
    steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    param: str | None = None      # file | package

    def to_api(self) -> dict:
        return {"id": self.id, "group": self.group, "platform": self.platform, "kind": self.kind, "title": self.title,
                "summary": self.summary, "method": self.method, "impact": self.impact, "modes": self.modes,
                "needsAuth": self.needs_auth, "tool": self.tool, "commands": self.commands, "steps": self.steps,
                "warnings": self.warnings, "param": self.param}


WIPE_WARNINGS = [
    "Se borrarán TODOS los datos del usuario: fotos, mensajes, apps, cuentas y ajustes. No se puede deshacer.",
    "Tras el restablecimiento, la protección del fabricante (FRP en Android, Bloqueo de activación en Apple) "
    "seguirá exigiendo la cuenta del titular. MR Lab no la elimina.",
]

OPERATIONS: list[Operation] = [
    # ------------------------------------------------------------ Android · reparación
    Operation("android_reboot_system", "repair", "android", "auto", "Reiniciar el sistema",
              "Reinicio normal desde ADB o desde el bootloader.", "Comando oficial de Android SDK Platform Tools",
              modes=["normal", "recovery", "sideload", "bootloader", "fastbootd"], needs_auth=False, tool="adb|fastboot",
              commands=["adb -s <serie> reboot", "fastboot -s <serie> reboot (en bootloader)"]),
    Operation("android_reboot_recovery", "repair", "android", "auto", "Reiniciar en modo recovery",
              "Abre el menú de recuperación del fabricante.", "adb reboot recovery", tool="adb",
              commands=["adb -s <serie> reboot recovery"]),
    Operation("android_reboot_bootloader", "repair", "android", "auto", "Reiniciar en bootloader (fastboot)",
              "Modo de servicio para diagnóstico de arranque y herramientas oficiales.", "adb reboot bootloader", tool="adb",
              commands=["adb -s <serie> reboot bootloader"]),
    Operation("android_reboot_sideload", "repair", "android", "auto", "Preparar sideload de OTA",
              "Reinicia en modo sideload para instalar una actualización oficial.", "adb reboot sideload",
              modes=["normal", "recovery"], tool="adb", commands=["adb -s <serie> reboot sideload"],
              warnings=["En algunos modelos hay que elegir «Apply update from ADB» en el menú recovery."]),
    Operation("android_ota_sideload", "repair", "android", "auto", "Instalar OTA oficial (sideload)",
              "Reinstala o actualiza el sistema con el paquete OTA firmado del fabricante, sin borrar datos.",
              "adb sideload con paquete OTA oficial; el dispositivo verifica la firma del fabricante",
              modes=["sideload"], needs_auth=False, tool="adb", param="file",
              commands=["adb -s <serie> sideload <paquete_ota.zip>"],
              steps=["Descargue el paquete OTA oficial del modelo exacto desde el sitio del fabricante.",
                     "Ponga el dispositivo en modo sideload.", "Seleccione el archivo y ejecute."],
              warnings=["Use solo paquetes OTA oficiales del modelo exacto: el dispositivo rechazará paquetes no firmados.",
                        "No desconecte el cable durante la instalación."]),
    Operation("android_trim_caches", "repair", "android", "auto", "Liberar caché del sistema",
              "Libera la caché de las apps cuando el almacenamiento está lleno.", "pm trim-caches (Android)",
              tool="adb", commands=["adb -s <serie> shell pm trim-caches 999G"]),
    Operation("android_uninstall_app", "repair", "android", "auto", "Desinstalar una app de terceros",
              "Elimina una app instalada por el usuario que provoca fallos o reinicios.",
              "pm uninstall --user 0 (solo apps de terceros)", impact="app_data", tool="adb", param="package",
              commands=["adb -s <serie> shell pm uninstall --user 0 <paquete>"],
              warnings=["Se borrarán los datos de esa app.", "Solo se permiten apps instaladas por el usuario, no del sistema."]),
    Operation("android_safe_mode", "repair", "android", "guided", "Arranque en modo seguro",
              "Inicia sin apps de terceros para aislar la causa de un fallo.", "Procedimiento del sistema Android",
              steps=["Mantenga pulsado el botón de encendido hasta ver el menú de apagado.",
                     "Mantenga pulsado «Apagar» o «Reiniciar» y acepte «Reiniciar en modo seguro».",
                     "Si el fallo desaparece, la causa es una app de terceros: desinstálela.",
                     "Reinicie normalmente para salir del modo seguro."]),
    Operation("android_oem_reflash", "repair", "android", "guided", "Reinstalar firmware con la herramienta oficial",
              "Para bucles de arranque o sistema dañado que no se corrige con OTA.",
              "Herramienta oficial del fabricante", impact="full_wipe",
              steps=["Identifique el modelo y región exactos.",
                     "Use la herramienta oficial: Pixel → Android Flash Tool; Samsung → Smart Switch (recuperación de emergencia); "
                     "Motorola → Software Fix; Xiaomi → Mi Flash (con bootloader del fabricante).",
                     "Siga el procedimiento del fabricante hasta completar la instalación.",
                     "Tras arrancar, el titular debe completar la verificación de su cuenta (FRP)."],
              warnings=WIPE_WARNINGS + ["Algunos fabricantes conservan datos con su modo de reparación; confírmelo antes."]),
    # ------------------------------------------------------------ Android · restauración de fábrica
    Operation("android_reset_settings", "reset", "android", "guided", "Restablecer desde Ajustes",
              "Método preferente cuando el titular puede desbloquear el equipo.",
              "Ajustes > Sistema > Opciones de restablecimiento > Borrar todos los datos", impact="full_wipe",
              steps=["El titular desbloquea el equipo.", "Ajustes > Sistema > Opciones de restablecimiento.",
                     "«Borrar todos los datos (restablecer configuración de fábrica)» y confirmar con su credencial."],
              warnings=WIPE_WARNINGS),
    Operation("android_reset_recovery", "reset", "android", "guided", "Restablecer desde el menú recovery",
              "Para equipos que no arrancan o no se pueden manejar desde Ajustes.",
              "Recovery del fabricante: Wipe data / factory reset", impact="full_wipe",
              steps=["Reinicie en modo recovery (puede usar «Reiniciar en modo recovery» de MR Lab).",
                     "Con los botones de volumen, elija «Wipe data/factory reset» y confirme con encendido.",
                     "Al terminar, elija «Reboot system now»."],
              warnings=WIPE_WARNINGS),
    Operation("android_reset_findmy", "reset", "android", "guided", "Borrado remoto con Find My Device",
              "Cuando el equipo está conectado a internet y el titular tiene su cuenta.",
              "Google Find My Device (android.com/find)", impact="full_wipe",
              steps=["El titular inicia sesión en android.com/find.", "Selecciona el equipo y «Restablecer dispositivo»."],
              warnings=WIPE_WARNINGS),
    Operation("android_fastboot_wipe", "reset", "android", "auto", "Borrado de datos con fastboot",
              "Borra la partición de usuario desde el bootloader (solo con bootloader desbloqueado).",
              "fastboot -w (Android SDK Platform Tools)", impact="full_wipe", modes=["bootloader", "fastbootd"],
              needs_auth=False, tool="fastboot", commands=["fastboot -s <serie> -w", "fastboot -s <serie> reboot"],
              warnings=WIPE_WARNINGS + ["Con el bootloader bloqueado el fabricante no permite este método; use recovery o Ajustes."]),
    # ------------------------------------------------------------ Apple
    Operation("apple_enter_recovery", "repair", "apple", "auto", "Entrar en modo recuperación",
              "Prepara el dispositivo para actualizar o restaurar con Apple Devices / Finder.",
              "ideviceenterrecovery (libimobiledevice)", tool="ideviceenterrecovery",
              commands=["ideviceenterrecovery <UDID>"],
              warnings=["El dispositivo quedará en modo recuperación hasta que se actualice, restaure o reinicie con los botones."]),
    Operation("apple_update", "repair", "apple", "guided", "Actualizar iOS sin borrar datos",
              "Reinstala iOS conservando los datos del usuario.", "Apple Devices (Windows) o Finder (Mac): «Actualizar»",
              steps=["Conecte el dispositivo y ponga el modo recuperación (puede usar MR Lab).",
                     "En Apple Devices / Finder elija «Actualizar» (no «Restaurar»).",
                     "Espere a que termine; si tarda más de 15 minutos, el dispositivo sale del modo y hay que repetir."]),
    Operation("apple_reset_settings", "reset", "apple", "guided", "Borrar contenidos y ajustes",
              "Método preferente cuando el titular puede desbloquear el equipo.",
              "Ajustes > General > Transferir o restablecer > Borrar contenidos y ajustes", impact="full_wipe",
              steps=["El titular desbloquea el equipo.", "Ajustes > General > Transferir o restablecer.",
                     "«Borrar contenidos y ajustes» e introducir su código y contraseña del Apple ID."],
              warnings=WIPE_WARNINGS),
    Operation("apple_restore", "reset", "apple", "guided", "Restaurar con Apple Devices / Finder",
              "Para equipos que no arrancan o con código olvidado.", "Modo recuperación + «Restaurar» en Apple Devices / Finder",
              impact="full_wipe",
              steps=["Ponga el dispositivo en modo recuperación (puede usar MR Lab).",
                     "En Apple Devices / Finder elija «Restaurar» y confirme.",
                     "Al terminar, el titular activa el equipo con su Apple ID."],
              warnings=WIPE_WARNINGS),
    Operation("apple_findmy_erase", "reset", "apple", "guided", "Borrado remoto con Buscar (iCloud)",
              "Cuando el titular tiene acceso a su Apple ID.", "icloud.com/find > Borrar dispositivo", impact="full_wipe",
              steps=["El titular inicia sesión en icloud.com/find.", "Selecciona el dispositivo y «Borrar este dispositivo»."],
              warnings=WIPE_WARNINGS),
]

BY_ID = {o.id: o for o in OPERATIONS}
