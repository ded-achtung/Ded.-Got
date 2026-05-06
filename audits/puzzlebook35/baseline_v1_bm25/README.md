# baseline_v1_bm25 — BM25 Okapi over the same raw chunks as v0

Goal of this baseline: controlled retrieval-method swap. Test whether
the `generic_chunk_dominance` failure mode observed in `baseline_v0`
(NOTES §4) is a TF-IDF-specific artifact, or persists across lexical
retrieval methods.

**Conclusion (see `COMPARE_v0_v1.md` §"Epistemic update"):**
`generic_chunk_dominance` survives the swap. BM25 fixes 1 of 10 known
false-hits, reshuffles 4, leaves 5 unchanged, and *breaks* 2
previously-correct picks. Not a win for BM25 as a fix.

## Inputs (all inherited)

| Input | Location |
|---|---|
| Chunks | `audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl` (from baseline_v0) |
| Questions | `audits/puzzlebook35/audit_v0.questions.jsonl` |
| PDF (only if chunks missing) | `Python в задачах и упражнениях.pdf` (repo root) |

If `puzzlebook_raw_chunks_v1.jsonl` is missing, the v1 pipeline falls
back to running v0's extractor end-to-end so this baseline stays
self-contained.

## Outputs

| File | What |
|---|---|
| `audits/puzzlebook35/runs/<DATE>_v1_bm25.jsonl` | 35 rows, BM25 top-10 + same fit_check |
| `audits/puzzlebook35/manifests/<DATE>_v1_bm25.manifest.json` | Manifest with `simulated: false`, declares retrieval-only delta vs v0 |
| `audits/puzzlebook35/baseline_v1_bm25/COMPARE_v0_v1.md` | Per-qid v0 vs v1 diff, NOTES §4 false-hit tracking, dominance aggregate |

## Setup

Same venv as baseline_v0, plus one extra dep:

```bash
.venv/bin/pip install -r audits/puzzlebook35/baseline_v1_bm25/requirements.txt
```

## Run

```bash
.venv/bin/python audits/puzzlebook35/baseline_v1_bm25/pipeline.py --run-date 2026-05-02
```

Expected stdout:

```
Chunks loaded: 30
Run completed: 35 / 35 questions processed (BM25)
Outcomes: hit=34, fit_refuse=1, given_up=0
fit_status distribution: match=3, mismatch=1, partial=0, skipped=31
```

## Validate

```bash
.venv/bin/python audits/puzzlebook35/baseline_v1_bm25/validate_outputs.py
```

Reuses `baseline_v0/validate_outputs.py` schemas; locates the v1 run +
manifest pair instead of v0's.

## Determinism

Two consecutive pipeline runs produce byte-identical run JSONLs
(verified during development with `sha256sum`).

## What is held constant vs v0

- `puzzlebook_raw_chunks_v1.jsonl` — same file, same SHA-256
- Tokenizer: `lowercase + \b\w\w+\b` (identical to v0 TfidfVectorizer)
- Top-k = 10, downstream-effective-k = 4
- fit_check policy: same regex rules (when / who / how_many), all other
  intents `skipped`
- Run JSONL schema (validated by reused validator)

## What changed

- Scoring formula: `cosine(tfidf(q), tfidf(d))` → `BM25Okapi(q, d)` with
  default `k1=1.5`, `b=0.75`.
- Library: `scikit-learn TfidfVectorizer` → `rank-bm25==0.2.2`.

## What this baseline does NOT test

- Semantic similarity. BM25 is still bag-of-words. To test semantics,
  see the planned `baseline_v2_embedding/` (blocked: HuggingFace not
  reachable from this environment; weights need to be uploaded
  manually under `vendored_models/multilingual-e5-small/`).
