# Rust reference port (in progress)

Target: `evaluate(spec, graph, mrh, chain_range) -> (scores, receipt)` such
that `harness/check.py` passes with this implementation swapped into L1/L3 —
receipt bytes identical to the Python reference.

Owner: kimi-code (volunteered 2026-07-24). The fold-order vector (V7) and
JCS float rules are the expected pain points; they have pinned bytes for
exactly that reason.

**Package name constraint:** do NOT name the Cargo package
`web4-trust-core` — that name is taken by a live AGPL crate at
`dp-web4/web4/web4-trust-core` (0.2.0, crates.io publish track) that
hardbound links. The port does not block on dp's rename decision: use
`web4-trust-derivation` as a **provisional** package name (comment it as
provisional in `Cargo.toml`), and match whatever name dp settles on before
any crates.io publish — a pre-publish rename is a one-line edit. No publish
until the repo rename lands. See "Relationship to the existing
`web4-trust-core` crate" in the top-level README, and
`response-claude-code-2026-07-24-rust-port-green-light.md` in the origin
thread for the green-light terms.

**Naming constraint (dp ruling 2026-07-24):** `[package] name` must be
`web4-trust-derivation-ref` — NOT `web4-trust-core`, which stays reserved for the
incumbent crate in `dp-web4/web4` until the merge gate passes (see root README,
"Relationship" section). Nothing here publishes to crates.io.

**Byte-target fence (2026-07-24, thread trust-derivation-rdf):** do NOT pin
milestone-4 expected hashes against the draft1 vectors. The R1 namespace
remediation (legion's reconciliation finding; PR #2) re-pins every
`law_hash`/`graph_hash`/`receipt_hash` in the suite — the byte targets are
the draft2 vectors on the PR #2 branch, final once dp merges. Milestones 1–3
(spec ingestion, graph loading, evaluator semantics) are unaffected; only
hash pinning and the CI hook (milestones 4–5) wait.
