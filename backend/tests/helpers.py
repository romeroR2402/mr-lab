import os
import tempfile
import unittest
from pathlib import Path

from mrlab import db


class TempDbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["MRLAB_DATA_DIR"] = self.tmp.name
        db.set_db_path(Path(self.tmp.name) / "test.sqlite3")
        db.migrate()

    def tearDown(self):
        db.set_db_path(None)
        self.tmp.cleanup()
