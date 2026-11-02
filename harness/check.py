#!/usr/bin/env python3
"""web4-trust-core conformance check harness (skeleton).

Four levels, checked in order:
  L1 semantic     — the reference evaluator regenerates the golden score output
  L2 canonical    — graph canonicalization hashes (blank-node RDFC-1.0 and
                    skolemized sorted-N-Quads) match their pinned values
  L3 byte-level   — law_hash / graph_hash / receipt_hash of the pinned receipts
                    recompute from the committed spec/graph/receipt bytes
  L4 standard     — no collisions with web4-standard: nothing minted in its
                    ontology namespace, no root derivation, no composite over
                    the T3/V3 triples (SPEC.md §11, l4_standard_profile.py)

Exit 0 iff every check passes. A future trust-core implementation swaps its
own evaluator into L1 and its own receipt emitter into L3; the vectors are the
contract, this harness is just the reference wiring.

Requires `jcs` (RFC 8785) for L3:
    python3 -m pip install -r ../requirements.txt
Run from the harness dir:
    python3 check.py
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from legacy_vectors import verify_legacy_vectors

SUITE = Path(__file__).resolve().parent.parent
HARNESS = Path(__file__).resolve().parent
# R1 is a new vector set; the original draft1 paths remain immutable.
VECTORS = SUITE / "vectors" / "r1"

FAILURES = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "ok  " if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


print("Legacy evidence — original vector bytes")
legacy_failures = verify_legacy_vectors(SUITE, HARNESS / "legacy-vector-sha256.json")
check("original vector files match their baseline SHA-256 pins", not legacy_failures,
      "; ".join(legacy_failures))
legacy_run = subprocess.run([sys.executable, str(HARNESS / "legacy_draft1_evaluator.py")],
                            capture_output=True, text=True)
check("draft1 historical evaluator matches original golden output", legacy_run.returncode == 0
      and legacy_run.stdout == (SUITE / "vectors" / "scores" / "expected-output.txt").read_text(),
      legacy_run.stderr.strip()[:200])


# ---------------------------------------------------------------- L1 semantic
print("L1 semantic — reference evaluator vs golden scores")
golden = (VECTORS / "scores" / "expected-output.txt").read_text()
run = subprocess.run(
    [sys.executable, str(HARNESS / "evaluator.py")],
    capture_output=True, text=True,
)
check("evaluator exits 0", run.returncode == 0, run.stderr.strip()[:200])
check("evaluator stdout matches golden output", run.stdout == golden)

# ------------------------------------------------------------- L2 canonical
print("L2 canonicalization — graph hashes")
bn = VECTORS / "canonicalization" / "blank-node-rdfc10"
check(
    "blank-node RDFC-1.0 canonical hash",
    sha256_file(bn / "expected-canonical.nq")
    == "a4f8b66fe8c89ccef71d34f2592c95076156000ec4181a4a882d1e69a4eb147a",
)

# The original canonicalization vectors remain independently exercised, not
# just retained as inert files. They predate R1 and are historical evidence.
legacy_bn = SUITE / "vectors" / "canonicalization" / "blank-node-rdfc10"
check("draft1 blank-node canonical hash", sha256_file(legacy_bn / "expected-canonical.nq")
      == "ba8b2deb20e0ec6be26f27e250b43f63945dcec3c0895158df2bce37128a84d4")
# Full RDFC-1.0 recomputation from input.nq (ported from the origin exploration).
verify = HARNESS / "rdfc10_verify.py"
if verify.exists():
    vrun = subprocess.run(
        [sys.executable, str(verify),
         str(bn / "input.nq"), str(bn / "expected-canonical.nq")],
        capture_output=True, text=True, cwd=str(verify.parent))
    check("blank-node RDFC-1.0 recomputation (verify.py)", vrun.returncode == 0,
          (vrun.stdout + vrun.stderr).strip()[:200])
    legacy_verify = subprocess.run([sys.executable, str(verify), str(legacy_bn / "input.nq"),
                                    str(legacy_bn / "expected-canonical.nq")],
                                   capture_output=True, text=True, cwd=str(verify.parent))
    check("draft1 blank-node RDFC-1.0 recomputation", legacy_verify.returncode == 0,
          (legacy_verify.stdout + legacy_verify.stderr).strip()[:200])

sk = VECTORS / "canonicalization" / "skolemized-sorted-nquads"
sk_input = sk.joinpath("input.nq").read_text().splitlines()
sk_canon = sk.joinpath("expected-canonical.nq").read_text().splitlines()
check("skolemized canonical = sorted(input) lines", sorted(sk_input) == sk_canon)
check(
    "skolemized canonical hash matches pin",
    sha256_file(sk / "expected-canonical.nq") == sk.joinpath("expected-hash.txt").read_text().strip(),
)
legacy_sk = SUITE / "vectors" / "canonicalization" / "skolemized-sorted-nquads"
check("draft1 skolemized canonical = sorted input",
      sorted(legacy_sk.joinpath("input.nq").read_text().splitlines())
      == legacy_sk.joinpath("expected-canonical.nq").read_text().splitlines())
check("draft1 skolemized canonical hash matches pin", sha256_file(legacy_sk / "expected-canonical.nq")
      == legacy_sk.joinpath("expected-hash.txt").read_text().strip())

# ------------------------------------------------------------- L3 byte-level
print("L3 byte-level — receipt vectors")
try:
    import jcs  # type: ignore
except ModuleNotFoundError:
    check("jcs available (RFC 8785)", False,
          "pip install jcs  (see requirements.txt)")
    jcs = None

if jcs is not None:
    for name in ("v3", "v4b", "v6b", "v7-fold-order"):
        d = VECTORS / "receipts" / name
        expected = json.loads(d.joinpath("expected-hashes.json").read_text())
        spec_bytes = d.joinpath("spec.json").read_bytes()

        # law_hash = sha256(JCS(spec)); spec.json is stored in canonical bytes.
        spec = json.loads(spec_bytes)
        check(f"{name}: spec.json is JCS-canonical bytes",
              jcs.canonicalize(spec, utf8=True) == spec_bytes)
        check(f"{name}: law_hash",
              hashlib.sha256(spec_bytes).hexdigest() == expected["law_hash"])

        receipt = json.loads(d.joinpath("receipt.json").read_text())
        check(f"{name}: receipt.law_hash binds spec",
              receipt["law_hash"] == expected["law_hash"])

        hash_source = {k: v for k, v in receipt.items()
                       if k not in ("evaluator", "receipt_hash")}
        canonical = jcs.canonicalize(hash_source, utf8=True)
        check(f"{name}: receipt.jcs matches recomputed canonical bytes",
              canonical == d.joinpath("receipt.jcs").read_bytes())
        check(f"{name}: receipt_hash",
              hashlib.sha256(canonical).hexdigest() == expected["receipt_hash"]
              == receipt["receipt_hash"])

        if d.joinpath("expected-canonical.nq").exists():
            check(f"{name}: graph_hash binds canonical graph bytes",
                  sha256_file(d / "expected-canonical.nq") == expected["graph_hash"]
                  == receipt["graph_hash"])

# The draft1 receipts retain their original L3 checks. L4 is deliberately run
# only on R1: draft1's known namespace collision is the reason R1 is proposed.
if jcs is not None:
    for name in ("v3", "v4b", "v6b", "v7-fold-order"):
        d = SUITE / "vectors" / "receipts" / name
        expected = json.loads(d.joinpath("expected-hashes.json").read_text())
        spec_bytes = d.joinpath("spec.json").read_bytes()
        spec = json.loads(spec_bytes)
        check(f"draft1 {name}: spec.json is JCS-canonical bytes",
              jcs.canonicalize(spec, utf8=True) == spec_bytes)
        check(f"draft1 {name}: law_hash", hashlib.sha256(spec_bytes).hexdigest() == expected["law_hash"])
        receipt = json.loads(d.joinpath("receipt.json").read_text())
        check(f"draft1 {name}: receipt.law_hash binds spec", receipt["law_hash"] == expected["law_hash"])
        canonical = jcs.canonicalize({k: v for k, v in receipt.items()
                                      if k not in ("evaluator", "receipt_hash")}, utf8=True)
        check(f"draft1 {name}: receipt.jcs matches recomputed canonical bytes",
              canonical == d.joinpath("receipt.jcs").read_bytes())
        check(f"draft1 {name}: receipt_hash", hashlib.sha256(canonical).hexdigest()
              == expected["receipt_hash"] == receipt["receipt_hash"])
        if d.joinpath("expected-canonical.nq").exists():
            check(f"draft1 {name}: graph_hash binds canonical graph bytes",
                  sha256_file(d / "expected-canonical.nq") == expected["graph_hash"] == receipt["graph_hash"])

# ------------------------------------------------------- L4 standard-profile
print("L4 standard-profile — DerivationSpec vs web4-standard")
l4 = subprocess.run(
    [sys.executable, str(HARNESS / "l4_standard_profile.py")]
    + [str(VECTORS / "receipts" / n / "spec.json")
       for n in ("v3", "v4b", "v6b", "v7-fold-order")],
    capture_output=True, text=True,
)
check("L4 audit: no collisions with web4-standard", l4.returncode == 0,
      l4.stdout.strip().splitlines()[-1][:300] if l4.stdout.strip() else l4.stderr[:300])

print()
if FAILURES:
    print(f"CONFORMANCE: FAIL ({len(FAILURES)}): {', '.join(FAILURES)}")
    sys.exit(1)
print("CONFORMANCE: PASS")
