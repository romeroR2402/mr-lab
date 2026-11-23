"""Escaneo y diagnóstico completos contra el adb FALSO de tests/fake_tools."""
import json
import os
from pathlib import Path

from mrlab import rpc, settings
from mrlab.diagnostics import engine

from .helpers import TempDbCase

FAKE = Path(__file__).parent / "fake_tools" / "adb"


class ScanDiagTests(TempDbCase):
    def setUp(self):
        super().setUp()
        if os.name == "nt":
            self.skipTest("adb falso requiere shebang POSIX")
        settings.update({"adbPath": str(FAKE)})

    def test_scan_and_diagnose(self):
        srv = rpc.Server()
        scan = srv.handle({"id": 1, "method": "devices.scan"})["result"]
        devs = {d["serial"]: d for d in scan["devices"]}
        a52 = devs["R58N12ABCDE"]
        self.assertEqual((a52["manufacturer"], a52["model"], a52["osVersion"]), ("samsung", "SM-A525F", "14"))
        self.assertEqual(a52["authState"], "authorized")
        self.assertEqual(devs["ZY22XXXXXX"]["authState"], "unauthorized")
        self.assertEqual(devs["192.168.1.20:5555"]["connection"], "network")

        rep = srv.handle({"id": 2, "method": "diagnostics.run", "params": {"deviceKey": a52["key"]}})["result"]
        checks = {c["id"]: c for c in rep["checks"]}
        self.assertEqual(checks["battery"]["value"], "54%")
        self.assertEqual(checks["storage"]["status"], "ok")
        self.assertEqual(checks["touch"]["data"]["Dispositivos"], "sec_touchscreen")
        self.assertEqual(checks["verified_boot"]["status"], "ok")
        self.assertEqual(rep["summaryStatus"], "ok")
        self.assertEqual(engine.get_report(rep["id"])["summaryStatus"], "ok")

        unauth = srv.handle({"id": 3, "method": "diagnostics.run",
                             "params": {"deviceKey": devs["ZY22XXXXXX"]["key"]}})["result"]
        self.assertEqual(unauth["summaryStatus"], "error")
        self.assertTrue(any(c["status"] == "unavailable" for c in unauth["checks"]))

        summary = srv.handle({"id": 4, "method": "dashboard.summary"})["result"]
        self.assertEqual(summary["deviceCount"], 3)
        json.dumps(summary)

    def test_unknown_and_not_implemented(self):
        srv = rpc.Server()
        self.assertEqual(srv.handle({"id": 1, "method": "nope"})["error"]["code"], "method_not_found")
        self.assertEqual(srv.handle({"id": 2, "method": "reports.export"})["error"]["code"], "method_not_found")
        self.assertEqual(srv.handle({"id": 3, "method": "diagnostics.run", "params": {}})["error"]["code"], "invalid_params")
