//! Integration tests against the pinned conformance vectors in `../vectors`.
//!
//! - JCS(parse(spec.json)) must reproduce the spec file bytes exactly
//!   (the pinned specs are stored in canonical bytes), per vector.
//! - The emitted receipt bytes must equal the pinned `receipt.jcs` bytes for
//!   v3 and v7-fold-order, and the recomputed law_hash / graph_hash must
//!   match `expected-hashes.json`.
//! - Canonicalization vector: sorted-lines bytes and hash.
//!
//! KNOWN VECTOR ERRATA (2026-07-24, thread trust-derivation-rdf — reported to
//! the steward, ruling pending): the hand-authored `result` objects in the
//! v4b and v6b pinned receipts do NOT reproduce from spec+graph under
//! semantics 1. Three implementations (exploration `evaluator-kimi-code.py`,
//! `harness/evaluator.py`, this crate) agree with this crate's values:
//!   - v4b member-M BoundaryResponse sigma: pin 0.1632993161855452,
//!     reproduced 0.16329931618554522 (1 ulp; a=4, b=1 exact fold).
//!   - v6b member-M result triple: pin {mu 0.5689655172413793,
//!     sigma 0.27178483084735455, strength 0.31999999999999984} — internally
//!     inconsistent with the receipt's own w_d = 0.32; reproduced
//!     {mu 0.5689655172413792, sigma 0.2717877878714068,
//!     strength 0.3200000000000003}.
//! The byte comparisons for those two vectors are `#[ignore]`d until the
//! steward lands corrected vectors (v4c/v6c or a sanctioned pre-merge
//! re-pin); the reproduced semantics are locked in by
//! `reproduced_semantics_pending_vector_errata` below.

use std::path::PathBuf;

use web4_trust_derivation_ref::json::{self, Value};
use web4_trust_derivation_ref::{eval, jcs, nquads, sha256};

fn vectors() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../vectors")
}

fn read(p: PathBuf) -> String {
    std::fs::read_to_string(&p).unwrap_or_else(|e| panic!("reading {:?}: {}", p, e))
}

const SKOLEMIZED_VECTORS: [&str; 2] = ["v3", "v7-fold-order"];

#[test]
fn spec_round_trips_to_canonical_bytes() {
    for v in SKOLEMIZED_VECTORS {
        let text = read(vectors().join(format!("receipts/{}/spec.json", v)));
        let parsed = json::parse(&text).expect("spec parses");
        let canonical = jcs::canonicalize(&parsed);
        assert_eq!(
            canonical,
            text.as_bytes(),
            "JCS(parse(spec.json)) must equal spec.json bytes for {}",
            v
        );
    }
}

#[test]
fn spec_validation_rejects_unknown_fields() {
    let text = read(vectors().join("receipts/v3/spec.json"));
    let mut v = json::parse(&text).unwrap();
    if let Value::Obj(ref mut pairs) = v {
        pairs.push(("bogus".into(), Value::Num(1.0)));
    }
    assert!(eval::Spec::parse(&jcs::canonicalize_string(&v)).is_err());
}

#[test]
fn receipt_bytes_match_pinned_vectors() {
    for v in SKOLEMIZED_VECTORS {
        let dir = vectors().join(format!("receipts/{}", v));
        let spec_text = read(dir.join("spec.json"));
        let nq_text = read(dir.join("input.nq"));
        let expected = std::fs::read(dir.join("receipt.jcs")).unwrap();

        let spec = eval::Spec::parse(&spec_text).expect("spec ingests");
        let quads = nquads::parse(&nq_text).expect("graph parses");
        let mrh = eval::detect_mrh(&spec, &quads).expect("single mrh in graph");
        let receipt = eval::evaluate(&spec, &nq_text, &mrh).expect("evaluation succeeds");
        let bytes = jcs::canonicalize(&receipt);

        assert_eq!(
            bytes,
            expected,
            "receipt bytes differ for {}\n ours: {}\n pin:  {}",
            v,
            String::from_utf8_lossy(&bytes),
            String::from_utf8_lossy(&expected),
        );

        // Recomputed hashes match expected-hashes.json.
        let hashes_text = read(dir.join("expected-hashes.json"));
        let hashes = json::parse(&hashes_text).unwrap();
        let get = |k: &str| hashes.get(k).and_then(Value::as_str).unwrap().to_string();
        assert_eq!(spec.law_hash, get("law_hash"), "law_hash for {}", v);
        let graph_hash = sha256::sha256_hex(&nquads::canonical_bytes(&nq_text));
        assert_eq!(graph_hash, get("graph_hash"), "graph_hash for {}", v);
        // receipt_hash pins sha256 of exactly these bytes too.
        assert_eq!(
            sha256::sha256_hex(&bytes),
            get("receipt_hash"),
            "receipt_hash for {}",
            v
        );
    }
}

#[test]
fn canonicalization_vector() {
    let dir = vectors().join("canonicalization/skolemized-sorted-nquads");
    let input = read(dir.join("input.nq"));
    let canonical = nquads::canonical_bytes(&input);
    let expected = std::fs::read(dir.join("expected-canonical.nq")).unwrap();
    assert_eq!(canonical, expected);
    let expected_hash = read(dir.join("expected-hash.txt"));
    assert_eq!(sha256::sha256_hex(&canonical), expected_hash.trim());
}

