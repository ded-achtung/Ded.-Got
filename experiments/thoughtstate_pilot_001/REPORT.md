# ThoughtState Pilot 001 — Q9 / Q4 Disambiguation Skeleton

**Status:** shadow exploration. **Not** a Pack v0.2.1 deliverable. Does **not**
influence the retrieval audit gate. ThoughtState remains off-mainline per
Pack v0.2.1 §2 (no prototype in main contour until retrieval audit completes).

This report documents a closed milestone. Decisions provoked by Result 3 are
explicitly deferred to a separate session — see "What this pilot did NOT show"
and "Discipline note" below.

---

## Provenance

- Branch: `claude/test-q9-skeleton-Av3OB`
- Commits:
  - `a29d539` — Stage 1 (Q9 skeleton + 8 tests)
  - `07be2a3` — Stages 2 & 3 (Q4 unextended + extended; +20 tests)
- Code: `q9_pilot/` (sibling to `prototype/`, off the Cargo workspace)
- Reproduction:
  ```
  cd q9_pilot
  python3 -m unittest test_q9 test_q4_unextended test_q4_extended -v
  ```
- Total: **28 unittest cases, 0 failures.**

---

## Scope

Three-stage exercise on the 7-slot ThoughtState skeleton (K, G, Ex, H, E, T, P)
with a tension-driven `think_step`. Stages were run in order; no restart.

| Stage | Question | Corpus | Extractors |
| --- | --- | --- | --- |
| 1 | Q9 (Vector special methods, ch.12) | stub, reconstructed from chat trace | Q9-trained |
| 2 | Q4 (FrenchDeck card count, ch.1-2) | real chunks c003 / c004 / c033 from user's test-retest archive | Q9-trained, **unmodified** |
| 3 | Q4 (same) | real chunks, three sub-configurations | extended (`_doctest_output`, `_author_count_phrase`) |

All stages are deterministic: regex extractors and keyword-overlap retrieve.
No LLM in the loop.

---

## Three empirical results

### Result 1 — Q9 primary path resolved by P; alternative path stalls without P

Concept holds at the level it was designed for. Three typed claims extracted:

| Source | Value | Origin |
| --- | --- | --- |
| `forward_reference` | 4 | `c009` "the special methods __repr__, __abs__, __add__, and __mul__" |
| `author_anchor` | 5 | `c010_canonical` "We implemented five special methods in addition to the familiar __init__" |
| `code_literal` | 6 | `c010_code` six `def __X__(` patterns |

E transitions `unknown → conflicting → supported`. P[how_many] selects rule_1
(`author_anchor`); winner = c010_canonical; answer = 5 with scope
`'in addition to the familiar __init__'`.

Alternative path (refine_Ex + second retrieve, P explicitly cleared)
deterministically stalls: K identical to primary, E remains `conflicting`,
|H_active| = 3, goal status remains `open`. Trace logs explicit
`STALLED — refine_Ex cannot resolve conflict without P`.

**Why this matters.** Earlier in chat this was a claim from inference
("if we ran it, P would be required"). Here it is the exit state of a
Python program that could have falsified it through any side-effect
convergence. It did not.

### Result 2 — Extractors do not generalise across questions; failure mode is silent-wrong

Q9-trained extractors run unchanged on Q4 chunks.

