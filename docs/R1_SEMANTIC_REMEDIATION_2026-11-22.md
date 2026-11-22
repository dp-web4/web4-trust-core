# R1 semantic-remapping execution record — 2026-11-22

**Status:** OPERATOR SEMANTIC RULING IS RECORDED; IMPLEMENTATION NOT YET ACCEPTED. **DO NOT MERGE / PUBLISH THIS HEAD.**

**Authority:** dp's 2026-11-06 decision, recorded in [PR #2 operator review](https://github.com/dp-web4/web4-trust-core/pull/2#pullrequestreview-5810099505), reaffirmed 2026-11-13. This is an implementation record, not a request to reopen the naming question.

## 1. Resolved conceptual decision

- V3 **Validity** concerns confirmed delivery/transfer of value, not boundary conduct.
- T3 **Temperament** concerns role-contextual consistency, judgment, restraint and ethics. Evidence of response to governance boundaries, correction acceptance and proportional escalation is a **candidate T3 Temperament extension**, not an implementation of V3 Validity.
- Use tensor-qualified **human labels** and extension identifiers: `V3_Validity`, `T3_Temperament`, and `<Tensor>_<CanonicalDimension>[_<SpecificSubdimension>]`.
- A local derivation must **not reuse canonical Web4 RDF IRIs**, assert `owl:sameAs`, or claim canonical parameter/score equivalence. Different semantic identities remain different even where their labels contain the same words.
- The current `w4td:BoundaryConformance` replacement is **rejected**; it repairs namespace ownership but renames the measured construct into a different one.

