# Autonomía de la plataforma

Objetivo: que el técnico instale **solo MR Lab** y la estación funcione completa,
sin instalar Python, Android SDK, libimobiledevice ni otras herramientas por separado.

## Qué integra MR Lab en su instalador

| Componente | Cómo se integra | Resultado para el técnico |
|---|---|---|
| Servicios locales (backend) | Python congelado con PyInstaller (`mrlab-backend.exe`) | No necesita Python |
| Motor Android (adb / fastboot) | `scripts/fetch_components.py` lo descarga del repositorio oficial de Google, lo verifica y lo empaqueta | No necesita Android SDK |
| Controlador USB Android (WinUSB) | Empaquetado y registrado por el instalador con `pnputil` | No necesita instalar controladores aparte (dispositivos compatibles con el controlador genérico de Google) |
| Motor Apple (libimobiledevice, LGPL) | Empaquetado desde una compilación Windows validada (`--local` o URL en `components/manifest.json`) | No necesita instalar libimobiledevice |
| Base de datos, cifrado, reportes | SQLite y `cryptography` dentro del backend | Nada que instalar |

### Verificación de integridad
Al compilar se genera `resources/tools/components.json` con el SHA-256 de cada archivo.
En cada inicio la app lo verifica: un componente **alterado** o **incompleto** se bloquea y no se ejecuta.
La pantalla *Configuración → Componentes integrados* muestra el estado y el origen de cada herramienta:
**Integrado**, **Ruta personalizada** o **Externo (sistema)**.

### Modo autónomo
*Configuración → Modo autónomo* obliga a usar solo componentes integrados y verificados,
ignorando cualquier herramienta instalada en el sistema. Recomendado en producción.

## Lo que no puede eliminarse (y por qué)

1. **Servicio USB de Apple en Windows.** Windows solo puede hablar con un iPhone/iPad por USB
   mediante el controlador y el servicio *Apple Mobile Device Service* de Apple, cuya licencia no
   permite redistribuirlos. MR Lab lo detecta y ofrece un botón **Instalar** que abre la app oficial
   *Apple Devices* en Microsoft Store (gratuita, una sola vez por equipo).
   Alternativa técnica posible (no implementada): un usbmuxd propio con libusb + WinUSB, que
   reemplaza el controlador de Apple y deja de funcionar con Apple Devices/iTunes.
2. **Controladores de algunos fabricantes.** Ciertos Android (p. ej. Samsung) requieren su
   controlador OEM; Windows Update suele instalarlo al conectar el equipo.
3. **Servicios del fabricante.** Activación, recuperación de cuentas Google/Apple ID y firma de
   firmware para restauraciones dependen de servidores de Google/Apple. Sustituirlos implicaría
   evadir protecciones de seguridad, lo cual MR Lab no hace.

## Licencias
- adb/fastboot: código fuente AOSP bajo Apache-2.0. Los binarios oficiales de Google están sujetos
  a los términos de Android SDK; para distribución comercial se recomienda revisión legal o compilar
  adb desde AOSP.
- libimobiledevice: LGPL-2.1 — distribuir como DLL/EXE separados (como se hace) y acompañar la licencia.
