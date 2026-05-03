# SPIKE_FINDINGS.md

Empirical report from three runs of `thought_spike.py` against the
puzzlebook35 audit corpus. Hand-fed chunks, no retrieve, no benchmark.

Runs:
- **Q22** (when, no_answer): converges step 3, h4=0.55
- **Q7** (who, ambiguous): converges step 4, h3=0.55, h1 monotonic 0.40→0.25
- **Q1** (what, Q-known-hit): step 1 h1=0.65 from corroborated classes;
  no convergence event for candidate leader

Structure (G, Ex, H, K, T, E, history) held across all three without
slot additions. `_base`, `_role`, `_step_initial` added as fields on
existing H entries.

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

- **`pattern_class` is a necessary mediator between K and H.**
  Concept had K and H as adjacent layers. Aggregating K into H by raw
  count produces oscillation (Q7 h1 bouncing 0.40→0.50→0.45→0.55→0.50).
  Aggregating by pattern_class with diminishing-per-class fixes
  oscillation **and** yields earlier, cleaner convergence (Q7 moved
  from step 5 to step 4). Three categories matter: disambiguating-
  strong, disambiguating-weak, non-disambiguating (the last
  contributes 0 to H, emits T tension instead).

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

- **T-resolution requires explicit T ↔ pattern_class linkage.**
  Q1 step 1 contains both `python3_command` (symmetric, supports h1
  and h2) and `version_with_min_phrase` (differentiates, supports h1).
  The un_disambiguating tension from the symmetric class persists to
  the end of the run, even though the differentiating class arrived
  in the same chunk. T accumulates ambiguity but has no mechanism to
  retire it through structural reasoning.

## 3. Open

- Convergence semantics for candidate-leader. Q1 is one data point;
  needs another hit-class question to confirm pattern.
- Resolution rule for un_disambiguating when differentiating evidence
  arrives in a different class for the same H-set. One Q1 datum.
- Whether the four §2 findings are uniform across intents or some are
  intent-conditional. Three runs is not enough to tell.

## 4. Q-specific, localized

- `leader_id == 'h4'` hardcode in `reevaluate_existing_K`. Q22-ism;
  silent bug on Q7 (K_relabelled=0 despite convergence). Fixed via
  `_role=='no_answer'` check.
- Convergence threshold (`no_answer ≥ 0.55`, margin ≥ 0.15). Tuned to
  absence-dynamics on Q22; happens to work on Q7. Not stress-tested
  on different scales.
- Convergence semantics (no_answer-specific). Surfaced only on Q1.
  Recorded in §3 as open, **not** fixed in the spike.

---

Three runs, three different question classes. Two §2 findings
(pattern_class as a layer, role-conditional convergence) are
candidates for revising the conceptual ThoughtState — that revision
belongs in a separate session, not in spike polishing.

Stop here. The next conversation is "where does ThoughtState go from
here", not "what to dig in the spike next".
