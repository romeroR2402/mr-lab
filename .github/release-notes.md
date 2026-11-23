## Mobile Recovery Lab para Windows

Descarga **MRLab-Setup-*.exe**, ejecútalo y sigue el asistente en español. Pide permisos de administrador para registrar el controlador USB Android.

**Incluye:** servicios locales (no necesitas Python) y el motor Android (adb / fastboot); también el controlador USB Android si estaba disponible al compilar.

**Módulos**
- Resumen, detección y diagnóstico de dispositivos Android y Apple
- Asistente de pantalla dañada con recomendaciones técnicas
- Centro de recuperación de datos y administrador de respaldos cifrados (AES-256-GCM)
- Análisis de recuperación de acceso por vías oficiales, con módulos de análisis extensibles
- Reparación de sistema y restauración de fábrica con plan, confirmación, registro y reporte
- Expedientes, registro de evidencias verificable y reporte final en PDF

**Notas**
- El instalador no está firmado digitalmente, así que Windows SmartScreen puede mostrar «Windows protegió su PC». Pulsa *Más información → Ejecutar de todas formas*.
- Para iPhone/iPad, Windows necesita además la app gratuita *Apple Devices* (MR Lab ofrece un botón para instalarla). El motor Apple (libimobiledevice, LGPL-2.1) se integra al compilar; compruebe en Configuración → Componentes que aparece como «Verificado».
- Página del proyecto: https://romeror2402.github.io/mr-lab/
