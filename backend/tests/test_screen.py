import os
from pathlib import Path

from mrlab import evidence, rpc, settings
from mrlab.errors import RpcError
from mrlab.screen import engine, questionnaire

from .helpers import TempDbCase

FAKE = Path(__file__).parent / "fake_tools" / "adb"
NO_SIGNALS = {"deviceConnected": False, "usb": None, "authorized": None, "platform": None,
              "displayPower": None, "touchDriver": None, "battery": None, "diagnosticId": None, "commState": None}
ANDROID_ON = {**NO_SIGNALS, "deviceConnected": True, "usb": True, "authorized": True, "platform": "android",
              "displayPower": "ON", "touchDriver": True, "commState": "online"}


def ans(**kw):
    return questionnaire.validate(kw)


class ClassificationTests(TempDbCase):
    def cat(self, a, s=NO_SIGNALS):
        return engine.classify(a, s)

    def test_categories(self):
        self.assertEqual(self.cat(ans(powers_on="yes", display="normal", touch="ok"))[0], "visible_touch_ok")
        self.assertEqual(self.cat(ans(powers_on="yes", display="normal", touch="none"))[0], "visible_touch_faulty")
        self.assertEqual(self.cat(ans(powers_on="yes", display="black"))[0], "black_screen")
        self.assertEqual(self.cat(ans(powers_on="yes", display="partial"))[0], "partial_display")
        self.assertEqual(self.cat(ans(powers_on="no"))[0], "no_response")
        self.assertEqual(self.cat(ans())[0], "no_response")

    def test_system_overrides_observation(self):
        # El técnico cree que está apagado, pero responde por USB: no es "sin respuesta".
        cat, flags, notes = self.cat(ans(powers_on="no", display="black"), ANDROID_ON)
        self.assertEqual(cat, "black_screen")
        self.assertTrue(any("responde por USB" in n["text"] for n in notes))
        self.assertTrue(any("display ENCENDIDO" in n["text"] for n in notes))
        self.assertEqual(next(f for f in flags if f["id"] == "usb_available")["state"], "yes")

    def test_touch_driver_cross_check(self):
        cat, _, notes = self.cat(ans(powers_on="yes", display="normal", touch="none"), ANDROID_ON)
        self.assertEqual(cat, "visible_touch_faulty")
        self.assertTrue(any("digitalizador" in n["text"] for n in notes))
        cat, _, _ = self.cat(ans(powers_on="yes", display="normal", touch="unknown"), {**ANDROID_ON, "touchDriver": False})
        self.assertEqual(cat, "visible_touch_faulty")

    def test_backup_flag(self):
        _, flags, _ = self.cat(ans(powers_on="yes", display="black", backup="yes"))
        self.assertEqual(next(f for f in flags if f["id"] == "prior_backup")["state"], "yes")

    def test_recommendations(self):
        a = ans(powers_on="yes", display="black", damage="liquid", usb_debug_before="yes", owner_credential="no")
        ids = [r["id"] for r in engine.recommend("black_screen", a, ANDROID_ON)]
        self.assertEqual(ids[0], "liquid")  # seguridad primero
        for expected in ("otg_input", "video_out", "mirror", "backup_now", "access_module", "replace_screen"):
            self.assertIn(expected, ids)
        self.assertNotIn("apple_av", ids)
        ids = [r["id"] for r in engine.recommend("no_response", ans(powers_on="no", backup="maybe"), NO_SIGNALS)]
        self.assertEqual(ids[:1], ["revive"])
        self.assertIn("restore_backup_new", ids)
        self.assertNotIn("otg_input", ids)

    def test_invalid_answers(self):
        with self.assertRaises(RpcError):
            questionnaire.validate({"display": "rota"})
        with self.assertRaises(RpcError):
            questionnaire.validate({"pin": "1234"})


class ScreenRpcTests(TempDbCase):
    def setUp(self):
        super().setUp()
        if os.name == "nt":
            self.skipTest("adb falso requiere shebang POSIX")
        settings.update({"adbPath": str(FAKE)})

    def test_assess_with_device_and_offline(self):
        srv = rpc.Server()
        devs = {d["serial"]: d for d in srv.handle({"id": 1, "method": "devices.scan"})["result"]["devices"]}
        key = devs["R58N12ABCDE"]["key"]
        srv.handle({"id": 2, "method": "diagnostics.run", "params": {"deviceKey": key}})
        r = srv.handle({"id": 3, "method": "screen.assess",
                        "params": {"deviceKey": key, "answers": {"powers_on": "yes", "display": "black", "touch": "unknown"}}})
        self.assertNotIn("error", r, r)
        res = r["result"]
        self.assertEqual(res["category"], "black_screen")
        self.assertEqual(res["signals"]["displayPower"], "ON")
        self.assertTrue(res["signals"]["authorized"])
        self.assertIn("backup_now", [x["id"] for x in res["recommendations"]])
        self.assertEqual(srv.handle({"id": 4, "method": "screen.get", "params": {"id": res["id"]}})["result"]["category"], "black_screen")

        off = srv.handle({"id": 5, "method": "screen.assess",
                          "params": {"deviceLabel": "iPhone 12 del cliente", "answers": {"powers_on": "no"}}})["result"]
        self.assertEqual((off["category"], off["deviceLabel"]), ("no_response", "iPhone 12 del cliente"))
        self.assertEqual(len(srv.handle({"id": 6, "method": "screen.history"})["result"]), 2)
        self.assertEqual(len(srv.handle({"id": 7, "method": "screen.questionnaire"})["result"]), 9)
        dash = srv.handle({"id": 8, "method": "dashboard.summary"})["result"]
        self.assertEqual(dash["screenAssessment"]["category"], "black_screen")
        self.assertIn("Evaluación de pantalla", [e["operation"] for e in evidence.list_entries()["entries"]])
        self.assertTrue(evidence.verify_chain()["valid"])
