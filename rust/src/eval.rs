//! DerivationSpec ingestion (SPEC.md §2) and the semantics-1 evaluator
//! (SPEC.md §3), plus receipt assembly matching `harness/generate.py`'s
//! byte contract.
//!
//! All recursion is strictly-below (stratified) with a memo cache keyed
//! `(subject, dimension, height)`. Evidence folds left-to-right over
//! observations sorted by `(height asc, canonical node identifier asc by
//! code point)`, in IEEE 754 binary64, matching the determinism law.

use std::collections::HashMap;

use crate::json::{self, Value};
use crate::jcs;
use crate::nquads::{self, Object, Quad};
use crate::sha256;

const INTEGRITY_CURIE: &str = "web4:Integrity";

// ---------------------------------------------------------------------------
// Spec ingestion
// ---------------------------------------------------------------------------

pub struct Params {
    pub prior_alpha: f64,
    pub prior_beta: f64,
    pub unmeasured_if_total_weight_below: f64,
    pub provenance_unmeasured_weight: f64,
    pub dependency_discount_per_hop: f64,
    pub provenance_weight_statistic: String,
}

pub struct Ontology {
    pub has_observation: String,
    pub dimension: String,
    pub adjudicated_by: String,
    pub confidence: String,
    pub depends_on: String,
    pub height: String,
    pub mrh: String,
}

pub struct Anchor {
    pub id: String, // full IRI
    pub law_weight: f64,
}

pub struct Spec {
    pub raw: Value,
    pub law_hash: String,
    #[allow(dead_code)]
    pub spec_id: String,
    pub prefixes: Vec<(String, String)>,
    pub ontology: Ontology,
    /// Parent dimension (full IRI) → children (full IRIs), spec map order;
    /// children in `subDimensions` array order.
    pub dimensions: Vec<(String, Vec<String>)>,
    /// The spec's `parameters` object, copied verbatim into the receipt.
    pub parameters_raw: Value,
    pub params: Params,
    pub trust_anchors: Vec<Anchor>,
    #[allow(dead_code)]
    pub observation_nodes: String,
}

const SPEC_FIELDS: [&str; 9] = [
    "spec_id",
    "core",
    "prefixes",
    "ontology",
    "dimensions",
    "parameters",
    "trust_anchors",
    "evidence_rules",
    "observation_nodes",
];

