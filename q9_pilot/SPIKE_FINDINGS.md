# SPIKE_FINDINGS.md

Empirical report from four runs of `thought_spike.py` against the
puzzlebook35 audit corpus. Hand-fed chunks, no retrieve, no benchmark.

Runs:
- **Q22** (when, no_answer): converges step 3, h4=0.55
- **Q7** (who, ambiguous): converges step 4, h3=0.55, h1 monotonic 0.40→0.25
- **Q1** (what, Q-known-hit, single answer): step 1 h1=0.65 from
  corroborated classes; no convergence event for candidate leader
- **Q2** (what, Q-known-hit, plural answer): step 1 h1=0.41 only
  (diminishing on same-class pieces); ends stuck — no convergence
  in either direction

Structure (G, Ex, H, K, T, E, history) held across all four without
slot additions. `_base`, `_role`, `_step_initial` added as fields on
existing H entries; `extractor_pack` added to G for sub-dispatch
within shared intent.

## 1. Confirmed from THINKING_CORE

- **Single-state-with-one-update.** `think_step` stayed atomic across
  all three runs. Nothing wanted to decompose into pipeline stages.
- **Read-back inside one step is necessary and sufficient for
  thought-shaped traces.** Q22 step 3 — convergence triggers, prior K
  relabel, H statuses flip, all in one `think_step` — is the canonical
  case.
- **Rich progress vocabulary earns its place.** `noticing` (Q7 step 1,
  ambiguity recorded without moving H) and `minor` (Q1 step 2, repeat
  observation acknowledged as repeat) are the markers that distinguish
  thought from log entry.

## 2. Not in the concept; emerged from running

Each is structural — would not surface from a design review.

**Status (after commit 14a90f6, STATE_AS_GRAPH implementation):**
all four findings below are incorporated into STATE_AS_GRAPH §2-§4
as structural properties. Each entry remains as the empirical
observation that produced it; the structural account lives in
STATE_AS_GRAPH.

- **`pattern_class` is a necessary mediator between K and H.**
  Concept had K and H as adjacent layers. Aggregating K into H by raw
  count produces oscillation (Q7 h1 bouncing 0.40→0.50→0.45→0.55→0.50).
  Aggregating by pattern_class with diminishing-per-class fixes
  oscillation **and** yields earlier, cleaner convergence (Q7 moved
  from step 5 to step 4). Three categories matter: disambiguating-
  strong, disambiguating-weak, non-disambiguating (the last
  contributes 0 to H, emits T tension instead).
  **Confirmed on Q2.** New pattern_classes (`pip_install_with_module`,
  `pip_mention_no_modules`) added to the enum as flat extensions; no
  structural change in revise/recompute. Layer is sound.

- **Same-class repetition has two semantic modes that the spike
  conflates** (NEW, found on Q2). Q1 step 1 had two same-fact-twice
  evidences in *different* classes (version_with_min + versioned_
  command both encoding 3.10) — different classes stack at full
  strength, h1: 0.30→0.65. Q2 step 1 had two same-class entries
  (`pip install pygame` + `pip install PythonTurtle`) — diminishing
  treated the second piece as a repeat, h1: 0.35→0.41. But the
  pieces are the **constituents** of THE answer (the pair), not a
  redundant restatement. Diminishing-per-class collapses redundancy
  and constituency into one rule; for plural-answer questions it
  demotes parts of the answer.

- **H status is two-dimensional.** Q1 final: `h1 = 0.55 weakening /
  leading`. Movement (delta vs step_initial) and position (rank among
  H, margin to runner-up) are orthogonal axes. The current single-
  axis status collapses them and produces nonsense labels like
  "weakening but leading".

- **Convergence is role-conditional, not universal.** Q22-ism
  "converged ⟺ refuse" survived five runs because the no_answer
  hypothesis was always the one to hit threshold. Q1 made the gap
  visible: h1 (candidate role) dominates from step 1, no convergence
  event ever fires because `recompute_tensions` checks only
  `_role=='no_answer'`. Three semantic kinds — convergence-for-refuse,
  convergence-for-hit, convergence-stuck-ambiguous — were collapsed
  into one threshold rule.
  **Confirmed on Q2.** Same gap, different shape: Q2 ends in a stuck
  state (h3=0.40 vs h1=0.31, neither passes its own threshold),
  next_action returns `address_tension(drift)` with no path
  forward. Two datapoints; pattern is real.

- **T-resolution requires explicit T ↔ pattern_class linkage.**
  Q1 step 1 contains both `python3_command` (symmetric, supports h1
  and h2) and `version_with_min_phrase` (differentiates, supports h1).
  The un_disambiguating tension from the symmetric class persists to
  the end of the run, even though the differentiating class arrived
  in the same chunk. T accumulates ambiguity but has no mechanism to
  retire it through structural reasoning.

## 3. Open (status after STATE_AS_GRAPH implementation)

- **Convergence semantics for candidate-leader** — **CLOSED**.
  Confirmed on n=4 (Q22, Q7 refuse; Q1, Q2 hit). Further runs would
  expand coverage to new configurations, not confirm the gap.
  Incorporated as `compute_state_predicate` in STATE_AS_GRAPH §4.

