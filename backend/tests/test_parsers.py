import unittest

from mrlab.connectors.android import connection_type, parse_adb_devices, parse_fastboot_vars, parse_getprop
from mrlab.connectors.apple import classify_lockdown_error, parse_kv
from mrlab.diagnostics.android import parse_df, parse_dumpsys_battery, parse_touch_devices


class ParserTests(unittest.TestCase):
    def test_adb_devices(self):
        out = ("* daemon started successfully\nList of devices attached\n"
               "R58N12ABCDE  device usb:1-1 product:a52q model:SM_A525F device:a52q transport_id:3\n"
               "ZY22  unauthorized usb:1-2 transport_id:4\n"
               "0123  no permissions (user in plugdev group; are your udev rules wrong?); see [http://x] usb:2-1 transport_id:7\n"
               "emulator-5554 offline\n")
        devs = parse_adb_devices(out)
        self.assertEqual([d["state"] for d in devs], ["device", "unauthorized", "no permissions", "offline"])
        self.assertEqual(devs[0]["props"]["model"], "SM_A525F")
        self.assertEqual(devs[2]["props"].get("usb"), "2-1")
        self.assertEqual(connection_type("emulator-5554", {}), "emulator")
        self.assertEqual(connection_type("10.0.0.2:5555", {}), "network")

    def test_getprop(self):
        p = parse_getprop("[ro.product.model]: [Pixel 7]\n[empty]: []\ngarbage")
        self.assertEqual(p, {"ro.product.model": "Pixel 7", "empty": ""})

    def test_fastboot_vars(self):
        v = parse_fastboot_vars("(bootloader) product: panther\n(bootloader) unlocked:no\nall: Done!!\n")
        self.assertEqual(v, {"product": "panther", "unlocked": "no"})

    def test_battery_df_touch(self):
        b = parse_dumpsys_battery("  level: 80\n  health: 2\n")
        self.assertEqual(b["level"], "80")
        df = parse_df("Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/x 1000 500 500 50% /data\n")
        self.assertEqual(df["total"], 1024000)
        inp = ("Input Reader State:\n  Device 4: fts_ts\n    Sources: TOUCHSCREEN | STYLUS\n"
               "  Device 2: gpio-keys\n    Sources: KEYBOARD\n")
        self.assertEqual(parse_touch_devices(inp), ["fts_ts"])

    def test_apple(self):
        self.assertEqual(parse_kv("ProductType: iPhone14,5\nProductVersion: 17.5\n")["ProductType"], "iPhone14,5")
        self.assertEqual(classify_lockdown_error("ERROR: Could not connect to lockdownd: Password protected (-17)")[0], "locked")
        self.assertEqual(classify_lockdown_error("Pairing dialog response pending (-19)")[0], "pending")
        self.assertEqual(classify_lockdown_error("Invalid HostID (-21)")[0], "not_paired")


if __name__ == "__main__":
    unittest.main()
