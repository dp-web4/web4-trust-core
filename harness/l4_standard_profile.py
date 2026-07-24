#!/usr/bin/env python3
"""L4 standard-profile audit — does a DerivationSpec collide with web4-standard?

Fourth conformance level (L1 semantic / L2 canonicalization / L3 byte-level /
**L4 standard-profile**). Authored by legion on thread trust-derivation-rdf
(`shared-context/explorations/trust-derivation-rdf-2026-07-24/`
`l4-standard-profile-audit.py`); adopted here with one extension: the L4d
namespace sweep covers EVERY IRI the spec uses — `dimensions`, the `ontology`
property map, and `evidence_rules` vocabulary, plus any sibling `input.nq`
graph — not just the dimension tree. (The original swept only `dimensions`
and therefore missed 10 minted property/vocabulary terms; see the thread
response of 2026-07-24.)

Checks
  L4a  no standard root dimension IRI is derived by this law
       (V3 roots have a protocol-invariant calculation, §10.2 / t3v3-014;
        T3 roots have protocol-invariant update dynamics, t3v3-003)
  L4b  no parent aggregates the T3 or V3 root triple
       (semantics-1 aggregates by strength-weighted mean; the standard
        composites by fixed weights — different operators, not different
        parameterizations of one operator)
  L4c  every root claim (a parent that is nobody's child) is either a standard
       root or lives in a society-local namespace
  L4d  no term used anywhere in the spec or its graph is minted inside the
       standard's namespace (the ontology invites extending the *tree*, not
       the *namespace*)
  L4e  parameter diff against §10.2/§10.3 — informational; vacuous today, and
       says so rather than passing silently
  L4f  informational: standard-defined terms the spec reuses — their
       rdfs:domain/range compatibility is not decidable from the spec alone
       (e.g. web4:dimension is declared rdfs:domain web4:DimensionScore;
        using it on observation nodes entails they are DimensionScores)

Library-free by design (repo law rule 5; L4 needs not even `jcs`).

    python3 l4_standard_profile.py <spec.json> [spec.json ...]
    python3 l4_standard_profile.py --verify-pins <path/to/t3v3-ontology.ttl>

Exit 0 iff every spec passes every blocking check.

--------------------------------------------------------------------------
CONSTANTS-IN-CODE SUCCESSION STATEMENT (research target #1, applied to self)

The pinned sets below are transcribed from
`dp-web4/web4:web4-standard/ontology/t3v3-ontology.ttl` and
`web4-standard/core-spec/t3-v3-tensors.md` §10.2, read at web4 commit
8c3711c6 (2026-07-24) and re-verified at 950eb251. They are code, not law.
The ontology file is law. Run `--verify-pins <ttl>` wherever a web4 checkout
exists and the pins re-derive from source; where it does not, they are an
unwitnessed copy and should be treated as such.
--------------------------------------------------------------------------
"""
import json
import re
import sys
from pathlib import Path

STANDARD_NS = "https://web4.io/ontology#"

T3_ROOTS = {"Talent", "Training", "Temperament"}
V3_ROOTS = {"Valuation", "Veracity", "Validity"}

# Every term t3v3-ontology.ttl defines in STANDARD_NS. Minting anything else
# into that namespace is squatting, not extending.
ONTOLOGY_TERMS = {
    # classes
    "Dimension", "T3Tensor", "V3Tensor", "DimensionScore",
    # root dimensions
    "Talent", "Training", "Temperament",
    "Valuation", "Veracity", "Validity",
    # the fractal edge + binding/score properties
    "subDimensionOf", "entity", "role", "hasDimensionScore",
    "dimension", "score", "observedAt", "witnessedBy",
    "talent", "training", "temperament",
    "valuation", "veracity", "validity",
}

# §10.2 protocol-invariant + §10.3 society-configurable parameter names, in the
# only form a DerivationSpec could plausibly spell them.
STANDARD_PARAMETERS = {
    "t3_composite_weights", "v3_composite_weights", "t3_update_formula",
    "t3_dimension_update_factors", "talent_no_decay", "t3_value_range",
    "v3_value_range", "diminishing_returns_base", "diminishing_returns_floor",
    "bridge_primary_weight", "bridge_secondary_weight", "v3_calculation",
    "operational_health_weights", "atp_conservation",
    "training_decay_rate", "temperament_recovery_rate", "atp_decay_rate",
    "atp_transfer_fees", "demurrage_policy", "role_requirement_thresholds",
}

