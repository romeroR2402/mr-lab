import json
import os
import zipfile
from pathlib import Path

from mrlab import backups, cases, evidence, jobs, rpc, settings
from mrlab.recovery import categories, engine, sources
from mrlab.errors import RpcError

from .helpers import TempDbCase

FAKE = Path(__file__).parent / "fake_tools" / "adb"
PASS = "frase-larga-del-titular"


class CategoryTests(TempDbCase):
    def test_classify(self):
        self.assertEqual(categories.classify("DCIM/Camera/IMG_1.JPG"), "photos")
        self.assertEqual(categories.classify("x/video.mov"), "videos")
        self.assertEqual(categories.classify("contrato.pdf"), "documents")
        self.assertEqual(categories.classify("contactos.vcf"), "contacts")
        self.assertEqual(categories.classify("apple_backup/X/Manifest.db"), "backups")
        self.assertEqual(categories.classify("sin_extension", b"\xff\xd8\xff\xe0"), "photos")
        self.assertEqual(categories.classify("musica.mp3"), "files")

    def test_remote_path_validation(self):
        self.assertEqual(sources.validate_remote("/sdcard/DCIM/"), "/sdcard/DCIM")
        for bad in ("/data/data", "/sdcard/Android/data/com.app", "/sdcard/../etc", "/sdcard/x';rm -rf /;'"):
            with self.assertRaises(RpcError):
                sources.validate_remote(bad)

    def test_vcf(self):
        rows = sources._parse_content_rows(
            "Row: 0 display_name=Ana, mimetype=vnd.android.cursor.item/phone_v2, data1=+52 1\n"
            "Row: 1 display_name=Ana, mimetype=vnd.android.cursor.item/email_v2, data1=a@b.c\n")
        vcf = sources.rows_to_vcf(rows)
        self.assertIn("FN:Ana", vcf)
        self.assertIn("TEL:+52 1", vcf)
        self.assertIn("EMAIL:a@b.c", vcf)


