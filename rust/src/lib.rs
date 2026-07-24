//! Rust reference port of the web4 trust-derivation conformance evaluator
//! (semantics 1). Zero external dependencies: JSON, JCS (RFC 8785), SHA-256
//! and N-Quads are implemented in-crate.
//!
//! The byte contract is pinned by `../vectors/receipts/{v3,v4b,v7-fold-order}`:
//! `receipt.jcs` bytes, `law_hash = sha256(JCS(spec))`, and
//! `graph_hash = sha256(canonical N-Quads)` must match exactly.

pub mod eval;
pub mod jcs;
pub mod json;
pub mod nquads;
pub mod sha256;
