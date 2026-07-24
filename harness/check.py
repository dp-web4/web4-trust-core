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

SUITE = Path(__file__).resolve().parent.parent
HARNESS = Path(__file__).resolve().parent

FAILURES = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "ok  " if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- L1 semantic
print("L1 semantic — reference evaluator vs golden scores")
golden = (SUITE / "vectors" / "scores" / "expected-output.txt").read_text()
run = subprocess.run(
    [sys.executable, str(HARNESS / "evaluator.py")],
    capture_output=True, text=True,
)
check("evaluator exits 0", run.returncode == 0, run.stderr.strip()[:200])
check("evaluator stdout matches golden output", run.stdout == golden)

# ------------------------------------------------------------- L2 canonical
print("L2 canonicalization — graph hashes")
bn = SUITE / "vectors" / "canonicalization" / "blank-node-rdfc10"
check(
    "blank-node RDFC-1.0 canonical hash",
    sha256_file(bn / "expected-canonical.nq")
    == "a4f8b66fe8c89ccef71d34f2592c95076156000ec4181a4a882d1e69a4eb147a",
)
# Full RDFC-1.0 recomputation from input.nq (ported from the origin exploration).
verify = HARNESS / "rdfc10_verify.py"
if verify.exists():
    vrun = subprocess.run(
        [sys.executable, str(verify),
         str(bn / "input.nq"), str(bn / "expected-canonical.nq")],
        capture_output=True, text=True, cwd=str(verify.parent))
    check("blank-node RDFC-1.0 recomputation (verify.py)", vrun.returncode == 0,
          (vrun.stdout + vrun.stderr).strip()[:200])

sk = SUITE / "vectors" / "canonicalization" / "skolemized-sorted-nquads"
sk_input = sk.joinpath("input.nq").read_text().splitlines()
sk_canon = sk.joinpath("expected-canonical.nq").read_text().splitlines()
check("skolemized canonical = sorted(input) lines", sorted(sk_input) == sk_canon)
check(
    "skolemized canonical hash matches pin",
    sha256_file(sk / "expected-canonical.nq") == sk.joinpath("expected-hash.txt").read_text().strip(),
)

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
        d = SUITE / "vectors" / "receipts" / name
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

# ------------------------------------------------------- L4 standard-profile
print("L4 standard-profile — DerivationSpec vs web4-standard")
l4 = subprocess.run(
    [sys.executable, str(HARNESS / "l4_standard_profile.py")]
    + [str(SUITE / "vectors" / "receipts" / n / "spec.json")
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
