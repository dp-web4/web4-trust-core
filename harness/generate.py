#!/usr/bin/env python3
"""Deterministic generator for the pinned conformance artifacts.

Produces (relative to the suite root):
  vectors/canonicalization/skolemized-sorted-nquads/{input.nq,expected-canonical.nq,expected-hash.txt}
  vectors/receipts/v6b/{spec.json,receipt.json,receipt.jcs,expected-hashes.json}
  vectors/receipts/v7-fold-order/{spec.json,input.nq,expected-canonical.nq,receipt.json,receipt.jcs,expected-hashes.json,anti-vector.txt}

Everything here is derivable; the committed artifacts are the pinned bytes.
Requires the `jcs` package (RFC 8785):
    python3 -m pip install -r ../requirements.txt
Run from the harness dir:
    python3 generate.py
"""
import hashlib
import json
import sys
from math import sqrt
from pathlib import Path

SUITE = Path(__file__).resolve().parent.parent
HARNESS = Path(__file__).resolve().parent
import jcs  # type: ignore

# R1 namespace discipline: every term this suite mints lives in the
# exploration's own namespace, never in the standard's ontology namespace
# (https://web4.io/ontology# is web4-standard's; its terms carry pinned
# semantics this evaluator does not implement).
W = "https://web4.io/trust-derivation#"
XSD = "http://www.w3.org/2001/XMLSchema#"
MRH = "urn:web4:mrh:interactive-dev"
ANCHOR = "urn:web4:entity:measured-adj"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"  wrote {path.relative_to(SUITE)}")


# --------------------------------------------------------------------------
# Shared spec scaffolding (DERIVATIONSPEC.md draft-1 syntax)
# --------------------------------------------------------------------------

def base_spec(spec_id: str, observation_nodes: str) -> dict:
    return {
        "spec_id": spec_id,
        "core": {"name": "web4-trust-core", "semantics": 1},
        "prefixes": {"w4td": W, "xsd": XSD},
        "ontology": {
            "hasObservation": "w4td:hasObservation",
            "dimension": "w4td:dimension",
            "adjudicatedBy": "w4td:adjudicatedBy",
            "confidence": "w4td:confidence",
            "dependsOn": "w4td:dependsOn",
            "height": "w4td:height",
            "mrh": "w4td:mrh",
        },
        "dimensions": {
            "w4td:BoundaryConformance": {
                "subDimensions": [
                    "w4td:BoundaryResponse",
                    "w4td:CorrectionAcceptance",
                    "w4td:EscalationProportionality",
                ]
            },
            "w4td:Integrity": {"subDimensions": ["w4td:AdjudicationQuality"]},
        },
        "parameters": {
            "prior_alpha": 1.0,
            "prior_beta": 1.0,
            "unmeasured_if_total_weight_below": 0.01,
            "provenance_unmeasured_weight": 0.0,
            "dependency_discount_per_hop": 0.5,
            "provenance_weight_statistic": "mean",
        },
        "trust_anchors": [{"id": ANCHOR, "law_weight": 1.0}],
        "evidence_rules": [
            {
                "match": {
                    "w4td:method": "w4td:Adjudication",
                    "w4td:outcome": "w4td:Upheld",
                },
                "confidence": 1.0,
            }
        ],
        "observation_nodes": observation_nodes,
    }


def law_hash_of(spec: dict) -> tuple[str, bytes]:
    canonical = jcs.canonicalize(spec, utf8=True)
    return sha256_hex(canonical), canonical


def finish_receipt(receipt: dict, evaluator_version: str) -> tuple[dict, bytes, str]:
    receipt = dict(receipt)
    receipt["evaluator"] = {"name": "web4-trust-core", "version": evaluator_version}
    hash_source = {k: v for k, v in receipt.items() if k not in ("evaluator", "receipt_hash")}
    canonical = jcs.canonicalize(hash_source, utf8=True)
    receipt["receipt_hash"] = sha256_hex(canonical)
    return receipt, canonical, receipt["receipt_hash"]