impl Spec {
    pub fn parse(text: &str) -> Result<Spec, String> {
        let raw = json::parse(text)?;
        let obj = raw
            .as_obj()
            .ok_or_else(|| "spec must be a JSON object".to_string())?;
        for (k, _) in obj {
            if !SPEC_FIELDS.contains(&k.as_str()) {
                return Err(format!("unknown top-level spec field '{}'", k));
            }
        }
        for f in SPEC_FIELDS {
            if raw.get(f).is_none() {
                return Err(format!("missing required spec field '{}'", f));
            }
        }

        let law_hash = sha256::sha256_hex(&jcs::canonicalize(&raw));

        let spec_id = required_str(&raw, "spec_id")?.to_string();

        // core: {name, semantics}; this crate implements semantics 1 only.
        let core = raw.get("core").unwrap();
        let name = core
            .get("name")
            .and_then(Value::as_str)
            .ok_or("core.name must be a string")?;
        if name != "web4-trust-core" {
            return Err(format!("unsupported core.name '{}'", name));
        }
        let semantics = core
            .get("semantics")
            .and_then(Value::as_num)
            .ok_or("core.semantics must be a number")?;
        if semantics != 1.0 {
            return Err(format!("unsupported core.semantics {}", semantics));
        }

        let mut prefixes = Vec::new();
        for (k, v) in raw
            .get("prefixes")
            .unwrap()
            .as_obj()
            .ok_or("prefixes must be an object")?
        {
            prefixes.push((
                k.clone(),
                v.as_str().ok_or("prefix values must be strings")?.to_string(),
            ));
        }

        let ont_v = raw.get("ontology").unwrap();
        let ont = |role: &str| -> Result<String, String> {
            let curie = ont_v
                .get(role)
                .and_then(Value::as_str)
                .ok_or_else(|| format!("ontology.{} must be a string", role))?;
            Ok(resolve_curie(curie, &prefixes))
        };
        let ontology = Ontology {
            has_observation: ont("hasObservation")?,
            dimension: ont("dimension")?,
            adjudicated_by: ont("adjudicatedBy")?,
            confidence: ont("confidence")?,
            depends_on: ont("dependsOn")?,
            height: ont("height")?,
            mrh: ont("mrh")?,
        };

        let mut dimensions = Vec::new();
        for (parent, def) in raw
            .get("dimensions")
            .unwrap()
            .as_obj()
            .ok_or("dimensions must be an object")?
        {
            let subs = def
                .get("subDimensions")
                .and_then(Value::as_arr)
                .ok_or_else(|| format!("dimensions.{}.subDimensions must be an array", parent))?;
            let mut children = Vec::new();
            for c in subs {
                children.push(resolve_curie(
                    c.as_str().ok_or("subDimensions entries must be strings")?,
                    &prefixes,
                ));
            }
            dimensions.push((resolve_curie(parent, &prefixes), children));
        }

        let parameters_raw = raw.get("parameters").unwrap().clone();
        let pnum = |k: &str| -> Result<f64, String> {
            parameters_raw
                .get(k)
                .and_then(Value::as_num)
                .ok_or_else(|| format!("parameters.{} must be a number", k))
        };
        let params = Params {
            prior_alpha: pnum("prior_alpha")?,
            prior_beta: pnum("prior_beta")?,
            unmeasured_if_total_weight_below: pnum("unmeasured_if_total_weight_below")?,
            provenance_unmeasured_weight: pnum("provenance_unmeasured_weight")?,
            dependency_discount_per_hop: pnum("dependency_discount_per_hop")?,
            provenance_weight_statistic: parameters_raw
                .get("provenance_weight_statistic")
                .and_then(Value::as_str)
                .ok_or("parameters.provenance_weight_statistic must be a string")?
                .to_string(),
        };
        if params.provenance_weight_statistic != "mean"
            && params.provenance_weight_statistic != "lower_bound"
        {
            return Err(format!(
                "unknown provenance_weight_statistic '{}'",
                params.provenance_weight_statistic
            ));
        }

        let mut trust_anchors = Vec::new();
        for a in raw
            .get("trust_anchors")
            .unwrap()
            .as_arr()
            .ok_or("trust_anchors must be an array")?
        {
            let id = a
                .get("id")
                .and_then(Value::as_str)
                .ok_or("trust_anchors[].id must be a string")?;
            let law_weight = a
                .get("law_weight")
                .and_then(Value::as_num)
                .ok_or("trust_anchors[].law_weight must be a number")?;
            trust_anchors.push(Anchor {
                id: resolve_curie(id, &prefixes),
                law_weight,
            });
        }

        // evidence_rules: validated for shape only. Per SPEC.md §7 the current
        // vectors carry confidence directly in the graph (projection-applies-rules);
        // the evaluate-applies-rules fork is reserved for V8.
        raw.get("evidence_rules")
            .unwrap()
            .as_arr()
            .ok_or("evidence_rules must be an array")?;

        let observation_nodes = required_str(&raw, "observation_nodes")?.to_string();
        if observation_nodes != "skolemized-iri" && observation_nodes != "blank-node" {
            return Err(format!(
                "observation_nodes must be \"skolemized-iri\" or \"blank-node\", got '{}'",
                observation_nodes
            ));
        }
        // Note: milestone 1 canonicalizes graphs in skolemized mode (sorted
        // lines). The evaluation semantics below are mode-agnostic, so a
        // blank-node-mode spec can still drive evaluation over an already-
        // canonical graph (the v6b semantic cross-check does exactly this);
        // full RDFC-1.0 canonicalization is out of scope for milestone 1.

        Ok(Spec {
            raw,
            law_hash,
            spec_id,
            prefixes,
            ontology,
            dimensions,
            parameters_raw,
            params,
            trust_anchors,
            observation_nodes,
        })
    }

