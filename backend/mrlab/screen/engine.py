"""Motor del Asistente de pantalla dañada.

Combina las observaciones del técnico (cuestionario) con señales reales del
sistema (escaneo y último diagnóstico) para:
  1. Clasificar el caso (categoría principal + indicadores).
  2. Detectar inconsistencias entre lo observado y lo que reporta el sistema.
  3. Generar recomendaciones técnicas priorizadas.
Si no hay dispositivo conectado (p. ej. sin respuesta), trabaja solo con el cuestionario.
"""
from __future__ import annotations

import json

from .. import cases, db, evidence, scanner
from ..diagnostics import engine as diag_engine
from ..errors import RpcError
from ..util.timeutil import now_iso
from . import questionnaire

CATEGORIES = {
    "visible_touch_ok": "Pantalla visible y táctil funcional",
    "visible_touch_faulty": "Pantalla visible y táctil defectuoso",
    "black_screen": "Pantalla negra",
    "partial_display": "Display parcialmente visible",
    "no_response": "Dispositivo sin respuesta",
    "undetermined": "Sin determinar",
}
USB_STATES = {"online", "unauthorized", "recovery", "sideload", "bootloader", "no_permissions", "connecting"}


# --------------------------------------------------------------------- señales
def _signals(device_key: str | None) -> dict:
    """Señales objetivas del sistema. None = no disponible (no se inventa)."""
    s = {"deviceConnected": False, "usb": None, "authorized": None, "platform": None,
         "displayPower": None, "touchDriver": None, "battery": None, "diagnosticId": None, "commState": None}
    if not device_key:
        return s
    dev = scanner.get_cached(device_key)
    if dev is None:
        return s
    s.update({"deviceConnected": True, "platform": dev.platform, "commState": dev.comm_state,
              "usb": dev.comm_state in USB_STATES, "authorized": dev.auth_state == "authorized"})
    diag = diag_engine.latest_for(dev.serial)
    if diag:
        s["diagnosticId"] = diag.get("id")
        checks = {c["id"]: c for c in diag.get("checks", [])}
        disp, touch, bat = checks.get("display"), checks.get("touch"), checks.get("battery")
        if disp and disp.get("status") != "unavailable":
            s["displayPower"] = (disp.get("data") or {}).get("Estado del display")
        if touch and touch.get("status") != "unavailable":
            s["touchDriver"] = touch.get("status") == "ok"
        if bat and bat.get("status") != "unavailable":
            s["battery"] = bat.get("value")
    return s


# --------------------------------------------------------------- clasificación
def classify(a: dict, s: dict) -> tuple[str, list[dict], list[dict]]:
    """Devuelve (categoría, indicadores, inconsistencias)."""
    notes: list[dict] = []
    alive = a["powers_on"] == "yes" or bool(s["usb"])

    if not alive and a["powers_on"] == "no":
        cat = "no_response"
    elif not alive and a["display"] in ("black", "unknown") and s["deviceConnected"] is False and a["powers_on"] == "unknown":
        cat = "no_response"
    elif a["display"] == "normal":
        cat = "visible_touch_faulty" if a["touch"] in ("partial", "none") or s["touchDriver"] is False else "visible_touch_ok"
    elif a["display"] == "partial":
        cat = "partial_display"
    elif a["display"] == "black":
        cat = "black_screen"
    elif s["displayPower"] == "ON":
        cat = "black_screen"  # sistema activo pero el técnico no pudo valorar la imagen
        notes.append({"level": "info", "text": "Clasificación apoyada en el sistema: el display está encendido pero no se pudo valorar la imagen."})
    else:
        cat = "undetermined"

    # Inconsistencias / evidencias cruzadas
    if a["display"] == "black" and s["displayPower"] == "ON":
        notes.append({"level": "warning", "text": "El sistema reporta el display ENCENDIDO aunque no hay imagen: la placa funciona; "
                                                   "probable falla de panel, flex o retroiluminación."})
    if a["display"] == "black" and a["backlight"] == "yes":
        notes.append({"level": "info", "text": "Hay brillo sin imagen: apunta a panel/LCD dañado más que a la retroiluminación."})
    if a["touch"] == "none" and s["touchDriver"] is True:
        notes.append({"level": "warning", "text": "El controlador táctil está registrado en el sistema pero no responde: "
                                                   "probable digitalizador o flex dañado físicamente."})
    if a["touch"] in ("none", "partial") and s["touchDriver"] is False:
        notes.append({"level": "warning", "text": "El sistema no registra controlador táctil: flex desconectado o falla del controlador."})
    if a["touch"] == "ok" and s["touchDriver"] is False:
        notes.append({"level": "warning", "text": "El técnico reporta táctil funcional pero el sistema no detecta controlador; repita la prueba."})
    if a["powers_on"] == "yes" and s["deviceConnected"] is False:
        notes.append({"level": "info", "text": "Da señales de vida pero no se detecta por USB: revise cable, puerto de carga y controlador."})
    if a["powers_on"] == "no" and s["usb"]:
        notes.append({"level": "warning", "text": "Parece apagado pero responde por USB: el sistema está activo (pantalla sin imagen)."})

    flags = [
        {"id": "usb_available", "label": "Comunicación USB disponible",
         "state": "yes" if s["usb"] else ("no" if s["deviceConnected"] or a["powers_on"] == "no" else "unknown"),
         "detail": ("Autorizado" if s["authorized"] else f"Sin autorización ({s['commState']})") if s["usb"] else
                   "No detectado por el escáner" if s["deviceConnected"] is False else None},
        {"id": "prior_backup", "label": "Respaldo previo disponible",
         "state": {"yes": "yes", "maybe": "probable", "no": "no"}.get(a["backup"], "unknown"),
         "detail": "Declarado por el titular; verificar antes de cualquier operación con pérdida de datos."},
        {"id": "usb_authorized_before", "label": "Autorización USB previa al daño",
         "state": a["usb_debug_before"], "detail": None},
    ]
    return cat, flags, notes


