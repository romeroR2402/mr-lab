"""Registro de módulos y su estado real de implementación."""

MODULES = [
    {"id": "dashboard", "name": "Resumen", "stage": 1, "status": "implemented",
     "description": "Resumen del dispositivo conectado, diagnóstico, accesos y casos recientes."},
    {"id": "devices", "name": "Detección de dispositivos", "stage": 1, "status": "implemented",
     "description": "Detección USB/red vía adb, fastboot y libimobiledevice."},
    {"id": "diagnostics", "name": "Diagnóstico de dispositivos", "stage": 1, "status": "implemented",
     "description": "Diagnóstico de solo lectura: batería, almacenamiento, pantalla, táctil, seguridad."},
    {"id": "case-files", "name": "Gestión de expedientes", "stage": 1, "status": "partial",
     "description": "Alta, consulta y cambio de estado de expedientes. Pendiente: adjuntar archivos exportados."},
    {"id": "evidence", "name": "Registro de evidencias", "stage": 1, "status": "implemented",
     "description": "Registro automático, de solo inserción, encadenado con SHA-256 y verificable."},
    {"id": "screen-recovery", "name": "Asistente de pantalla dañada", "stage": 2, "status": "implemented",
     "description": "Clasificación del caso (cuestionario + señales del sistema), inconsistencias y recomendaciones técnicas priorizadas.",
     "scope": ["Cuestionario de síntomas", "Correlación con diagnóstico táctil/display",
               "Recomendaciones: OTG, salida de video, scrcpy, respaldo previo"]},
    {"id": "data-recovery", "name": "Centro de recuperación de datos", "stage": 3, "status": "planned",
     "description": "Respaldo, importación, clasificación y exportación por interfaces autorizadas.",
     "scope": ["Fotografías", "Videos", "Documentos", "Archivos", "Contactos (si la interfaz lo permite)",
               "Respaldos locales", "Otras fuentes autorizadas"]},
    {"id": "backup-manager", "name": "Administrador de respaldos", "stage": 3, "status": "partial",
     "description": "Motor de cifrado AES-256-GCM listo; gestión de respaldos pendiente.",
     "scope": ["Respaldos cifrados", "Verificación de integridad", "Respaldos Apple con idevicebackup2"]},
    {"id": "access-recovery", "name": "Análisis y recuperación de acceso", "stage": 4, "status": "implemented",
     "description": "Identifica mecanismos de autenticación y restricciones, evalúa vías oficiales, compatibilidad y plugins de análisis. Sin evasión."},
    {"id": "system-repair", "name": "Reparación de sistema", "stage": 5, "status": "planned",
     "description": "Reparación de software con herramientas oficiales (sideload de OTA oficial, modo recuperación).",
     "scope": ["Actualización OTA oficial", "Modo recuperación", "Restauración asistida"]},
    {"id": "reset-center", "name": "Asistente de restauración de fábrica", "stage": 5, "status": "planned",
     "description": "Restauración de fábrica con advertencia, confirmación, registro y reporte.",
     "scope": ["Advertencia de pérdida de datos", "Confirmación explícita", "Registro y reporte"]},
    {"id": "reports", "name": "Exportación y reportes", "stage": 6, "status": "planned",
     "description": "Exportación de reportes de diagnóstico y expedientes (PDF/JSON)."},
]


def list_modules() -> list[dict]:
    return MODULES
