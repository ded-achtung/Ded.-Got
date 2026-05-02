# Integration Alternatives — q9_pilot Loop Architecture

**Status:** discipline-compliant enumeration, **not a decision**. Per
`experiments/thoughtstate_pilot_001/REPORT.md` discipline note, no
architectural choice is made in the same session that surfaced the
problem.

This document enumerates three alternatives for integrating the
think-loop machinery (probes K/D/G2/L/G5/N/O/V) back into `pilot.py`.
A fourth fallback option ("do nothing") is included as the null
hypothesis. The intent is to give the next session a starting menu.

---

## Empirical context (recap)

What the probes established, on the live audit corpus
(`audits/puzzlebook35/audit_v0.{chunks,questions,manual}.jsonl`):

| Probe | Finding |
|---|---|
| `probe_k0` | Refuse-gate fires on K=0; absent on K=1 (S3, S4 wrong-scope answers) |
| `probe_real_corpus` | English regex × Russian corpus → 0 claims, system refuses correctly |
| `probe_g2_retrievers` | Pilot's keyword overlap is provably weakest; TF-IDF and BM25 indistinguishable |
| `probe_h_ru_extractor` | ~50 lines of RU regex lifts Q14 from K=0 to K=3, value=1 unanimous |
| `probe_l_thinkloop` | Two-iter loop (STANDARD → PERMISSIVE_RE) + noun filter resolves Q5 to value=50 |
| `probe_g5_full_grid` | L without intent gate: 17 ANSWER, 15 false positives ("50 plague") |
| `probe_n_t_decomposition` | T is 6-dim in reality, 1-dim in code (`recompute_tensions` sees only `evidence_gap`) |
| `probe_o_intent_gated` | One-line gate (`intent != how_many → REFUSE`) zeros all 15 G5 false positives |
| `probe_v_health_audit` | Q14 is the only 6/6 health case; gap to 4/6 is two conditions wide; **C2 (multi-source) is corpus-bound, not code-fixable** |

Net: a working integration must answer four questions:

1. **Where does intent routing live?** (G5, O imply intent gate is necessary)
2. **Where does the loop live?** (L, N imply a `while T_unresolved` body)
3. **What is the source of truth for state?** (existing `ThoughtState` vs duplicate)
4. **How do existing 28 tests survive?** (q9_pilot tests assert specific trace lines)

---

## Alternative A1 — Wrapper layer above `pilot.py`

**Shape:** new module `q9_pilot/loop.py` that imports
`pilot.run_primary` and `pilot.retrieve`, wraps them in a tension-
driven outer loop. `pilot.py` is unchanged.

```
                                    +-------------------+
                                    |   loop.py         |
                                    |  (intent gate,    |
   q['intent']  -------->          |   T-decomp,       |  --> verdict
                                    |   while-loop,     |
                                    |   action dispatch)|
                                    +---------+---------+
                                              | calls
                                              v
                                    +-------------------+
                                    |   pilot.py        |  <- untouched
                                    |  run_primary,     |
                                    |  retrieve,        |
                                    |  ThoughtState     |
                                    +-------------------+
```

**What lives where:**
- intent gate, rich T computation, action dispatch, max_iter loop → `loop.py`
- single-pass retrieve+extract+evaluate → `pilot.py` (called from `loop.py`)
- ThoughtState → `pilot.py`, but `loop.py` keeps its own outer-loop counter and tension log

**Pros:**
- Smallest blast radius. The 28 existing tests pass untouched because
  they exercise `run_primary` directly.
- `loop.py` can evolve independently per intent / per corpus.
- Reverse-engineering risk on `pilot.py` semantics is zero.

**Cons:**
- Duplicate state: T is recomputed in `loop.py` from `ThoughtState`
  fields, but `recompute_tensions()` inside `pilot.py` writes its own
  (smaller) T into the same state. Two writers, divergent contents.
- The "real" think-step (multi-action) happens **outside** the
  ThoughtState skeleton that the original report described as the
  whole point. Skeleton becomes a transcript of one inner step, not
  of the loop.
