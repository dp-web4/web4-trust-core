# web4-trust-core

Portable trust derivation for Web4 societies: a **DerivationSpec** (trust
computation as inspectable law), a pure reference **evaluator**, and a
**conformance suite** whose vectors pin the failure modes, not just the happy
path.

```
evaluate(spec, graph, mrh, chain_range) -> (scores, receipt)
```

Pure function, no I/O. Consumers (hub, hestia, hardbound) share this core;
each society defines its *own* DerivationSpec instance — how trust is computed
is sovereign, but always transparent, hash-pinned, and receipt-auditable.

## Layout

| Path | What |
|---|---|
| `SPEC.md` | DerivationSpec draft 2 — semantics 1, normative |
| `vectors/` | Conformance vectors (canonicalization, receipts, scores) |
| `harness/check.py` | Conformance runner — exit 0 = conforming |
| `harness/generate.py` | Vector authority — the only writer of `vectors/` |
| `harness/evaluator.py` | Python reference evaluator (stdlib-only) |
| `harness/rdfc10_verify.py` | RDFC-1.0 recomputation check |
| `rust/` | Rust reference port (in progress) |

## Run the suite

```bash
pip install -r requirements.txt   # jcs (RFC 8785)
cd harness && python3 check.py    # CONFORMANCE: PASS, exit 0
```

## Repo law (not folklore)

1. **Vector authority.** A released vector never changes; corrections add a
   new vector (the v6→v6b precedent). CI fails any PR that modifies an
   existing file under `vectors/`. *(One sanctioned exception on record: the
   2026-07-24 R1 namespace remediation re-pinned every vector in place —
   executed while consumers = 0 and the Rust port pre-milestone-4, with
   spec_ids bumped draft1→draft2 so the superseded laws stay citable from git
   history. Witnessed on thread trust-derivation-rdf.)*
2. **Bytes, not checkouts.** Every JSON hash is JCS (RFC 8785); spec
   instances are stored in canonical bytes so `sha256(file) == law_hash`.
3. **Nothing unexercised is law.** A semantics claim without a vector is
   *reserved*. Current reserved ledger: V4a (measured basis), V8
   (evidence-rules fork), V9 (multi-child aggregation), decay parameters
   (reserved **and pre-constrained** by `web4-standard` t3v3-012: Talent MUST
   NOT decay — see SPEC.md §5).
4. **`core.semantics` discipline.** Any change to receipt bytes for the same
   (spec, graph) bumps the semantics version; old-version vectors stay — a
   receipt in the wild cites the semantics it was computed under.
5. **The harness stays library-free apart from `jcs`.** A portability claim
   whose conformance suite needs no RDF stack is the artifact; verified on a
   second machine (legion, 2026-07-24) with `pyld` absent and all 29 checks
   green. New harness dependencies are a review flag.
6. **Standard-profile rules R1–R3** (SPEC.md §11): no minting or redefining
   in the standard's namespace, no aggregating the T3/V3 root triples, every
   root claim declared standard or society-local. Enforced by
   `harness/l4_standard_profile.py` (L4, part of `check.py`), whose pinned
   ontology constants re-derive from a web4 checkout via `--verify-pins`.
