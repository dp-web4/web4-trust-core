#!/usr/bin/env python3
"""Independent verifier for the RDFC-1.0 canonicalization vector.

Implements the Hash-First-Degree-Quads path of RDFC-1.0 (W3C REC, the
standardized URDNA2015) from the spec text, with no RDF library. It only
handles graphs where every blank node gets a UNIQUE first-degree hash --
the N-degree/gossip path is deliberately not implemented, and the script
refuses (exit 2) if it would be needed. The vector graph is chosen to
stay inside this fragment so any member can re-derive it by hand.

Usage: python3 verify.py input.nq expected-canonical.nq
Exit 0 = canonical bytes + sha256 reproduce; 1 = mismatch; 2 = out of fragment.
"""
import hashlib
import re
import sys

TERM = re.compile(
    r'(<[^>]*>'                       # IRI
    r'|_:[A-Za-z0-9]+'                # blank node label
    r'|"(?:[^"\\]|\\.)*"'             # literal (escapes allowed)
    r'(?:\^\^<[^>]*>|@[A-Za-z0-9-]+)?'  # optional datatype / langtag
    r')')


def parse(line):
    terms = TERM.findall(line)
    if len(terms) not in (3, 4):
        raise ValueError(f"unparseable N-Quads line: {line!r}")
    return tuple(terms) + (None,) * (4 - len(terms))


def serialize(quad, bnode_map):
    parts = []
    for t in quad:
        if t is None:
            continue
        parts.append(bnode_map.get(t, t) if t.startswith('_:') else t)
    return ' '.join(parts) + ' .'


def hash_first_degree(node, quads):
    nquads = []
    for q in quads:
        if node not in q:
            continue
        m = {b: ('_:a' if b == node else '_:z')
             for b in q if b and b.startswith('_:')}
        nquads.append(serialize(q, m) + '\n')
    return hashlib.sha256(''.join(sorted(nquads)).encode()).hexdigest()


def main(input_path, expected_path):
    quads = [parse(l) for l in open(input_path) if l.strip()]
    bnodes = sorted({t for q in quads for t in q if t and t.startswith('_:')})

    hashes = {b: hash_first_degree(b, quads) for b in bnodes}
    if len(set(hashes.values())) != len(hashes):
        print("shared first-degree hashes: N-degree path required, "
              "out of this verifier's fragment", file=sys.stderr)
        return 2

    issued = {b: f'_:c14n{i}'
              for i, (b, _) in enumerate(sorted(hashes.items(), key=lambda kv: kv[1]))}
    for b in bnodes:
        print(f"{b}  H1d={hashes[b]}  ->  {issued[b]}")

    canonical = ''.join(sorted(serialize(q, issued) + '\n' for q in quads))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    print(f"sha256: {digest}")

    expected = open(expected_path).read()
    if canonical != expected:
        print("MISMATCH against expected-canonical.nq", file=sys.stderr)
        return 1
    print("OK: canonical bytes reproduce")
    return 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
