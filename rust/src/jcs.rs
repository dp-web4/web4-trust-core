//! RFC 8785 (JCS) canonical JSON serializer.
//!
//! - Object keys sorted by UTF-16 code unit order (byte order is equivalent
//!   for pure-ASCII keys; we implement the real UTF-16 comparison anyway).
//! - Minimal string escaping: only `\" \\ \b \f \n \r \t`, plus `\u00XX`
//!   for other control characters; non-ASCII is emitted as raw UTF-8.
//! - Numbers follow ECMAScript `Number::toString`: shortest round-trip
//!   decimal (Rust's `{}` Display for f64 produces exactly the shortest
//!   round-trip digits), integral values print without `.0`, `-0.0` prints
//!   as `0`, and values with `abs >= 1e21` or `0 < abs < 1e-6` use JS-style
//!   exponential notation (`1e+21`, `1e-7` — note the `+`, which Rust's
//!   `{:e}` omits). NaN/Infinity never occur in this suite.

use crate::json::Value;

pub fn canonicalize(v: &Value) -> Vec<u8> {
    let mut out = Vec::new();
    write_value(v, &mut out);
    out
}

pub fn canonicalize_string(v: &Value) -> String {
    String::from_utf8(canonicalize(v)).expect("JCS output is valid UTF-8")
}

fn write_value(v: &Value, out: &mut Vec<u8>) {
    match v {
        Value::Null => out.extend_from_slice(b"null"),
        Value::Bool(true) => out.extend_from_slice(b"true"),
        Value::Bool(false) => out.extend_from_slice(b"false"),
        Value::Num(n) => out.extend_from_slice(format_number(*n).as_bytes()),
        Value::Str(s) => write_string(s, out),
        Value::Arr(items) => {
            out.push(b'[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(b',');
                }
                write_value(item, out);
            }
            out.push(b']');
        }
        Value::Obj(pairs) => {
            let mut sorted: Vec<&(String, Value)> = pairs.iter().collect();
            sorted.sort_by(|a, b| utf16_key(&a.0).cmp(&utf16_key(&b.0)));
            out.push(b'{');
            for (i, (k, val)) in sorted.iter().enumerate() {
                if i > 0 {
                    out.push(b',');
                }
                write_string(k, out);
                out.push(b':');
                write_value(val, out);
            }
            out.push(b'}');
        }
    }
}

/// Sort key: the key's UTF-16 code units, per RFC 8785.
fn utf16_key(s: &str) -> Vec<u16> {
    s.encode_utf16().collect()
}

fn write_string(s: &str, out: &mut Vec<u8>) {
    out.push(b'"');
    for c in s.chars() {
        match c {
            '"' => out.extend_from_slice(b"\\\""),
            '\\' => out.extend_from_slice(b"\\\\"),
            '\u{0008}' => out.extend_from_slice(b"\\b"),
            '\u{000C}' => out.extend_from_slice(b"\\f"),
            '\n' => out.extend_from_slice(b"\\n"),
            '\r' => out.extend_from_slice(b"\\r"),
            '\t' => out.extend_from_slice(b"\\t"),
            c if (c as u32) < 0x20 => {
                out.extend_from_slice(format!("\\u{:04x}", c as u32).as_bytes());
            }
            c => {
                let mut buf = [0u8; 4];
                out.extend_from_slice(c.encode_utf8(&mut buf).as_bytes());
            }
        }
    }
    out.push(b'"');
}

/// ECMAScript `Number::toString` for finite f64.
pub fn format_number(n: f64) -> String {
    assert!(n.is_finite(), "JCS cannot serialize NaN/Infinity");
    if n == 0.0 {
        return "0".to_string(); // covers -0.0
    }
    let a = n.abs();
    if a >= 1e21 || a < 1e-6 {
        // Rust's {:e} also yields shortest round-trip digits, e.g. "1e21",
        // "1e-7", "1.5e-7". JS wants an explicit '+' on positive exponents.
        let s = format!("{:e}", n);
        let (mantissa, exp) = s.split_once('e').expect("LowerExp always contains 'e'");
        let exp: i32 = exp.parse().expect("LowerExp exponent is an integer");
        if exp >= 0 {
            format!("{}e+{}", mantissa, exp)
        } else {
            format!("{}e-{}", mantissa, -exp)
        }
    } else {
        // Shortest round-trip decimal, no exponent, integral values without ".0".
        format!("{}", n)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn num(n: f64) -> String {
        format_number(n)
    }

    #[test]
    fn number_serialization() {
        assert_eq!(num(1.0), "1");
        assert_eq!(num(0.0), "0");
        assert_eq!(num(-0.0), "0");
        assert_eq!(num(0.01), "0.01");
        assert_eq!(num(0.5689655172413793), "0.5689655172413793");
        assert_eq!(num(0.614), "0.614");
        assert_eq!(num(0.8), "0.8");
        assert_eq!(num(3.0), "3");
        assert_eq!(num(1e21), "1e+21");
        assert_eq!(num(1e-7), "1e-7");
        assert_eq!(num(-1e21), "-1e+21");
        assert_eq!(num(1.5e-7), "1.5e-7");
        assert_eq!(num(100.0), "100");
        assert_eq!(num(0.3333333333333333), "0.3333333333333333");
        assert_eq!(num(0.23570226039551584), "0.23570226039551584");
    }

    #[test]
    fn key_sorting() {
        let v = Value::Obj(vec![
            ("b".into(), Value::Num(1.0)),
            ("a".into(), Value::Num(2.0)),
        ]);
        assert_eq!(canonicalize_string(&v), "{\"a\":2,\"b\":1}");

        // UTF-16 order differs from UTF-8 byte order here: U+1F600 has a high
        // surrogate (0xD83D) below U+FFFD, while its UTF-8 lead byte (0xF0)
        // is above U+FFFD's (0xEF).
        let v = Value::Obj(vec![
            ("\u{FFFD}".into(), Value::Num(1.0)),
            ("\u{1F600}".into(), Value::Num(2.0)),
        ]);
        assert_eq!(canonicalize_string(&v), "{\"\u{1F600}\":2,\"\u{FFFD}\":1}");
    }

    #[test]
    fn string_escaping() {
        assert_eq!(
            canonicalize_string(&Value::Str("a\"b\\c\nd\u{0001}eé".into())),
            "\"a\\\"b\\\\c\\nd\\u0001eé\""
        );
    }
}