`_code_literal` regex matches `def __X__\(` and fires on `c003` (FrenchDeck
class body has three dunder defs: `__init__`, `__len__`, `__getitem__`),
producing `code_literal = 3`. Neither `_author_anchor` ("implemented N special
methods") nor `_forward_reference` ("the special methods __a__, __b__")
matches anything in the Q4 chunks.

Outcome:
- K = 1 claim
- |H| = 1
- E = `supported`
- `narrow_hypothesis` is **never invoked**
- pilot returns answer **3** with goal status `solved`

**Refinement of the chat prediction.** The chat anticipated either an empty K
or K with irrelevant claims. The first would have triggered `E=unsupported`
and an explicit halt. The second materialised as a confident wrong answer
with no T-tension flagging the mismatch. The pilot did not stall — it
*answered confidently in the wrong domain*. This is strictly worse than
stalling, because there is no signal upstream that anything went wrong.

### Result 3 — P resolves cross-type conflicts, **not** within-type

This was not part of the chat analysis going in.

**3A — extended extractors + full Q4 corpus.** K = 3 claims:
- `c003` `code_literal = 3`
- `c004` `code_literal = 52` (from `_doctest_output`: `>>> len(deck)\n52`)
- `c033` `author_anchor = 52` (from `_author_count_phrase`: "list made of 52 cards")

E = `conflicting` on values {3, 52}. `narrow_hypothesis` fires `rule_1`
(`author_anchor`); winner = c033; answer = **52**. Correct.

**3B1 — extended extractors minus `_author_count_phrase`, corpus = {c004}.**
K = 1 claim (`c004` `code_literal = 52`). E = `supported`. No narrow needed.
Answer = **52**. Correct. Demonstrates that an absent top-priority source
does not break the loop when no within-type conflict exists.

**3B2 — extended extractors minus `_author_count_phrase`, corpus = {c003, c004}.**
K = 2 claims, both `code_literal`, values 3 and 52. E = `conflicting`.
`narrow_hypothesis` fires `rule_3` (`code_literal`). Within the bucket,
ordering is by retrieve rank: c003 has three keyword overlaps with the
query ("FrenchDeck", "Example", "1-1"); c004 has one ("FrenchDeck"). Bucket
order is `[c003, c004]`. Winner = c003; answer = **3**. Wrong, with
E = `supported` and goal status `solved`.

**Categorical observation.** Adding more structure to P (rules, conditions,
rationale, metadata, confidence) cannot fix 3B2. The problem is not that P
ordering is too weak — it is that *P ordering yields no constraint inside a
single source_type*, and bucket order falls back to retrieve rank, which is
keyword-overlap and domain-blind. This is on a different axis from "make P
more structured", and would not have surfaced no matter how rich P became
along the original axis.

---

## Four limits

1. **Q9 corpus is stub text** reconstructed from the chat trace narrative,
   not real Fluent Python ch.12 text. Q9 results are conditional on the stub
   matching what the real chunks would produce.
2. **Q4 corpus is three real chunks**, not a sample. Author-phrase regex is
   tuned to the exact phrasing of c033 ("list made of N cards"); rephrasings
   ("deck contains N", "N total cards") will miss.
3. **P fallback to `rule_2` (`forward_reference` as winner) was not
   exercised.** Q4 contains no natural `forward_reference` chunk;
   fabrication was declined. Only `rule_1` (Stage 1, Stage 3A) and `rule_3`
   (Stage 3B2) have run.
4. **Pilot has not run the K = 0 case.** *This limit is categorically
   distinct from limits 1–3.*

   Limits 1–3 are coverage gaps within the regime of "pilot answered" —
   we want more cases of correct/incorrect *answers*. Limit 4 asks
   whether the system *refuses* when it should. K = 0 tests the
   refuse-gate, which is the entire point of the honesty work in v3.20.
   If a future pilot iteration runs K = 0 and the loop confidently
   produces any answer, that does not "expand coverage" — it
   **regresses an already-achieved property** of the system.

   Treat limit 4 as high-priority. Limits 1–3 are nice-to-have.

---

## What this pilot did **not** show

To be cited honestly later. Result 3 is a problem statement, not a
solution direction.

- 3B2 does **not** show that `extract_claim` must be intent-aware.
  That is one hypothesis.
- 3B2 does **not** show that P must become a function with fallback
  rather than an ordered list. That is one hypothesis.
- 3B2 does **not** show that a secondary tie-break rule (scope match,
  specificity, doctest > class-body) belongs *inside* P. That is one
  hypothesis.
- 3B2 does **not** identify *where* the fix lives — P, the extractor,
  retrieve scoring, or a new component none of the above describes.

The next session must begin with formulation of **at least three
alternatives** for intra-bucket disambiguation before choosing one.
Citing this pilot as "P needs a fallback function" or "extractor must
be intent-aware" is over-reading.

---

## Discipline note

This pilot is shadow exploration. The retrieval audit (Pack v0.2.1 §2)
remains the gating deliverable. ThoughtState is **not** on mainline.

The decision about intra-bucket tie-breaking is deferred to a separate
session that explicitly enumerates alternatives. Per discipline applied
elsewhere in the project (audit fields evolved manual → auto-suggested
→ human-vetted → telemetry → limited influence), no architectural
decision is taken in the same session in which the problem was
discovered.

This report does not request follow-up. It records a closed milestone.

---

## File map

```
q9_pilot/
├── state.py              7-slot ThoughtState dataclass
├── corpus.py             Q9_CHUNKS (stub) + Q4_CHUNKS (real)
├── claims.py             Q9 detectors: _author_anchor, _forward_reference, _code_literal
├── claims_extended.py    Q4 detectors: _doctest_output, _author_count_phrase
├── pilot.py              parametrised run_primary / run_alternative + Q9 wrappers
├── test_q9.py            8 cases (Stage 1)
├── test_q4_unextended.py 6 cases (Stage 2)
└── test_q4_extended.py   14 cases (Stage 3 — 3A: 5, 3B1: 5, 3B2: 4)
```

`experiments/thoughtstate_pilot_001/` (this directory) — report only,
no code. Code lives in `q9_pilot/` for historical reasons (created
before this report's directory existed). Future shadow pilots should
co-locate code and report under `experiments/<name>/`.
