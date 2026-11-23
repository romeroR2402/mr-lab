"""Registro de módulos y su estado real de implementación."""

MODULES = [
    {"id": "dashboard", "name": "Dashboard", "stage": 1, "status": "implemented",
     "description": "Resumen del dispositivo conectado, diagnóstico, accesos y casos recientes."},
    {"id": "devices", "name": "Device Scanner", "stage": 1, "status": "implemented",
     "description": "Detección USB/red vía adb, fastboot y libimobiledevice."},
    {"id": "diagnostics", "name": "Device Diagnostic", "stage": 1, "status": "implemented",
     "description": "Diagnóstico de solo lectura: batería, almacenamiento, pantalla, táctil, seguridad."},
    {"id": "case-files", "name": "Case Management", "stage": 1, "status": "partial",
     "description": "Alta, consulta y cambio de estado de expedientes. Pendiente: adjuntar archivos exportados."},
    {"id": "evidence", "name": "Evidence Log", "stage": 1, "status": "implemented",
     "description": "Registro automático, de solo inserción, encadenado con SHA-256 y verificable."},
    {"id": "screen-recovery", "name": "Screen Recovery Assistant", "stage": 2, "status": "planned",
     "description": "Clasificación de daño de pantalla y recomendaciones técnicas.",
     "scope": ["Cuestionario de síntomas", "Correlación con diagnóstico táctil/display",
               "Recomendaciones: OTG, salida de video, scrcpy, respaldo previo"]},
    {"id": "data-recovery", "name": "Data Recovery Center", "stage": 3, "status": "planned",
     "description": "Respaldo, importación, clasificación y exportación por interfaces autorizadas.",
     "scope": ["Fotografías", "Videos", "Documentos", "Archivos", "Contactos (si la interfaz lo permite)",
               "Respaldos locales", "Otras fuentes autorizadas"]},
    {"id": "backup-manager", "name": "Backup Manager", "stage": 3, "status": "partial",
     "description": "Motor de cifrado AES-256-GCM listo; gestión de respaldos pendiente.",
     "scope": ["Respaldos cifrados", "Verificación de integridad", "Respaldos Apple con idevicebackup2"]},
    {"id": "access-recovery", "name": "Access Recovery Assistant", "stage": 4, "status": "planned",
     "description": "Guía de métodos oficiales del fabricante. Sin bypass, cracking ni extracción oculta.",
     "scope": ["Recuperación de cuenta Google / Apple ID", "Respaldos existentes", "Soporte del fabricante"]},
    {"id": "system-repair", "name": "System Repair", "stage": 5, "status": "planned",
     "description": "Reparación de software con herramientas oficiales (sideload OTA, Apple Devices/Finder).",
     "scope": ["Actualización OTA oficial", "Modo recuperación", "Restauración asistida"]},
    {"id": "reset-center", "name": "Factory Reset Assistant", "stage": 5, "status": "planned",
     "description": "Restauración de fábrica con advertencia, confirmación, registro y reporte.",
     "scope": ["Advertencia de pérdida de datos", "Confirmación explícita", "Registro y reporte"]},
    {"id": "reports", "name": "Export and Reports", "stage": 6, "status": "planned",
     "description": "Exportación de reportes de diagnóstico y expedientes (PDF/JSON)."},
]


def list_modules() -> list[dict]:
    return MODULES
