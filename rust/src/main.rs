//! CLI: `web4-trust-derive <vector-dir> [--mrh <iri>]`
//!
//! Reads `<vector-dir>/spec.json` and `<vector-dir>/input.nq` and writes the
//! receipt JCS bytes to stdout — exactly the bytes that should equal
//! `<vector-dir>/receipt.jcs`.

use std::io::Write;
use std::process::ExitCode;

use web4_trust_derivation_ref::{eval, jcs, nquads};

fn main() -> ExitCode {
    match run() {
        Ok(bytes) => {
            let stdout = std::io::stdout();
            let mut lock = stdout.lock();
            if lock.write_all(&bytes).is_err() {
                eprintln!("error: failed writing to stdout");
                return ExitCode::FAILURE;
            }
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("error: {}", e);
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<Vec<u8>, String> {
    let mut args = std::env::args().skip(1);
    let dir = args
        .next()
        .ok_or_else(|| "usage: web4-trust-derive <vector-dir> [--mrh <iri>]".to_string())?;
    let mut mrh: Option<String> = None;
    while let Some(a) = args.next() {
        match a.as_str() {
            "--mrh" => {
                mrh = Some(
                    args.next()
                        .ok_or_else(|| "--mrh requires an IRI argument".to_string())?,
                );
            }
            other => return Err(format!("unknown argument '{}'", other)),
        }
    }

    let spec_text = std::fs::read_to_string(format!("{}/spec.json", dir))
        .map_err(|e| format!("reading {}/spec.json: {}", dir, e))?;
    let nq_text = std::fs::read_to_string(format!("{}/input.nq", dir))
        .map_err(|e| format!("reading {}/input.nq: {}", dir, e))?;

    let spec = eval::Spec::parse(&spec_text)?;
    let mrh = match mrh {
        Some(m) => m,
        None => {
            let quads = nquads::parse(&nq_text)?;
            eval::detect_mrh(&spec, &quads)?
        }
    };

    let receipt = eval::evaluate(&spec, &nq_text, &mrh)?;
    Ok(jcs::canonicalize(&receipt))
}
