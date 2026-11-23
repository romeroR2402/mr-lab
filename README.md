# Mobile Recovery Lab (MR Lab)

Estación de trabajo técnica para Windows destinada al diagnóstico de dispositivos móviles,
recuperación de información accesible por interfaces autorizadas, administración de respaldos
y gestión de expedientes con registro de evidencias.

> **Principio de diseño:** MR Lab solo usa interfaces oficiales y autorizadas por el titular
> (depuración USB aceptada, "Confiar en este equipo", respaldos oficiales). No implementa
> evasión de autenticación, bypass de cifrado, cracking de contraseñas ni extracción oculta,
> y nunca simula resultados: lo que no está implementado se indica como tal.

## Estado (Etapa 1)

| Módulo | Estado |
|---|---|
| Dashboard | ✅ Implementado |
| Device Scanner (adb, fastboot, libimobiledevice) | ✅ Implementado |
| Device Diagnostic (Android, bootloader, Apple) | ✅ Implementado |
| Evidence Log (solo inserción + cadena SHA-256) | ✅ Implementado |
| Case Management | 🟡 Parcial (falta adjuntar archivos exportados) |
| Backup Manager | 🟡 Motor de cifrado AES-256-GCM listo; gestión pendiente |
| Screen Recovery Assistant | ⏳ Etapa 2 |
| Data Recovery Center | ⏳ Etapa 3 |
| Access Recovery Assistant | ⏳ Etapa 4 |
| System Repair / Factory Reset Assistant | ⏳ Etapa 5 |
| Export and Reports | ⏳ Etapa 6 |

## Inicio rápido (desarrollo)

```bash
npm install
pip install -r backend/requirements.txt
npm run dev
```

Documentación:

- [docs/INSTALL.md](docs/INSTALL.md) — instalación, requisitos y generación del instalador de Windows.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — arquitectura, protocolo RPC, base de datos y seguridad.
- [docs/ROADMAP.md](docs/ROADMAP.md) — plan por etapas.
