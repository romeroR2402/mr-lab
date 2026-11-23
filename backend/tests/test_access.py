import os
from pathlib import Path

from mrlab import evidence, rpc, settings
from mrlab.access import plugins, policy
from mrlab.errors import RpcError

from .helpers import TempDbCase

FAKE = Path(__file__).parent / "fake_tools" / "adb"


class PolicyTests(TempDbCase):
    def test_prohibited_capabilities_rejected(self):
        for cap in ("bypass_auth", "bruteforce", "decrypt", "frp_bypass", "covert_extraction", "algo_desconocido"):
            with self.assertRaises(RpcError):
                policy.validate_capabilities([cap])
        self.assertEqual(policy.validate_capabilities(["document", "inspect_auth"]), ["document", "inspect_auth"])

    def test_prohibited_text_rejected(self):
        for text in ("FRP bypass tool", "Brute force PIN", "romper el cifrado", "extracción oculta", "iCloud bypass"):
            with self.assertRaises(RpcError):
                policy.scan_text(text)
        policy.scan_text("Guía de recuperación de cuenta Google del titular")


class PluginTests(TempDbCase):
    def write_plugin(self, name, body):
        path = plugins.plugins_dir() / f"{name}.py"
        path.write_text(body, encoding="utf-8")
        return path

    def test_malicious_plugin_not_executed(self):
        marker = Path(self.tmp.name) / "ejecutado.txt"
        self.write_plugin("malo", f'''
open({str(marker)!r}, "w").write("x")
MANIFEST = {{"id": "malo", "name": "FRP bypass", "capabilities": ["document"]}}
def analyze(ctx): return []
''')
        listed = {p["id"]: p for p in plugins.list_plugins()}
        self.assertIn("Rechazado por política", listed["malo"]["error"])
        self.assertFalse(marker.exists(), "el código del plugin no debe ejecutarse si la política lo rechaza")
        with self.assertRaises(RpcError):
            plugins.set_enabled("malo", True)

    def test_whole_file_rejected_by_text(self):
        self.write_plugin("texto", '''
MANIFEST = {"id": "texto", "name": "Notas", "capabilities": ["document"]}
def analyze(ctx): return [{"title": "Usar FRP bypass"}]
''')
        listed = {p["id"]: p for p in plugins.list_plugins()}
        self.assertIn("Rechazado por política", listed["texto"]["error"])

    def test_capability_violation(self):
        self.write_plugin("cap", '''
MANIFEST = {"id": "cap", "name": "Analizador", "capabilities": ["document", "decrypt"]}
def analyze(ctx): return []
''')
        listed = {p["id"]: p for p in plugins.list_plugins()}
        self.assertIn("capacidad no permitida", listed["cap"]["error"])

    def test_external_plugin_lifecycle(self):
        self.write_plugin("lab", '''
MANIFEST = {"id": "lab-notas", "name": "Notas de laboratorio", "version": "1.0", "capabilities": ["document"],
            "platforms": ["android"]}
def analyze(ctx):
    ctx["device"]["serial"] = "ALTERADO"   # no debe afectar al análisis real
    return [{"title": "Modelo en inventario", "severity": "info", "detail": ctx["device"]["model"]},
            {"title": "Usar FRP " + "by" + "pass", "detail": "x"}]  # generado en ejecución
''')
        listed = {p["id"]: p for p in plugins.list_plugins()}
        self.assertFalse(listed["lab-notas"]["enabled"], "los plugins externos inician deshabilitados")
        self.assertTrue(listed["damaged-interaction"]["enabled"])
        plugins.set_enabled("lab-notas", True)
        snap = {"platform": "android", "device": {"serial": "S1", "model": "X"}, "properties": {},
                "diagnostic": None, "mechanisms": [], "restrictions": []}
        found = [f for f in plugins.run_all(snap) if f.plugin_id == "lab-notas"]
        self.assertEqual(found[0].title, "Modelo en inventario")
        self.assertEqual(found[1].title, "Hallazgo descartado por política")
        self.assertEqual(snap["device"]["serial"], "S1")

    def test_failing_plugin_isolated(self):
        self.write_plugin("falla", '''
MANIFEST = {"id": "falla", "name": "Falla", "capabilities": ["document"]}
def analyze(ctx): raise ValueError("boom")
''')
        plugins.set_enabled("falla", True)
        found = [f for f in plugins.run_all({"platform": "apple", "device": {}}) if f.plugin_id == "falla"]
        self.assertEqual(found[0].title, "Error del plugin")


class AccessEngineTests(TempDbCase):
    def setUp(self):
        super().setUp()
        if os.name == "nt":
            self.skipTest("adb falso requiere shebang POSIX")
        settings.update({"adbPath": str(FAKE)})

    def test_full_analysis(self):
        srv = rpc.Server()
        devs = {d["serial"]: d for d in srv.handle({"id": 1, "method": "devices.scan"})["result"]["devices"]}
        key = devs["R58N12ABCDE"]["key"]
        srv.handle({"id": 2, "method": "diagnostics.run", "params": {"deviceKey": key}})
        res = srv.handle({"id": 3, "method": "access.analyze", "params": {"deviceKey": key}})
        self.assertNotIn("error", res, res)
        a = res["result"]
        mech = {m["id"]: m for m in a["mechanisms"]}
        self.assertEqual(mech["screen_lock"]["present"], "yes")
        self.assertEqual(mech["mdm"]["present"], "no")
        restr = {r["id"]: r for r in a["restrictions"]}
        self.assertEqual((restr["encryption"]["status"], restr["encryption"]["severity"]), ("active", "blocker"))
        self.assertEqual(a["recoverability"], "conditional")
        self.assertIn("google_account_recovery", [o["id"] for o in a["options"]])
        compat = {c["procedureId"]: c for c in a["compatibility"]}
        self.assertEqual(compat["screen_mirror"]["verdict"], "compatible")
        self.assertNotIn("apple_official_restore", compat)
        titles = [f["title"] for f in a["findings"]]
        self.assertIn("Pantalla visible y táctil funcional", titles)
        self.assertIn("Datos de usuario cifrados y protegidos por credencial", titles)
        self.assertTrue(a["disclaimer"])
        # persistido y registrado
        self.assertEqual(srv.handle({"id": 4, "method": "access.get", "params": {"id": a["id"]}})["result"]["recoverability"], "conditional")
        self.assertEqual(len(srv.handle({"id": 5, "method": "access.history"})["result"]), 1)
        ops = [e["operation"] for e in evidence.list_entries()["entries"]]
        self.assertIn("Análisis de acceso", ops)
        self.assertTrue(evidence.verify_chain()["valid"])

    def test_unauthorized_device(self):
        srv = rpc.Server()
        devs = {d["serial"]: d for d in srv.handle({"id": 1, "method": "devices.scan"})["result"]["devices"]}
        a = srv.handle({"id": 2, "method": "access.analyze", "params": {"deviceKey": devs["ZY22XXXXXX"]["key"]}})["result"]
        self.assertEqual(a["recoverability"], "unknown")
        self.assertTrue(any("no está autorizado" in l for l in a["limitations"]))
        damage = next(f for f in a["findings"] if f["pluginId"] == "damaged-interaction")
        self.assertEqual(damage["title"], "Comunicación USB sin autorización")
