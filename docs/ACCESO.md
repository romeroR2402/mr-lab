# Módulo de análisis y recuperación de acceso

Analiza **cómo** está protegido un dispositivo y **qué vías oficiales** existen para que su
titular recupere el acceso. Es de solo lectura y no evade ninguna protección.

## Qué hace

| Función | Implementación |
|---|---|
| Identificar mecanismos de autenticación | Presencia (nunca el valor) de bloqueo de pantalla, FRP/cuenta Google, MDM/Device Owner, biometría; en Apple: código, bloqueo de activación, supervisión. Fuentes: `adb` (getprop, locksettings, dumpsys), `fastboot getvar`, lockdownd (`ideviceinfo`). |
| Restricciones del SO y hardware | Cifrado (FBE/FDE, Secure Enclave), arranque verificado/AVB, bootloader, parche de seguridad, cifrado de respaldos, bloqueo de activación. Cada una con severidad (incluida **bloqueante**). |
| Vías de recuperación | Catálogo de procedimientos oficiales (recuperación de cuenta Google / Apple ID, Find My, restauración oficial, respaldos, MDM, soporte del fabricante, asistencia por OTG/video) evaluado contra el estado del dispositivo: aplicabilidad, pérdida de datos, requisitos, pasos, advertencias y fuente oficial. |
| Pantalla/táctil dañados | Plugin integrado *Escenarios con interacción comprometida*: combina diagnóstico, comunicación y autorización para clasificar el escenario y proponer apoyos para que el titular use su propia credencial. |
| Compatibilidad | Motor declarativo de procedimientos con precondiciones (`compat.py`). Evalúa sin ejecutar: Compatible / Incompatible / Sin determinar. |
| Documentación | Cada análisis se guarda (tabla `access_analyses`), se registra en el Registro de evidencias y, si se vincula, en las operaciones del expediente. |
| Extensibilidad | Plugins de análisis independientes y procedimientos de compatibilidad registrables. |

## Lo que no hace (por diseño)

No obtiene ni prueba códigos, no descifra datos, no elimina FRP ni bloqueo de activación,
no explota vulnerabilidades y no extrae datos sin autorización. Esto no es solo una norma:
`access/policy.py` lo aplica en el código.

## Barreras de política (`backend/mrlab/access/policy.py`)

1. **Capacidades permitidas** (lista blanca): `inspect_auth`, `inspect_restrictions`,
   `inspect_encryption`, `evaluate_recovery`, `evaluate_compat`, `document`, `read_diagnostics`.
   Cualquier otra se rechaza.
2. **Revisión de texto**: el código fuente del plugin se revisa *antes de ejecutarlo*; si describe
   evasión, descifrado, fuerza bruta o extracción no autorizada se rechaza sin ejecutarse. Los
   hallazgos que produzca un plugin también se filtran.
3. **Contexto de solo lectura**: el plugin recibe una copia de los datos ya leídos; no recibe
   conectores ni puede ejecutar comandos sobre el dispositivo a través de MR Lab.
4. **Aislamiento**: tiempo límite de 10 s y errores contenidos.
5. **Habilitación explícita**: los plugins externos inician deshabilitados.

> Limitación honesta: los plugins son código Python que se ejecuta dentro del proceso de servicios.
> Las barreras impiden registrar o activar módulos con funciones prohibidas a través de MR Lab,
> pero no son un sandbox de seguridad. La carpeta de plugins debe estar controlada por el
> responsable del laboratorio.

## Crear un plugin de análisis

Copie un archivo `.py` en la carpeta indicada en *Recuperación de acceso → Módulos*
(`%APPDATA%\Mobile Recovery Lab\data\access_plugins\`), pulse **Recargar** y habilítelo.

```python
MANIFEST = {
    "id": "bateria-servicio",
    "name": "Bateria apta para servicio",
    "version": "1.0.0",
    "author": "Laboratorio",
    "description": "Indica si la bateria permite procedimientos largos (restauracion oficial).",
    "capabilities": ["read_diagnostics", "evaluate_compat", "document"],
    "platforms": ["android", "apple"],
}

def analyze(ctx):
    # ctx: platform, device, properties, diagnostic, mechanisms, restrictions (copia de solo lectura)
    bat = next((c for c in (ctx.get("diagnostic") or {}).get("checks", []) if c["id"] == "battery"), None)
    if not bat or not bat.get("value"):
        return []
    level = int(bat["value"].rstrip("%"))
    if level < 30:
        return [{"title": "Cargar antes de restaurar", "severity": "medium",
                 "detail": f"Nivel {level}%: una restauracion oficial interrumpida puede dejar el equipo sin arrancar."}]
    return [{"title": "Bateria suficiente para servicio", "severity": "info", "data": {"Nivel": bat["value"]}}]
```

Cada hallazgo: `title` (obligatorio), `severity` (`info|low|medium|high`), `detail`, `data` (dict).

## Registrar un procedimiento de compatibilidad

```python
from mrlab.access.compat import Procedure, register, _comm, _platform

register(Procedure("mi_procedimiento", "Nombre del procedimiento oficial", ["android"], [
    ("platform", "Plataforma Android", _platform("android")),
    ("comm", "Comunicación USB", _comm),
]))
```

## RPC

| Método | Descripción |
|---|---|
| `access.analyze {deviceKey, caseId?}` | Ejecuta y guarda un análisis |
| `access.history {deviceSerial?}` / `access.get {id}` | Consultar análisis guardados |
| `access.procedures` | Procedimientos de compatibilidad registrados |
| `access.plugins` / `access.setPlugin {id, enabled}` | Listar y habilitar módulos de análisis |
