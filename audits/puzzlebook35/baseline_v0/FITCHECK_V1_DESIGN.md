# FITCHECK_V1_DESIGN — non-regex fit_check policy

Status: **proposal**. No code yet. Pick a direction (or modify), then
implementation lands in `baseline_v0/fitcheck_v1.py` (replacing
`retriever.py::fit_check`) or as a separate module under
`audits/puzzlebook35/fitcheck_v1/`.

## Goal

Replace the bare-regex `fit_check` v0 with a policy that:

1. **Does not always say `match`.** v0's `who` rule matches 100% of
   chunks; `how_many` matches 73%. `mismatch` is structurally
   unreachable on this corpus.
2. **Distinguishes answer-bearing chunks from incidental tokens.**
   v0 fires on table headers, sentence-initial words, list markers,
   version strings — none of which support the question's relation.
3. **Covers the 31 currently-skipped questions** (`intent ∈ {what,
   why, how}`) without inheriting the v0 over-match idiom.

## Constraints (firm)

- No LLM in the pipeline.
- No embedding models (HF unreachable from this environment; user
  cannot install locally).
- Pure Python + PyPI-installable deps; deterministic.
- Pinned reproducibility (sha256-stable JSONL outputs).

## What v0 got wrong (recap from FITCHECK_AUDIT.md)

A bare regex of the form `<surface-pattern>.match(chunk_content) >= 1`
treats *any* token of the right shape as evidence. It loses:

- **Context**. `2024 строки кода` is year-shaped but not a year. `1.`
  is a digit but a list marker, not a count. `Python` is capitalized
  but a language, not a person.
- **Question-relation grounding**. The chunk may contain digits, but
  do they answer the *specific* count the question asks about?
- **Discriminative pressure**. If 100% of chunks match, the rule has
  zero information; aggregate hit rate is determined entirely by
  retrieval, not fit_check.

The fix is not a tighter regex — it's a different signal class.

## Design space

Three candidates. Not mutually exclusive; can be combined.

### Candidate A: question-conditioned trigger windows

For each intent, require a candidate token (year / number / name) to
appear within ±N tokens of an intent-trigger phrase **and** within
±M tokens of a question-keyword. Tokens are still found by surface
patterns, but the conjunctive context kills incidental matches.

```
intent=when:
  candidate    = year-shaped 19xx/20xx token
  intent_trigger = {"год","году","в…году","выпущен","издан","опубликован",
                   "вышла","year","date","published","released"}
  question_kw  = content nouns from the question (filtered by stop-list)
  fit_status = match  iff  ∃ candidate s.t.
                 ∃ intent_trigger within ±N tokens AND
                 ∃ question_kw within ±M tokens
```

**Strength.** Directly addresses Q22 brittleness ("port=1999" no longer
matches), Q7 over-match ("автор" trigger required for `who`), Q5/Q14
specificity ("задач"/"параметров" required as question_kw).

**Weakness.** Triggers are hand-curated lexicons. Multilingual handling
(question in Russian, content mixed Russian+English) needs explicit
trigger lists per language. Coverage gaps will show up in evaluation,
not in design.

**Cost.** ~1 day. ~200 LOC. Trigger lexicons per intent (~5–20 phrases
each).

### Candidate B: question-chunk lexical alignment + content-type gate

Not regex-on-chunk. Instead:

1. **Question parsing** (heuristic, no NLP libs): extract content
   tokens (lowercase, stop-list filtered, optional Russian stemming via
   `pymorphy3` or simple suffix trimming).
2. **Chunk content-type signals** (already in `section_path` and
   `type`): is this chunk prose? code? mixed? Which section?
3. **Joint check**: `match` requires:
   - ≥K question content-tokens appear in chunk (lexical alignment);
   - chunk type matches intent expectation (e.g., `intent=how` →
     prefer `mixed`/`prose` with numbered-list markers; `intent=what`
     factoid → prefer `prose` with table headers or specific noun
     phrases).
4. `fit_refuse` when alignment is below threshold.

**Strength.** Closes the `generic_chunk_dominance` failure mode: a
generic short prose chunk with broad vocabulary fails the alignment
floor on most questions even though it shares some words. Section-path
can encode `out_of_scope_within_topic` (Q26/Q31) — if question asks for
"решение" and chunk's section_path is "Серьезные задачи/Задача N", the
solution category is not in this active_corpus.

**Weakness.** Threshold tuning is corpus-specific. Stop-list and
stemming for Russian add complexity. May conflict with retrieval
ordering (TF-IDF already does lexical alignment; we are partly
re-checking it with a stricter floor).

**Cost.** ~1.5 days. ~300 LOC. Russian stop-list (~50 tokens) + simple
suffix trim.

### Candidate C: typed answer-shape templates

For each intent, define what an answer-bearing chunk *structurally
looks like*:

| intent | structural marker |
|---|---|
| `when` | year token + temporal trigger within window |
| `who`  | name token + authorship verb/relation trigger |
| `how_many` | number token + counting noun matching question's noun |
| `what` (factoid) | exact noun-phrase match for question's missing slot — e.g., "Какую версию" → look for "версию X" or "версия X" patterns |
| `why`  | discourse marker (`потому что`, `так как`, `чтобы`) OR enumerated reason structure |
| `how`  | procedural marker (numbered list, imperative verbs, `шаг`/`сначала`/`затем`) |

