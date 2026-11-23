# Instalación técnica — Mobile Recovery Lab

## 1. Requisitos

### Estación de trabajo (usuario final)
- Windows 10 22H2 / Windows 11, x64.
- **Android:** Android SDK Platform Tools (adb / fastboot) y el controlador USB del fabricante
  (Google USB Driver, Samsung USB Driver, etc.).
- **Apple:** app **Apple Devices** (Microsoft Store) o **iTunes**, que instalan el servicio
  *Apple Mobile Device Service* y sus controladores, y binarios de **libimobiledevice** para Windows
  (`idevice_id`, `ideviceinfo`, `idevicepair`, `idevicediagnostics`, `idevicebackup2`).

Las herramientas pueden incluirse en el instalador (ver `resources/tools/README.md`) o
instalarse aparte y configurarse en **Settings**. MR Lab las busca en este orden:
1. Ruta configurada en Settings.
2. `resources/tools` del instalador.
3. `PATH` del sistema.
4. `%LOCALAPPDATA%\Android\Sdk\platform-tools`, `%ANDROID_SDK_ROOT%`, `%ANDROID_HOME%`, `C:\platform-tools`.

La pantalla **Settings → Herramientas detectadas** muestra qué se encontró, la ruta y la versión.

### Equipo de desarrollo
- Node.js 20 o superior y npm.
- Python 3.11 o superior (probado con 3.13).
- Git.

## 2. Ejecución en modo desarrollo

```powershell
git clone <repo> mr-lab
cd mr-lab
npm install
python -m pip install -r backend\requirements.txt
npm run dev
```

`npm run dev` inicia Vite (interfaz), compila el proceso principal en modo *watch* y abre Electron.
El backend se lanza como `python -m mrlab` desde `backend/`. Para usar otro intérprete:
`set MRLAB_PYTHON=C:\ruta\python.exe`.

Pruebas del backend:

```powershell
npm run test:backend
```

Verificación de tipos del frontend:

```powershell
npm run typecheck
```

## 3. Generar el instalador de Windows

En una máquina Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```

El script:
1. Crea `backend\.venv` e instala `cryptography` y `pyinstaller`.
2. Ejecuta las pruebas del backend.
3. Congela el backend en `backend\dist\mrlab-backend\mrlab-backend.exe` (PyInstaller; Electron lo inicia con la consola oculta).
4. Compila Electron/React y genera `release\MRLab-Setup-<versión>.exe` (NSIS, x64).

El instalador permite elegir carpeta, crea accesos directos y **no** borra los datos del usuario al desinstalar.
Para distribuir en producción se recomienda firmar el ejecutable (variables `CSC_LINK` y
`CSC_KEY_PASSWORD` de electron-builder) para evitar advertencias de SmartScreen.

## 4. Datos locales

Todos los datos permanecen en el equipo, en `%APPDATA%\Mobile Recovery Lab\data\`:

| Archivo / carpeta | Contenido |
|---|---|
| `mrlab.sqlite3` | Expedientes, dispositivos vistos, reportes de diagnóstico, registro de evidencias, ajustes. |

Respaldar esta carpeta conserva todo el historial. MR Lab no envía datos a servicios externos.

## 5. Preparación de dispositivos

**Android**
1. Ajustes → Acerca del teléfono → tocar 7 veces "Número de compilación".
2. Opciones de desarrollador → activar "Depuración USB".
3. Conectar por USB y aceptar la huella RSA del equipo en la pantalla del dispositivo.
   Si la pantalla no funciona, la autorización no puede completarse desde MR Lab: el
   Screen Recovery Assistant (Etapa 2) documentará alternativas (OTG, salida de video).

**Apple**
1. Desbloquear el dispositivo (el titular).
2. Pulsar "Confiar" en el diálogo "¿Confiar en este equipo?" e introducir el código en el propio dispositivo.

## 6. Solución de problemas

| Síntoma | Causa probable / acción |
|---|---|
| "adb no disponible" | Instale Platform Tools o configure la ruta en Settings. |
| Dispositivo "Sin autorizar" | Acepte el diálogo de depuración USB; revoque autorizaciones y reconecte si no aparece. |
| Dispositivo "Sin permisos USB" | Falta el controlador USB del fabricante (Windows) o reglas udev (Linux). |
| Dispositivo Apple "No emparejado" / "Bloqueado" | El titular debe desbloquear y confiar en el equipo. |
| Servicio Apple inactivo | Instale/abra Apple Devices o iTunes; verifique el servicio en `services.msc`. |
| "Backend no disponible" | En desarrollo, verifique Python en PATH o `MRLAB_PYTHON`. En el instalador, reinstale. |