    /// Resolve a CURIE through the prefixes map; strings whose prefix is not
    /// in the map (e.g. full `urn:`/`https:` IRIs) pass through unchanged.
    pub fn resolve(&self, curie: &str) -> String {
        resolve_curie(curie, &self.prefixes)
    }

    /// Compact a full IRI to CURIE form for receipt output; IRIs matching no
    /// prefix are emitted unchanged.
    pub fn to_curie(&self, iri: &str) -> String {
        for (prefix, ns) in &self.prefixes {
            if let Some(rest) = iri.strip_prefix(ns.as_str()) {
                return format!("{}:{}", prefix, rest);
            }
        }
        iri.to_string()
    }

    pub fn children_of(&self, dimension: &str) -> Option<&[String]> {
        self.dimensions
            .iter()
            .find(|(p, _)| p == dimension)
            .map(|(_, c)| c.as_slice())
    }

    pub fn anchor_for(&self, id: &str) -> Option<&Anchor> {
        self.trust_anchors.iter().find(|a| a.id == id)
    }
}

fn required_str<'a>(v: &'a Value, key: &str) -> Result<&'a str, String> {
    v.get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| format!("spec field '{}' must be a string", key))
}

fn resolve_curie(s: &str, prefixes: &[(String, String)]) -> String {
    if let Some((head, rest)) = s.split_once(':') {
        for (prefix, ns) in prefixes {
            if prefix == head {
                return format!("{}{}", ns, rest);
            }
        }
    }
    s.to_string()
}

// ---------------------------------------------------------------------------
// Graph loading
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub struct Observation {
    pub iri: String,
    pub subject: String,
    pub dimension: String, // full IRI, as carried by the graph
    pub adjudicator: String,
    pub confidence: f64,
    pub height: i64,
    pub mrh: String,
    pub depends_on: Vec<String>, // observation IRIs
}

/// Extract observations from parsed quads. An observation node is any IRI
/// appearing as the object of `hasObservation`; each such node must carry
/// dimension, adjudicatedBy, confidence, height and mrh.
pub fn load_observations(spec: &Spec, quads: &[Quad]) -> Result<Vec<Observation>, String> {
    let o = &spec.ontology;
    let mut subject_of: HashMap<String, String> = HashMap::new();
    let mut props: HashMap<String, Vec<(String, Object)>> = HashMap::new();
    for q in quads {
        if q.predicate == o.has_observation {
            if let Object::Iri(obs) = &q.object {
                subject_of.insert(obs.clone(), q.subject.clone());
            }
        } else {
            props
                .entry(q.subject.clone())
                .or_default()
                .push((q.predicate.clone(), q.object.clone()));
        }
    }

    let mut out = Vec::new();
    for (iri, subject) in &subject_of {
        let empty = Vec::new();
        let ps = props.get(iri).unwrap_or(&empty);
        let mut dimension = None;
        let mut adjudicator = None;
        let mut confidence = None;
        let mut height = None;
        let mut mrh = None;
        let mut depends_on = Vec::new();
        for (pred, obj) in ps {
            if *pred == o.dimension {
                dimension = Some(iri_obj(obj, "dimension")?);
            } else if *pred == o.adjudicated_by {
                adjudicator = Some(iri_obj(obj, "adjudicatedBy")?);
            } else if *pred == o.confidence {
                confidence = Some(lit_num(obj, "confidence")?);
            } else if *pred == o.height {
                height = Some(lit_num(obj, "height")? as i64);
            } else if *pred == o.mrh {
                mrh = Some(iri_obj(obj, "mrh")?);
            } else if *pred == o.depends_on {
                depends_on.push(iri_obj(obj, "dependsOn")?);
            }
        }
        out.push(Observation {
            iri: iri.clone(),
            subject: subject.clone(),
            dimension: dimension.ok_or_else(|| format!("obs {} missing dimension", iri))?,
            adjudicator: adjudicator.ok_or_else(|| format!("obs {} missing adjudicatedBy", iri))?,
            confidence: confidence.ok_or_else(|| format!("obs {} missing confidence", iri))?,
            height: height.ok_or_else(|| format!("obs {} missing height", iri))?,
            mrh: mrh.ok_or_else(|| format!("obs {} missing mrh", iri))?,
            depends_on,
        });
    }
    // Deterministic baseline order; folds re-sort explicitly.
    out.sort_by(|a, b| a.iri.cmp(&b.iri));
    Ok(out)
}

