import unittest

from mrlab.connectors.usb_windows import analyze

SAMSUNG_NO_DRIVER = [
    {"Name": "SAMSUNG Mobile USB Composite Device", "DeviceID": "USB\\VID_04E8&PID_6860\\R58N12ABCDE", "PNPClass": "USB",
     "ConfigManagerErrorCode": 0},
    {"Name": "Galaxy A52", "DeviceID": "USB\\VID_04E8&PID_6860&MI_00\\6&1", "PNPClass": "WPD", "ConfigManagerErrorCode": 0},
    {"Name": "ADB Interface", "DeviceID": "USB\\VID_04E8&PID_6860&MI_01\\6&2", "PNPClass": None, "ConfigManagerErrorCode": 28},
    {"Name": "Teclado USB", "DeviceID": "USB\\VID_046D&PID_C31C\\5&3", "PNPClass": "Keyboard", "ConfigManagerErrorCode": 0},
]


class UsbWindowsTests(unittest.TestCase):
    def test_samsung_missing_driver(self):
        res = analyze(SAMSUNG_NO_DRIVER)
        self.assertEqual(len(res), 1)
        p = res[0]
        self.assertEqual((p["vendor"], p["diagnosis"]), ("Samsung", "missing_driver"))
        self.assertIn("developer.samsung.com", p["driverUrl"])
        self.assertIn("controlador", p["message"])

    def test_samsung_ready(self):
        ok = [dict(e, ConfigManagerErrorCode=0, Name="SAMSUNG Android ADB Interface") if "MI_01" in e["DeviceID"] else e
              for e in SAMSUNG_NO_DRIVER]
        self.assertEqual(analyze(ok)[0]["diagnosis"], "adb_ready")

    def test_mtp_only(self):
        mtp = [e for e in SAMSUNG_NO_DRIVER if "MI_01" not in e["DeviceID"]]
        self.assertEqual(analyze(mtp)[0]["diagnosis"], "no_adb_interface")

    def test_honor(self):
        honor = [{"Name": "HONOR 90", "DeviceID": "USB\\VID_339B&PID_107E&MI_00\\7&1", "PNPClass": "WPD", "ConfigManagerErrorCode": 0}]
        p = analyze(honor)[0]
        self.assertEqual((p["vendor"], p["diagnosis"]), ("Honor", "no_adb_interface"))
        self.assertIn("modo Solo carga", p["message"])
        self.assertIn("HONOR Suite", p["message"])

    def test_charge_only_mass_storage(self):
        # Caso real observado: Honor/Huawei en «Solo carga» se presenta como almacenamiento USB.
        res = analyze([{"Name": "Dispositivo de almacenamiento USB", "DeviceID": "USB\\VID_12D1&PID_107E\\ABC123",
                        "PNPClass": "USB", "ConfigManagerErrorCode": 0}])
        self.assertEqual(res[0]["diagnosis"], "charge_only")
        self.assertIn("Transferir archivos", res[0]["message"])

    def test_apple_and_unrelated(self):
        res = analyze([{"Name": "Apple Mobile Device USB Composite Device", "DeviceID": "USB\\VID_05AC&PID_12A8\\00008101",
                        "PNPClass": "USB", "ConfigManagerErrorCode": 0}])
        self.assertEqual(res[0]["diagnosis"], "apple")
        self.assertEqual(analyze([SAMSUNG_NO_DRIVER[3]]), [])