- `loop.py` re-implementing intent routing means PR #4's fitcheck v2
  per-intent rules must be ported again, not reused.

**What this preserves about findings:**
- O (intent gate) → first thing `loop.py` does
- L (re-entry) → outer while
- G5 false-positive elimination → handled before any extractor call
- N (rich T) → computed in `loop.py`, not visible in `ThoughtState`
- V (C2 ceiling) → typed refuse can be emitted directly by `loop.py`

**What this concedes:**
- ThoughtState's `T` slot stays "decorative" (the report's word).

---

## Alternative A2 — Promote loop into `pilot.py`

**Shape:** rewrite `pilot.recompute_tensions()` to compute the 6
tensions from probe N. Add `think_step(state)` that picks an action
from T. Replace `run_primary` body with `while T_has_actionable and
iter < max_iter: think_step(state)`. Intent dispatch happens inside
`extract_into` (or in a new `select_extractor(intent)` helper).

```
                                    +-------------------+
                                    |   pilot.py        |
                                    |  run_primary:     |
   q['intent']  -------->          |    while T-loop   |  --> verdict
                                    |  recompute_tensions: 6 keys
                                    |  think_step:      |
                                    |    action policy  |
                                    |  ThoughtState as  |
                                    |    single source  |
                                    +-------------------+
```

**What lives where:**
- everything in `pilot.py`. ThoughtState carries everything.

**Pros:**
- Single source of truth. ThoughtState really tracks the whole loop.
- The "tension-driven think_step" the original report described
  becomes literally what the code does.
- `claims.py` / `claims_extended.py` get pluggable per intent
  (`select_extractor`); PR #4 fitcheck rules can be lifted directly.

**Cons:**
- 28 existing tests likely break. Many assert trace-line content like
  `"step3: K empty — extractor produced no claims, halting"`. With a
  loop, that line would either not fire or fire with different
  surrounding context. Tests need to be re-pinned.
- High blast radius. `run_primary` signature may need to change to
  take `intent` (currently inferred from question via hardcoded
  `s.intent = "how_many"` at `pilot.py:108`).
- One commit touches semantics of state transitions, refuse-gate,
  extractor selection, and tension reading. Hard to roll back
  partial.

**What this preserves about findings:**
- All eight probes fold cleanly into one place.
- ThoughtState is finally used as the report imagined.
- `experiments/thoughtstate_pilot_001/REPORT.md` Result 3 (intra-
  bucket disambiguation) becomes addressable inside `narrow_hypothesis`.

**What this concedes:**
- Test re-pinning will require deciding which trace lines are part of
  the contract and which are incidental. That itself is an unresolved
  question.

---

## Alternative A3 — Strategy / Action pattern

**Shape:** define an `Action` interface with two methods —
`should_fire(state) -> bool`, `apply(state) -> ThoughtState`. Each
capability becomes an action: `BroadenRetrieve`, `SwitchExtractor`,
`SeekCorroboration`, `RefuseTyped`, `IntentGate`, etc. `run_primary`
becomes a thin dispatcher that picks the highest-priority firing
action until none fire.

```
                                    +-------------------+
                                    |   pilot.py        |
                                    |  run_primary:     |
   q['intent']  -------->          |   while any.fires:|  --> verdict
                                    |     pick & apply  |
                                    +---------+---------+
                                              | composes
                                              v
                                    +-------------------+
                                    |   actions/        |
                                    |   IntentGate.py   |
                                    |   StandardExtract |
                                    |   PermissiveExtract
                                    |   NounFilter      |
                                    |   Corroborate     |
                                    |   RefuseTyped     |
                                    +-------------------+
```

**What lives where:**
- Tiny dispatcher in `pilot.py`. Every capability in its own file
  under `actions/`.
- ThoughtState passed to each action; actions mutate it.
- Intents register their action chains via a registry: `INTENT_CHAINS
  = {"how_many": [IntentGate, StandardExtract, PermissiveExtract,
  NounFilter, Corroborate], "when": [..]}`.

**Pros:**
- Extensible. Adding a new intent = define its action chain in the
  registry. Adding a new failure mode = new action class.
- Each action testable in isolation. Per-action tests stay stable
  even when chain composition changes.
