# Arquitectura — Mobile Recovery Lab

```
┌───────────────────────────── Electron ─────────────────────────────┐
│  Renderer (React + TS + Tailwind)     sandbox, contextIsolation    │
│        │  window.mrlab.rpc(method, params)                         │
│  Preload (contextBridge) ── IPC "rpc" ──▶ Main process (TS)        │
│                                          BackendBridge             │
└──────────────────────────────────────────┬─────────────────────────┘
                                           │ stdio, JSON por línea
┌──────────────────────────── Backend Python ────────────────────────┐
│  rpc.Server (ThreadPool) ─▶ servicios: scanner, diagnostics,       │
│                             cases, evidence, settings, tools       │
│  connectors/  android.py (adb, fastboot) · apple.py (libimobiledev)│
│  db.py  SQLite (WAL, migraciones)   crypto.py  AES-256-GCM         │
└────────────────────────────────────────────────────────────────────┘
```

## Estructura

```
src/
  main/        Proceso principal: ventana, IPC, ciclo de vida del backend (backend.ts)
  preload/     API mínima expuesta al renderer (window.mrlab)
  shared/      Tipos y contrato RPC compartidos (types.ts)
  renderer/    Interfaz React: pages/, components/, lib/
backend/
  mrlab/
    rpc.py           Servidor JSON-RPC y tabla de métodos
    connectors/      Integraciones con herramientas externas (sin lógica de UI)
    diagnostics/     Motores de diagnóstico por plataforma + persistencia de reportes
    scanner.py       Agregación de conectores y registro de detecciones
    cases.py         Expedientes
    evidence.py      Registro de evidencias encadenado
    crypto.py        Cifrado de respaldos
    tools.py         Resolución de herramientas (personalizada → integrada → sistema)
    components.py    Verificación SHA-256 de los componentes integrados
    modules.py       Estado de implementación de cada módulo
  tests/             Pruebas unitarias y de integración (adb falso solo para pruebas)
```

## Protocolo backend

Petición (una línea): `{"id": 7, "method": "diagnostics.run", "params": {"deviceKey": "android:R58..."}}`
Respuesta: `{"id": 7, "result": {...}}` o `{"id": 7, "error": {"code": "device_not_found", "message": "..."}}`
Al iniciar, el backend emite `{"event": "ready"}`. El proceso principal aplica timeouts por método,
rechaza llamadas pendientes si el backend termina y lo reinicia automáticamente (máx. 5 veces).

| Método | Descripción |
|---|---|
| `system.health`, `system.modules` | Versión, rutas, esquema; estado de los módulos |
| `tools.detect` | Herramientas, origen y autonomía (cache 30 s; `force: true` para refrescar) |
| `components.status` | Integridad de los componentes integrados |
| `settings.get`, `settings.update` | Ajustes (lista blanca de claves) |
| `devices.scan`, `devices.last`, `devices.known` | Escaneo de dispositivos |
| `diagnostics.run`, `.history`, `.get` | Diagnóstico y reportes |
| `dashboard.summary` | Datos agregados del Overview |
| `cases.list`, `.get`, `.create`, `.updateStatus` | Expedientes |
| `evidence.list`, `evidence.verify` | Registro de evidencias e integridad |
| `screen.classify`, `recovery.start`, `backup.create`, `repair.start`, `reset.prepare`, `reports.export` | Responden `not_implemented` con la etapa planificada |

## Base de datos (SQLite)

Migraciones versionadas con `PRAGMA user_version` (`db.MIGRATIONS`). Tablas: `settings`, `devices`,
`cases`, `case_operations`, `case_files`, `evidence_log`, `diagnostic_reports`.

**Evidence Log:** triggers impiden `UPDATE` y `DELETE`. Cada entrada guarda `prev_hash` y
`entry_hash = SHA-256(prev_hash + JSON canónico de la entrada)`. `evidence.verify` recalcula la
cadena y señala la primera entrada alterada. Se registran automáticamente: detección y
desconexión de dispositivos, diagnósticos (éxito o falla), apertura y cambios de expedientes.

## Seguridad

- Renderer con `sandbox`, `contextIsolation`, sin `nodeIntegration`, CSP estricta, navegación externa bloqueada.
- El IPC solo acepta nombres de método con formato `dominio.metodo`; el backend valida parámetros.
- Procesos externos se ejecutan sin shell, con argumentos en lista y timeout.
- **Credenciales:** no hay campos para códigos de acceso; `settings` rechaza claves con nombres
  de credenciales; la UI advierte no registrarlos.
- **Respaldos cifrados** (`crypto.py`): scrypt (N=2^15, r=8, p=1) → clave AES-256; AES-GCM por
  bloques de 1 MiB con nonce = prefijo aleatorio + contador y AAD con encabezado, índice y marca
  de último bloque (detecta alteración, reordenamiento y truncado). La frase de paso no se guarda.
- Apertura de expediente exige confirmación explícita de autorización del titular.

## Agregar un conector o módulo

1. Conector: clase en `backend/mrlab/connectors/` con `available` y `list_devices() -> (list[Device], errores)`;
   registrarla en `scanner.scan()`.
2. Método RPC: función de servicio + entrada en `rpc.METHODS`; tipo en `src/shared/types.ts → RpcMethods`.
3. UI: página en `src/renderer/pages/`, entrada en `components/Sidebar.tsx` y en `App.tsx`.
4. Actualizar `modules.py` (estado) y añadir pruebas en `backend/tests/`.
