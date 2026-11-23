import json
import os
from pathlib import Path

from mrlab import cases, evidence, rpc, settings
from mrlab.errors import RpcError

from .helpers import TempDbCase

FAKE = Path(__file__).parent / "fake_tools" / "adb"


class ReportTests(TempDbCase):
    def setUp(self):
        super().setUp()
        if os.name == "nt":
            self.skipTest("adb falso requiere shebang POSIX")
        settings.update({"adbPath": str(FAKE), "technicianName": "Ana Pérez", "labName": "Lab Centro"})
        self.srv = rpc.Server()
        self.case = cases.create({"deviceType": "android", "deviceModel": "Galaxy A52", "deviceSerial": "R58N12ABCDE",
                                  "reason": "Pantalla rota <script>", "authorizationType": "owner",
                                  "authorizedBy": "Luis Gómez", "authorizationConfirmed": True})

    def call(self, method, **params):
        r = self.srv.handle({"id": 1, "method": method, "params": params})
        if "error" in r:
            raise RpcError(r["error"]["code"], r["error"]["message"])
        return r["result"]

    def test_build_and_register(self):
        key = {d["serial"]: d for d in self.call("devices.scan")["devices"]}["R58N12ABCDE"]["key"]
        self.call("diagnostics.run", deviceKey=key, caseId=self.case["id"])
        self.call("screen.assess", deviceKey=key, caseId=self.case["id"], answers={"powers_on": "yes", "display": "black"})
        self.call("access.analyze", deviceKey=key, caseId=self.case["id"])

        res = self.call("reports.build", caseId=self.case["id"])
        html = Path(res["html"]).read_text(encoding="utf-8")
        for text in (self.case["folio"], "Lab Centro", "Ana Pérez", "Luis Gómez", "Diagnósticos", "Pantalla negra",
                     "Análisis de acceso", "Registro de evidencias", "Cadena íntegra", "Titular / autorizante"):
            self.assertIn(text, html)
        self.assertNotIn("<script>", html)  # todo el contenido se escapa
        self.assertIn("&lt;script&gt;", html)
        data = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
        self.assertEqual(len(data["diagnostics"]), 1)
        self.assertEqual(len(data["screen"]), 1)

        partial = self.call("reports.build", caseId=self.case["id"], sections=["case", "evidence"])
        html2 = Path(partial["html"]).read_text(encoding="utf-8")
        self.assertNotIn("Evaluaciones de pantalla", html2)
        self.assertIn("2. Registro de evidencias", html2)

        pdf = Path(res["pdf"])
        pdf.write_bytes(b"%PDF-1.7 prueba")  # Electron genera el PDF real
        reg = self.call("reports.register", caseId=self.case["id"], paths=[str(pdf), res["json"]])
        self.assertEqual([f["kind"] for f in reg["files"]], ["PDF", "JSON"])
        self.assertEqual(len(self.call("reports.list", caseId=self.case["id"])), 2)
        with self.assertRaises(RpcError):
            self.call("reports.register", caseId=self.case["id"], paths=["/etc/passwd"])
        self.assertIn("Reporte del expediente generado", [e["operation"] for e in evidence.list_entries()["entries"]])
        self.assertTrue(evidence.verify_chain()["valid"])
