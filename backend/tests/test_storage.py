import sqlite3
import tempfile
from pathlib import Path

from mrlab import cases, crypto, db, evidence, settings
from mrlab.errors import RpcError

from .helpers import TempDbCase


class StorageTests(TempDbCase):
    def test_evidence_chain_and_append_only(self):
        for i in range(3):
            evidence.log(f"op{i}", "success", details={"i": i})
        self.assertEqual(evidence.verify_chain(), {"valid": True, "checked": 3, "brokenAtId": None})
        with db.read() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE evidence_log SET result='failure' WHERE id=1")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM evidence_log")

    def test_tamper_detected(self):
        evidence.log("a", "success")
        evidence.log("b", "success")
        with db.write() as conn:
            conn.execute("DROP TRIGGER evidence_log_no_update")
            conn.execute("UPDATE evidence_log SET operation='x' WHERE id=1")
        self.assertEqual(evidence.verify_chain()["brokenAtId"], 1)

    def test_cases(self):
        base = {"deviceType": "android", "reason": "Pantalla rota", "authorizationType": "owner",
                "authorizedBy": "Titular"}
        with self.assertRaises(RpcError):
            cases.create(base)
        c = cases.create({**base, "authorizationConfirmed": True})
        c2 = cases.create({**base, "authorizationConfirmed": True})
        self.assertTrue(c["folio"].endswith("-0001"))
        self.assertTrue(c2["folio"].endswith("-0002"))
        c = cases.update_status(c["id"], "in_progress")
        self.assertEqual(c["status"], "in_progress")
        self.assertEqual(evidence.list_entries(case_id=c["id"])["total"], 2)

    def test_settings_reject_credentials(self):
        settings.update({"technicianName": "Ana"})
        self.assertEqual(settings.technician(), "Ana")
        with self.assertRaises(RpcError) as ctx:
            settings.update({"devicePasscode": "1234"})
        self.assertEqual(ctx.exception.code, "forbidden_setting")

    def test_crypto_roundtrip_and_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            src, enc, out = Path(d, "a.bin"), Path(d, "a.mrlb"), Path(d, "b.bin")
            src.write_bytes(b"x" * (crypto.CHUNK + 123))
            crypto.encrypt_file(src, enc, "frase-de-prueba-larga", n=2**10)
            self.assertNotIn(b"xxxx", enc.read_bytes()[200:])
            crypto.decrypt_file(enc, out, "frase-de-prueba-larga")
            self.assertEqual(out.read_bytes(), src.read_bytes())
            with self.assertRaises(RpcError):
                crypto.decrypt_file(enc, out, "frase-incorrecta-xx")
            data = bytearray(enc.read_bytes())
            data[-5] ^= 1
            enc.write_bytes(bytes(data))
            with self.assertRaises(RpcError):
                crypto.decrypt_file(enc, out, "frase-de-prueba-larga")
            # truncado: quitar el último bloque
            crypto.encrypt_file(src, enc, "frase-de-prueba-larga", n=2**10)
            raw = enc.read_bytes()
            enc.write_bytes(raw[: -(123 + 16 + 4)])
            with self.assertRaises(RpcError):
                crypto.decrypt_file(enc, out, "frase-de-prueba-larga")
