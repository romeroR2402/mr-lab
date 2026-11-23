# Exportación y reportes (Etapa 6)

En **Expedientes → (expediente) → Reporte del expediente** se elige qué secciones incluir y se pulsa
**Generar PDF**. MR Lab:

1. Reúne los datos del expediente (`reports.build`): autorización y operaciones, diagnósticos, evaluaciones
   de pantalla, análisis de acceso, respaldos (sin la frase de cifrado), operaciones de servicio,
   archivos exportados y el registro de evidencias con el resultado de su verificación de integridad.
2. Genera un HTML autocontenido y un **JSON** con los mismos datos en `datos/exports/<folio>/reportes/`.
3. Electron convierte el HTML en **PDF A4** con numeración de páginas (motor de Chromium, sin dependencias
   externas ni JavaScript activo durante la conversión).
4. Registra el PDF y el JSON en «Archivos exportados» del expediente con su SHA-256, y deja constancia en
   el Registro de evidencias.

El reporte incluye espacio para la firma del técnico y del titular. Todo el contenido se escapa: un texto
introducido en el expediente no puede inyectar código en el documento.

Otros reportes que ya generan los módulos:
- **Operaciones de servicio**: un HTML por operación (Etapa 5).
- **Exportaciones de respaldo**: `manifiesto-exportacion.json` con la huella de cada archivo (Etapa 3).