fn iri_obj(obj: &Object, what: &str) -> Result<String, String> {
    match obj {
        Object::Iri(s) => Ok(s.clone()),
        _ => Err(format!("{} object must be an IRI", what)),
    }
}

fn lit_num(obj: &Object, what: &str) -> Result<f64, String> {
    match obj {
        Object::Literal(lex, _) => lex
            .parse::<f64>()
            .map_err(|e| format!("{} literal '{}' is not a number: {}", what, lex, e)),
        _ => Err(format!("{} object must be a literal", what)),
    }
}

/// The single mrh IRI present in the graph's observations (CLI default).
pub fn detect_mrh(spec: &Spec, quads: &[Quad]) -> Result<String, String> {
    let obs = load_observations(spec, quads)?;
    let mut mrhs: Vec<&str> = obs.iter().map(|o| o.mrh.as_str()).collect();
    mrhs.sort();
    mrhs.dedup();
    match mrhs.len() {
        1 => Ok(mrhs[0].to_string()),
        0 => Err("no observations in graph; pass --mrh explicitly".into()),
        _ => Err(format!(
            "graph carries {} distinct mrhs; pass --mrh explicitly",
            mrhs.len()
        )),
    }
}

// ---------------------------------------------------------------------------
// Evaluator (semantics 1)
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, Debug)]
pub struct Score {
    pub mu: f64,
    pub sigma: f64,
    pub strength: f64,
}

#[derive(Clone, Debug)]
pub enum Wp {
    Anchored {
        value: f64,
        id: String,
        law_weight: f64,
        derived_integrity: Option<f64>,
    },
    Unmeasured {
        value: f64,
    },
    Measured {
        value: f64,
        adjudicator: String,
    },
}

#[derive(Clone, Debug)]
pub struct DepEntry {
    pub obs: String,
    pub score_used: f64,
    pub discount: f64,
}

#[derive(Clone, Debug)]
pub struct Wd {
    pub value: f64,
    pub deps: Vec<DepEntry>,
}

#[derive(Clone, Debug)]
pub struct EvidenceEntry {
    pub obs: String,
    pub confidence: f64,
    pub height: i64,
    pub wp: Wp,
    pub wd: Wd,
}

#[derive(Clone, Debug)]
pub struct UnmeasuredEntry {
    pub obs: String,
    pub height: i64,
    pub adjudicator: String,
}

pub struct ScoreDetail {
    pub result: Option<Score>,
    pub evidence: Vec<EvidenceEntry>,
    pub unmeasured: Vec<UnmeasuredEntry>,
}

pub struct Evaluator<'a> {
    pub spec: &'a Spec,
    /// Observations eligible under the requested mrh.
    obs: Vec<Observation>,
    by_iri: HashMap<String, usize>,
    cache: HashMap<(String, String, i64), Option<Score>>,
    integrity_iri: String,
}

