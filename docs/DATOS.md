# Recuperación de datos y respaldos (Etapa 3)

## Fuentes autorizadas

| Fuente | Cómo | Requisito |
|---|---|---|
| Android | `adb pull` de carpetas del almacenamiento compartido (`/sdcard`): DCIM, Imágenes, Películas, Documentos, Descargas, Música, Grabaciones, multimedia de WhatsApp o rutas propias. | Depuración USB autorizada por el titular. |
| Contactos Android | `content query` del proveedor de contactos, convertido a vCard. | Solo si el sistema lo permite al shell; si no, se avisa y se sugiere la exportación del propio teléfono o de la cuenta del titular. |
| iPhone / iPad | Respaldo oficial completo con `idevicebackup2`. | El titular aceptó «Confiar en este equipo». Si tiene el cifrado de respaldos activado, el respaldo queda cifrado con su contraseña (MR Lab no la pide). |
| Importación | Carpeta o `.zip` (Google Takeout, tarjeta SD, respaldos entregados por el titular). | Autorización documentada en el expediente. |

Las carpetas privadas de cada app (`Android/data`, `Android/obb`) no son accesibles por interfaces
autorizadas y se rechazan. Las rutas se validan para impedir salir de `/sdcard` o inyectar comandos.

Todo respaldo exige un **expediente** y una **frase de cifrado** (mínimo 10 caracteres) que MR Lab no guarda.

## Proceso

1. **Inventario previo** (Android): cuenta archivos y tamaño por categoría antes de copiar.
2. **Adquisición** a una carpeta temporal de preparación.
3. **Inventario y huellas**: SHA-256 y categoría de cada archivo (fotografías, videos, documentos,
   contactos, respaldos locales, archivos) por extensión y firma del contenido.
4. **Empaquetado y cifrado**: contenedor `.mrlb` (AES-256-GCM por bloques, clave scrypt) más un
   manifiesto cifrado aparte para explorar sin descifrar todo.
5. **Limpieza**: la carpeta temporal se borra al terminar, al fallar o al cancelar, y al iniciar la app
   se eliminan restos de trabajos interrumpidos.
6. **Registro**: evidencias (inicio, resultado, huella del contenedor, avisos) y operación en el expediente.

Los trabajos corren en segundo plano con progreso y botón **Cancelar**.

## Administrador de respaldos

- **Verificar integridad**: compara la huella SHA-256 del contenedor y autentica cada bloque AES-GCM
  sin escribir texto plano a disco. Detecta alteración, truncado o frase incorrecta.
- **Explorar contenido**: descifra solo el manifiesto y lista archivos con categoría, tamaño, fecha y huella.
- **Exportar** por categorías o archivos seleccionados a `datos/exports/<folio>/…`, comprobando la huella
  de cada archivo y generando `manifiesto-exportacion.json`. La exportación se adjunta a «Archivos
  exportados» del expediente.
- **Eliminar**: requiere escribir `ELIMINAR <id>` y queda en el Registro de evidencias.

## Limitaciones

- Durante el proceso, los datos sin cifrar existen temporalmente en disco (carpeta de preparación) y se
  necesita espacio para el contenedor (aprox. el doble del tamaño de los datos).
- La exportación de contactos depende de lo que permita cada versión de Android.
- El respaldo de Apple se probó con su lógica y parámetros, pero no con un iPhone real en este desarrollo.
