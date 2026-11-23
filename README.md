# Mobile Recovery Lab (MR Lab)

Estación de trabajo técnica para Windows destinada al diagnóstico de dispositivos móviles,
recuperación de información accesible por interfaces autorizadas, administración de respaldos
y gestión de expedientes con registro de evidencias.

> **Principio de diseño:** MR Lab solo usa interfaces oficiales y autorizadas por el titular
> (depuración USB aceptada, "Confiar en este equipo", respaldos oficiales). No implementa
> evasión de autenticación, bypass de cifrado, cracking de contraseñas ni extracción oculta,
> y nunca simula resultados: lo que no está implementado se indica como tal.

## Estado (Etapas 1–6 completas)

| Módulo | Estado |
|---|---|
| Resumen (panel principal) | ✅ Implementado |
| Detección de dispositivos (motores Android y Apple) | ✅ Implementado |
| Diagnóstico de dispositivos (Android, bootloader, Apple) | ✅ Implementado |
| Registro de evidencias (solo inserción + cadena SHA-256) | ✅ Implementado |
| Componentes integrados y modo autónomo | ✅ Implementado |
| Gestión de expedientes | ✅ Implementado |
| Administrador de respaldos (verificar, explorar, exportar, eliminar) | ✅ Implementado |
| Asistente de pantalla dañada (clasificación + recomendaciones) | ✅ Implementado |
| Centro de recuperación de datos (Android ADB, Apple, importación) | ✅ Implementado |
| Análisis y recuperación de acceso (mecanismos, restricciones, vías oficiales, compatibilidad, plugins) | ✅ Implementado |
| Reparación de sistema / Restauración de fábrica (plan, confirmación, registro y reporte) | ✅ Implementado |
| Exportación y reportes (PDF y JSON del expediente) | ✅ Implementado |

**Plataforma autónoma:** el instalador incluye sus propios motores y controladores, verificados por
SHA-256; el técnico solo instala MR Lab. Detalles y límites en [docs/AUTONOMIA.md](docs/AUTONOMIA.md).

## Instalar en Windows

Descarga `MRLab-Setup-<versión>.exe` desde [Releases](https://github.com/romeroR2402/mr-lab/releases/latest) y ejecútalo.

## Inicio rápido (desarrollo)

```bash
npm install
pip install -r backend/requirements.txt
npm run dev
```

Documentación:

- [docs/INSTALL.md](docs/INSTALL.md) — instalación, requisitos y generación del instalador de Windows.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — arquitectura, protocolo RPC, base de datos y seguridad.
- [docs/AUTONOMIA.md](docs/AUTONOMIA.md) — componentes integrados y qué no puede eliminarse.
- [docs/REPORTES.md](docs/REPORTES.md) — reportes del expediente en PDF y JSON.
- [docs/SERVICIO.md](docs/SERVICIO.md) — reparación de sistema y restauración de fábrica.
- [docs/DATOS.md](docs/DATOS.md) — recuperación de datos y respaldos cifrados.
- [docs/PANTALLA.md](docs/PANTALLA.md) — asistente de pantalla dañada.
- [docs/ACCESO.md](docs/ACCESO.md) — módulo de análisis de acceso y guía de plugins.
- [docs/ROADMAP.md](docs/ROADMAP.md) — plan por etapas.

**Página del proyecto:** https://romeror2402.github.io/mr-lab/
