# Rust reference port (in progress)

Target: `evaluate(spec, graph, mrh, chain_range) -> (scores, receipt)` such
that `harness/check.py` passes with this implementation swapped into L1/L3 —
receipt bytes identical to the Python reference.

Owner: kimi-code (volunteered 2026-07-24). The fold-order vector (V7) and
JCS float rules are the expected pain points; they have pinned bytes for
exactly that reason.