def anchored_wp(anchor_id: str = ANCHOR, law_weight: float = 1.0) -> dict:
    return {
        "value": 1.0,
        "basis": "anchored",
        "anchor": {"id": anchor_id, "law_weight": law_weight, "derived_integrity": None},
    }


def unmeasured_wp() -> dict:
    return {"value": 0.0, "basis": "unmeasured"}


# --------------------------------------------------------------------------
# 1. Skolemized canonicalization vector: the V6b graph with chain-derived
#    observation IRIs. Canonical form = code-point-sorted N-Quad lines.
# --------------------------------------------------------------------------

OBS_S = "urn:web4:obs:blk10:0"   # subject-S obs, block at height 10, index 0
OBS_M = "urn:web4:obs:blk20:0"   # member-M obs, block at height 20, index 0

V6B_SKOLEM_QUADS = [
    f"<{OBS_M}> <{W}dependsOn> <{OBS_S}> .",
    f"<urn:web4:grain:member-M> <{W}hasObservation> <{OBS_M}> .",
    f'<{OBS_S}> <{W}confidence> "0.92"^^<{XSD}decimal> .',
    f'<{OBS_M}> <{W}height> "20"^^<{XSD}integer> .',
    f"<{OBS_S}> <{W}dimension> <{W}BoundaryResponse> .",
    f"<{OBS_M}> <{W}adjudicatedBy> <{ANCHOR}> .",
    f'<{OBS_S}> <{W}height> "10"^^<{XSD}integer> .',
    f"<{OBS_M}> <{W}dimension> <{W}BoundaryResponse> .",
    f"<{OBS_S}> <{W}adjudicatedBy> <{ANCHOR}> .",
    f"<urn:web4:grain:subject-S> <{W}hasObservation> <{OBS_S}> .",
    f'<{OBS_M}> <{W}confidence> "1.0"^^<{XSD}decimal> .',
    f"<{OBS_S}> <{W}mrh> <{MRH}> .",
    f"<{OBS_M}> <{W}mrh> <{MRH}> .",
]


def gen_skolemized_vector() -> None:
    out = SUITE / "vectors" / "canonicalization" / "skolemized-sorted-nquads"
    input_bytes = ("\n".join(V6B_SKOLEM_QUADS) + "\n").encode()
    canonical_bytes = ("\n".join(sorted(V6B_SKOLEM_QUADS)) + "\n").encode()
    write(out / "input.nq", input_bytes)
    write(out / "expected-canonical.nq", canonical_bytes)
    write(out / "expected-hash.txt", (sha256_hex(canonical_bytes) + "\n").encode())


# --------------------------------------------------------------------------
# 2. V6b receipt, corrected: law_hash over JCS bytes (finding 8) and the
#    draft-1 spec syntax. Scores identical to kimi's instance; only the law
#    binding changes. Uses the blank-node graph (general RDFC-1.0 path).
# --------------------------------------------------------------------------

BLANK_NODE_GRAPH_HASH = "a4f8b66fe8c89ccef71d34f2592c95076156000ec4181a4a882d1e69a4eb147a"