# -------------------------------------------------------------- recomendaciones
def _rec(id, title, priority, category, steps, requirements=None, risks=None, module=None, implemented=None):
    return {"id": id, "title": title, "priority": priority, "category": category, "steps": steps,
            "requirements": requirements or [], "risks": risks or [], "module": module,
            "implemented": implemented}


def recommend(cat: str, a: dict, s: dict) -> list[dict]:
    android = s["platform"] == "android" or (s["platform"] is None)
    apple = s["platform"] == "apple" or (s["platform"] is None)
    recs: list[dict] = []
    data_goal = a["goal"] in ("data", "both")

    # 1. Seguridad
    if a["damage"] == "liquid":
        recs.append(_rec("liquid", "Contacto con líquido: no encender ni cargar", 1, "Seguridad", [
            "No conectar a la corriente ni intentar encender.",
            "Abrir el equipo y desconectar la batería lo antes posible.",
            "Limpiar la placa con alcohol isopropílico (≥99 %) o baño ultrasónico y secar por completo.",
            "Inspeccionar corrosión en conectores de pantalla, batería y carga antes de volver a energizar."],
            risks=["Cortocircuito y daño progresivo por corrosión si se energiza húmedo"]))
    if a["damage"] == "bent":
        recs.append(_rec("battery_check", "Impacto fuerte: revisar la batería antes de trabajar", 1, "Seguridad", [
            "Verificar abombamiento o deformación de la batería.",
            "Si está dañada, no cargarla y sustituirla antes de continuar."],
            risks=["Riesgo de incendio con baterías de litio dañadas"]))

    # 2. Sin respuesta
    if cat == "no_response":
        recs.append(_rec("revive", "Recuperar señales de vida", 2, "Diagnóstico", [
            "Cargar 30 minutos con cargador y cable en buen estado.",
            "Reinicio forzado — Android: Encendido + Bajar volumen 10–15 s. iPhone 8 o posterior: Subir volumen, Bajar volumen y mantener el botón lateral.",
            "Conectar al PC y comprobar en Detección de dispositivos si aparece (aunque sea sin autorizar o en modo recovery).",
            "Medir consumo con un medidor USB: 0 mA sugiere batería/carga; consumo fijo sugiere falla de arranque."],
            module="devices", implemented=True))
        recs.append(_rec("board", "Diagnóstico a nivel de placa", 3, "Reparación", [
            "Probar con batería y conector de carga conocidos.",
            "Medir líneas de alimentación principales y buscar cortos.",
            "Si la placa no arranca, la recuperación de datos depende de reparar la placa (los datos están cifrados y ligados a ella)."],
            risks=["Los datos de teléfonos modernos no se pueden recuperar extrayendo la memoria: están cifrados con claves del propio SoC"]))
        if a["backup"] in ("yes", "maybe"):
            recs.append(_rec("restore_backup_new", "Restaurar el respaldo del titular en otro equipo", 2, "Datos", [
                "Iniciar sesión con la cuenta del titular en un equipo nuevo o de préstamo.",
                "Restaurar desde Google One / iCloud / respaldo local."],
                requirements=["Credenciales de la cuenta del titular"]))
        return sorted(recs, key=lambda r: r["priority"])

    visible = cat in ("visible_touch_ok", "visible_touch_faulty", "partial_display")
    needs_input = cat in ("visible_touch_faulty", "partial_display", "black_screen")

    # 3. Recuperar interacción para que el titular desbloquee y autorice
    if needs_input and android:
        recs.append(_rec("otg_input", "Ratón o teclado por OTG (Android)", 2, "Acceso", [
            "Conectar un adaptador OTG (USB-C/micro-USB a USB-A) con ratón o teclado.",
            "Con imagen: usar el puntero del ratón para desbloquear y aceptar diálogos.",
            "Sin imagen: con teclado, pulsar una tecla para despertar, escribir el PIN del titular y Enter."],
            requirements=["El equipo soporta OTG", "El titular introduce su credencial"],
            risks=["Sin imagen, la entrada es a ciegas: verificar el resultado por USB en Detección de dispositivos"]))
    if cat in ("black_screen", "partial_display") and android:
        recs.append(_rec("video_out", "Salida de video USB-C (Android)", 2, "Acceso", [
            "Comprobar si el modelo soporta DisplayPort Alt Mode (p. ej. Galaxy S/Note, algunos Motorola, Huawei, Sony).",
            "Conectar un adaptador USB-C a HDMI y un monitor.",
            "Combinar con ratón Bluetooth/OTG para operar el equipo desde el monitor."],
            requirements=["Modelo con salida de video por USB-C"]))
    if needs_input and apple:
        recs.append(_rec("apple_av", "Adaptador de video y teclado (iPhone/iPad)", 2, "Acceso", [
            "Conectar un adaptador AV digital Lightning o USB-C a HDMI: replica la pantalla en un monitor.",
            "En modelos con USB-C, un teclado USB permite introducir el código del titular.",
            "Con la imagen en el monitor, el titular desbloquea y acepta 'Confiar en este equipo'."],
            requirements=["Adaptador oficial o compatible", "El titular introduce su código"]))
    if needs_input and a["usb_debug_before"] == "yes" and android:
        recs.append(_rec("mirror", "Duplicación de pantalla en el PC (depuración ya autorizada)", 2, "Acceso", [
            "Si el PC ya estaba autorizado antes del daño, se puede ver y controlar la pantalla desde el PC.",
            "Usar una herramienta de duplicación por ADB (p. ej. scrcpy) para que el titular desbloquee."],
            requirements=["Depuración USB autorizada para este PC antes del daño",
                          "Herramienta de duplicación externa (aún no integrada en MR Lab)"]))
    if cat in ("black_screen", "partial_display", "visible_touch_faulty"):
        recs.append(_rec("donor_screen", "Pantalla temporal (donante)", 3, "Acceso", [
            "Conectar temporalmente un módulo de pantalla compatible, sin montarlo.",
            "El titular desbloquea, autoriza el equipo y se realiza el respaldo.",
            "Desconectar con la batería desconectada."],
            requirements=["Pantalla compatible con el modelo exacto"],
            risks=["Manipular conectores con la batería conectada puede dañar la placa"]))

    # 4. Datos
    if data_goal:
        if s["authorized"]:
            recs.append(_rec("backup_now", "Respaldar ahora: el equipo ya está autorizado", 1, "Datos", [
                "No reiniciar ni desconectar el equipo: la autorización actual permite respaldar.",
                "Ejecutar un respaldo por la interfaz autorizada (ADB o respaldo oficial de Apple)."],
                module="data-recovery", implemented=True))
        else:
            recs.append(_rec("backup_after_access", "Respaldar tras recuperar la interacción", 2, "Datos", [
                "Con alguna de las vías anteriores, el titular desbloquea y autoriza este equipo.",
                "Ejecutar el respaldo por interfaz autorizada antes de reemplazar componentes."],
                module="data-recovery", implemented=True))
        if a["backup"] in ("yes", "maybe"):
            recs.append(_rec("verify_backup", "Verificar el respaldo existente del titular", 2, "Datos", [
                "Confirmar con el titular la fecha y el contenido del último respaldo (Google One / iCloud / PC).",
                "Si es reciente, puede bastar con reparar o sustituir el equipo y restaurarlo."],
                requirements=["Credenciales de la cuenta del titular"]))
    if a["owner_credential"] in ("no", "unknown"):
        recs.append(_rec("access_module", "El titular no recuerda su credencial", 2, "Acceso", [
            "Sin la credencial, los datos cifrados no son accesibles aunque se repare la pantalla.",
            "Ejecutar el Análisis de recuperación de acceso para ver las vías oficiales."],
            module="access-recovery", implemented=True))

    # 5. Reparación
    if cat != "visible_touch_ok" or a["damage"] in ("glass", "panel"):
        steps = ["Reemplazar el módulo de pantalla (display + digitalizador) del modelo exacto.",
                 "Si solo el cristal está roto y el panel funciona, valorar cambio de cristal (requiere equipo de separación)."]
        risks = ["Respaldar antes: abrir el equipo implica riesgo para la placa y la batería"]
        if apple:
            steps.append("En iPhone, completar la configuración de piezas (Repair Assistant / Ajustes > General > Información) "
                         "para conservar True Tone y evitar avisos de pieza desconocida.")
        if android:
            steps.append("En equipos con lector de huella bajo pantalla, recalibrar el sensor tras el reemplazo.")
        recs.append(_rec("replace_screen", "Reemplazo de pantalla", 3 if data_goal else 2, "Reparación", steps, risks=risks))
    if cat == "visible_touch_ok" and a["damage"] == "none":
        recs.append(_rec("no_action", "Pantalla operativa", 4, "Diagnóstico", [
            "La pantalla y el táctil funcionan: el titular puede desbloquear normalmente.",
            "Continuar con el servicio solicitado (diagnóstico, respaldo, etc.)."]))
    return sorted(recs, key=lambda r: r["priority"])


