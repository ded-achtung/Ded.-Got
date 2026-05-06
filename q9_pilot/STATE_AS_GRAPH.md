# STATE_AS_GRAPH.md

A narrow revision to the state model in THINKING_CORE, derived from
four `thought_spike.py` runs (Q22, Q7, Q1, Q2). Not a replacement, not
a new formalism, not THINKING_FORMULAS_v3. One thing only: how the
concept of state should look so that the four §2 findings in
`SPIKE_FINDINGS.md` (pattern_class, constituency-vs-redundancy,
T-resolution via back-reference, convergence-as-state-property) are
there by construction, not as patches discovered after running.

Vocabulary stays the same as in the spike code: pattern_class,
redundancy, constituency, un_disambiguating, supports_H, weakens_H,
H-set. No new abstractions.

## 1. The setup

THINKING_CORE described state as six slots: G, Ex, K, H, T, E. The
slots survive. What changes is the description of **what lives inside
them**. The original framing implied that K is a list of supports,
H is a list of hypotheses, T is a list of tensions — flat collections
in compartments.

The spike doesn't fit that framing. Across four runs the structure
that worked was:

  state is a graph of categorized entries with explicit references
  between them. Slots are compartments; the substantive structure is
  the categorization inside each compartment and the references
  between compartments.

This is not a metaphorical claim. Each of the four spike findings
points at a specific kind of structure that flat slots cannot hold,
and that — when added — produces clean traces.

## 2. K is categorized, with relations inside categories

Every K-entry carries a `pattern_class`. The class isn't a tag for
display; it carries semantics that drive how the entry contributes
to H:

- `is_disambiguating`: does this class differentiate between competing
  H, or sit symmetric across them? Symmetric classes contribute
  nothing directly to H and instead produce un_disambiguating
  T-entries (see §3).
- `support_strength`: the contribution one first-instance entry of
  this class makes when it lands.

Within a category, entries have relations to each other relative to Ex:

- **redundancy**: two entries of the same class encode the same fact
  in different surface forms. Q1's `version_with_min_phrase`
  ("не ниже 3.10") and `versioned_command` (`python3.10`) are
  different classes pointing at the same answer; classes stack
  cleanly. Same-class same-fact (a hypothetical second min-phrase
  in a later chunk) should diminish.
- **constituency**: two entries of the same class encode different
  pieces of one structured answer. Q2's `pip_install pygame` and
  `pip_install PythonTurtle` are pieces of THE pair; both belong to
  the same class but the second is not a repeat. The current spike
  conflates this with redundancy and demoted PythonTurtle to a
  diminishing second-instance — h1 grew by 0.06 instead of 0.40.
  The fix is not "decide whether to apply diminishing" — it's
  representing the relation explicitly.
- **un_disambiguating** appears as a class property (`is_disambiguating
  = False`) at the entry level. It materializes as a T-entry, but
  its origin is in K — the class itself is the symmetric one.
  Q7's `name_in_url` and `anonymous_attribution` are these.

