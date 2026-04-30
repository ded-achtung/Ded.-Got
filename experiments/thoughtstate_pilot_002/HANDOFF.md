# ThoughtState Pilot 002 — Handoff (K=0 / refuse-gate)

**Status:** pre-registered, not yet executed. Shadow exploration. **Not** a
Pack v0.2.1 deliverable. Does **not** influence the retrieval audit gate.
ThoughtState remains off-mainline per Pack v0.2.1 §2.

**Successor to:** Pilot 001 (`experiments/thoughtstate_pilot_001/REPORT.md`,
closed milestone). This pilot addresses **Limit 4** from that report —
flagged as categorically distinct from limits 1–3 because it tests whether
the system *refuses* when it should, not whether it *answers*.

---

## Why this pilot is high-priority

Quoting Pilot 001 REPORT.md, Limit 4:

> Limits 1–3 are coverage gaps within the regime of "pilot answered". Limit 4
> asks whether the system *refuses* when it should. K = 0 tests the
> refuse-gate, which is the entire point of the honesty work in v3.20. If a
> future pilot iteration runs K = 0 and the loop confidently produces any
> answer, that does not "expand coverage" — it **regresses an
> already-achieved property** of the system.

Until run, it is unknown whether the current `q9_pilot/pilot.py` upholds
the refuse-gate at K = 0 or silently regresses it. The pilot must witness
one branch of this on running code.

---

## Scope: which K = 0

"K = 0" can mean three things. This pilot covers exactly one.

| Variant | Definition | In scope? | Reason |
| --- | --- | --- | --- |
| (a) | retrieve returns chunks; `extract_claim` returns no claims for any of them | **YES** | witnessed in v3.x audit (Q22 marked `not_in_corpus`); directly testable on current pilot without dependencies |
| (b) | retrieve returns chunks with claims; all are filtered out by target-type / Ex-shape mismatch | NO | requires Hole 1 (typed Ex / typed claims) to be implemented; not yet exists |
| (c) | retrieve returns no chunks at all | NO | not witnessed in current corpus; hypothetical |

---

## Scenario

**Question:** Q22 from the test-retest archive. Reported subject:
*"когда Python 2 объявлен deprecated"* (or whatever the exact phrasing is
in the test-retest pack — next session must verify against source).

**Why Q22 over a synthetic alternative:**
- Q22 is a real failure mode of the project, marked `not_in_corpus` in the
  v3.x audit. Pilot 002 reproduces an already-observed phenomenon, not an
  artificial one.
- A synthetic alternative ("когда был выпущен Python 4" + ch.1-2 chunks)
  is cleaner (guaranteed K = 0 by construction) but tests a stipulated
  scenario, not an empirical one. **Use synthetic only as fallback** if
  Q22 corpus extraction is blocked.

**Corpus:** real chunks that retrieval surfaced for Q22 in v3.x. Source
file: `retrieval_results.jsonl` from the test-retest pack (the same
archive that supplied c003/c004/c033 to Pilot 001). **This file is not
in the repository**; the next session must source it before running.

**Extractors:** `extract_claims` from `q9_pilot/claims.py`, **unmodified**.
The point of the pilot is to test the *current* pilot under K = 0, not a
hardened version. If `extract_claims_extended` has different behaviour at
K = 0, that is a follow-on question, not this pilot's question.

---

## Pre-registered hypotheses

**H_safe** — the refuse-gate holds.

> At K = 0 after retrieve + extract, the pipeline halts with an explicit
> "don't know" outcome. No `final_answer` value is committed. No tension
> resolves spuriously. The goal is not marked solved.

**H_regression** — the refuse-gate fails. Possible failure modes:

- `verify_form` (or any downstream step) crashes on empty K with an
  unhandled exception.
- `narrow_hypothesis` is invoked on empty H and returns something
  arbitrary (first element of `[]`, `None`, or raises).
- The pipeline runs to completion with an empty answer, which is
  interpreted by the caller as a valid result.
- The loop enters retry / `retrieve_more` cycles without bound.

---

## Hold / break / grey criteria

Verbatim from the design discussion that authored this handoff.

### Hold (concept holds at K = 0)

- After retrieve + extract, the pipeline stops.
- `state.E` is `unknown` or `underdetermined`, **not** `supported`.
- `state.G[0].status` is `unsolved`, **not** `solved`.
- No `final_answer` value is returned (None, or an explicit "I don't know"
  sentinel).
- If a tension of type `evidence_gap` (or equivalent) is exposed, it
  remains HIGH and is not silently dismissed.

### Break (regression of v3.20 honesty)