def gen_v6b_receipt() -> None:
    out = SUITE / "vectors" / "receipts" / "v6b"
    spec = base_spec("web4-trust-core-conformance-v6b-draft2", "blank-node")
    law_hash, spec_bytes = law_hash_of(spec)

    receipt = {
        "law_hash": law_hash,
        "graph_hash": BLANK_NODE_GRAPH_HASH,
        "chain_range": {"from": 0, "below": 21},
        "mrh": MRH,
        "parameters": spec["parameters"],
        "scores": [
            {
                "subject": "urn:web4:grain:subject-S",
                "dimension": "w4td:BoundaryResponse",
                "result": {"mu": 0.64, "sigma": 0.24, "strength": 1.0},
                "evidence": [
                    {
                        "obs": "urn:web4:chain:example:obs:10",
                        "confidence": 0.92,
                        "height": 10,
                        "w_p": anchored_wp(),
                        "w_d": {"value": 1.0, "deps": []},
                    }
                ],
                "unmeasured_upstream": [],
            },
            {
                "subject": "urn:web4:grain:member-M",
                "dimension": "w4td:BoundaryResponse",
                "result": {
                    "mu": 0.5689655172413793,
                    "sigma": 0.27178483084735455,
                    "strength": 0.31999999999999984,
                },
                "evidence": [
                    {
                        "obs": "urn:web4:chain:example:obs:20",
                        "confidence": 1.0,
                        "height": 20,
                        "w_p": anchored_wp(),
                        "w_d": {
                            "value": 0.32,
                            "deps": [
                                {
                                    "obs": "urn:web4:chain:example:obs:10",
                                    "score_used": 0.64,
                                    "discount": 0.5,
                                }
                            ],
                        },
                    }
                ],
                "unmeasured_upstream": [],
            },
        ],
    }
    receipt, canonical, receipt_hash = finish_receipt(receipt, "claude-code-conformance-2026-07-24")

    write(out / "spec.json", spec_bytes)
    write(out / "receipt.json", json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True).encode())
    write(out / "receipt.jcs", canonical)
    write(out / "expected-hashes.json", json.dumps({
        "law_hash": law_hash,
        "graph_hash": BLANK_NODE_GRAPH_HASH,
        "receipt_hash": receipt_hash,
        "note": "law_hash differs from experiment-kimi-code-receipt-v6b-2026-07-24 "
                "(1548ddbd...) because (a) law_hash is now over JCS bytes, not "
                "json.dumps bytes (finding 8), and (b) the spec follows the "
                "DERIVATIONSPEC.md draft-1 syntax.",
    }, indent=2).encode())
    print(f"  v6b law_hash:     {law_hash}")
    print(f"  v6b receipt_hash: {receipt_hash}")


# --------------------------------------------------------------------------
# 3. V3 receipt: adjudicator capture -> null with unmeasured_upstream.
#    Five observations from an unmeasured adjudicator; harsh default gives
#    total weight 0.0, so the score is null and every obs is recorded as
#    upstream-unmeasured.
# --------------------------------------------------------------------------

V3_OBS = [f"urn:web4:obs:blk100:{i}" for i in range(5)]
V3_SUBJECT = "urn:web4:grain:kimi-code"
V3_ADJUDICATOR = "urn:web4:entity:adjudicator-X"


def v3_quads() -> list:
    quads = []
    for iri in V3_OBS:
        quads.extend([
            f"<{V3_SUBJECT}> <{W}hasObservation> <{iri}> .",
            f"<{iri}> <{W}dimension> <{W}BoundaryResponse> .",
            f"<{iri}> <{W}adjudicatedBy> <{V3_ADJUDICATOR}> .",
            f'<{iri}> <{W}confidence> "1.0"^^<{XSD}decimal> .',
            f'<{iri}> <{W}height> "100"^^<{XSD}integer> .',
            f"<{iri}> <{W}mrh> <{MRH}> .",
        ])
    return quads


