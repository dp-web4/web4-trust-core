# Rust reference port

Status (2026-07-24): milestones 1–4 implemented — spec ingestion, N-Quads
graph loading, full semantics-1 evaluator (Beta fold, stratified strictly-
below recursion, anchored/measured/unmeasured provenance, product dependency
discount, strength-weighted parent aggregation), JCS receipt emission, CLI
(`web4-trust-derive <vector-dir>`). Zero external dependencies: JSON, JCS
(RFC 8785), SHA-256 and N-Quads are implemented in-crate.

Byte status against the draft2 vectors (PR #2 branch): **v3 and
v7-fold-order byte-exact**; canonicalization vector exact; spec JCS
round-trips exact. **v4b and the v6b member-M result triple do not
reproduce** — not a port defect: the pinned receipts carry hand-authored
arithmetic errata, and three implementations (exploration
`evaluator-kimi-code.py`, `harness/evaluator.py`, this crate) agree with
this port's values. Reported to the steward 2026-07-24 (thread
trust-derivation-rdf); ruling on corrected vectors pending. See
`tests/vectors.rs` header for the exact digits, and `./check-vectors.sh`
for the live status. Milestone 5 (CI hook) waits on dp's PR merges.

Target: `evaluate(spec, graph, mrh, chain_range) -> (scores, receipt)` such
that `harness/check.py` passes with this implementation swapped into L1/L3 —
receipt bytes identical to the Python reference.

Owner: kimi-code (volunteered 2026-07-24). The fold-order vector (V7) and
JCS float rules are the expected pain points; they have pinned bytes for
exactly that reason.

**Package name constraint (dp ruling 2026-07-24):** `[package] name` must be
`web4-trust-derivation-ref` — NOT `web4-trust-core`, which is a live AGPL
crate at `dp-web4/web4/web4-trust-core` (0.2.0) that hardbound links; that
name stays reserved for the incumbent. The repo rename proposed in legion's
review was **declined** — the repo name stays, nothing is pending on it.
**No crates.io publish, ever, from this repo** — the reference evaluator is
a conformance artifact, not a distributable library. See the "Relationship"
sections in the top-level README, and
`response-claude-code-2026-07-24-rust-port-green-light.md` in the origin
thread for the green-light terms.

**Byte-target fence (2026-07-24, thread trust-derivation-rdf):** do NOT pin
milestone-4 expected hashes against the draft1 vectors. The R1 namespace
remediation (legion's reconciliation finding; PR #2) re-pins every
`law_hash`/`graph_hash`/`receipt_hash` in the suite — the byte targets are
the draft2 vectors on the PR #2 branch, final once dp merges. Milestones 1–3
(spec ingestion, graph loading, evaluator semantics) are unaffected; only
hash pinning and the CI hook (milestones 4–5) wait.
