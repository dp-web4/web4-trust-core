//! N-Quads line parser for the skolemized-iri mode.
//!
//! Supported line forms (the only forms the skolemized vectors use):
//!   `<iri> <iri> <iri> .`
//!   `<iri> <iri> "literal"^^<datatype-iri> .`
//!
//! Canonicalization for skolemized mode degenerates to a code-point sort of
//! the raw lines (Rust's `str` ordering is byte order, which equals
//! code-point order for UTF-8) joined with "\n" plus a trailing "\n".
//! `graph_hash = sha256(canonical bytes)`.

#[derive(Clone, Debug, PartialEq)]
pub enum Object {
    Iri(String),
    /// (lexical form, datatype IRI)
    Literal(String, String),
}

#[derive(Clone, Debug, PartialEq)]
pub struct Quad {
    pub subject: String,
    pub predicate: String,
    pub object: Object,
}

/// Non-empty lines of the input, in file order.
pub fn lines(input: &str) -> Vec<&str> {
    input.split('\n').filter(|l| !l.is_empty()).collect()
}

/// Canonical N-Quads bytes for skolemized mode: code-point-sorted lines,
/// "\n"-joined, with a trailing "\n".
pub fn canonical_bytes(input: &str) -> Vec<u8> {
    let mut ls = lines(input);
    ls.sort();
    let mut out = ls.join("\n");
    out.push('\n');
    out.into_bytes()
}

pub fn parse(input: &str) -> Result<Vec<Quad>, String> {
    lines(input)
        .iter()
        .map(|l| parse_line(l))
        .collect()
}

fn parse_line(line: &str) -> Result<Quad, String> {
    let mut p = LineParser { b: line.as_bytes(), pos: 0 };
    let subject = p.iri()?;
    p.ws();
    let predicate = p.iri()?;
    p.ws();
    let object = if p.peek() == Some(b'"') {
        let lex = p.literal()?;
        p.expect2(b'^', b'^')?;
        let dt = p.iri()?;
        Object::Literal(lex, dt)
    } else {
        Object::Iri(p.iri()?)
    };
    p.ws();
    p.expect(b'.')?;
    p.ws();
    if p.pos != p.b.len() {
        return Err(format!("trailing content in N-Quads line: {}", line));
    }
    Ok(Quad { subject, predicate, object })
}

struct LineParser<'a> {
    b: &'a [u8],
    pos: usize,
}

impl<'a> LineParser<'a> {
    fn peek(&self) -> Option<u8> {
        self.b.get(self.pos).copied()
    }

    fn ws(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t')) {
            self.pos += 1;
        }
    }

    fn expect(&mut self, c: u8) -> Result<(), String> {
        if self.peek() == Some(c) {
            self.pos += 1;
            Ok(())
        } else {
            Err(format!("expected '{}' at byte {}", c as char, self.pos))
        }
    }

    fn expect2(&mut self, a: u8, b: u8) -> Result<(), String> {
        self.expect(a)?;
        self.expect(b)
    }

    fn iri(&mut self) -> Result<String, String> {
        self.expect(b'<')?;
        let start = self.pos;
        while let Some(c) = self.peek() {
            if c == b'>' {
                let s = std::str::from_utf8(&self.b[start..self.pos])
                    .map_err(|_| "invalid UTF-8 in IRI".to_string())?
                    .to_string();
                self.pos += 1;
                return Ok(s);
            }
            self.pos += 1;
        }
        Err("unterminated IRI".into())
    }

    fn literal(&mut self) -> Result<String, String> {
        self.expect(b'"')?;
        let mut out = String::new();
        loop {
            match self.peek() {
                None => return Err("unterminated literal".into()),
                Some(b'"') => {
                    self.pos += 1;
                    return Ok(out);
                }
                Some(b'\\') => {
                    self.pos += 1;
                    match self.peek() {
                        Some(b'"') => out.push('"'),
                        Some(b'\\') => out.push('\\'),
                        Some(b'n') => out.push('\n'),
                        Some(b'r') => out.push('\r'),
                        Some(b't') => out.push('\t'),
                        Some(other) => return Err(format!("unsupported escape '\\{}'", other as char)),
                        None => return Err("unterminated literal".into()),
                    }
                    self.pos += 1;
                }
                Some(_) => {
                    let start = self.pos;
                    while !matches!(self.peek(), None | Some(b'"') | Some(b'\\')) {
                        self.pos += 1;
                    }
                    out.push_str(
                        std::str::from_utf8(&self.b[start..self.pos])
                            .map_err(|_| "invalid UTF-8 in literal".to_string())?,
                    );
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_iri_and_literal_objects() {
        let q = parse("<urn:a> <urn:b> <urn:c> .").unwrap();
        assert_eq!(
            q,
            vec![Quad {
                subject: "urn:a".into(),
                predicate: "urn:b".into(),
                object: Object::Iri("urn:c".into()),
            }]
        );
        let q = parse(
            "<urn:a> <urn:b> \"0.92\"^^<http://www.w3.org/2001/XMLSchema#decimal> .",
        )
        .unwrap();
        assert_eq!(
            q,
            vec![Quad {
                subject: "urn:a".into(),
                predicate: "urn:b".into(),
                object: Object::Literal(
                    "0.92".into(),
                    "http://www.w3.org/2001/XMLSchema#decimal".into()
                ),
            }]
        );
    }

    #[test]
    fn canonical_sorts_and_terminates() {
        let input = "<b> <p> <o> .\n<a> <p> <o> .\n";
        assert_eq!(canonical_bytes(input), b"<a> <p> <o> .\n<b> <p> <o> .\n".to_vec());
    }
}