def gen_v3_receipt() -> None:
    out = SUITE / "vectors" / "receipts" / "v3"
    spec = base_spec("web4-trust-core-conformance-v3-draft2", "skolemized-iri")
    spec["trust_anchors"] = []  # no anchors => adjudicator-X is unmeasured
    law_hash, spec_bytes = law_hash_of(spec)

    quads = v3_quads()
    input_bytes = ("\n".join(quads) + "\n").encode()
    canonical_bytes = ("\n".join(sorted(quads)) + "\n").encode()
    graph_hash = sha256_hex(canonical_bytes)

    receipt = {
        "law_hash": law_hash,
        "graph_hash": graph_hash,
        "chain_range": {"from": 0, "below": 101},
        "mrh": MRH,
        "parameters": spec["parameters"],
        "scores": [
            {
                "subject": V3_SUBJECT,
                "dimension": "w4td:BoundaryResponse",
                "result": None,
                "evidence": [
                    {
                        "obs": iri,
                        "confidence": 1.0,
                        "height": 100,
                        "w_p": unmeasured_wp(),
                        "w_d": {"value": 1.0, "deps": []},
                    }
                    for iri in V3_OBS
                ],
                "unmeasured_upstream": [
                    {
                        "obs": iri,
                        "reason": "unmeasured_adjudicator",
                        "adjudicator": V3_ADJUDICATOR,
                    }
                    for iri in V3_OBS
                ],
            }
        ],
    }
    receipt, canonical, receipt_hash = finish_receipt(receipt, "kimi-code-conformance-2026-07-24")

    write(out / "spec.json", spec_bytes)
    write(out / "input.nq", input_bytes)
    write(out / "expected-canonical.nq", canonical_bytes)
    write(out / "receipt.json", json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True).encode())
    write(out / "receipt.jcs", canonical)
    write(out / "expected-hashes.json", json.dumps({
        "law_hash": law_hash,
        "graph_hash": graph_hash,
        "receipt_hash": receipt_hash,
        "note": "V3 exercises unmeasured_upstream: every observation has an unmeasured adjudicator.",
    }, indent=2).encode())
    print(f"  v3 law_hash:     {law_hash}")
    print(f"  v3 graph_hash:   {graph_hash}")
    print(f"  v3 receipt_hash: {receipt_hash}")


# --------------------------------------------------------------------------
# 4. V4b receipt: anchor drift visibility.
#    member-M is anchored by operator, but operator's own derived Integrity is
#    low (0.333) because measured-adj adjudicated a 0.0-confidence act against
#    it. Receipt shows both scores side by side.
# --------------------------------------------------------------------------

V4B_M_OBS = [f"urn:web4:obs:blk10:{i}" for i in range(3)]
V4B_OP_OBS = ["urn:web4:obs:blk20:0"]


def v4b_quads() -> list:
    quads = []
    for iri in V4B_M_OBS:
        quads.extend([
            f"<urn:web4:grain:member-M> <{W}hasObservation> <{iri}> .",
            f"<{iri}> <{W}dimension> <{W}BoundaryResponse> .",
            f"<{iri}> <{W}adjudicatedBy> <urn:web4:entity:operator> .",
            f'<{iri}> <{W}confidence> "1.0"^^<{XSD}decimal> .',
            f'<{iri}> <{W}height> "10"^^<{XSD}integer> .',
            f"<{iri}> <{W}mrh> <{MRH}> .",
        ])
    for iri in V4B_OP_OBS:
        quads.extend([
            f"<urn:web4:grain:operator> <{W}hasObservation> <{iri}> .",
            f"<{iri}> <{W}dimension> <{W}AdjudicationQuality> .",
            f"<{iri}> <{W}adjudicatedBy> <urn:web4:entity:measured-adj> .",
            f'<{iri}> <{W}confidence> "0.0"^^<{XSD}decimal> .',
            f'<{iri}> <{W}height> "20"^^<{XSD}integer> .',
            f"<{iri}> <{W}mrh> <{MRH}> .",
        ])
    return quads