def _summary(cat: str, flags: list[dict], s: dict) -> str:
    usb = next(f for f in flags if f["id"] == "usb_available")["state"]
    parts = [CATEGORIES[cat] + "."]
    if usb == "yes":
        parts.append("El equipo se comunica por USB" + (" y está autorizado." if s["authorized"] else " pero no está autorizado."))
    elif usb == "no":
        parts.append("Sin comunicación USB.")
    return " ".join(parts)


# ------------------------------------------------------------------ operaciones
def assess(answers: dict, device_key: str | None = None, case_id: int | None = None, device_label: str | None = None) -> dict:
    a = questionnaire.validate(answers)
    s = _signals(device_key)
    if device_key and not s["deviceConnected"]:
        raise RpcError("device_not_found", "El dispositivo seleccionado ya no está conectado. Escanee de nuevo o evalúe sin dispositivo.")
    dev = scanner.get_cached(device_key) if device_key else None
    label = dev.label if dev else (device_label or "Dispositivo sin conexión")
    serial = dev.serial if dev else None
    cat, flags, notes = classify(a, s)
    recs = recommend(cat, a, s)
    out = {"timestamp": now_iso(), "deviceKey": device_key, "deviceLabel": label, "deviceSerial": serial,
           "caseId": case_id, "category": cat, "categoryLabel": CATEGORIES[cat], "summary": _summary(cat, flags, s),
           "flags": flags, "notes": notes, "signals": s, "answers": a, "recommendations": recs}
    with db.write() as conn:
        cur = conn.execute("INSERT INTO screen_assessments(timestamp, device_serial, device_label, case_id, category, report_json)"
                           " VALUES(?,?,?,?,?,?)", (out["timestamp"], serial, label, case_id, cat, json.dumps(out, ensure_ascii=False)))
        out["id"] = cur.lastrowid
    evidence.log("Evaluación de pantalla", "success", device_serial=serial, device_label=label, case_id=case_id,
                 details={"evaluación": out["id"], "clasificación": CATEGORIES[cat],
                          "usb": next(f for f in flags if f["id"] == "usb_available")["state"],
                          "recomendaciones": len(recs)})
    if case_id:
        cases.add_operation(case_id, "Evaluación de pantalla", CATEGORIES[cat], "cuestionario + señales", f"Evaluación #{out['id']}")
    return out