- **Resolution rule for un_disambiguating when differentiating
  evidence arrives in a different class for the same H-set** —
  **CLOSED**. Resolution is now a structural property of T-entries'
  back-references, not a separate rule. Two visible patterns from
  the same property:
  - Synchronous (Q1 step 1): differentiating evidence arrives in
    the same think_step as the symmetric class. The
    un_disambiguating entry is never emitted because its
    active_condition is False from the start (a disambiguating
    K-entry with supports_H ⊊ H-set already exists).
  - Asynchronous (Q7 step 1 → step 2): the entry is emitted at
    step 1 because no disambiguating evidence yet exists, then is
    not re-emitted at step 2 once publisher_org arrives with
    supports_H=[h3] strict subset of [h1, h3]. Trace shows
    explicit `T_RETIRED`.
  Same back-reference mechanism, two manifestations.

- **Diminishing-per-class for "constituency" cases** — **CLOSED**.
  Incorporated as `constituent_of` relation on KEntry in
  STATE_AS_GRAPH §2. Q2 step 1 went from h1=+0.06 to h1=+0.40 once
  pygame and PythonTurtle carry the same constituent_of label.
  Whether constituency arises automatically from chunk co-location
  or requires explicit marking is an implementation question, not
  a structural one.

- **Halt condition / "give up after N steps" mechanism** — **subsumed
  by `compute_state_predicate`**. The `stuck` predicate is the
  honest equivalent of "give up": no remaining pattern_class can
  resolve active un_disambiguating, so further observation is not
  expected to change the configuration. No separate halt machinery
  needed.

- **Uniformity of §2 findings across intents** — **CLOSED on n=4**.
  pattern_class layer, role-conditional convergence, T
  back-references, constituency relation all hold uniformly across
  {when, who, what-single, what-plural}. Further runs would test
  scaling, not uniformity.

## 4. Q-specific, localized

- `leader_id == 'h4'` hardcode in `reevaluate_existing_K`. Q22-ism;
  silent bug on Q7 (K_relabelled=0 despite convergence). Fixed via
  `_role=='no_answer'` check.
- Convergence threshold (`no_answer ≥ 0.55`, margin ≥ 0.15). Tuned to
  absence-dynamics on Q22; happens to work on Q7. Not stress-tested
  on different scales.
- Convergence semantics (no_answer-specific). Surfaced on Q1, confirmed
  on Q2. Recorded in §3 as open, **not** fixed in the spike.
- `weakens_H` doesn't apply to `_role=='no_answer'` in revise (only
  `opposes_H` via oppose_pull does). Q2's `pip_mention_no_modules`
  class set `weakens_H=[h3]` expecting weak push-down on h3, but
  h3 didn't move. Local rule choice, not architectural.

## 5. What changed after STATE_AS_GRAPH implementation

Commit 14a90f6 reimplemented `thought_spike.py` so the four §2
findings live as structural properties (typed PatternClass, KEntry
with explicit relations, TEntry with back-references and
active_condition, compute_state_predicate replacing convergence as
T-entry). Prior-run arcs preserved: Q22 and Q7 produce identical H
trajectories step-by-step; Q1 step 1 produces h1=0.65 from the same
stack of disambiguating classes. Q2 step 1 changed from h1=0.41
(stuck final) to h1=0.75 (hit at step 1) because pygame and
PythonTurtle now carry constituent_of='pip_setup_pair' and revise
gives both full per-piece contribution. Q1 step 1 produces no
un_disambiguating T-entry at all — the active_condition is False
from the start because version_with_min_phrase arrives in the same
chunk as python3_command. compute_state_predicate detects 'hit' on
Q1 and Q2 from step 1 onwards; next_action returns
`answer(hypothesis=h1, …)`. Same-arc preservation on Q22/Q7/Q1 was
the success criterion for the structural transition; Q2 stuck →
hit was the new behavior earned by §2's constituency finding.

## 6. K-entry creation has two layers, robustness is layer-specific

K-entry creation decomposes into two layers: fragment-extraction
(chunk → candidate substrings) and classification (substring →
pattern_class). Robustness is layer-specific. Q1 paraphrase test
(commit `f4aef74`) confirmed examples-based classification on
paraphrase «требуется Python от 3.10» — score 0.515, 5× threshold —
but regex fragment-extraction missed entirely, and the missing
fragment changed Q1 final predicate from hit to refuse. The two
layers fail differently: regex fragment-finders are brittle to
paraphrase by construction (they encode specific surface patterns);
the examples-based classifier was robust to this paraphrase given
the fragment. Commit (this one) widens the version-mention regex to
"Python ... <version>" within 40 chars; classification continues to
handle filtering. Recorded as a structural observation, not an
intervention plan.

---

Four runs, four different question classes (no_answer, ambiguous,
single-hit, plural-hit). Two §2 findings now confirmed on a second
hit-case (pattern_class layer, role-conditional convergence). One
new §2 finding (constituency vs redundancy in same-class repetition)
surfaced specifically because Q2's plural answer exercised what
single-answer questions could not.

Stop here. The next conversation is "where does ThoughtState go from
here", not "what to dig in the spike next".
