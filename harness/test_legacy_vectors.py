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


R1_VECTORS = ("v3", "v4b", "v6b", "v7-fold-order")
LEGACY_IRI = "https://web4.io/ontology#"
LOCAL_IRI = "https://web4.io/trust-derivation#"
RECEIPT_HASHES = ("law_hash", "graph_hash", "receipt_hash")


def migrate_string(value):
    """Transform the stated legacy vocabulary, not embedded urn:web4 identifiers."""
    if value == LEGACY_IRI:
        return LOCAL_IRI
    if value == "web4:Validity":
        return "w4td:BoundaryConformance"
    if value.startswith("web4:"):
        return "w4td:" + value[len("web4:"):]
    if value.startswith("web4-trust-core-conformance-") and value.endswith("-draft1"):
        return value[:-1] + "2"
    return value


def migrate_json(value, parent=None):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key = "w4td" if key == "web4" and parent == "prefixes" else migrate_string(key)
            if key in result:
                raise ValueError("namespace migration would collide on a key")
            result[key] = migrate_json(item, key)
        return result
    if isinstance(value, list):
        return [migrate_json(item) for item in value]
    return migrate_string(value) if isinstance(value, str) else value


def typed_json(value):
    # JSON encoding distinguishes booleans from numbers (unlike Python's ==).
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def matching_spec(old, new):
    return typed_json(migrate_json(old)) == typed_json(new)


def matching_receipt(old, new):
    if any(key not in old or key not in new for key in RECEIPT_HASHES):
        return False
    old_body = {key: value for key, value in old.items() if key not in RECEIPT_HASHES}
    new_body = {key: value for key, value in new.items() if key not in RECEIPT_HASHES}
    return typed_json(migrate_json(old_body)) == typed_json(new_body)


def matching_graph(old, new):
    migrated = old.replace((LEGACY_IRI + "Validity>").encode(),
                           (LOCAL_IRI + "BoundaryConformance>").encode())
    return migrated.replace(LEGACY_IRI.encode(), LOCAL_IRI.encode()) == new


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

    def test_r1_specs_and_receipts_preserve_non_hash_content_under_rename(self):
        root = Path(__file__).resolve().parent.parent / "vectors"
        for name in R1_VECTORS:
            with self.subTest(vector=name):
                old = root / "receipts" / name
                new = root / "r1" / "receipts" / name
                old_spec = json.loads((old / "spec.json").read_text())
                new_spec = json.loads((new / "spec.json").read_text())
                self.assertTrue(matching_spec(old_spec, new_spec))
                old_receipt = json.loads((old / "receipt.json").read_text())
                new_receipt = json.loads((new / "receipt.json").read_text())
                self.assertTrue(matching_receipt(old_receipt, new_receipt))

    def test_r1_input_graphs_preserve_exact_bytes_under_iri_rename(self):
        root = Path(__file__).resolve().parent.parent / "vectors"
        paths = [f"receipts/{name}/input.nq" for name in ("v3", "v4b", "v7-fold-order")]
        paths += ["canonicalization/blank-node-rdfc10/input.nq",
                  "canonicalization/skolemized-sorted-nquads/input.nq"]
        for path in paths:
            with self.subTest(vector=path):
                self.assertTrue(matching_graph((root / path).read_bytes(),
                                               (root / "r1" / path).read_bytes()))

    def test_transformation_checks_do_not_hide_non_namespace_changes(self):
        baseline = {"web4:Validity": {"prior": 1, "enabled": True},
                    "id": "urn:web4:entity:unchanged"}
        transformed = migrate_json(baseline)
        self.assertEqual(transformed["id"], baseline["id"])
        self.assertEqual(migrate_json({"unrelated": {"web4": "ordinary text"}}),
                         {"unrelated": {"web4": "ordinary text"}})
        altered = {"w4td:BoundaryConformance": {"prior": 1, "enabled": 1},
                   "id": baseline["id"]}
        self.assertTrue(matching_spec(baseline, transformed))
        self.assertFalse(matching_spec(baseline, altered))
        old_receipt = {**{key: "old" for key in RECEIPT_HASHES}, "content": baseline}
        new_receipt = {**{key: "new" for key in RECEIPT_HASHES}, "content": transformed}
        self.assertTrue(matching_receipt(old_receipt, new_receipt))
        self.assertFalse(matching_receipt(old_receipt, {**new_receipt, "content": altered}))
        self.assertFalse(matching_receipt(old_receipt, {"content": transformed}))
        graph = b"<https://web4.io/ontology#Validity> <urn:p> <urn:o> .\n"
        expected = b"<https://web4.io/trust-derivation#BoundaryConformance> <urn:p> <urn:o> .\n"
        self.assertTrue(matching_graph(graph, expected))
        self.assertFalse(matching_graph(graph, expected.replace(b"<urn:o>", b"<urn:other>")))
        with self.assertRaises(ValueError):
            migrate_json({"web4:Validity": 1, "w4td:BoundaryConformance": 2})


if __name__ == "__main__":
    unittest.main()