impl<'a> Evaluator<'a> {
    pub fn new(spec: &'a Spec, observations: Vec<Observation>, mrh: &str) -> Evaluator<'a> {
        let obs: Vec<Observation> = observations
            .into_iter()
            .filter(|o| o.mrh == mrh)
            .collect();
        let by_iri = obs
            .iter()
            .enumerate()
            .map(|(i, o)| (o.iri.clone(), i))
            .collect();
        Evaluator {
            spec,
            obs,
            by_iri,
            cache: HashMap::new(),
            integrity_iri: spec.resolve(INTEGRITY_CURIE),
        }
    }

    pub fn subjects(&self) -> Vec<String> {
        let mut s: Vec<String> = self.obs.iter().map(|o| o.subject.clone()).collect();
        s.sort();
        s.dedup();
        s
    }

    /// Minimum evidence height for a subject (score-entry ordering key).
    pub fn min_height(&self, subject: &str) -> i64 {
        self.obs
            .iter()
            .filter(|o| o.subject == subject)
            .map(|o| o.height)
            .min()
            .unwrap_or(0)
    }

    fn provenance_statistic(&self, s: &Score) -> f64 {
        if self.spec.params.provenance_weight_statistic == "lower_bound" {
            (s.mu - s.sigma).max(0.0)
        } else {
            s.mu
        }
    }

    /// Indices of leaf observations for (subject, dimension) strictly below
    /// `height`, in canonical fold order (height asc, obs IRI code-point asc).
    fn fold_indices(&self, subject: &str, dimension: &str, height: i64) -> Vec<usize> {
        let mut idx: Vec<usize> = self
            .obs
            .iter()
            .enumerate()
            .filter(|(_, o)| {
                o.subject == subject && o.dimension == dimension && o.height < height
            })
            .map(|(i, _)| i)
            .collect();
        idx.sort_by(|&a, &b| {
            let (x, y) = (&self.obs[a], &self.obs[b]);
            (x.height, &x.iri).cmp(&(y.height, &y.iri))
        });
        idx
    }

    /// Score for (subject, dimension) over evidence strictly below `height`.
    pub fn score_at(&mut self, subject: &str, dimension: &str, height: i64) -> Option<Score> {
        let key = (subject.to_string(), dimension.to_string(), height);
        if let Some(cached) = self.cache.get(&key) {
            return *cached;
        }
        let result = if let Some(children) = self.spec.children_of(dimension) {
            // Parent: strength-weighted mean of measured children, iterated in
            // the spec's subDimensions order.
            let mut measured: Vec<Score> = Vec::new();
            for child in children {
                let child = child.clone();
                if let Some(s) = self.score_at(subject, &child, height) {
                    measured.push(s);
                }
            }
            if measured.is_empty() {
                None
            } else {
                let total: f64 = measured.iter().map(|s| s.strength).sum();
                let mu: f64 = measured.iter().map(|s| s.mu * s.strength).sum::<f64>() / total;
                let var: f64 = measured
                    .iter()
                    .map(|s| {
                        let w = s.strength / total;
                        w * w * s.sigma * s.sigma
                    })
                    .sum();
                Some(Score { mu, sigma: var.sqrt(), strength: total })
            }
        } else {
            // Leaf: Beta update over the canonical fold.
            let mut weights = Vec::new();
            for i in self.fold_indices(subject, dimension, height) {
                let o = self.obs[i].clone();
                let (w, _, _) = self.weight_of(&o);
                weights.push((o.confidence, w));
            }
            beta_update(&self.spec.params, &weights)
        };
        self.cache.insert(key, result);
        result
    }

    /// Effective weight for one observation, with the receipt-side records.
    fn weight_of(&mut self, o: &Observation) -> (f64, Wp, Wd) {
        let p = &self.spec.params;
        // Provenance weight.
        let (wp_val, wp) = if let Some(anchor) = self.spec.anchor_for(&o.adjudicator) {
            let law_weight = anchor.law_weight;
            let anchor_id = anchor.id.clone();
            // The anchor's own derived Integrity strictly below the
            // observation's height (SPEC.md §10): reported as receipt drift
            // signal; it never feeds w_p.value.
            let derived = self
                .score_at(&anchor_id, &self.integrity_iri.clone(), o.height)
                .map(|s| self.provenance_statistic(&s));
            (
                1.0 * law_weight,
                Wp::Anchored {
                    value: 1.0 * law_weight,
                    id: anchor_id,
                    law_weight,
                    derived_integrity: derived,
                },
            )
        } else {
            let adj = o.adjudicator.clone();
            match self.score_at(&adj, &self.integrity_iri.clone(), o.height) {
                None => (
                    p.provenance_unmeasured_weight,
                    Wp::Unmeasured { value: p.provenance_unmeasured_weight },
                ),
                Some(s) => (
                    self.provenance_statistic(&s),
                    Wp::Measured {
                        value: self.provenance_statistic(&s),
                        adjudicator: adj,
                    },
                ),
            }
        };

        // Dependency weight: product over dependsOn targets, each strictly
        // below the observation's height; 0.0 if any dependency is unmeasured.
        let mut wd_val = 1.0;
        let mut deps = Vec::new();
        for dep_iri in &o.depends_on {
            let target = self.by_iri.get(dep_iri).map(|&i| &self.obs[i]);
            let score = match target {
                Some(t) => {
                    let (s, d) = (t.subject.clone(), t.dimension.clone());
                    self.score_at(&s, &d, o.height)
                }
                None => None, // dependency not in the eligible graph
            };
            match score {
                None => {
                    wd_val = 0.0;
                    deps.clear();
                    break;
                }
                Some(s) => {
                    wd_val *= s.mu * p.dependency_discount_per_hop;
                    deps.push(DepEntry {
                        obs: dep_iri.clone(),
                        score_used: s.mu,
                        discount: p.dependency_discount_per_hop,
                    });
                }
            }
        }

        let w = (wp_val * wd_val * 1.0).clamp(0.0, 1.0);
        (w, wp, Wd { value: wd_val, deps })
    }

    /// Full detail (result + evidence records) at the given upper bound,
    /// used for receipt entries.
    pub fn detail(&mut self, subject: &str, dimension: &str, below: i64) -> ScoreDetail {
        if let Some(children) = self.spec.children_of(dimension) {
            let children = children.to_vec();
            let mut evidence = Vec::new();
            let mut unmeasured = Vec::new();
            for child in &children {
                let cd = self.detail(subject, child, below);
                evidence.extend(cd.evidence);
                unmeasured.extend(cd.unmeasured);
            }
            // Parent evidence is the descendants' fold merged back into
            // canonical fold order. (Unpinned beyond single-child parents:
            // no vector exercises a multi-child parent receipt yet — V9 is
            // reserved for exactly that.)
            evidence.sort_by(|a, b| (a.height, &a.obs).cmp(&(b.height, &b.obs)));
            unmeasured.sort_by(|a, b| (a.height, &a.obs).cmp(&(b.height, &b.obs)));
            let result = self.score_at(subject, dimension, below);
            ScoreDetail { result, evidence, unmeasured }
        } else {
            let indices = self.fold_indices(subject, dimension, below);
            let mut weights = Vec::with_capacity(indices.len());
            let mut evidence = Vec::with_capacity(indices.len());
            let mut unmeasured = Vec::new();
            for i in indices {
                let o = self.obs[i].clone();
                let (w, wp, wd) = self.weight_of(&o);
                if let Wp::Unmeasured { .. } = wp {
                    unmeasured.push(UnmeasuredEntry {
                        obs: o.iri.clone(),
                        height: o.height,
                        adjudicator: o.adjudicator.clone(),
                    });
                }
                weights.push((o.confidence, w));
                evidence.push(EvidenceEntry {
                    obs: o.iri,
                    confidence: o.confidence,
                    height: o.height,
                    wp,
                    wd,
                });
            }
            ScoreDetail {
                result: beta_update(&self.spec.params, &weights),
                evidence,
                unmeasured,
            }
        }
    }
}

/// The normative Beta fold: sums accumulate left-to-right in the given
/// (canonical) order, binary64. `weights` is `(confidence, effective weight)`
/// in fold order.
fn beta_update(params: &Params, weights: &[(f64, f64)]) -> Option<Score> {
    let mut scw = 0.0;
    let mut s1cw = 0.0;
    let mut total_w = 0.0;
    for &(c, w) in weights {
        scw += c * w;
        s1cw += (1.0 - c) * w;
        total_w += w;
    }
    if total_w < params.unmeasured_if_total_weight_below {
        return None;
    }
    let a = params.prior_alpha + scw;
    let b = params.prior_beta + s1cw;
    let s = a + b;
    Some(Score {
        mu: a / s,
        sigma: (a * b / (s * s * (s + 1.0))).sqrt(),
        strength: a + b - params.prior_alpha - params.prior_beta,
    })
}

// ---------------------------------------------------------------------------
// Receipt assembly
// ---------------------------------------------------------------------------

/// Evaluate and build the receipt object (the JCS-serialization of which is
/// the pinned `receipt.jcs` byte contract; `evaluator`/`receipt_hash` are
/// excluded, matching `generate.py`'s hash source).
pub fn evaluate(spec: &Spec, nq_input: &str, mrh: &str) -> Result<Value, String> {
    let quads = nquads::parse(nq_input)?;
    let canonical = nquads::canonical_bytes(nq_input);
    let graph_hash = sha256::sha256_hex(&canonical);

    let observations = load_observations(spec, &quads)?;
    let mut ev = Evaluator::new(spec, observations, mrh);

    let below = ev.obs.iter().map(|o| o.height).max().unwrap_or(0) + 1;

    // Score-entry ordering: subjects by (minimum evidence height asc,
    // subject IRI code-point asc).
    let mut subjects = ev.subjects();
    subjects.sort_by(|a, b| (ev.min_height(a), a).cmp(&(ev.min_height(b), b)));

    let mut scores = Vec::new();
    for subject in &subjects {
        for dim in select_dimensions(&mut ev, subject, below) {
            let d = ev.detail(subject, &dim, below);
            scores.push(score_entry(spec, subject, &dim, d));
        }
    }

    Ok(Value::Obj(vec![
        ("law_hash".into(), Value::Str(spec.law_hash.clone())),
        ("graph_hash".into(), Value::Str(graph_hash)),
        (
            "chain_range".into(),
            Value::Obj(vec![
                ("from".into(), Value::Num(0.0)),
                ("below".into(), Value::Num(below as f64)),
            ]),
        ),
        ("mrh".into(), Value::Str(mrh.to_string())),
        ("parameters".into(), spec.parameters_raw.clone()),
        ("scores".into(), Value::Arr(scores)),
    ]))
}

/// PROVISIONAL score-selection rule (hypothesis — no spec text pins which
/// (subject, dimension) pairs become receipt entries; the pinned vectors are
/// hand-authored). This rule reproduces all four pinned receipts:
///   (a) every parent dimension ALL of whose children (recursively) are
///       measured for this subject, and
///   (b) every leaf dimension with direct observations for this subject that
///       is NOT a descendant of an emitted parent.
/// Dimensions are returned in code-point order of their CURIE (receipt) form.
/// Verification: v3 → one entry; v4b → member-M BoundaryResponse + operator
/// Integrity (operator's AdjudicationQuality leaf is covered by its emitted
/// parent); v7 → one entry; v6b hand-check → subject-S, then member-M.
fn select_dimensions(ev: &mut Evaluator, subject: &str, below: i64) -> Vec<String> {
    let spec = ev.spec;

    fn all_children_measured(
        ev: &mut Evaluator,
        subject: &str,
        dim: &str,
        below: i64,
    ) -> bool {
        let children = match ev.spec.children_of(dim) {
            Some(c) => c.to_vec(),
            None => return true,
        };
        children.iter().all(|c| {
            ev.score_at(subject, c, below).is_some()
                && all_children_measured(ev, subject, c, below)
        })
    }

    fn descendants(spec: &Spec, dim: &str, out: &mut Vec<String>) {
        if let Some(children) = spec.children_of(dim) {
            for c in children {
                out.push(c.clone());
                descendants(spec, c, out);
            }
        }
    }

    let mut emitted_parents: Vec<String> = Vec::new();
    for (parent, _) in &spec.dimensions {
        if all_children_measured(ev, subject, parent, below) {
            emitted_parents.push(parent.clone());
        }
    }
    let mut covered: Vec<String> = Vec::new();
    for p in &emitted_parents {
        descendants(spec, p, &mut covered);
    }

    let mut dims: Vec<String> = emitted_parents;
    // Leaves (never a key in the dimensions map) with direct observations.
    let mut leaf_obs_dims: Vec<String> = ev
        .obs
        .iter()
        .filter(|o| o.subject == subject && spec.children_of(&o.dimension).is_none())
        .map(|o| o.dimension.clone())
        .collect();
    leaf_obs_dims.sort();
    leaf_obs_dims.dedup();
    for d in leaf_obs_dims {
        if !covered.contains(&d) {
            dims.push(d);
        }
    }
    // Order by code point of the CURIE (emitted) form.
    dims.sort_by_key(|d| spec.to_curie(d));
    dims
}

fn score_entry(spec: &Spec, subject: &str, dimension: &str, d: ScoreDetail) -> Value {
    let result = match d.result {
        None => Value::Null,
        Some(s) => Value::Obj(vec![
            ("mu".into(), Value::Num(s.mu)),
            ("sigma".into(), Value::Num(s.sigma)),
            ("strength".into(), Value::Num(s.strength)),
        ]),
    };
    let evidence: Vec<Value> = d.evidence.iter().map(evidence_entry).collect();
    let unmeasured: Vec<Value> = d
        .unmeasured
        .iter()
        .map(|u| {
            Value::Obj(vec![
                ("obs".into(), Value::Str(u.obs.clone())),
                ("reason".into(), Value::Str("unmeasured_adjudicator".into())),
                ("adjudicator".into(), Value::Str(u.adjudicator.clone())),
            ])
        })
        .collect();
    Value::Obj(vec![
        ("subject".into(), Value::Str(subject.to_string())),
        ("dimension".into(), Value::Str(spec.to_curie(dimension))),
        ("result".into(), result),
        ("evidence".into(), Value::Arr(evidence)),
        ("unmeasured_upstream".into(), Value::Arr(unmeasured)),
    ])
}

fn evidence_entry(e: &EvidenceEntry) -> Value {
    let wp = match &e.wp {
        Wp::Anchored {
            value,
            id,
            law_weight,
            derived_integrity,
        } => Value::Obj(vec![
            ("value".into(), Value::Num(*value)),
            ("basis".into(), Value::Str("anchored".into())),
            (
                "anchor".into(),
                Value::Obj(vec![
                    ("id".into(), Value::Str(id.clone())),
                    ("law_weight".into(), Value::Num(*law_weight)),
                    (
                        "derived_integrity".into(),
                        derived_integrity.map(Value::Num).unwrap_or(Value::Null),
                    ),
                ]),
            ),
        ]),
        Wp::Unmeasured { value } => Value::Obj(vec![
            ("value".into(), Value::Num(*value)),
            ("basis".into(), Value::Str("unmeasured".into())),
        ]),
        // PROVISIONAL, UNPINNED ENCODING: no pinned receipt exercises the
        // measured (non-anchor) basis (reserved for V4a). The weight
        // computation above is normative per SPEC.md §3; this JSON shape is
        // our choice until a vector pins it.
        Wp::Measured { value, adjudicator } => Value::Obj(vec![
            ("value".into(), Value::Num(*value)),
            ("basis".into(), Value::Str("measured".into())),
            ("adjudicator".into(), Value::Str(adjudicator.clone())),
        ]),
    };
    let deps: Vec<Value> = e
        .wd
        .deps
        .iter()
        .map(|d| {
            Value::Obj(vec![
                ("obs".into(), Value::Str(d.obs.clone())),
                ("score_used".into(), Value::Num(d.score_used)),
                ("discount".into(), Value::Num(d.discount)),
            ])
        })
        .collect();
    Value::Obj(vec![
        ("obs".into(), Value::Str(e.obs.clone())),
        ("confidence".into(), Value::Num(e.confidence)),
        ("height".into(), Value::Num(e.height as f64)),
        ("w_p".into(), wp),
        (
            "w_d".into(),
            Value::Obj(vec![
                ("value".into(), Value::Num(e.wd.value)),
                ("deps".into(), Value::Arr(deps)),
            ]),
        ),
    ])
}
