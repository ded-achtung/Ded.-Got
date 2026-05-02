# baseline_v0 — raw chunks exporter + TF-IDF retrieval baseline

Goal: produce a real (not paraphrased, not simulated) chunked corpus from
the Whiteside puzzlebook PDF and a TF-IDF top-k baseline run over the
35 puzzlebook35 questions, so that audit rows built on paraphrased chunks
can be re-checked against raw retrieval.

## Inputs

| Input | Location |
|---|---|
| PDF | `Python в задачах и упражнениях.pdf` (repo root) |
| Questions | `audits/puzzlebook35/audit_v0.questions.jsonl` |

## Outputs

| File | What |
|---|---|
| `audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl` | 30 raw chunks from pp.12–38, deterministic IDs `pb_raw_NN` |
| `audits/puzzlebook35/runs/<DATE>_v0_baseline.jsonl` | 35 rows, one per qid, with TF-IDF top-10 + minimal fit_check |
| `audits/puzzlebook35/manifests/<DATE>_v0_baseline.manifest.json` | Honest manifest with `simulated: false` and SHA-256s |

## Reproducible setup

Starting from a clean Ubuntu (or other Debian-derived) environment:

```bash
# system dep — pdftotext binary from poppler-utils
sudo apt-get install -y poppler-utils

# Python venv + pinned deps
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r audits/puzzlebook35/baseline_v0/requirements.txt
```

## Run

From repo root:

```bash
.venv/bin/python audits/puzzlebook35/baseline_v0/pipeline.py --run-date 2026-05-02
```

Expected stdout (with the PDF as committed at `ee7a7f9`):

```
Chunks extracted: 30 (from pp.12-38)
Run completed: 35 / 35 questions processed
Outcomes: hit=34, fit_refuse=1, given_up=0
fit_status distribution: match=3, mismatch=1, partial=0, skipped=31
```

The single `fit_refuse` is **Q22** (`intent=when`, `pilot_role=not_in_corpus_test`):
the year-regex finds no `(19|20)\d{2}` hits in the top-k, so the baseline
refuses. This is the expected canary — if Q22 ever flips to `hit` without
a year appearing in the corpus, the fit_check is broken.

> **Caveat — `intent=how` is not covered by fit_check v0.** Questions
> like **Q26** (`Какое предлагаемое решение задачи 5`) and **Q31** (`решить
> задачу 9 без словаря`) ask for solutions that live outside pp.12–38;
> `audit_v0.preflight.jsonl` flags them `not_in_corpus`. baseline_v0
> nevertheless returns `final_outcome=hit` (intent=how → skipped → hit).
> Do **not** compare baseline_v0 outcomes for these qids with pre-flight
> as if they should agree — they were measured against different policies.
> See `NOTES.md` for an eye-pass list of additional likely false-hits.

## Validate

```bash
.venv/bin/python audits/puzzlebook35/baseline_v0/validate_outputs.py
```

Exits `0` when:
- chunks JSONL is JSON-Schema valid; chunk_ids are unique, match `pb_raw_\d+`, and `char_count == len(content)`
- run JSONL has exactly 35 rows; `qid` set matches `audit_v0.questions.jsonl`
- every `retrieved_topk_chunk_ids` element exists in the corpus
- `fit_status` ∈ {match, mismatch, partial, skipped}; `final_outcome` ∈ {hit, fit_refuse, given_up}
- manifest has `simulated: false`, all `what_is_real_vs_constructed` keys present, and recorded SHA-256s match the on-disk files

## Determinism

Two consecutive runs produce byte-identical `chunks.jsonl` and run JSONL
(verified during development with `sha256sum`). No timestamps inside
chunk records (timestamp lives only in manifest under `generated_at_utc`).

## Scope (v0) — what is and is not in this baseline

In:
- `pdftotext -layout` extraction of pp.12–38 with deterministic section-header chunking
- TF-IDF cosine retrieval (scikit-learn, top-10)
- Minimal fit_check: regex year for `intent=when`, capitalized name for `who`, digit for `how_many`; everything else → `skipped`
- `final_outcome = fit_refuse` only when `fit_status == mismatch` and intent ∈ {when, who, how_many}; otherwise `hit`
- `answer` left as `null` (this baseline checks retrieval, not generation)

Out (TODO for follow-up sessions):
- Full Question_fit v0 (beyond three regex rules)
- BM25 / embedding retrieval for comparison
- Re-labelling the three existing pilot audit rows (Q2, Q22, Q7) against raw chunks
- Inter-rater between paraphrased-based rows and raw-based rows
- Real answer generation