Canonical source checked: [Web4 T3/V3 tensor specification at the R1-pinned Web4 commit](https://github.com/dp-web4/web4/blob/950eb2514b647a06e0e71f3192cf09f8d8458d28/web4-standard/core-spec/t3-v3-tensors.md), §§2.1 and 2.4 (Temperament, contextual subdimensions), and V3 Validity. This suite's `SPEC.md` already warns that its Beta/posterior semantics and parameter choices are **not** automatically the standard's normative tensor arithmetic.

## 2. Proposed meaning-preserving migration map (requires independent exact-head semantic review)

The `w4td:` namespace is **society-local derivation** (`https://web4.io/trust-derivation#`), not `web4:` (`https://web4.io/ontology#`). The following are **candidate local IDs**, not declarations of a new standard ontology:

| Existing R1 local ID | Candidate R1 local ID | Meaning | Ontology status |
| --- | --- | --- | --- |
| `w4td:BoundaryConformance` | `w4td:T3_Temperament_ConductEvidence` | Derived aggregate of three behavioral observations | Local *projection*, not canonical `web4:Temperament`; no normative score equivalence |
| `w4td:BoundaryResponse` | `w4td:T3_Temperament_BoundaryResponse` | Witnessed response to scope/boundary rulings | Candidate local child under a role-scoped T3 Temperament extension |
| `w4td:CorrectionAcceptance` | `w4td:T3_Temperament_CorrectionAcceptance` | Response to a valid correction, not merely an apology | Candidate local child |
| `w4td:EscalationProportionality` | `w4td:T3_Temperament_EscalationProportionality` | Whether escalation is appropriate to role/context/stakes | Candidate local child |
| `w4td:Integrity` | `w4td:Evidence_Integrity` | Derived credibility of provenance/adjudication in this *experimental evaluator* | Local evidence-weight construct; do not silently place on T3/V3 root |
| `w4td:AdjudicationQuality` | `w4td:Evidence_AdjudicationQuality` | Input to derived evidence provenance weight | Local evidence-weight construct; separate from observed member temperament |

**Why the parent is not just `w4td:T3_Temperament`:** this evaluator derives a particular uncertainty/strength-bearing Beta aggregate. The standard's canonical Temperament has its own role-binding and parameter rules. `ConductEvidence` preserves the restricted meaning of the local research metric rather than impersonating the entire canonical dimension. The final identifier must pass NOT-SAME semantic review.

**No renaming of** `urn:web4:obs:`, `urn:web4:entity:`, `urn:web4:grain:`, or other non-ontology identifiers. No change to the original 29 draft1 vector paths/bytes. Avoid extending a mechanical string replacement to quoted history, old law hashes or canonical standard tokens.

## 3. Audited touchpoints

| Surface | Evidence on checked source | Required action |
| --- | --- | --- |
| `SPEC.md` §4 | Current R1 example declares `w4td:BoundaryConformance` parent of the three observed leaves and `w4td:Integrity` parent of adjudication quality | Replace example with reviewed local IDs, label experimental and role-contextual, explain no canonical RDF equivalence |
| `README.md` | R1 narrative currently calls the replacement `BoundaryConformance` | Update normative versus experimental description |
| `harness/evaluator.py` | R1 parent/score references in example and evaluation paths | Rename only after map accepted; ensure exactly same numerical algorithm unless a separate semantics-version change is approved |
| `harness/generate.py` | `base_spec`, graph quad and receipt generation name current R1 dimensions | Rewrite IDs, regenerate every R1 artifact; recompute JCS `law_hash`, canonical graph hash and receipt hash |
| `harness/test_legacy_vectors.py` | `migrate_json` and `matching_graph` encode `Validity -> BoundaryConformance` | Update to explicit, bijective mapping; add negative controls for extra semantic changes and no leaked old R1 identifiers |
| `vectors/r1/` | Four receipt vector sets and canonicalization artifacts pin now-rejected local names | Regenerate from pinned generator; compare transformed inputs/receipts and hash changes; frozen originals untouched |
| `rust/README.md` | Points port to `vectors/r1/receipts` rather than old draft1 | Keep the fence; adjust target hashes after accepted regeneration |
| `web4-standard` | T3 Temperament and V3 Validity are distinct roots with role context | Preserve unchanged; do not amend standard just to accommodate this experimental R1 |
| `web4` incumbent trust core | Public Rust `TrustDimension::Temperament` and `ValueDimension::Validity` are distinct | No unreviewed API migration; explicitly distinguish research-suite IDs |
| Hestia | `core/src/rdf.rs` maps canonical roots; `core/src/derivation.rs` exposes both derived temperament/validity; `docs/V3_EVIDENCE_EVENTS.md` cautions self-correction is not automatic Temperament | Audit any bridge and ensure R1 local metric does not overwrite these canonical fields |
| Hub/4-hub | Contains canonical tensor consumers and Hub role trust projections in the Web4 tree | Consumer/schema inventory before migration; no evidence yet of live dependency on R1 local IDs |
| SAGE | `sage/web4/sage_web4_lct_bridge.py` names canonical T3/V3; `sage/web4/act_chain_client.py` accepts both tensors | Preserve canonical fields; research R1 aliases cannot silently become them |
| Hardbound | `CANONICAL_AUDIT.md` distinguishes confirmed transfer and role reliability; `src/core/v3-validity-protocol.ts` has a separate V3 path | Inventory exported receipt fields; avoid implying R1 experimental conduct is V3 Validity |
| Shared schemas/other consumers | Not exhaustively inspected yet | Enumerate imports and RDF IRI references before claiming systemwide closure |

This is a **targeted source inventory**, not an exhaustive dependency sweep. Source locations above are audit starting points. The exact cross-repository search must record inspected commit SHAs and negative results (including alias/IRI spellings) before closing the operator's systemwide-audit requirement.

## 4. Exact implementation and acceptance gates

1. Make one explicit, version-controlled old→new map (ID, IRI, display label, semantic measurement, canonical relationship, and compatibility status). Include all terms used in specs, graphs, receipts and generator; do not use a broad `replace('Validity', ...)`.
2. Finish a **full-system grep/AST/RDF audit** with precise paths and commit pins. Classify root, subdimension, field alias, consumer, score formula, receipt hash and namespace collision, not only text occurrences.
3. Change executable evaluator/generator/test/spec/docs only to reflect the reviewed semantics. Regenerate all R1 pinned artifacts; produce before/after byte and hash manifests. Leave all 29 released draft1 vectors byte-identical and keep immutability CI enforced.
4. Add refusal tests: unexpected canonical namespace IRIs; rejected `BoundaryConformance` on new R1 artifacts; `web4:Validity` used for behavioral evidence; non-namespace mutation accidentally treated as mechanical rename; duplicate/missing mapping; wrong-parent edge; naive equality of research aggregate to canonical T3/V3 root.
5. Run conformance, legacy-vector tests, vector-immutability, regeneration determinism, and cross-implementation Rust target checks at the **new exact head**; include failure mode when old draft1 vectors pass but new R1 is not checked.
6. Obtain a **NOT-SAME semantic review** and a separate **NOT-SAME implementation/CI review**, explicitly recording evidence and scope.
7. Return the reviewed implementation to dp for final **adoption of revised R1 bytes**. The 2026-11-06 semantic ruling itself **does not need to be repeated**.

**Stop condition:** never merge a green but semantically rejected branch. Green CI on head `e18c4446` proves only the *old* rejected candidate is reproducible.

## 5. Current state

As of this record: concept decided; branch still contains `BoundaryConformance`; all accepted draft1 immutability and R1 separation machinery should be retained; revised IDs, regenerated R1, complete consumer audit and independent final reviews are outstanding. This document is a handoff/specification, **not evidence that those tasks were executed**.