def gen_v4b_receipt() -> None:
    out = SUITE / "vectors" / "receipts" / "v4b"
    spec = base_spec("web4-trust-core-conformance-v4b-draft2", "skolemized-iri")
    spec["trust_anchors"] = [
        {"id": "urn:web4:entity:operator", "law_weight": 1.0},
        {"id": "urn:web4:entity:measured-adj", "law_weight": 1.0},
    ]
    law_hash, spec_bytes = law_hash_of(spec)

    quads = v4b_quads()
    input_bytes = ("\n".join(quads) + "\n").encode()
    canonical_bytes = ("\n".join(sorted(quads)) + "\n").encode()
    graph_hash = sha256_hex(canonical_bytes)

    receipt = {
        "law_hash": law_hash,
        "graph_hash": graph_hash,
        "chain_range": {"from": 0, "below": 21},
        "mrh": MRH,
        "parameters": spec["parameters"],
        "scores": [
            {
                "subject": "urn:web4:grain:member-M",
                "dimension": "w4td:BoundaryResponse",
                "result": {"mu": 0.8, "sigma": 0.1632993161855452, "strength": 3.0},
                "evidence": [
                    {
                        "obs": iri,
                        "confidence": 1.0,
                        "height": 10,
                        "w_p": anchored_wp("urn:web4:entity:operator", 1.0),
                        "w_d": {"value": 1.0, "deps": []},
                    }
                    for iri in V4B_M_OBS
                ],
                "unmeasured_upstream": [],
            },
            {
                "subject": "urn:web4:grain:operator",
                "dimension": "w4td:Integrity",
                "result": {
                    "mu": 0.3333333333333333,
                    "sigma": 0.23570226039551584,
                    "strength": 1.0,
                },
                "evidence": [
                    {
                        "obs": V4B_OP_OBS[0],
                        "confidence": 0.0,
                        "height": 20,
                        "w_p": anchored_wp("urn:web4:entity:measured-adj", 1.0),
                        "w_d": {"value": 1.0, "deps": []},
                    }
                ],
                "unmeasured_upstream": [],
            },
        ],
    }
    receipt, canonical, receipt_hash = finish_receipt(receipt, "kimi-code-conformance-2026-07-24")

    write(out / "spec.json", spec_bytes)
    write(out / "input.nq", input_bytes)
    write(out / "expected-canonical.nq", canonical_bytes)
    write(out / "receipt.json", json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True).encode())
    write(out / "receipt.jcs", canonical)
    write(out / "expected-hashes.json", json.dumps({
        "law_hash": law_hash,
        "graph_hash": graph_hash,
        "receipt_hash": receipt_hash,
        "note": "V4b exercises anchor drift: member-M anchored by operator, operator derived Integrity low.",
    }, indent=2).encode())
    print(f"  v4b law_hash:     {law_hash}")
    print(f"  v4b graph_hash:   {graph_hash}")
    print(f"  v4b receipt_hash: {receipt_hash}")


# --------------------------------------------------------------------------
# 5. V7 fold-order vector: three same-height observations whose confidence
#    sums are fold-order sensitive in binary64. Canonical fold order is
#    (height asc, canonical node identifier asc by code point).
# --------------------------------------------------------------------------

V7_OBS = [
    ("urn:web4:obs:blk10:0", 0.8),
    ("urn:web4:obs:blk10:1", 0.95),
    ("urn:web4:obs:blk10:2", 0.32),
]


def v7_quads() -> list:
    quads = []
    for iri, c in V7_OBS:
        # Shortest round-trip decimal for the literal, matching receipt bytes.
        quads.extend([
            f"<urn:web4:grain:subject-S> <{W}hasObservation> <{iri}> .",
            f"<{iri}> <{W}adjudicatedBy> <{ANCHOR}> .",
            f'<{iri}> <{W}confidence> "{repr(c)}"^^<{XSD}decimal> .',
            f"<{iri}> <{W}dimension> <{W}BoundaryResponse> .",
            f'<{iri}> <{W}height> "10"^^<{XSD}integer> .',
            f"<{iri}> <{W}mrh> <{MRH}> .",
        ])
    return quads


def beta_fold(cs: list, params: dict) -> dict:
    """The normative fold: left-to-right in the given order, binary64."""
    scw = 0.0
    s1cw = 0.0
    total_w = 0.0
    for c in cs:            # weights are all 1.0 here (anchored, no deps)
        scw += c * 1.0
    for c in cs:
        s1cw += (1 - c) * 1.0
    for c in cs:
        total_w += 1.0
    a = params["prior_alpha"] + scw
    b = params["prior_beta"] + s1cw
    mu = a / (a + b)
    sigma = sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
    strength = a + b - params["prior_alpha"] - params["prior_beta"]
    return {"mu": mu, "sigma": sigma, "strength": strength}


