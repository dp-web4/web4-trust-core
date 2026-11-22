#!/usr/bin/env python3
"""Operator ruling regression: R1 may not ship rejected semantic identities.

2026-11-06 operator decision: boundary/correction/escalation behavior is
potentially T3 Temperament evidence, not V3 Validity or a new normative
"BoundaryConformance" root. This check is deliberately narrower than a
semantic proof; NOT-SAME review of the eventual local mapping remains required.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R1 = ROOT / "vectors" / "r1"
REJECTED = ("w4td:BoundaryConformance", "https://web4.io/trust-derivation#BoundaryConformance")
CANONICAL_VALIDITY = "https://web4.io/ontology#Validity"


class R1OperatorSemanticRuling(unittest.TestCase):
    def test_r1_spec_dimension_identities_obey_ruling(self):
        paths = sorted((R1 / "receipts").glob("*/spec.json"))
        self.assertGreaterEqual(len(paths), 4, "missing proposed R1 specs")
        for path in paths:
            with self.subTest(path=path):
                spec = json.loads(path.read_text(encoding="utf-8"))
                dims = spec["dimensions"]
                text = json.dumps(spec, sort_keys=True, ensure_ascii=False)
                for token in REJECTED:
                    self.assertNotIn(token, text, f"rejected semantic identity in {path}")
                self.assertEqual(
                    spec["prefixes"]["w4td"], "https://web4.io/trust-derivation#",
                    "R1 derivations must retain a local, non-standard namespace",
                )
                self.assertNotIn("web4:Validity", dims)
                self.assertNotIn("web4:Temperament", dims)
                self.assertNotIn("w4td:Validity", dims)
                self.assertNotIn("w4td:Temperament", dims)
                # The behavioral evidence must be expressly tensor-qualified
                # and distinguished from the normative canonical root. The
                # precise local extension names remain subject to NOT-SAME review.
                behavioral = sorted(k for k in dims if
                    any("BoundaryResponse" in str(c) for c in dims[k].get("subDimensions", [])))
                self.assertEqual(len(behavioral), 1, f"missing/ambiguous behavioral parent in {path}")
                self.assertIn("T3_Temperament_", behavioral[0],
                    "behavioral aggregate must identify a local T3 Temperament-derived construct")

    def test_r1_new_graphs_and_receipts_do_not_retain_rejected_iri(self):
        artifacts = sorted(
            p for p in R1.rglob("*")
            if p.is_file() and p.suffix in (".nq", ".json", ".jcs")
        )
        self.assertTrue(artifacts)
        for path in artifacts:
            with self.subTest(path=path.relative_to(ROOT)):
                data = path.read_bytes()
                for token in REJECTED:
                    self.assertNotIn(token.encode(), data,
                        "newly generated R1 evidence still has rejected identity")
                self.assertNotIn(CANONICAL_VALIDITY.encode(), data,
                    "R1 graph/receipt may not place local behavioral evidence on standard V3 Validity")

    def test_historical_draft1_vectors_remain_in_separate_tree(self):
        # The existing legacy hash manifest and vector-immutability job check
        # their actual bytes; this guard makes accidental relocation visible.
        manifest = ROOT / "harness" / "legacy-vector-sha256.json"
        pinned = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(len(pinned), 29)
        self.assertTrue(all(str(p).startswith("vectors/") and not
                            str(p).startswith("vectors/r1/") for p in pinned))


if __name__ == "__main__":
    unittest.main()
