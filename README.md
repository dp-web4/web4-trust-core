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
   existing file under `vectors/`.
2. **Bytes, not checkouts.** Every JSON hash is JCS (RFC 8785); spec
   instances are stored in canonical bytes so `sha256(file) == law_hash`.
3. **Nothing unexercised is law.** A semantics claim without a vector is
   *reserved*. Current reserved ledger: V4a (measured basis), V8
   (evidence-rules fork), V9 (multi-child aggregation), decay parameters.
4. **`core.semantics` discipline.** Any change to receipt bytes for the same
   (spec, graph) bumps the semantics version; old-version vectors stay — a
   receipt in the wild cites the semantics it was computed under.

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

## Provenance

Produced 2026-07-24 by a multi-agent refute-or-accept exploration
(claude-code steward, kimi-code co-implementer; two independent evaluator
implementations reproduced all receipt vectors byte-for-byte before
anything here was called law). The full finding trail, including the
mistakes, remains in the origin exploration thread.

License: AGPL-3.0-or-later (matches hestia and web4).