- Pilot crashes with an unhandled exception triggered by the empty-K path.
- `state.G[0].status = solved` with an empty or junk answer.
- Any code path activates on empty data and returns a confident result.
- Pipeline loops without termination.

### Grey

- Pipeline returns an explicit "don't know" outcome **but through a path
  that was not designed for refuse-gate behaviour**. For example,
  `verify_form` returns False for technical reasons (empty input → None
  comparison fails → False) rather than through a deliberate "K is empty,
  therefore I cannot answer" branch.

  A grey result is reported as **partially holding** — the system did not
  silently lie, but the safety came from accidental code geometry, not
  from a designed gate. This is documented as a *fragile pass*: it
  could regress under any refactor that changes the accidental path.

---

## What this pilot does **not** decide

This pilot produces one empirical signal about Hole 4. It does **not**:

- Decide the right architecture for the refuse-gate (explicit slot in
  `state`? Tension type? `verify_form` extension? Pre-step assertion?).
- Decide whether `evidence_gap` should be exposed as a first-class
  tension or kept implicit.
- Touch the Hole 1 fix (typed Ex / typed claims). H4 and H1 are
  independent: Pilot 002 runs against the *current* `q9_pilot/`, not a
  hypothetical post-H1 version.
- Touch Hole 2 (extractor domain-specificity) or Hole 3 (within-type
  P unresolved).

If the pilot results in `H_regression`, the architectural response is
deferred to a separate session per project discipline ("no architectural
decision in the same session as problem discovery").

---

## Handoff requirements (next session)

What the executing session must produce, in order:

1. **Source Q22.** Locate Q22 in the test-retest corpus and extract:
   - exact question text
   - retrieved chunks that v3.x surfaced for Q22 (from
     `retrieval_results.jsonl` or equivalent)
   - audit annotation confirming `not_in_corpus` status
2. **Set up corpus.** Add `Q22_CHUNKS` to `q9_pilot/corpus.py` (or, if
   pilot 002 spawns a sibling directory like `q22_pilot/`, mirror the
   structure of `q9_pilot/`).
3. **Run unmodified `pilot.run_primary`** with Q22 question, Q22 query
   (derived from question), Q22_CHUNKS, and the existing `extract_claims`
   from `q9_pilot/claims.py`. **No modifications** to `pilot.py` or
   `claims.py` before the first run.
4. **Capture trace.** Whatever the pipeline does, log the full
   `state.trace`, `state.K`, `state.H`, `state.E`, `state.G[0].status`,
   and `winner`. If the pipeline crashes, capture the stack trace and
   the partial state at crash time.
5. **Classify outcome.** Map the captured behaviour to H_safe, H_regression,
   or grey using the criteria above. If grey, identify the accidental
   path that produced the safe result.
6. **Write `experiments/thoughtstate_pilot_002/REPORT.md`.** Same format
   as Pilot 001's REPORT.md. Sections: status header, scope, scenario,
   pre-registered hypothesis vs observed outcome, what the pilot did
   *not* show, discipline note, provenance.
7. **Document any defensive guards needed.** If the executing session
   feels compelled to add `if not state.K: return None` or similar
   guards to make the pilot run, that is itself the test result —
   document the line numbers where guards were needed and the reason.
   Do **not** harden the pipeline as part of pilot 002. Hardening is the
   architectural decision deferred to a later session.

---

## What is **not** required

- No new extractors. No new tension types. No `claims_extended`-style
  expansion.
- No fix to Hole 1, 2, or 3.
- No decision about where the refuse-gate should live structurally.
- No tests beyond what is needed to capture the K = 0 behaviour.

---

## Discipline

Pilot 002 is shadow exploration. Pack v0.2.1 §2 status preserved:
ThoughtState off-mainline, retrieval audit gate untouched.

This handoff records the pre-registration. The executing session
produces the empirical result. Whatever the result, the architectural
response is a **separate session** that explicitly enumerates
alternatives (per the "minimum three alternatives" discipline applied
to the Hole 3 / intra-bucket tie-breaker question in Pilot 001 closure).

This document does not request execution today. It records what the
next pilot session needs to do.

---

## Provenance

- Authored: handoff session following the Hole 1 deep-dive that
  prioritised Hole 4 as next subject.
- Pilot 001 lineage: `a29d539` → `07be2a3` → `5c2972c` → squash
  `2f0aaa1` (merged on `main`).
- Pilot 002 location: `experiments/thoughtstate_pilot_002/`. This
  handoff (`HANDOFF.md`) is the only artefact that exists today;
  `REPORT.md` will be added when the executing session runs.
- Branch: `claude/pilot-002-handoff-K-zero` (handoff only, no code
  changes). Handoff PR is independent of pilot execution PR.
