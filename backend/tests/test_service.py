import os
from pathlib import Path

from mrlab import cases, evidence, jobs, rpc, settings
from mrlab.errors import RpcError

from .helpers import TempDbCase

TOOLS = Path(__file__).parent / "fake_tools"


class ServiceTests(TempDbCase):
    def setUp(self):
        super().setUp()
        if os.name == "nt":
            self.skipTest("herramientas falsas requieren shebang POSIX")
        os.environ["FAKE_SIDELOAD"] = "1"
        self.fblog = Path(self.tmp.name) / "fastboot.log"
        os.environ["FAKE_FB_LOG"] = str(self.fblog)
        settings.update({"adbPath": str(TOOLS / "adb"), "fastbootPath": str(TOOLS / "fastboot"), "technicianName": "Ana"})
        self.srv = rpc.Server()
        self.devs = {d["serial"]: d for d in self.call("devices.scan")["devices"]}
        self.case = cases.create({"deviceType": "android", "reason": "Bucle de arranque", "authorizationType": "owner",
                                  "authorizedBy": "Titular", "authorizationConfirmed": True})

    def tearDown(self):
        for k in ("FAKE_SIDELOAD", "FAKE_FB_LOG", "FAKE_FB_UNLOCKED"):
            os.environ.pop(k, None)
        super().tearDown()

    def call(self, method, **params):
        r = self.srv.handle({"id": 1, "method": method, "params": params})
        if "error" in r:
            raise RpcError(r["error"]["code"], r["error"]["message"])
        return r["result"]

    def key(self, serial):
        return self.devs[serial]["key"]

    def test_availability_by_mode(self):
        ops = {o["id"]: o for o in self.call("service.operations", deviceKey=self.key("R58N12ABCDE"))["operations"]}
        self.assertTrue(ops["android_reboot_recovery"]["available"])
        self.assertFalse(ops["android_fastboot_wipe"]["available"])  # no está en bootloader
        self.assertFalse(ops["android_ota_sideload"]["available"])
        self.assertTrue(ops["android_reset_settings"]["available"])  # guiada
        fb = {o["id"]: o for o in self.call("service.operations", deviceKey=self.key("FB0012345"))["operations"]}
        self.assertTrue(fb["android_fastboot_wipe"]["available"])
        self.assertFalse(fb["android_reboot_recovery"]["available"])
        unauth = {o["id"]: o for o in self.call("service.operations", deviceKey=self.key("ZY22XXXXXX"))["operations"]}
        self.assertIn("autorizado", unauth["android_trim_caches"]["unavailableReason"])

    def test_case_required(self):
        with self.assertRaises(RpcError) as c:
            self.call("service.plan", deviceKey=self.key("R58N12ABCDE"), opId="android_reboot_recovery")
        self.assertEqual(c.exception.code, "case_required")

    def test_factory_reset_flow(self):
        plan = self.call("service.plan", deviceKey=self.key("FB0012345"), opId="android_fastboot_wipe", caseId=self.case["id"])
        self.assertFalse(plan["blocked"])
        self.assertEqual(plan["confirmationPhrase"], "RESTABLECER 2345")
        checks = {c["id"]: c for c in plan["checks"]}
        self.assertEqual(checks["bootloader"]["result"], "pass")
        self.assertEqual(checks["backup"]["result"], "warn")
        acks = [a["id"] for a in plan["acknowledgements"]]
        for a in ("authorized", "no_backup", "account", "data_loss"):
            self.assertIn(a, acks)
        self.assertTrue(any("Se borrarán TODOS" in w for w in plan["operation"]["warnings"]))

        with self.assertRaises(RpcError) as c:  # faltan reconocimientos
            self.call("service.execute", planId=plan["planId"], confirmation="RESTABLECER 2345", acknowledged=["authorized"])
        self.assertEqual(c.exception.code, "ack_required")
        with self.assertRaises(RpcError) as c:  # frase incorrecta
            self.call("service.execute", planId=plan["planId"], confirmation="si", acknowledged=acks)
        self.assertEqual(c.exception.code, "confirmation_required")
        self.assertFalse(self.fblog.exists() and "-w" in self.fblog.read_text(), "no debe ejecutarse sin confirmación")

        job = self.call("service.execute", planId=plan["planId"], confirmation="RESTABLECER 2345", acknowledged=acks)
        res = jobs.wait(job["id"])
        self.assertEqual(res["status"], "done", res)
        self.assertIn("-s FB0012345 -w", self.fblog.read_text())
        report = Path(res["result"]["report"])
        html = report.read_text(encoding="utf-8")
        for text in ("Borrado de datos con fastboot", "fastboot -w", "RESTABLECER 2345", "Se borrarán TODOS", "Completada"):
            self.assertIn(text, html)
        with self.assertRaises(RpcError):  # el plan no se puede reutilizar
            self.call("service.execute", planId=plan["planId"], confirmation="RESTABLECER 2345", acknowledged=acks)
        hist = self.call("service.history", caseId=self.case["id"])
        self.assertEqual((hist[0]["status"], hist[0]["impact"]), ("success", "full_wipe"))
        detail = cases.get(self.case["id"])
        self.assertTrue(any(f["path"] == str(report) for f in detail["files"]))
        ops = [e["operation"] for e in evidence.list_entries()["entries"]]
        for op in ("Plan de operación de servicio", "Operación de servicio confirmada",
                   "Operación de servicio: Borrado de datos con fastboot", "Reporte de operación generado"):
            self.assertIn(op, ops)
        self.assertTrue(evidence.verify_chain()["valid"])

    def test_locked_bootloader_blocks_wipe(self):
        os.environ["FAKE_FB_UNLOCKED"] = "no"
        plan = self.call("service.plan", deviceKey=self.key("FB0012345"), opId="android_fastboot_wipe", caseId=self.case["id"])
        self.assertTrue(plan["blocked"])
        with self.assertRaises(RpcError) as c:
            self.call("service.execute", planId=plan["planId"], confirmation=plan["confirmationPhrase"],
                      acknowledged=[a["id"] for a in plan["acknowledgements"]])
        self.assertEqual(c.exception.code, "blocked")

    def test_uninstall_only_third_party(self):
        self.assertEqual(self.call("service.packages", deviceKey=self.key("R58N12ABCDE")), ["com.example.juego", "com.whatsapp"])
        bad = self.call("service.plan", deviceKey=self.key("R58N12ABCDE"), opId="android_uninstall_app",
                        caseId=self.case["id"], params={"package": "com.android.systemui"})
        self.assertTrue(bad["blocked"])
        plan = self.call("service.plan", deviceKey=self.key("R58N12ABCDE"), opId="android_uninstall_app",
                         caseId=self.case["id"], params={"package": "com.example.juego"})
        self.assertEqual(plan["confirmationPhrase"], "DESINSTALAR com.example.juego")
        res = jobs.wait(self.call("service.execute", planId=plan["planId"], confirmation="DESINSTALAR com.example.juego",
                                  acknowledged=[a["id"] for a in plan["acknowledgements"]])["id"])
        self.assertEqual(res["status"], "done", res)

    def test_ota_sideload_progress(self):
        ota = Path(self.tmp.name) / "ota-oficial.zip"
        ota.write_bytes(b"PK\x03\x04" + b"0" * 2048)
        plan = self.call("service.plan", deviceKey=self.key("SIDE0001"), opId="android_ota_sideload",
                         caseId=self.case["id"], params={"file": str(ota)})
        self.assertFalse(plan["blocked"], plan)
        self.assertIn("official", [a["id"] for a in plan["acknowledgements"]])
        res = jobs.wait(self.call("service.execute", planId=plan["planId"], confirmation=plan["confirmationPhrase"],
                                  acknowledged=[a["id"] for a in plan["acknowledgements"]])["id"])
        self.assertEqual(res["status"], "done", res)
        self.assertIn("Total xfer", res["result"]["output"])

    def test_guided_reset_recorded(self):
        plan = self.call("service.plan", deviceKey=self.key("R58N12ABCDE"), opId="android_reset_recovery", caseId=self.case["id"])
        acks = [a["id"] for a in plan["acknowledgements"]]
        self.assertIn("performed", acks)
        with self.assertRaises(RpcError):
            self.call("service.execute", planId=plan["planId"], confirmation=plan["confirmationPhrase"], acknowledged=acks)
        plan = self.call("service.plan", deviceKey=self.key("R58N12ABCDE"), opId="android_reset_recovery", caseId=self.case["id"])
        res = self.call("service.recordGuided", planId=plan["planId"], confirmation=plan["confirmationPhrase"],
                        acknowledged=acks, result="success", notes="Equipo arrancó en el asistente de configuración.")
        html = Path(res["report"]).read_text(encoding="utf-8")
        self.assertIn("Guiada (realizada por el técnico)", html)
        self.assertIn("Wipe data/factory reset", html)
        self.assertIn("asistente de configuración", html)
