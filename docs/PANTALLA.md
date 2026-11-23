# Asistente de pantalla dañada (Etapa 2)

Clasifica un equipo con pantalla o táctil dañados y genera un plan técnico priorizado.

## Entradas

1. **Cuestionario del técnico** (`backend/mrlab/screen/questionnaire.py`): señales de encendido,
   estado de la imagen, retroiluminación, táctil, daño físico, autorización USB previa al daño,
   respaldo previo, si el titular conoce su credencial y objetivo del cliente. El esquema se sirve
   a la interfaz: añadir una pregunta solo requiere editar ese archivo.
2. **Señales del sistema** (si el equipo está conectado): comunicación y autorización USB del escaneo,
   estado del display, controlador táctil y batería del último diagnóstico. Si una señal no existe
   se muestra «No disponible»; nunca se inventa.

El modo **Sin conexión** evalúa equipos que no aparecen en el escaneo (por ejemplo, sin respuesta).

## Clasificación

| Categoría | Criterio principal |
|---|---|
| Pantalla visible y táctil funcional | Imagen completa y táctil OK (y controlador registrado) |
| Pantalla visible y táctil defectuoso | Imagen completa; táctil parcial/nulo o sin controlador en el sistema |
| Display parcialmente visible | Zonas negras, líneas o manchas |
| Pantalla negra | Sin imagen con señales de vida o comunicación USB |
| Dispositivo sin respuesta | Sin señales de vida y sin comunicación USB |
| Sin determinar | Información insuficiente |

Indicadores adicionales: **Comunicación USB disponible**, **Respaldo previo disponible** y
**Autorización USB previa al daño**.

Las señales del sistema prevalecen sobre la percepción: un equipo «apagado» que responde por USB
se clasifica como pantalla negra. Las incoherencias se muestran en «Observación vs. sistema»
(por ejemplo, display encendido sin imagen → falla de panel/flex, no de placa).

## Recomendaciones

Priorizadas (inmediata, alta, media, baja) y agrupadas en Seguridad, Diagnóstico, Acceso, Datos y Reparación:
líquido y batería dañada primero; reanimación y diagnóstico de placa; OTG, salida de video USB-C,
adaptador AV en iPhone, duplicación si la depuración ya estaba autorizada, pantalla donante;
respaldo inmediato si el equipo ya está autorizado; verificación del respaldo del titular;
enlace al análisis de acceso si el titular no recuerda su credencial; y reemplazo de pantalla
(con configuración de piezas en iPhone y recalibración de huella en Android).

Toda vía de acceso supone que **el titular introduce su propia credencial**.

## RPC

`screen.questionnaire`, `screen.assess {answers, deviceKey?, deviceLabel?, caseId?}`,
`screen.history {deviceSerial?}`, `screen.get {id}`. Cada evaluación se guarda en
`screen_assessments`, queda en el Registro de evidencias y en el expediente vinculado.