# Parameters that WILL land in the diff once their vector exists. Named so the
# vacuity below is a known gap, not an unnoticed one.
PENDING_PARAMETER_OVERLAP = {
    "decay_halflife_days": "§10.3 Training decay rate / §10.4 Talent decay "
                           "(t3v3-012: Talent MUST NOT decay; audit C192-N1)",
    "max_weight_per_source_per_halflife": "no standard row yet — would be a "
                                          "new society-configurable parameter",
}

IRI_IN_NQ = re.compile(r"<(" + re.escape(STANDARD_NS) + r"[^>]*)>")

FAILURES = []
WARNINGS = []


def check(spec_name, level, name, ok, detail="", blocking=True):
    if ok:
        print(f"  [ok  ] {level} {name}")
        return
    mark = "FAIL" if blocking else "warn"
    print(f"  [{mark}] {level} {name} — {detail}")
    (FAILURES if blocking else WARNINGS).append(f"{spec_name}: {level} {name}")


def resolve(curie, prefixes):
    """CURIE -> IRI via the spec's own prefix map; passthrough for full IRIs."""
    if ":" not in curie:
        return curie
    if curie.startswith(("http://", "https://", "urn:")):
        return curie
    pfx, local = curie.split(":", 1)
    return prefixes.get(pfx, pfx + ":") + local


def local_name(iri):
    return iri[len(STANDARD_NS):] if iri.startswith(STANDARD_NS) else None


def spec_iris(node, prefixes, skip_keys=("spec_id", "core", "prefixes",
                                         "parameters", "observation_nodes")):
    """Every IRI the spec uses: walk all strings (keys and values), resolve
    CURIEs through the spec's own prefix map. Sections that cannot hold term
    IRIs are skipped."""
    out = set()
    if isinstance(node, dict):
        for k, v in node.items():
            if k in skip_keys:
                continue
            if isinstance(k, str) and ":" in k:
                out.add(resolve(k, prefixes))
            out |= spec_iris(v, prefixes, skip_keys=())
    elif isinstance(node, list):
        for v in node:
            out |= spec_iris(v, prefixes, skip_keys=())
    elif isinstance(node, str) and ":" in node:
        out.add(resolve(node, prefixes))
    return out