def history(device_serial: str | None = None, limit: int = 50) -> list[dict]:
    q = "SELECT id, timestamp, device_serial, device_label, case_id, category FROM screen_assessments"
    args: list = []
    if device_serial:
        q += " WHERE device_serial = ?"
        args.append(device_serial)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(max(1, min(int(limit), 500)))
    with db.read() as conn:
        rows = conn.execute(q, args).fetchall()
    return [{"id": r["id"], "timestamp": r["timestamp"], "deviceSerial": r["device_serial"], "deviceLabel": r["device_label"],
             "caseId": r["case_id"], "category": r["category"], "categoryLabel": CATEGORIES.get(r["category"], r["category"])}
            for r in rows]


def get(assessment_id: int) -> dict:
    with db.read() as conn:
        row = conn.execute("SELECT report_json FROM screen_assessments WHERE id = ?", (assessment_id,)).fetchone()
    if not row:
        raise RpcError("not_found", f"Evaluación {assessment_id} no encontrada")
    out = json.loads(row["report_json"])
    out["id"] = assessment_id
    return out


def latest_for(serial: str) -> dict | None:
    with db.read() as conn:
        row = conn.execute("SELECT id, report_json FROM screen_assessments WHERE device_serial = ? ORDER BY id DESC LIMIT 1",
                           (serial,)).fetchone()
    if not row:
        return None
    out = json.loads(row["report_json"])
    out["id"] = row["id"]
    return out
