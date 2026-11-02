"""Negative controls for the immutable legacy-vector evidence check."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from legacy_vectors import verify_legacy_vectors


class LegacyVectorsTests(unittest.TestCase):
    def test_generator_preserves_legacy_and_reproduces_r1_bytes(self):
        source = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(source / "harness", root / "harness")
            shutil.copytree(source / "vectors", root / "vectors")
            def snapshot(folder):
                return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in folder.rglob("*") if p.is_file()}
            before = snapshot(root / "vectors")
            run = subprocess.run([sys.executable, str(root / "harness" / "generate.py")],
                                 capture_output=True, text=True, cwd=root)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(snapshot(root / "vectors"), before)

    def test_original_is_checked_and_extra_new_vectors_are_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = root / "vectors" / "legacy.txt"
            legacy.parent.mkdir()
            legacy.write_bytes(b"original")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"vectors/legacy.txt": hashlib.sha256(b"original").hexdigest()}))
            self.assertEqual(verify_legacy_vectors(root, manifest), [])
            (legacy.parent / "new-vector.txt").write_bytes(b"new")
            self.assertEqual(verify_legacy_vectors(root, manifest), [])
            legacy.write_bytes(b"changed")
            self.assertTrue(any("differs" in x for x in verify_legacy_vectors(root, manifest)))
            legacy.unlink()
            self.assertTrue(any("unavailable" in x for x in verify_legacy_vectors(root, manifest)))

    def test_invalid_empty_and_escaping_manifests_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "vectors").mkdir()
            manifest = root / "manifest.json"
            for data in ({}, {"vectors/../secret": "0" * 64}, {"vectors/r1/not-legacy": "0" * 64}):
                manifest.write_text(json.dumps(data))
                self.assertTrue(verify_legacy_vectors(root, manifest), data)
            manifest.write_text("{")
            self.assertTrue(verify_legacy_vectors(root, manifest))


if __name__ == "__main__":
    unittest.main()
