# Rust reference port (in progress)

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

**Byte-target fence (2026-07-24, thread trust-derivation-rdf; updated for
versioned vectors):** do NOT use the frozen draft1 files under
`vectors/receipts/` as the milestone-4 byte targets. The proposed R1/draft2
targets are `vectors/r1/receipts/{v3,v4b,v7-fold-order}` on PR #2; their
status remains subject to dp's R1 decision. Both sets coexist, so a port
still pinned only to `vectors/receipts/` can pass while testing historical
draft1 rather than the proposed R1 law. Explicitly run the R1 vectors when
validating the port; checking both versions is useful, but passing draft1
alone is not R1 conformance. Milestones 1–3 (spec ingestion, graph loading,
evaluator semantics) are unaffected by the vector-path fence.
