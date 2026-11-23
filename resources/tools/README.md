# Herramientas redistribuibles (opcional)

Coloque aquí herramientas externas para incluirlas en el instalador. MR Lab las
busca en `resources/tools` antes que en el `PATH`:

```
resources/tools/
  platform-tools/      adb.exe, fastboot.exe, AdbWinApi.dll, AdbWinUsbApi.dll
  libimobiledevice/    idevice_id.exe, ideviceinfo.exe, idevicepair.exe, idevicediagnostics.exe, idevicebackup2.exe (+ DLLs)
```

Revise la licencia de cada herramienta antes de redistribuirla (Android SDK
Platform Tools tiene términos propios de Google; libimobiledevice es LGPL-2.1).
Si no se incluyen, el técnico puede instalarlas y configurar su ruta en **Settings**.