def gen_v7_vector() -> None:
    out = SUITE / "vectors" / "receipts" / "v7-fold-order"
    spec = base_spec("web4-trust-core-conformance-v7-fold-order-draft2", "skolemized-iri")
    law_hash, spec_bytes = law_hash_of(spec)

    quads = v7_quads()
    # input.nq deliberately scrambles: reverse observation-block order.
    scrambled = quads[12:18] + quads[6:12] + quads[0:6]
    input_bytes = ("\n".join(scrambled) + "\n").encode()
    canonical_bytes = ("\n".join(sorted(quads)) + "\n").encode()
    graph_hash = sha256_hex(canonical_bytes)

    params = spec["parameters"]
    canonical_cs = [c for _, c in V7_OBS]          # obs IRI order = canonical order
    result = beta_fold(canonical_cs, params)
    wrong = beta_fold(list(reversed(canonical_cs)), params)

    receipt = {
        "law_hash": law_hash,
        "graph_hash": graph_hash,
        "chain_range": {"from": 0, "below": 11},
        "mrh": MRH,
        "parameters": params,
        "scores": [
            {
                "subject": "urn:web4:grain:subject-S",
                "dimension": "w4td:BoundaryResponse",
                "result": result,
                "evidence": [
                    {
                        "obs": iri,
                        "confidence": c,
                        "height": 10,
                        "w_p": anchored_wp(),
                        "w_d": {"value": 1.0, "deps": []},
                    }
                    for iri, c in V7_OBS
                ],
                "unmeasured_upstream": [],
            }
        ],
    }
    receipt, canonical, receipt_hash = finish_receipt(receipt, "claude-code-conformance-2026-07-24")

    write(out / "spec.json", spec_bytes)
    write(out / "input.nq", input_bytes)
    write(out / "expected-canonical.nq", canonical_bytes)
    write(out / "receipt.json", json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True).encode())
    write(out / "receipt.jcs", canonical)
    write(out / "expected-hashes.json", json.dumps({
        "law_hash": law_hash,
        "graph_hash": graph_hash,
        "receipt_hash": receipt_hash,
    }, indent=2).encode())

    anti = (
        "V7 anti-vector: what a NON-conforming evaluator produces.\n"
        "\n"
        f"Canonical fold order (height asc, obs IRI asc): {canonical_cs}\n"
        f"  mu       = {result['mu']!r}\n"
        f"  sigma    = {result['sigma']!r}\n"
        f"  strength = {result['strength']!r}\n"
        "\n"
        f"Reverse fold order: {list(reversed(canonical_cs))}\n"
        f"  mu       = {wrong['mu']!r}\n"
        f"  sigma    = {wrong['sigma']!r}\n"
        f"  strength = {wrong['strength']!r}\n"
        "\n"
        "Both are 'correct' real-number arithmetic; only the canonical fold\n"
        "order yields the pinned receipt bytes. If your evaluator produces the\n"
        "reverse-order values, its evidence fold is not sorted by\n"
        "(height, canonical node identifier).\n"
    )
    write(out / "anti-vector.txt", anti.encode())
    print(f"  v7 law_hash:     {law_hash}")
    print(f"  v7 graph_hash:   {graph_hash}")
    print(f"  v7 receipt_hash: {receipt_hash}")
    print(f"  v7 canonical result: {result}")
    print(f"  v7 wrong-fold result: {wrong}")


if __name__ == "__main__":
    print("generating pinned conformance artifacts:")
    gen_skolemized_vector()
    gen_v6b_receipt()
    gen_v3_receipt()
    gen_v4b_receipt()
    gen_v7_vector()