- Maps naturally to PR #4 fitcheck v2 per-intent rule structure.

**Cons:**
- Heavy infrastructure for the current scale (35 questions, 1 working
  intent, 6 probes). Risk of over-engineering before learning what
  the action vocabulary actually needs to be.
- Existing 28 tests break harder than in A2; signatures change, trace
  semantics change.
- Action ordering / priority becomes a separate hidden contract that
  needs documenting and testing.

**What this preserves about findings:**
- Maximum future flexibility. Any capability surfaced by a future
  probe can land as a new action without restructuring.
- N's six tensions naturally map to six should_fire predicates.

**What this concedes:**
- Early commitment to abstraction shape before the corpus has
  exercised more than one intent-with-extractor (`how_many`).

---

## Alternative A4 — Status quo (do nothing)

Included only because the report's discipline note explicitly
requires considering null option.

**Shape:** keep `pilot.py` exactly as-is. Probes stay in `q9_pilot/probe_*.py`
as a testbed but never integrate. Q9/Q4 synthetic tests keep passing.
Audit gate (PR #4) proceeds to completion independently.

**Pros:**
- Honors the original discipline note ("ThoughtState remains off-mainline
  per Pack v0.2.1 §2"). No architectural commitment in a session that
  found problems.
- Audit gate doesn't get blocked on q9_pilot integration.
- All probe findings remain available as inputs for whichever future
  session does this work.

**Cons:**
- The Russian-extractor capability (probe H), the intent gate (O), and
  the multi-tension diagnostic (N) stay as scratch. None of them
  exercise on real questions in production.
- Anyone reading the codebase later sees `pilot.py` (synthetic stubs,
  English regex, single-pass) as the system, with the probes as
  detached commentary. The empirical learning isn't compounded.

**What this preserves:**
- Optionality. All three alternatives above remain on the table.

**What this concedes:**
- Time. Each future session re-discovers G5 / N / V before being
  able to act.

---

## Comparison axes

| Axis | A1 wrapper | A2 promote | A3 strategy | A4 status quo |
|---|---|---|---|---|
| Test breakage (28 q9_pilot tests) | none | high | very high | none |
| Code duplication w/ pilot.py | high | none | medium | n/a |
| ThoughtState used as designed | no | yes | yes | partly |
| PR #4 fitcheck reuse path | re-port | direct | direct | n/a |
| Single source of truth | no | yes | yes | n/a |
| Future intent expansion cost | medium | medium | low | n/a |
| Risk of over-engineering | low | medium | high | none |
| Empirical findings landed in production | yes | yes | yes | no |

## Open questions (must be answered before picking)

1. **Are q9_pilot test trace lines part of the contract?** A2 / A3
   require re-pinning them; A1 does not. The original report did not
   declare which trace strings are stable.
2. **Should `pilot.py` know about intents at all, or stay
   intent-agnostic?** A2 / A3 say yes; A1 hides intent in the wrapper.
3. **Does PR #4 fitcheck v2 belong inside the loop, before it (as a
   filter on retrieve top-K), or after it (as a verifier on the
   answer)?** None of A1/A2/A3 commits to this; all three need a
   separate decision.
4. **What is the budget for `max_iter`?** Probe L used 2 iterations
   and that sufficed for both how_many questions. No probe stress-tested
   beyond 2.
5. **Where does `low_corroboration` confidence marking live (V)?** This
   is orthogonal to A1/A2/A3 — each can carry it differently.

## Discipline note

This document **does not** pick A1, A2, A3, or A4. It does not even
rank them. The empirical comparison axes above are the input to a
later decision; the decision itself requires:

- a session that explicitly opens with these alternatives as the
  agenda;
- answers to the five open questions above (especially #1 — test
  contract — which is the single biggest unknown);
- a writeup of the decision with the same level of empirical
  grounding the probes carry, so future sessions can audit the
  reasoning.

Per the original report:

> "Citing this pilot as 'P needs a fallback function' or 'extractor
> must be intent-aware' is over-reading."

The same caution applies to citing this document as endorsement of
any specific alternative.