Each intent gets a small inspector function returning `match` / `partial` /
`mismatch` / `skipped`.

**Strength.** Explicit per-intent expectation; debuggable; aligns with
RVP `fit_expected_type` field.

**Weakness.** Multiplies code surface (six inspectors); each inspector
needs corpus-specific tuning. `what` is the hardest — covers most
questions and has the widest answer-shape variability.

**Cost.** ~2 days. ~500 LOC. Per-intent inspectors with their own
trigger lists and structural detectors.

## Recommendation

**Hybrid: Candidate A + minimal slice of Candidate B.**

Concretely:

1. Apply Candidate A (trigger windows) to the three already-implemented
   intents (`when`, `who`, `how_many`). This is the minimal fix for
   the v0 over-match documented in FITCHECK_AUDIT.
2. Apply Candidate B (lexical-alignment floor + section-path gate) to
   the previously-skipped intents (`what`, `why`, `how`). The gate
   handles `out_of_scope_within_topic` (Q26/Q31) cheaply; the floor
   handles `generic_chunk_dominance` for `pb_raw_05` / `pb_raw_13`.
3. Skip Candidate C for now. Per-intent typed templates are a v2
   refinement; `what` alone is too high-variance to template without
   significantly more design work.

### Why this hybrid

- **Tractable scope**: ~2 days end-to-end with tests, well-defined.
- **Fixes named failure modes**: `lexical_pattern_overmatch` (Q7),
  `generic_chunk_dominance` (Q5/Q9/Q11/Q13/Q16/Q20/Q29/Q34),
  `out_of_scope_within_topic` (Q26/Q31).
- **Leaves room for v2**: if hybrid leaves residual false-hits, v2
  layers Candidate C templates on top per-intent.
- **Falsifiable**: each failure mode has a measurable signal (see
  Falsifiability below).

### Why not embeddings (when they arrive)

Even when v2 weights become available, **fit_check ≠ retrieval**.
Embedding similarity helps retrieval pick semantically-relevant
chunks; it does not by itself answer "does this chunk contain a
year-typed answer near an authorship trigger". `fit_check_v1` and
`baseline_v2_embedding` are independent axes; both should ship.

## Falsifiability — how we know v1 is better than v0

Re-run all 35 questions through v0 and v1 on the same chunks.
Pre-registered metrics, decided **before** running v1:

| metric                                    | v0 value | v1 success criterion |
|-------------------------------------------|----------|----------------------|
| `fit_status=match` rate                  | 6/35 (17%) — but `who` and `how_many` rules trivially match | ≤ 50% (because most questions should not have machine-verifiable evidence — refuse should be common) |
| `fit_refuse` rate                        | 1/35     | ≥ 5/35 (covering at least Q22 + Q26 + Q31 + 2 more out-of-scope or low-alignment cases) |
| Q22 still `fit_refuse`                   | yes      | yes (no regression on the canary) |
| Q2 still `match → hit`                   | yes      | yes (Q-known-hit must not break) |
| `who` regex 100% match rate              | yes      | ≤ 30% on the corpus self-test (FITCHECK_AUDIT regenerated) |
| 9 NOTES §4 false-hits                    | hit (eye-pass) | ≥ 4 of them flip to `fit_refuse` or `partial` |

If v1 fails ≥2 of these, the design is wrong, not the implementation —
revisit before iterating.

## Open questions for user

1. **Scope of v1 release.** Hybrid as described, or smaller (only the
   trigger-windows half, defer alignment-floor)?
2. **Trigger lexicons.** Hand-curated per intent? Or seed from a
   minimal Russian-language NLP library (`pymorphy3` for stems,
   `nltk-data` Russian stop-list)?
3. **Where does v1 live?** Replace `baseline_v0/retriever.py::fit_check`
   in-place (with `fit_check_v0` preserved as legacy), or new module
   `audits/puzzlebook35/fitcheck_v1/` parallel to `baseline_v0`/
   `baseline_v1_bm25`?
4. **Re-run scope.** Run v1 on both v0 (TF-IDF) and v1 (BM25) retrieved
   top-k, or only one? Running on both gives 4-way comparison
   (retrieval × fit_check); running on one halves the cost but loses
   one independence axis.
5. **Pre-registration discipline.** The falsifiability table above is
   the v1 success criterion. Should I commit this file *before*
   touching any v1 code, so the criterion can't be retrofit to fit
   the implementation? (Recommended: yes.)

## What this design does NOT cover

- Question parsing beyond simple tokenization. NER, semantic role
  labeling, dependency parsing — out of scope.
- Multilingual robustness. Implementation will be Russian-first
  (matching the corpus). Latin-language questions/chunks are handled
  only incidentally.
- Cross-chunk reasoning. Each fit_check decision is local to top-k
  chunks. Multi-hop / aggregation questions (Q11: "в каких задачах из
  1-15 функция должна возвращать None") still won't get correct
  fit_status. Best v1 can do is `partial`.
- Generation. `answer` field stays `null`. v1 still checks retrieval,
  not generation.
