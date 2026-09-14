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