#[test]
fn v6b_semantic_cross_check() {
    // Not byte-level: the v6b receipt was produced from the blank-node graph.
    // We evaluate the skolemized V6b graph under the v6b law and confirm the
    // structure that IS correctly pinned: subject-S's score, and the
    // dependency path (w_d = 0.64 * 0.5 = 0.32 over the blk10 dependency).
    // member-M's result triple is the known pin erratum (see header).
    let spec_text = read(vectors().join("receipts/v6b/spec.json"));
    let nq_text = read(vectors().join("canonicalization/skolemized-sorted-nquads/input.nq"));
    let spec = eval::Spec::parse(&spec_text).expect("v6b spec ingests");
    let quads = nquads::parse(&nq_text).unwrap();
    let mrh = eval::detect_mrh(&spec, &quads).unwrap();
    let receipt = eval::evaluate(&spec, &nq_text, &mrh).unwrap();

    let scores = receipt.get("scores").and_then(Value::as_arr).unwrap();
    assert_eq!(scores.len(), 2, "subject-S then member-M");

    let mu_of = |entry: &Value| entry.get("result").and_then(|r| r.get("mu")).and_then(Value::as_num);
    assert_eq!(
        scores[0].get("subject").and_then(Value::as_str),
        Some("urn:web4:grain:subject-S")
    );
    assert_eq!(mu_of(&scores[0]), Some(0.64));
    assert_eq!(
        scores[1].get("subject").and_then(Value::as_str),
        Some("urn:web4:grain:member-M")
    );

    // The dependency path: w_d = 0.64 * 0.5 = 0.32 over the blk10 dependency.
    let evidence = scores[1].get("evidence").and_then(Value::as_arr).unwrap();
    let wd = evidence[0].get("w_d").unwrap();
    assert_eq!(wd.get("value").and_then(Value::as_num), Some(0.32));
    let deps = wd.get("deps").and_then(Value::as_arr).unwrap();
    assert_eq!(deps.len(), 1);
    assert_eq!(
        deps[0].get("obs").and_then(Value::as_str),
        Some("urn:web4:obs:blk10:0")
    );
    assert_eq!(deps[0].get("score_used").and_then(Value::as_num), Some(0.64));
    assert_eq!(deps[0].get("discount").and_then(Value::as_num), Some(0.5));
}

/// Byte comparison for the two vectors with known pin errata (see header).
/// Ignored until the steward lands corrected vectors; run explicitly with
/// `cargo test -- --ignored` to re-check after a re-pin.
#[test]
#[ignore = "v4b/v6b pinned receipts carry hand-authored result errata; awaiting steward ruling"]
fn receipt_bytes_errata_vectors_pending_repin() {
    for v in ["v4b"] {
        let dir = vectors().join(format!("receipts/{}", v));
        let spec_text = read(dir.join("spec.json"));
        let nq_text = read(dir.join("input.nq"));
        let expected = std::fs::read(dir.join("receipt.jcs")).unwrap();
        let spec = eval::Spec::parse(&spec_text).expect("spec ingests");
        let quads = nquads::parse(&nq_text).expect("graph parses");
        let mrh = eval::detect_mrh(&spec, &quads).expect("single mrh in graph");
        let receipt = eval::evaluate(&spec, &nq_text, &mrh).expect("evaluation succeeds");
        assert_eq!(jcs::canonicalize(&receipt), expected, "receipt bytes for {}", v);
    }
}

/// Locks in the semantics-1 values reproduced by three implementations
/// (exploration evaluator, harness evaluator, this crate) for the two
/// errata entries, so the port's behaviour is regression-pinned on SPEC
/// semantics — not on the erroneous hand-authored digits — while the
/// steward's correction is pending. When corrected vectors land, update
/// these to the new pins and un-ignore the byte test above.
#[test]
fn reproduced_semantics_pending_vector_errata() {
    // v4b: a=4, b=1 exact fold (three observations, c=1, w=1; priors 1/1).
    let dir = vectors().join("receipts/v4b");
    let spec = eval::Spec::parse(&read(dir.join("spec.json"))).unwrap();
    let nq_text = read(dir.join("input.nq"));
    let quads = nquads::parse(&nq_text).unwrap();
    let mrh = eval::detect_mrh(&spec, &quads).unwrap();
    let receipt = eval::evaluate(&spec, &nq_text, &mrh).unwrap();
    let scores = receipt.get("scores").and_then(Value::as_arr).unwrap();
    let result = scores[0].get("result").unwrap();
    assert_eq!(result.get("mu").and_then(Value::as_num), Some(0.8));
    assert_eq!(
        result.get("sigma").and_then(Value::as_num),
        Some(0.16329931618554522)
    );
    assert_eq!(result.get("strength").and_then(Value::as_num), Some(3.0));

    // v6b member-M: w_d = 0.32 (the double nearest 0.32) over a single c=1
    // observation. The pin's triple is unreachable from its own evidence.
    let spec = eval::Spec::parse(&read(vectors().join("receipts/v6b/spec.json"))).unwrap();
    let nq_text = read(vectors().join("canonicalization/skolemized-sorted-nquads/input.nq"));
    let quads = nquads::parse(&nq_text).unwrap();
    let mrh = eval::detect_mrh(&spec, &quads).unwrap();
    let receipt = eval::evaluate(&spec, &nq_text, &mrh).unwrap();
    let scores = receipt.get("scores").and_then(Value::as_arr).unwrap();
    let result = scores[1].get("result").unwrap();
    assert_eq!(
        result.get("mu").and_then(Value::as_num),
        Some(0.5689655172413792)
    );
    assert_eq!(
        result.get("sigma").and_then(Value::as_num),
        Some(0.2717877878714068)
    );
    assert_eq!(
        result.get("strength").and_then(Value::as_num),
        Some(0.3200000000000003)
    );
}