Without categories and within-category relations, K-aggregation
collapses to count. Q7 oscillation showed that count alone produces
nonsense trajectories. Q2 stuck-state showed that diminishing-on-
count (the spike's fix) handles redundancy correctly but mis-handles
constituency. The structural fix is to keep both kinds of relations
explicit, not to choose between them.

## 3. T entries know what produced them

T was originally described as a list of noticed tensions. The spike
shows it must carry more.

Each T-entry holds back-references:
- which `pattern_class` (or class-set) triggered it
- which H-set it concerns
- what condition made it active

This isn't decoration. It's what makes resolution structural rather
than rule-driven. Q1 step 1 produced `un_disambiguating(name_in_url
×  python3_command, [h1, h2])` from a symmetric class, AND in the
same chunk produced `version_with_min_phrase` evidence that
differentiates h1 from h2. Without back-references, retiring the
un_disambiguating tension requires a rule: "when class C₂ arrives,
search T for entries about [h1, h2] and remove if C₂ is
disambiguating". This rule is a compensation for missing structure.

With back-references, the resolution is a property: a T-entry is
active only as long as the conditions in its back-reference still
hold. When a disambiguating class arrives for the same H-set the
un_disambiguating entry was tagged on, its triggering condition no
longer holds, and the entry retires. No special rule.

The same applies to other T kinds. A `gap` tension knows which Ex
clause is unsatisfied; it retires when the clause is satisfied. A
`drift` tension knows which observation window produced it; it
retires when the window changes. The pattern is uniform: T is not an
accumulator of facts, T is a set of conditional indicators each tied
to a specific claim about K, H, or Ex.

## 4. Convergence is a property of the whole graph

The original convergence check sat in `recompute_tensions` as a
threshold on one hypothesis's weight. Five spike runs survived
calling this a "tuning concern" — the threshold was no_answer-
specific, but Q22 and Q7 both ended in no_answer dominance, so the
specificity didn't surface. Q1 made it visible: a candidate-role H
dominant from step 1 with margin 0.45 produced no convergence event.
Q2 confirmed the gap and added a third configuration.

The right framing is not "tune the threshold". It is: convergence is
a property of the whole state asking "no further observation of any
pattern_class is expected to materially change the configuration".
Three configurations of that stability the spike encountered:

- **refuse**: the no_answer-role H accumulated enough support from
  disambiguating absence-class entries; candidate H weakened from the
  same. T contains no actionable tensions (all gaps absorbed by
  no_answer's accumulation). Q22 step 3.
- **hit**: a candidate-role H received differentiating evidence from
  one or more disambiguating classes pointing at it; T's
  un_disambiguating entries (if any) retired by back-reference once
  differentiating classes arrived. Q1 step 1 produced the dominance
  but the spike did not detect it as convergence because it lacked
  the framing.
- **stuck**: candidate-role and no_answer-role H both accumulated
  some support but neither pulled past threshold; T contains
  un_disambiguating entries that have no path to resolution because
  no remaining class could provide the disambiguation. Q2 ended here.

Stuck is meaningful only when K is categorized and T is back-
referenced. Without those two structures, "stuck" is
indistinguishable from "still processing more chunks" — the system
has no way to predicate "no remaining pattern_class could shift the
current H balance". With them, stuck is a specific graph predicate
that can be detected and acted on (the action being acknowledgment of
inability, not refuse and not answer).

A caveat on stuck. Q2's prior stuck reading (h1=0.31, h3=0.40, no
remaining disambiguating class) disappeared once the concept gained
the constituency relation: the same evidence stream now produces
hit. A stuck reading may therefore indicate that the concept is
incomplete relative to the data, not that the data is genuinely
unresolvable. Stuck remains valid only for configurations whose
un_disambiguating tensions have no candidate disambiguating class
in the corpus's full vocabulary; distinguishing those two cases is
an observer's task, not a property the framework decides.

## What this earns

A concept where the four §2 findings are not patches discovered after
running; they are aspects of one structural claim. A future
think_step implementation built on this concept does not need to
discover them. Pattern_class is the entry-level structure;
constituency vs redundancy is the within-category structure;
T back-references are the cross-slot structure; convergence-as-state-
property is what reading the structure globally produces.

## What this is not

This document does not address:
- Two-dimensional H status (movement × leadership). Local labeling
  fix; doesn't need structural revision.
- Halt mechanism for stuck states. Once stuck is detectable as a
  graph predicate, halting is one line.
- The `weakens_H` / no_answer interaction in revise_hypotheses. Local
  rule choice within whatever revise rule the next implementation
  uses.

These three are local fixes that fit inside this concept. They are
not arguments against it.

## Implementation questions outside this revision

This document describes structure and semantics. It does not specify:

- **Pattern_class assignment.** STATE_AS_GRAPH says what state does
  with categorized entries; how the categories are assigned (regex,
  hand-labeled, learned) is a separate question.
- **K and T entry lifecycle.** When entries are immutable, when they
  may be retired, whether prior entries can be recomputed in light
  of later evidence — open at implementation time. Back-references
  and active_condition give the structural hooks; the policy that
  uses them is left to the implementation.
- **Fragment-extraction vs classification.** Fragment-extraction
  (chunk → candidate substrings) is a separate concern from
  classification (substring → pattern_class). Both contribute to
  K-entry creation; their robustness properties are independent.

---

This document is also not THINKING_CORE v2. It is a single revision
to the description of what the slots contain. Everything else in
THINKING_CORE — single-state-with-one-update, read-back inside one
step, rich progress vocabulary, fixed-point in think_step — survives
unchanged and was confirmed across all four runs.