class BackupFlowTests(TempDbCase):
    def setUp(self):
        super().setUp()
        if os.name == "nt":
            self.skipTest("adb falso requiere shebang POSIX")
        self.sd = Path(self.tmp.name) / "sdcard"
        (self.sd / "DCIM" / "Camera").mkdir(parents=True)
        (self.sd / "DCIM" / "Camera" / "IMG_001.jpg").write_bytes(b"\xff\xd8\xff" + b"a" * 5000)
        (self.sd / "DCIM" / "Camera" / "VID_001.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"v" * 9000)
        (self.sd / "Documents").mkdir()
        (self.sd / "Documents" / "factura.pdf").write_bytes(b"%PDF-1.7 " + b"d" * 3000)
        os.environ["FAKE_SDCARD"] = str(self.sd)
        os.environ["FAKE_CONTACTS"] = "1"
        settings.update({"adbPath": str(FAKE)})
        self.srv = rpc.Server()
        devs = {d["serial"]: d for d in self.call("devices.scan")["devices"]}
        self.key = devs["R58N12ABCDE"]["key"]
        self.unauth = devs["ZY22XXXXXX"]["key"]
        self.case = cases.create({"deviceType": "android", "reason": "Respaldo", "authorizationType": "owner",
                                  "authorizedBy": "Titular", "authorizationConfirmed": True})

    def tearDown(self):
        os.environ.pop("FAKE_SDCARD", None)
        os.environ.pop("FAKE_CONTACTS", None)
        super().tearDown()

    def call(self, method, **params):
        r = self.srv.handle({"id": 1, "method": method, "params": params})
        if "error" in r:
            raise RpcError(r["error"]["code"], r["error"]["message"])
        return r["result"]

    def test_full_cycle(self):
        scan = self.call("recovery.scan", deviceKey=self.key, paths=["/sdcard/DCIM", "/sdcard/Documents", "/sdcard/Nope"])
        self.assertEqual(scan["totalFiles"], 3)
        self.assertEqual(scan["categories"]["photos"]["files"], 1)
        self.assertEqual(scan["categories"]["videos"]["files"], 1)

        with self.assertRaises(RpcError):  # expediente obligatorio
            self.call("recovery.start", source="android_adb", deviceKey=self.key, paths=["/sdcard/DCIM"],
                      passphrase=PASS, passphraseConfirm=PASS)
        with self.assertRaises(RpcError):  # dispositivo sin autorizar
            sources.android_scan(__import__("mrlab").scanner.get_cached(self.unauth), ["/sdcard/DCIM"])

        job = self.call("recovery.start", source="android_adb", deviceKey=self.key, caseId=self.case["id"],
                        paths=["/sdcard/DCIM", "/sdcard/Documents"], includeContacts=True,
                        passphrase=PASS, passphraseConfirm=PASS, expectedBytes=scan["totalBytes"])
        done = jobs.wait(job["id"])
        self.assertEqual(done["status"], "done", done)
        bid = done["result"]["backupId"]
        self.assertEqual(done["result"]["files"], 4)  # 3 archivos + contactos.vcf

        b = backups.get(bid)
        self.assertEqual(b["categories"]["contacts"]["files"], 1)
        self.assertEqual(b["folio"], self.case["folio"])
        container = Path(backups._get(bid)["_path"]).read_bytes()
        self.assertTrue(container.startswith(b"MRLB1"))
        self.assertNotIn(b"%PDF", container)  # cifrado: no hay texto plano reconocible
        self.assertFalse(any(engine.staging_root().iterdir()), "no debe quedar texto plano en preparación")

        listing = self.call("backups.browse", id=bid, passphrase=PASS)
        self.assertEqual(sorted(f["category"] for f in listing["files"]), ["contacts", "documents", "photos", "videos"])
        with self.assertRaises(RpcError):
            self.call("backups.browse", id=bid, passphrase="frase-equivocada")

        v = jobs.wait(self.call("backups.verify", id=bid, passphrase=PASS)["id"])
        self.assertEqual(v["result"]["result"], "ok")
        self.assertEqual(backups.get(bid)["verifyResult"], "ok")

        ex = jobs.wait(self.call("backups.export", id=bid, passphrase=PASS, categories=["photos", "contacts"])["id"])
        self.assertEqual(ex["status"], "done", ex)
        out = Path(ex["result"]["path"])
        self.assertEqual(ex["result"]["files"], 2)
        self.assertEqual(ex["result"]["mismatches"], [])
        self.assertTrue((out / "Fotografías" / "android" / "DCIM" / "Camera" / "IMG_001.jpg").exists())
        vcf = next(out.rglob("contactos.vcf")).read_text(encoding="utf-8")
        self.assertIn("EMAIL:ana@example.com", vcf)
        report = json.loads((out / "manifiesto-exportacion.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["files"]), 2)
        detail = cases.get(self.case["id"])
        self.assertEqual(len(detail["files"]), 1)
        self.assertIn("Respaldo cifrado", [o["operation"] for o in detail["operations"]])

        with self.assertRaises(RpcError):
            self.call("backups.delete", id=bid, confirmation="si")
        self.call("backups.delete", id=bid, confirmation=f"ELIMINAR {bid}")
        self.assertEqual(self.call("backups.list"), [])
        ops = [e["operation"] for e in evidence.list_entries()["entries"]]
        for op in ("Respaldo iniciado", "Respaldo cifrado creado", "Verificación de respaldo",
                   "Exportación de datos", "Eliminación de respaldo"):
            self.assertIn(op, ops)
        self.assertTrue(evidence.verify_chain()["valid"])

    def test_tampered_backup_fails_verification(self):
        job = self.call("recovery.start", source="android_adb", deviceKey=self.key, caseId=self.case["id"],
                        paths=["/sdcard/Documents"], passphrase=PASS, passphraseConfirm=PASS)
        bid = jobs.wait(job["id"])["result"]["backupId"]
        path = Path(backups._get(bid)["_path"])
        data = bytearray(path.read_bytes())
        data[len(data) // 2] ^= 0xFF
        path.write_bytes(bytes(data))
        v = jobs.wait(self.call("backups.verify", id=bid, passphrase=PASS)["id"])
        self.assertEqual(v["status"], "failed")
        self.assertEqual(backups.get(bid)["verifyResult"], "failed")

    def test_contacts_denied_and_local_import(self):
        os.environ["FAKE_CONTACTS"] = "0"
        job = self.call("recovery.start", source="android_adb", deviceKey=self.key, caseId=self.case["id"],
                        paths=["/sdcard/DCIM"], includeContacts=True, passphrase=PASS, passphraseConfirm=PASS)
        res = jobs.wait(job["id"])["result"]
        self.assertTrue(any("no permite exportar contactos" in w for w in res["warnings"]))

        import tempfile
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        src = Path(other.name) / "origen.zip"
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("fotos/a.png", b"\x89PNG....")
            z.writestr("notas.txt", "hola")
        job = self.call("recovery.start", source="local_import", localPath=str(src), caseId=self.case["id"],
                        passphrase=PASS, passphraseConfirm=PASS)
        res = jobs.wait(job["id"])
        self.assertEqual(res["status"], "done", res)
        b = backups.get(res["result"]["backupId"])
        self.assertEqual((b["categories"]["photos"]["files"], b["categories"]["documents"]["files"]), (1, 1))
        inside = Path(self.tmp.name) / "dentro.zip"
        inside.write_bytes(src.read_bytes())
        res = jobs.wait(self.call("recovery.start", source="local_import", localPath=str(inside), caseId=self.case["id"],
                                  passphrase=PASS, passphraseConfirm=PASS)["id"])
        self.assertIn("carpeta de datos", res["error"])

    def test_cancel_and_weak_passphrase(self):
        with self.assertRaises(RpcError):
            self.call("recovery.start", source="android_adb", deviceKey=self.key, caseId=self.case["id"],
                      paths=["/sdcard/DCIM"], passphrase="corta", passphraseConfirm="corta")
        job = self.call("recovery.start", source="android_adb", deviceKey=self.key, caseId=self.case["id"],
                        paths=["/sdcard/DCIM"], passphrase=PASS, passphraseConfirm=PASS)
        jobs.cancel(job["id"])
        res = jobs.wait(job["id"])
        self.assertIn(res["status"], ("cancelled", "done"))  # puede terminar antes de ver la cancelación
        self.assertFalse(any(engine.staging_root().iterdir()))
