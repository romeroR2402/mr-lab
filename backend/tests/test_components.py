import json
import os
import stat
from pathlib import Path

from mrlab import components, settings, tools

from .helpers import TempDbCase


class ComponentTests(TempDbCase):
    def setUp(self):
        super().setUp()
        self.res = Path(self.tmp.name) / "resources"
        tool_dir = self.res / "tools" / "platform-tools"
        tool_dir.mkdir(parents=True)
        self.adb = tool_dir / ("adb.exe" if os.name == "nt" else "adb")
        self.adb.write_bytes(b"#!/bin/sh\necho 'Android Debug Bridge version 1.0.41'\n")
        self.adb.chmod(self.adb.stat().st_mode | stat.S_IEXEC)
        import hashlib
        inv = {"components": [{"id": "platform-tools", "name": "Motor Android", "kind": "tool",
                               "dest": "tools/platform-tools",
                               "files": {f"tools/platform-tools/{self.adb.name}": hashlib.sha256(self.adb.read_bytes()).hexdigest()}}]}
        (self.res / "tools" / "components.json").write_text(json.dumps(inv))
        os.environ["MRLAB_RESOURCES_DIR"] = str(self.res)
        components.reset_cache()
        tools.invalidate()

    def tearDown(self):
        os.environ.pop("MRLAB_RESOURCES_DIR", None)
        components.reset_cache()
        super().tearDown()

    def test_integrated_preferred_and_verified(self):
        if os.name == "nt":
            self.skipTest("el ejecutable de prueba es un script POSIX")
        self.assertEqual(components.status()["components"][0]["status"], "ok")
        path, source = tools.locate("adb")
        self.assertEqual((path, source), (str(self.adb), "integrated"))
        report = tools.detect(force=True)
        adb = next(t for t in report["tools"] if t["id"] == "adb")
        self.assertEqual(adb["source"], "integrated")
        self.assertEqual(adb["version"], "1.0.41")

    def test_altered_component_not_used(self):
        self.adb.write_bytes(self.adb.read_bytes() + b"# modificado\n")
        components.reset_cache()
        self.assertEqual(components.status()["components"][0]["status"], "altered")
        settings.update({"autonomousMode": True})
        self.assertEqual(tools.locate("adb"), (None, None))

    def test_autonomous_mode_ignores_system(self):
        settings.update({"autonomousMode": True})
        self.assertEqual(tools.locate("idevice_id"), (None, None))
