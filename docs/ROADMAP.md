# Plan por etapas

## Etapa 1 — Base (actual)
- Estructura modular Electron / React / Python / SQLite. ✅
- Device Scanner: adb (USB, red, emulador; estados device/unauthorized/offline/recovery/sideload/no permissions),
  fastboot, libimobiledevice (USB y red; estados de pairing). ✅
- Device Diagnostic: Android (identidad, batería, almacenamiento, RAM, pantalla, táctil, cifrado,
  arranque verificado, uptime, Wi-Fi), bootloader (getvar), Apple (identidad, activación, batería y salud,
  almacenamiento, cifrado de respaldos). ✅
- Dashboard funcional, Case Files básico, Evidence Log verificable, Settings con detección de herramientas. ✅
- Instalador NSIS y documentación. ✅

## Etapa 2 — Screen Recovery Assistant
Cuestionario de síntomas + correlación con diagnóstico (display/táctil/USB/autorización/respaldo previo) →
clasificación en: visible y táctil funcional; visible con táctil defectuoso; pantalla negra; display parcial;
sin respuesta; comunicación USB disponible; respaldo previo disponible. Recomendaciones técnicas por caso
(mouse/teclado OTG, salida de video, duplicación de pantalla con depuración ya autorizada, reemplazo de panel, etc.).

## Etapa 3 — Data Recovery Center y Backup Manager
Copia del almacenamiento compartido vía `adb pull` (dispositivo autorizado), respaldos Apple con
`idevicebackup2`, importación de respaldos/carpetas, clasificación (fotos, videos, documentos, archivos,
contactos cuando la interfaz lo permita), visor, exportación con hash SHA-256 y cifrado AES-256-GCM.

## Etapa 4 — Access Recovery Assistant
Guías por fabricante: recuperación de cuenta Google / Apple ID, Find My Device / Buscar, respaldos existentes,
restauración y contacto con soporte. Requisitos, advertencias y pasos; sin evasión de autenticación.

## Etapa 5 — System Repair y Factory Reset Assistant
Sideload de OTA oficial, modo recuperación, restauración asistida (Apple Devices/Finder, herramientas OEM).
Restauración de fábrica solo por métodos del fabricante con advertencia, confirmación, registro y reporte.

## Etapa 6 — Export and Reports
Reportes PDF/JSON de diagnóstico y expedientes, firma con hash, adjuntos al expediente.
