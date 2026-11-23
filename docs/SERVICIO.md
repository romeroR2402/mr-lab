# Reparación de sistema y restauración de fábrica (Etapa 5)

## Operaciones

| Operación | Plataforma | Tipo | Impacto | Requisito |
|---|---|---|---|---|
| Reiniciar el sistema | Android | MR Lab ejecuta | Ninguno | adb o fastboot |
| Reiniciar en recovery / bootloader / sideload | Android | MR Lab ejecuta | Ninguno | Autorizado por ADB |
| Instalar OTA oficial (sideload) | Android | MR Lab ejecuta | Ninguno | Modo sideload + paquete OTA oficial |
| Liberar caché del sistema | Android | MR Lab ejecuta | Ninguno | Autorizado por ADB |
| Desinstalar una app de terceros | Android | MR Lab ejecuta | Datos de esa app | Solo apps instaladas por el usuario |
| Arranque en modo seguro | Android | Guiada | Ninguno | — |
| Reinstalar firmware con herramienta oficial | Android | Guiada | Borrado total | Herramienta del fabricante |
| Restablecer desde Ajustes / recovery / Find My Device | Android | Guiada | Borrado total | — |
| Borrado de datos con fastboot (`fastboot -w`) | Android | MR Lab ejecuta | Borrado total | Bootloader **desbloqueado** |
| Entrar en modo recuperación | Apple | MR Lab ejecuta | Ninguno | `ideviceenterrecovery`, dispositivo emparejado |
| Actualizar iOS sin borrar datos | Apple | Guiada | Ninguno | Apple Devices / Finder |
| Borrar contenidos y ajustes / Restaurar / Buscar (iCloud) | Apple | Guiada | Borrado total | — |

Las operaciones **guiadas** existen porque el fabricante no permite hacerlas desde el PC: MR Lab muestra
los pasos oficiales, exige la misma confirmación y registra el resultado declarado por el técnico.

## Protocolo obligatorio

1. **Plan** (`service.plan`): método oficial, comandos exactos, pasos, advertencias y comprobaciones:
   batería (≥ 50 % recomendado), respaldo en MR Lab, FRP / Bloqueo de activación (del último análisis de
   acceso), bootloader desbloqueado (para `fastboot -w`), paquete OTA o app válidos. Si alguna comprobación
   **no cumple**, la operación queda bloqueada.
2. **Confirmación**: casillas de reconocimiento (autorización del titular, ausencia de respaldo, cuenta
   del fabricante, pérdida de datos, paquete oficial…) y una frase escrita, por ejemplo `RESTABLECER 2345`
   (últimos 4 caracteres del identificador). El plan caduca a los 15 minutos y solo se puede usar una vez.
3. **Ejecución o registro** con evidencias: plan, confirmación (con la frase), resultado y salida del comando.
4. **Reporte HTML** en `datos/exports/<folio>/reportes/`, con su SHA-256, adjunto al expediente. Se genera
   también cuando la operación falla.

## Lo que no hace

No elimina FRP ni el Bloqueo de activación, no desbloquea bootloaders y no instala firmware no oficial.
Tras cualquier restablecimiento, el titular necesitará su cuenta Google o Apple ID.