7. **Dependency fence** (legion, 2026-07-24). Any name-bearing artifact —
   package name, repo name, IRI namespace, published constant — carries an
   explicit "not load-bearing until X" fence at creation; an identifier
   becomes irreversible exactly when something starts depending on it. The
   fence, not a wait state, preserves the option. (Current fences:
   `rust/README.md` Cargo name; publish gated on dp's rename decision.)

## Key vectors

- **V3** — adjudicator capture: unmeasured adjudicator → `null` score +
  `unmeasured_upstream` receipt entry, never a fabricated number.
- **V4b** — anchor drift: an anchor whose own derived integrity has decayed
  shows both scores side by side in one receipt.
- **V6b** — dependency discount (capture resistance via `dependsOn`).
- **V7** — float determinism / canonical fold order.

## The seam

- **trust-core owns:** beta update, aggregation, stratification,
  provenance/dependency weights, fold order, float rules, all hash definitions.
- **hub-local:** chain→evidence-graph projection; role occupant enumeration;
  receipt cache keyed by `(subject, role, law_hash, chain_head)`.
- **hestia-local:** display + the `GET /api/trust/derivation` receipt surface.
- **society-local:** the DerivationSpec instance itself.
- **hardbound-local:** relying party, not folder — hardbound consumes receipts
  as enforcement input, so it needs the receipt-verification half of the API
  (recompute hashes, check `unmeasured_upstream`, validate against a pinned
  `law_hash`) and none of the evaluation half. A verifier seam is a genuinely
  different surface from hub's (legion review, 2026-07-24).

## Relationship to the existing `web4-trust-core` crate (name collision)

**Resolved (dp ruling 2026-07-24): the repo name stays; the crate name is
reserved for the incumbent.** The rename legion's review proposed
(`web4-trust-derivation`, thread `trust-derivation-rdf`, 2026-07-24) was
declined — nothing is pending on it. There is a live crate named
`web4-trust-core` at `dp-web4/web4/web4-trust-core` (0.2.0,
AGPL-3.0-or-later, on the crates.io publish track) whose public surface is
*stateful and mutable* (`t3_update_from_outcome(&mut T3, …)`,
`t3_apply_decay(&mut T3, …)`, storage/witnessing traits) — the opposite shape
from this repo's pure `evaluate(...)`. No Cargo
package in `rust/` may ever take the name `web4-trust-core` — the Rust port must
not create a second, semantically incompatible package under a name that
already resolves ("name that resolves, meaning undefined" — the finding-8/9
lesson at package granularity).

**Succession statement.** The existing crate's `t3_update_from_outcome` /
`t3_apply_decay` are derivation logic shipped as constants-in-code — research
target #1 of the origin exploration. Status today: **coexist**. hardbound
currently enforces via that constants-in-code path (through a vendored copy),
and this evaluator does not supersede it. Supersession is *gated* on the
`web4-standard` reconciliation round (which authority wins where the
standard's normative table and a DerivationSpec disagree) plus a migration
plan for the live consumers; until that round closes, "one semantics for
three products" is an aspiration this repo works toward, not a claim it makes.

## Relationship to the `web4-trust-core` crate (dp ruling, 2026-07-24)

The Rust crate `web4-trust-core` (in `dp-web4/web4`, linked by hardbound, constants
normatively pinned by web4-standard's t3v3 vectors) is the **incumbent** trust
arithmetic. This repo is the **successor research track** for its derivation half:
constants-in-code become signed law; mutate-in-place scores become read-time
derivations with receipts. Succession is earned, not claimed:

- **Merge gate:** a DerivationSpec instance reproduces the incumbent's normative
  vectors (t3v3-001..012) byte-for-byte as one society's law. When that passes, this
  work ships as a **new release of the existing crate, under the existing name**.
  *Status: contested, replacement pending dp.* Legion's L5 audit
  (`l5-merge-gate-expressibility.py`, exploration thread, 2026-07-24 — reproduced by
  claude-code on a second machine) finds no gate vector expressible as
  DerivationSpec law: the update/decay vectors mutate a prior score that
  `evaluate()` never receives, and after the R1 namespace separation (PR #2) the
  spec and the standard share no identifiers at all. See
  `response-legion-2026-07-24-to-dp-ruling-merge-gate-refuted.md` §2.3 and §5 for
  the two proposed replacements (additive dimension family vs. profile-mapping
  document).
- **Nothing in this repo is published to crates.io.** The reference evaluator is a
  conformance artifact, not a distributable library.
- **The Rust reference port's Cargo package name MUST NOT be `web4-trust-core`**
  (use `web4-trust-derivation-ref`). The crate name stays with the incumbent until
  the merge gate passes — so incumbent + evaluator can coexist in one dependency
  graph during migration with no collision.

## Provenance

Produced 2026-07-24 by a multi-agent refute-or-accept exploration
(claude-code steward, kimi-code co-implementer; two independent evaluator
implementations reproduced all receipt vectors byte-for-byte before
anything here was called law). The full finding trail, including the
mistakes, remains in the origin exploration thread.

License: AGPL-3.0-or-later (matches hestia and web4).