def audit(path):
    path = Path(path)
    spec = json.loads(path.read_text())
    name = spec.get("spec_id", str(path))
    print(f"\n{path}  ({name})")

    prefixes = spec.get("prefixes", {})
    dims = spec.get("dimensions", {})
    parents = {resolve(k, prefixes): [resolve(c, prefixes)
                                      for c in v.get("subDimensions", [])]
               for k, v in dims.items()}
    children = {c for cs in parents.values() for c in cs}
    all_dims = set(parents) | children

    # ---- L4a: standard root dimensions are not this law's to derive --------
    derived_roots = []
    for iri in sorted(all_dims):
        ln = local_name(iri)
        if ln in V3_ROOTS:
            derived_roots.append(
                f"{iri} is a V3 root; §10.2 pins its calculation "
                f"({'validity=1.0 if transferred else 0.0' if ln == 'Validity' else 'see §3.3'}, "
                f"t3v3-014) — this law derives it from evidence instead")
        elif ln in T3_ROOTS:
            derived_roots.append(
                f"{iri} is a T3 root; §10.2 pins its update dynamics "
                f"(0.02×(quality−0.5), factors, t3v3-003)")
    check(name, "L4a", "no standard root dimension is derived by this law",
          not derived_roots, "; ".join(derived_roots))

    # ---- L4b: no composite parent over a root triple -----------------------
    composites = []
    for p, cs in sorted(parents.items()):
        locals_ = {local_name(c) for c in cs}
        if T3_ROOTS <= locals_:
            composites.append(f"{p} aggregates the T3 root triple "
                              f"(standard: fixed 0.4/0.3/0.3, t3v3-001; "
                              f"semantics-1: strength-weighted mean)")
        if V3_ROOTS <= locals_:
            composites.append(f"{p} aggregates the V3 root triple "
                              f"(standard: fixed 0.3/0.35/0.35, t3v3-002; "
                              f"semantics-1: strength-weighted mean)")
    check(name, "L4b", "no parent aggregates a T3/V3 root triple",
          not composites, "; ".join(composites))

    # ---- L4c: root claims are declared or society-local ---------------------
    root_claims = [p for p in sorted(parents) if p not in children]
    undeclared = [f"{p} is a root claim in the standard's namespace but is not "
                  f"one of the six standard roots"
                  for p in root_claims
                  if local_name(p) and local_name(p) not in (T3_ROOTS | V3_ROOTS)]
    check(name, "L4c", "root claims are standard roots or society-local",
          not undeclared, "; ".join(undeclared))

    # ---- L4d: no minting anywhere in spec or graph -------------------------
    used = spec_iris(spec, prefixes)
    graph = path.parent / "input.nq"
    graph_terms = set()
    if graph.exists():
        graph_terms = set(IRI_IN_NQ.findall(graph.read_text()))
        used |= graph_terms
    minted = sorted(local_name(i) for i in used
                    if local_name(i) and local_name(i) not in ONTOLOGY_TERMS)
    check(name, "L4d",
          "no term used in spec or graph is minted in the standard's namespace",
          not minted,
          f"{len(minted)} minted: {', '.join(minted)} — the ontology invites "
          f"extending the dimension tree, not the namespace")

    # ---- L4e: parameter diff (informational) --------------------------------
    params = set(spec.get("parameters", {}))
    overlap = params & STANDARD_PARAMETERS
    pending = params & set(PENDING_PARAMETER_OVERLAP)
    if overlap:
        check(name, "L4e", "no undeclared standard-parameter override",
              False, f"spec sets {sorted(overlap)} which §10.2/§10.3 govern")
    else:
        print(f"  [info] L4e parameter diff: {len(params)} spec parameters, "
              f"0 governed by §10.2/§10.3 — VACUOUS by construction, not by "
              f"conformance (disjoint surfaces)")
    for p in sorted(pending):
        print(f"  [info] L4e pending overlap: {p} — {PENDING_PARAMETER_OVERLAP[p]}")

    # ---- L4f: reused standard terms (informational) -------------------------
    reused = sorted(local_name(i) for i in used
                    if local_name(i) and local_name(i) in ONTOLOGY_TERMS)
    if reused:
        print(f"  [info] L4f standard terms reused: {', '.join(reused)} — "
              f"rdfs:domain/range compatibility is not decidable from the "
              f"spec; verify against t3v3-ontology.ttl manually")


def verify_pins(ttl_path):
    """Re-derive the pinned root sets from the ontology. Constants are code."""
    text = Path(ttl_path).read_text()
    declared = set(re.findall(r"^web4:(\w+)\s+a\s+web4:Dimension", text, re.M))
    ok = declared == (T3_ROOTS | V3_ROOTS)
    print(f"pins vs {ttl_path}")
    print(f"  ontology declares web4:Dimension instances: {sorted(declared)}")
    print(f"  pinned roots:                               "
          f"{sorted(T3_ROOTS | V3_ROOTS)}")
    print("  [ok  ] pins re-derive from source" if ok else
          f"  [FAIL] pins DIVERGED — missing {sorted((T3_ROOTS|V3_ROOTS)-declared)}, "
          f"extra {sorted(declared-(T3_ROOTS|V3_ROOTS))}")
    terms = set(re.findall(r"^web4:(\w+)\s+a\s+", text, re.M))
    unknown = terms - ONTOLOGY_TERMS
    missing = ONTOLOGY_TERMS - terms
    if unknown or missing:
        print(f"  [warn] ONTOLOGY_TERMS drift — in ttl not pinned: "
              f"{sorted(unknown)}; pinned not in ttl: {sorted(missing)}")
    return 0 if ok else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if args[0] == "--verify-pins":
        sys.exit(verify_pins(args[1]))

    print("L4 standard-profile audit — DerivationSpec vs web4-standard")
    for p in args:
        audit(p)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} BLOCKING: " + "; ".join(FAILURES))
    if WARNINGS:
        print(f"{len(WARNINGS)} warning: " + "; ".join(WARNINGS))
    if not FAILURES and not WARNINGS:
        print("all specs clear")
    sys.exit(1 if FAILURES else 0)
