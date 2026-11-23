# Plan por etapas

## Etapa 1 — Base (actual)
- Estructura modular Electron / React / Python / SQLite. ✅
- Detección de dispositivos: adb (USB, red, emulador; estados device/unauthorized/offline/recovery/sideload/no permissions),
  fastboot, libimobiledevice (USB y red; estados de pairing). ✅
- Diagnóstico: Android (identidad, batería, almacenamiento, RAM, pantalla, táctil, cifrado,
  arranque verificado, uptime, Wi-Fi), bootloader (getvar), Apple (identidad, activación, batería y salud,
  almacenamiento, cifrado de respaldos). ✅
- Panel de resumen funcional, expedientes básicos, registro de evidencias verificable, configuración con detección de herramientas. ✅
- Traducción completa al español. ✅
- Componentes integrados (motores Android/Apple, controlador USB) con verificación SHA-256 y modo autónomo. ✅
- Instalador NSIS y documentación. ✅

## Etapa 2 — Asistente de pantalla dañada ✅
Implementado. Ver [PANTALLA.md](PANTALLA.md).

Cuestionario de síntomas + correlación con diagnóstico (display/táctil/USB/autorización/respaldo previo) →
clasificación en: visible y táctil funcional; visible con táctil defectuoso; pantalla negra; display parcial;
sin respuesta; comunicación USB disponible; respaldo previo disponible. Recomendaciones técnicas por caso
(mouse/teclado OTG, salida de video, duplicación de pantalla con depuración ya autorizada, reemplazo de panel, etc.).

## Etapa 3 — Centro de recuperación de datos y respaldos
Copia del almacenamiento compartido vía `adb pull` (dispositivo autorizado), respaldos Apple con
`idevicebackup2`, importación de respaldos/carpetas, clasificación (fotos, videos, documentos, archivos,
contactos cuando la interfaz lo permita), visor, exportación con hash SHA-256 y cifrado AES-256-GCM.

## Etapa 4 — Análisis y recuperación de acceso ✅
Detección de mecanismos de autenticación y restricciones por interfaces oficiales, evaluación de vías oficiales
(cuenta Google / Apple ID, Find My, restauración, respaldos, MDM, soporte del fabricante, asistencia por OTG/video),
motor de compatibilidad, escenarios con pantalla/táctil dañados y plugins de solo análisis con barreras de política.
Ver [ACCESO.md](ACCESO.md). Pendiente: ampliar el catálogo por fabricante (Samsung, Xiaomi, Motorola…).

## Etapa 5 — Reparación de sistema y restauración de fábrica
Sideload de OTA oficial, modo recuperación, restauración asistida (Apple Devices/Finder, herramientas OEM).
Restauración de fábrica solo por métodos del fabricante con advertencia, confirmación, registro y reporte.

## Etapa 6 — Exportación y reportes
Reportes PDF/JSON de diagnóstico y expedientes, firma con hash, adjuntos al expediente.
