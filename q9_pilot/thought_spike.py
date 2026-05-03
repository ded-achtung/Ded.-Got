"""thought_spike.py — single-file ThoughtState skeleton.

Spike, not integration. One question (Q22 — book publication date),
no retrieve, no corpus loading, no benchmark. Chunks are hand-fed
fixtures copied from audits/puzzlebook35/audit_v0.chunks.jsonl,
matching the retrieved_topk_chunk_ids that the live retriever
produced for Q22 per audit_v0.manual.jsonl.

Goal: feel one act of thinking through the structure. After running,
inspect state.history and ask: am I seeing a sequence of thought, or
a log of dict updates?

Run: python thought_spike.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------- ThoughtState ----------------

@dataclass
class ThoughtState:
    G: dict = field(default_factory=dict)        # what we understood
    Ex: dict = field(default_factory=dict)       # evidence contract
    H: list = field(default_factory=list)        # competing readings
    K: list = field(default_factory=list)        # accumulated evidence
    T: list = field(default_factory=list)        # tensions noticed
    E: dict = field(default_factory=dict)        # last-step self-eval
    history: list = field(default_factory=list)  # move tape


# ---------------- regexes used during update ----------------

YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
PYTHON_VERSION_RE = re.compile(
    r"\bPython[\s\-]?(\d+(?:\.\d+)+)\b", re.IGNORECASE
)
ISBN_RE = re.compile(r"\b97[89][\-\d]{10,}\b")
PATH_DIGIT_RE = re.compile(r"/\d+(?:/|\b)")

# who-intent regexes
URL_RE = re.compile(
    r"(?:https?://[^\s`]+|github\.com[^\s`]+|[a-z]+\.com[^\s`/]*)",
    re.IGNORECASE,
)
LATIN_CAMEL_RE = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b")
NAME_CYR_RE = re.compile(
    r"\b[А-ЯЁ][а-яё]{2,}(?:\s+[А-ЯЁ][а-яё]{2,})?\b"
)
ORG_CYR_RE = re.compile(r"\b[А-Я]{2,5}\s+[А-ЯЁ][а-яё]+\b")
AUTHOR_KW_RE = re.compile(
    r"\b(?:автор|написал[аи]?|составил[аи]?|написавш\w+|составивш\w+)\b",
    re.IGNORECASE,
)


# ---------------- update_knowledge (dispatch on intent) ----------------

def update_knowledge(state: "ThoughtState", obs: dict) -> list:
    """Dispatch by G.intent. Each intent has its own pattern set, but
    they all produce the same verdict vocabulary so revise_hypotheses
    and recompute_tensions stay generic."""
    intent = state.G.get("intent")
    if intent == "when":
        return _update_when(state, obs)
    if intent == "who":
        return _update_who(state, obs)
    return state.K + [{
        "from": obs.get("id", "?"),
        "finding": f"no extractor for intent={intent}",
        "evidence_verdict": "absent_extending_gap",
        "links_to_Ex": False,
        "supports_H": [_no_answer_id(state.H)] if _no_answer_id(state.H) else [],
        "weakens_H": _candidate_ids(state.H),
        "opposes_H": [],
    }]


def _no_answer_id(H: list) -> str | None:
    return next((h["id"] for h in H if h.get("_role") == "no_answer"), None)


def _candidate_ids(H: list) -> list:
    return [h["id"] for h in H if h.get("_role") != "no_answer"]


def _update_when(state: "ThoughtState", obs: dict) -> list:
    """Q22-class extractor: years, Python versions, URL paths."""
    text = obs.get("text", "")
    cid = obs.get("id", "?")
    H = state.H
    leader = max(H, key=lambda h: h["weight"]) if H else None
    leader_id = leader["id"] if leader else None
    convergence_active = any(t["kind"] == "convergence" for t in state.T)
    no_answer = _no_answer_id(H)
    candidate_hyps = _candidate_ids(H)

    new = []
    years = YEAR_RE.findall(text)
    py_versions = PYTHON_VERSION_RE.findall(text)
    py_version_digits = {tok for v in py_versions for tok in v.split(".")}

    if years:
        for y_str in years:
            y = int(y_str)
            in_py_version = y_str in py_version_digits or any(
                pv in text for pv in (f"Python {y_str}", f"Python-{y_str}")
            )
            if in_py_version:
                new.append({
                    "from": cid,
                    "verbatim": y_str,
                    "finding": (f"date-shaped token '{y_str}' inside Python "
                                f"version — would have supported "
                                f"{candidate_hyps} if real, type-rejected"),
                    "evidence_verdict": "rejected_type_mismatch",
                    "links_to_Ex": False,
                    "supports_H": [no_answer] if no_answer else [],
                    "weakens_H": [],
                    "opposes_H": [],
                })
            else:
                new.append({
                    "from": cid,
                    "verbatim": y_str,
                    "finding": f"raw year '{y}' in prose context — candidate",
                    "value": y,
                    "evidence_verdict": "candidate",
                    "links_to_Ex": True,
                    "supports_H": candidate_hyps,
                    "weakens_H": [no_answer] if no_answer else [],
                    "opposes_H": [no_answer] if no_answer else [],
                })
    elif py_versions or PATH_DIGIT_RE.search(text):
        marker = (f"Python version {py_versions[0]}" if py_versions
                   else "URL path digits")
        new.append({
            "from": cid,
            "finding": (f"numeric markers ({marker}) but type-incompatible "
                        f"with Ex.type=date — these are decoys for "
                        f"{candidate_hyps}"),
            "evidence_verdict": "off_topic",
            "links_to_Ex": False,
            "supports_H": [no_answer] if no_answer else [],
            "weakens_H": candidate_hyps,
            "opposes_H": [],
        })
    else:
        if convergence_active and leader_id == no_answer:
            verdict = "absent_confirming_leader"
            note = f"another empty chunk after {no_answer} already dominant"
        else:
            verdict = "absent_extending_gap"
            note = "expected date binding, none found"
        new.append({
            "from": cid,
            "finding": (f"no date markers; topic={_sniff_topic(text)}; "
                        f"{note}"),
            "evidence_verdict": verdict,
            "links_to_Ex": False,
            "supports_H": [no_answer] if no_answer else [],
            "weakens_H": candidate_hyps,
            "opposes_H": [],
        })
    return state.K + new


def _update_who(state: "ThoughtState", obs: dict) -> list:
    """Q7-class extractor: person names, author keywords, URL usernames,
    publisher orgs. Verdict vocabulary kept compatible with revise/T:
      - candidate          named author + verb in same chunk
      - weak_candidate     author keyword without name; OR name in URL
                            (split-supporting both 'has author' and
                            'no real authorship statement')
      - off_topic          publisher organization without authorship verb
      - absent_*           nothing relevant
    """
    text = obs.get("text", "")
    cid = obs.get("id", "?")
    H = state.H
    leader = max(H, key=lambda h: h["weight"]) if H else None
    leader_id = leader["id"] if leader else None
    convergence_active = any(t["kind"] == "convergence" for t in state.T)
    no_answer = _no_answer_id(H)
    candidate_hyps = _candidate_ids(H)
    # for split-support: pick FIRST candidate as 'single-author' default
    # this is the spike's honest minimal disambiguation — h1 by convention
    # is the "single named author" hypothesis when constructing K entries
    h_single = candidate_hyps[0] if candidate_hyps else None

    new = []

    # 1) URL containing a Latin CamelCase name
    url_m = URL_RE.search(text)
    if url_m:
        url_span = url_m.group(0)
        latin_in_url = LATIN_CAMEL_RE.search(url_span)
        if latin_in_url:
            name = latin_in_url.group(0)
            new.append({
                "from": cid,
                "verbatim": name,
                "finding": (f"name-shaped token '{name}' inside URL "
                             f"({url_span[:50]}...) — could be author of "
                             "the work, could be just a username; "
                             "ambiguous, splits support"),
                "evidence_verdict": "weak_candidate",
                "links_to_Ex": False,
                "supports_H": [h_single, no_answer] if (h_single and no_answer) else [],
                "weakens_H": [],
                "opposes_H": [],
            })

    # 2) Author keyword present
    kw_m = AUTHOR_KW_RE.search(text)
    if kw_m:
        after = text[kw_m.end():kw_m.end() + 60]
        cyr_name = NAME_CYR_RE.search(after)
        if cyr_name and cyr_name.group(0).strip().lower() not in (
            "программист", "разработчик", "автор", "пользоват",
        ):
            # Real candidate: keyword + Cyrillic name in proximity
            new.append({
                "from": cid,
                "verbatim": cyr_name.group(0),
                "finding": (f"'{kw_m.group(0)}' followed by named entity "
                             f"'{cyr_name.group(0)}' — explicit attribution"),
                "evidence_verdict": "candidate",
                "links_to_Ex": True,
                "supports_H": [h_single] if h_single else [],
                "weakens_H": [no_answer] if no_answer else [],
                "opposes_H": [no_answer] if no_answer else [],
            })
        else:
            # Anonymous self-reference: 'автор' without follow-up name
            new.append({
                "from": cid,
                "finding": (f"'{kw_m.group(0)}' present but no named entity "
                             "follows — anonymous self-reference; suggests "
                             "an author entity exists somewhere but unnamed"),
                "evidence_verdict": "weak_candidate",
                "links_to_Ex": False,
                "supports_H": [h_single] if h_single else [],
                "weakens_H": [no_answer] if no_answer else [],
                "opposes_H": [],
            })

    # 3) Publisher organization (without authorship verb)
    if not new:  # only if we didn't catch authorship above
        org_m = ORG_CYR_RE.search(text)
        publisher_context = (
            "издательств" in text.lower()
            or "пресс" in text.lower()
            or "press" in text.lower()
        )
        if org_m and publisher_context:
            new.append({
                "from": cid,
                "verbatim": org_m.group(0),
                "finding": (f"organization '{org_m.group(0)}' in publisher "
                             "context — publishing is not authoring; "
                             "Ex.forbidden hit"),
                "evidence_verdict": "off_topic",
                "links_to_Ex": False,
                "supports_H": [no_answer] if no_answer else [],
                "weakens_H": candidate_hyps,
                "opposes_H": [],
            })

    # 4) Fallback: nothing relevant found
    if not new:
        if convergence_active and leader_id == no_answer:
            verdict = "absent_confirming_leader"
            note = f"another empty chunk after {no_answer} dominant"
        else:
            verdict = "absent_extending_gap"
            note = "no name, no author keyword"
        new.append({
            "from": cid,
            "finding": (f"no name, no author keyword; "
                        f"topic={_sniff_topic(text)}; {note}"),
            "evidence_verdict": verdict,
            "links_to_Ex": False,
            "supports_H": [no_answer] if no_answer else [],
            "weakens_H": candidate_hyps,
            "opposes_H": [],
        })

    return state.K + new


def reevaluate_existing_K(state: "ThoughtState") -> list:
    """Inner-loop pass: relabel verdicts on existing K entries given current
    H/T. Same K membership, possibly different verdict tags. No new obs.

    Today this is small: an 'absent_extending_gap' entry promotes to
    'absent_confirming_leader' once convergence is active. That changes
    nothing arithmetically but reflects the entry's *current* role."""
    convergence_active = any(t["kind"] == "convergence" for t in state.T)
    leader = max(state.H, key=lambda h: h["weight"]) if state.H else None
    leader_is_no_answer = (leader is not None
                            and leader.get("_role") == "no_answer")

    out = []
    for k in state.K:
        if (k.get("evidence_verdict") == "absent_extending_gap"
                and convergence_active and leader_is_no_answer):
            out.append({**k, "evidence_verdict": "absent_confirming_leader",
                        "_relabelled": True})
        else:
            out.append(k)
    return out


def _sniff_topic(text: str) -> str:
    """Hand-rolled topic guess so the K narrative reads like thought, not noise."""
    s = text.lower()
    if "издательств" in s or "dmkpress" in s:
        return "publisher contact"
    if "github.com" in s or "git clone" in s:
        return "repository / install"
    if "структура" in s or "состоит из" in s:
        return "book structure"
    if "приветств" in s:
        return "reader greeting"
    if "python" in s and ("install" in s or "установ" in s or "downloads" in s):
        return "Python install"
    return "general prose"


# ---------------- revise_hypotheses ----------------

def revise_hypotheses(state: "ThoughtState") -> list:
    """Pure-K target weight: weight is a function of K and the immutable
    base weight (set in initial_state). Inner-loop iterations therefore
    converge: same K -> same target, no compounding offsets.

    Status reads T (convergence -> non-leader fading) and the step's
    *initial* weight (state.H[i]['_step_initial']) so the growing/weakening
    tag reflects movement-this-step, not movement-this-iter.
    """
    H = state.H
    K = state.K
    T = state.T
    convergence_active = any(t["kind"] == "convergence" for t in T)
    leader_id = _leader_id(H)

    out = []
    for h in H:
        hid = h["id"]
        base = h.get("_base", h["weight"])
        step_initial = h.get("_step_initial", h["weight"])

        supports_real = sum(
            1 for k in K
            if hid in k.get("supports_H", [])
            and k.get("evidence_verdict") == "candidate"
        )
        supports_indirect = sum(
            1 for k in K
            if hid in k.get("supports_H", [])
            and k.get("evidence_verdict") in (
                "absent_extending_gap", "absent_confirming_leader",
                "off_topic", "rejected_type_mismatch",
            )
        )
        supports_weak = sum(
            1 for k in K
            if hid in k.get("supports_H", [])
            and k.get("evidence_verdict") == "weak_candidate"
        )
        weakened = sum(1 for k in K if hid in k.get("weakens_H", []))
        opposed = sum(1 for k in K if hid in k.get("opposes_H", []))

        if h.get("_role") == "no_answer":
            # 'no answer' grows from indirect signal AND from weak split
            # support; shrinks from real candidates that succeed
            target = max(0.0, min(1.0,
                base
                + 0.10 * supports_indirect
                + 0.05 * supports_weak
                - 0.25 * supports_real,
            ))
        else:
            # candidate hypotheses grow from real evidence; partial
            # credit for weak signals (split-supporting URL names,
            # anonymous author keywords)
            target = max(0.0, min(1.0,
                base
                + 0.20 * supports_real
                + 0.10 * supports_weak
                - 0.05 * weakened
                - 0.05 * opposed,
            ))

        # status: against step_initial (preserved across inner iters)
        if convergence_active and hid != leader_id:
            status = "fading"
        elif target > step_initial + 0.005:
            status = "growing"
        elif target < step_initial - 0.005:
            status = "weakening"
        elif weakened >= 1 and supports_real >= 1:
            status = "disputed"
        else:
            status = "stable"

        out.append({**h, "weight": round(target, 3), "status": status})
    return out


def _leader_id(H: list) -> str | None:
    if not H:
        return None
    return max(H, key=lambda h: h["weight"])["id"]


# ---------------- recompute_tensions ----------------

def recompute_tensions(state: "ThoughtState") -> list:
    """Reads H statuses (fading non-leaders strengthen convergence),
    reads K. T entries are the *current* set, not an accumulation —
    if a tension is resolved by inner-loop iteration, it disappears."""
    H = state.H
    K = state.K
    Ex = state.Ex
    T = []

    linked = sum(1 for k in K if k.get("links_to_Ex"))
    if linked == 0 and len(K) >= 1:
        T.append({
            "kind": "gap",
            "what": (f"Ex.must_link_to {Ex.get('must_link_to')} unsatisfied "
                     f"after {len(K)} observations"),
            "severity": "HIGH" if len(K) >= 3 else "MEDIUM",
        })

    rejects = [k for k in K
               if k.get("evidence_verdict") == "rejected_type_mismatch"]
    if rejects:
        T.append({
            "kind": "type_mismatch",
            "what": (f"{len(rejects)} year-shaped token(s) appeared but in "
                      "Python-version contexts (Ex.forbidden hit)"),
            "severity": "MEDIUM",
            "examples": [r.get("verbatim") for r in rejects],
        })

    if len(K) >= 3:
        recent = K[-3:]
        if all(k.get("evidence_verdict") != "candidate" for k in recent):
            T.append({
                "kind": "drift",
                "what": ("last 3 observations produced no candidate "
                          "evidence; possibility space narrowing"),
                "severity": "INFORMATIONAL",
            })

    # convergence: 'no_answer' role hypothesis dominant AND non-leaders fading
    no_answer = next((h for h in H if h.get("_role") == "no_answer"), None)
    others = [h for h in H if h.get("_role") != "no_answer"]
    if no_answer and no_answer["weight"] >= 0.55:
        top_other = max(others, key=lambda h: h["weight"]) if others else None
        margin = (no_answer["weight"] - top_other["weight"]) if top_other else 1.0
        non_leader_fading = (
            all(h["status"] in ("fading", "weakening", "stable")
                and h["weight"] < no_answer["weight"] for h in others)
        )
        if margin >= 0.15 and non_leader_fading:
            T.append({
                "kind": "convergence",
                "what": (f"{no_answer['id']} (no_answer) weight "
                          f"{no_answer['weight']} dominates next "
                          f"({top_other['id']}: {top_other['weight']}) "
                          f"by margin {margin:.2f}; non-leaders fading"),
                "severity": "RESOLVED",
            })

    return T


# ---------------- self_evaluate ----------------

def self_evaluate(prev: ThoughtState, K: list, H: list, T: list,
                  obs: dict) -> dict:
    new_K_count = len(K) - len(prev.K)
    h_shift = sum(abs(h["weight"] - p["weight"])
                   for h, p in zip(H, prev.H))
    prev_T_kinds = {(t["kind"], t.get("severity")) for t in prev.T}
    cur_T_kinds = {(t["kind"], t.get("severity")) for t in T}
    opened = cur_T_kinds - prev_T_kinds
    closed = prev_T_kinds - cur_T_kinds

    if any(t["kind"] == "convergence" for t in T):
        no_answer = next((h for h in H if h.get("_role") == "no_answer"), None)
        leader_id = no_answer["id"] if no_answer else "?"
        return {"progress": 1.0, "kind": "convergence",
                "note": (f"{leader_id} (no_answer) dominant; refuse is the "
                          "resolved answer, not a fallback when nothing "
                          "else worked")}

    if new_K_count == 0:
        return {"progress": 0.0, "kind": "stagnant",
                "note": "observation produced no K change"}

    if h_shift >= 0.05:
        last_k = K[-1]
        verdict = last_k.get("evidence_verdict")
        if verdict == "candidate":
            return {"progress": round(h_shift, 3), "kind": "growth",
                    "note": f"candidate {last_k.get('verbatim','?')} "
                             "lifted h1/h2/h3"}
        if verdict == "rejected_type_mismatch":
            return {"progress": round(h_shift, 3), "kind": "narrowing",
                    "note": "type-rejection ruled out a decoy; "
                             "possibility space shrinks but I now know "
                             "more about what the answer is NOT"}
        no_answer = next((h for h in H if h.get("_role") == "no_answer"), None)
        no_answer_id = no_answer["id"] if no_answer else "?"
        return {"progress": round(h_shift, 3), "kind": "narrowing",
                "note": (f"K grew with verdict={verdict}; "
                          f"{no_answer_id} nudges toward refuse")}

    if opened:
        return {"progress": 0.3, "kind": "noticing",
                "note": f"new tension(s): {sorted(opened)}"}
    if closed:
        return {"progress": 0.4, "kind": "resolving",
                "note": f"closed tension(s): {sorted(closed)}"}

    return {"progress": 0.05, "kind": "minor",
            "note": "K grew, H stable, T unchanged"}


# ---------------- think_step (fixed-point) ----------------

MAX_INNER_ITERS = 4


def _snapshot(state: ThoughtState) -> tuple:
    """What 'stable' means: H weights+statuses, T kinds, K verdicts."""
    return (
        tuple((h["id"], h["weight"], h["status"]) for h in state.H),
        tuple((t["kind"], t.get("severity")) for t in state.T),
        tuple(k.get("evidence_verdict") for k in state.K),
    )


def think_step(state: ThoughtState, obs: Any) -> ThoughtState:
    """Single observation, but K-H-T iterate to fixed-point inside.

    Pass 0: ingest obs into K.
    Inner loop: revise H reading T+K; recompute T reading H+K;
                relabel existing K verdicts in light of new H+T.
                Repeat until snapshot stable or MAX_INNER_ITERS.
    Then: self_evaluate against the OUTER previous state.
    """
    # iter 0 — ingest new observation. Stamp _step_initial so status
    # comparisons inside the inner loop measure movement-this-step,
    # not oscillation across inner iterations.
    K = update_knowledge(state, obs)
    H_with_step_initial = [
        {**h, "_step_initial": h["weight"]} for h in state.H
    ]
    work = ThoughtState(
        G=state.G, Ex=state.Ex,
        K=K, H=H_with_step_initial, T=state.T,
        E=state.E, history=state.history,
    )

    iters_run = 0
    for i in range(MAX_INNER_ITERS):
        iters_run = i + 1
        before = _snapshot(work)
        # H reads K+T
        new_H = revise_hypotheses(work)
        work = ThoughtState(
            G=work.G, Ex=work.Ex, K=work.K,
            H=new_H, T=work.T,
            E=work.E, history=work.history,
        )
        # T reads H+K
        new_T = recompute_tensions(work)
        work = ThoughtState(
            G=work.G, Ex=work.Ex, K=work.K,
            H=work.H, T=new_T,
            E=work.E, history=work.history,
        )
        # K relabel reads H+T
        new_K = reevaluate_existing_K(work)
        work = ThoughtState(
            G=work.G, Ex=work.Ex, K=new_K,
            H=work.H, T=work.T,
            E=work.E, history=work.history,
        )
        if _snapshot(work) == before:
            break

    new_E = self_evaluate(state, work.K, work.H, work.T, obs)
    new_E["inner_iters"] = iters_run

    return ThoughtState(
        G=state.G, Ex=state.Ex,
        K=work.K, H=work.H, T=work.T, E=new_E,
        history=state.history + [{
            "obs_id": obs.get("id"),
            "K_size": len(work.K),
            "K_last": work.K[-1] if work.K else None,
            "K_relabelled_count": sum(
                1 for k in work.K if k.get("_relabelled")
            ),
            "H": [{"id": h["id"], "w": h["weight"], "s": h["status"]}
                  for h in work.H],
            "T": [{"kind": t["kind"], "sev": t["severity"],
                   "what": t["what"]} for t in work.T],
            "E": new_E,
            "inner_iters": iters_run,
        }],
    )


# ---------------- next_action ----------------

def next_action(state: ThoughtState) -> str:
    convergence = next(
        (t for t in state.T if t["kind"] == "convergence"), None,
    )
    if convergence:
        no_answer = next(
            (h for h in state.H if h.get("_role") == "no_answer"), None,
        )
        if no_answer:
            return (f"refuse(reason=oop_signal_absent, "
                    f"backing_hypothesis={no_answer['id']}, "
                    f"weight={no_answer['weight']})")

    severity_rank = {"HIGH": 3, "MEDIUM": 2, "INFORMATIONAL": 1, "RESOLVED": 0}
    if state.T:
        worst = max(state.T, key=lambda t: severity_rank.get(t["severity"], 0))
        return f"address_tension({worst['kind']}, sev={worst['severity']})"
    return "continue_observing"


# ---------------- initial_state for Q22 ----------------

def initial_state_q22() -> ThoughtState:
    return ThoughtState(
        G={
            "intent": "when",
            "target_entity": "book 'Programming Puzzles, Python Edition'",
            "target_relation": "first publication date",
            "question": ("Когда была впервые выпущена книга "
                          "«Programming Puzzles, Python Edition»?"),
        },
        Ex={
            "type": "date",
            "formats": ["YYYY", "MM YYYY", "DD MMM YYYY"],
            "must_link_to": ["book entity", "publication relation"],
            "forbidden": ["Python version digits", "URL path digits",
                           "ISBN strings", "problem-data digits"],
        },
        H=[
            {"id": "h1", "_role": "candidate",
             "reading": "year of English original publication",
             "_base": 0.30, "weight": 0.30, "status": "stable"},
            {"id": "h2", "_role": "candidate",
             "reading": "year of Russian translation",
             "_base": 0.25, "weight": 0.25, "status": "stable"},
            {"id": "h3", "_role": "candidate",
             "reading": "copyright year of an edition",
             "_base": 0.20, "weight": 0.20, "status": "stable"},
            {"id": "h4", "_role": "no_answer",
             "reading": "answer not present in active corpus",
             "_base": 0.25, "weight": 0.25, "status": "stable"},
        ],
        K=[],
        T=[],
        E={"progress": 0.0, "kind": "initial",
            "note": "before any observation"},
        history=[],
    )


# ---------------- initial_state for Q7 (no audit peeking) ----------------

def initial_state_q7() -> ThoughtState:
    """Honest first parse of 'Кто является автором задач в книге?' without
    consulting audit's PI1/PI2/PI3/PI4 list. Three coarse readings a system
    might come up with on its own:

      h1 — 'one named individual wrote the tasks' (default for 'автор')
      h2 — 'tasks are compiled from various sources' (puzzle books often
            do this; particularly likely for problems that look classical)
      h3 — 'no answer findable in this corpus'
    """
    return ThoughtState(
        G={
            "intent": "who",
            "target_entity": "tasks in the puzzle book",
            "target_relation": "authorship",
            "question": "Кто является автором задач в книге?",
        },
        Ex={
            "type": "person_name + authorship_relation",
            "formats": ["X написал/составил Y", "автор: X"],
            "must_link_to": ["named person", "authorship verb"],
            "forbidden": [
                "URL usernames (Latin CamelCase in github.com/X/...)",
                "publisher organizations without authorship verb",
                "anonymous 'автор' references that name no one",
            ],
        },
        H=[
            {"id": "h1", "_role": "candidate",
             "reading": "tasks have a single named author",
             "_base": 0.40, "weight": 0.40, "status": "stable"},
            {"id": "h2", "_role": "candidate",
             "reading": "tasks are compiled from various sources",
             "_base": 0.25, "weight": 0.25, "status": "stable"},
            {"id": "h3", "_role": "no_answer",
             "reading": "answer not present in active corpus",
             "_base": 0.35, "weight": 0.35, "status": "stable"},
        ],
        K=[],
        T=[],
        E={"progress": 0.0, "kind": "initial",
           "note": "before any observation"},
        history=[],
    )


# ---------------- chunk fixtures (hand-copied from audit_v0.chunks.jsonl) ----------------
# Order matches Q22 retrieved_topk_chunk_ids per audit_v0.manual.jsonl,
# truncated to 5 chunks for the spike.

CHUNKS = [
    {
        "id": "pb_intro_001",
        "text": (
            "Предисловие издательства ДМК Пресс. Контактные адреса для "
            "отзывов (dmkpress@gmail.com, www.dmkpress.com), процедура "
            "сообщения об опечатках, политика по нарушению авторских прав. "
            "Не содержит технического материала."
        ),
    },
    {
        "id": "pb_intro_003",
        "text": (
            "Структура книги. Книга состоит из двух частей: «Серьезные "
            "задачи» и «Шуточные задачи». В первой части — 50 (плюс "
            "несколько дополнительных) задач, расположенных по нарастанию "
            "сложности; рекомендуется начинать с задачи 1 и решать по "
            "порядку, ничего не пропуская. Шуточные задачи требуют "
            "творческих способностей и использования предлагаемых Python-"
            "библиотек; их рекомендуется пробовать, когда читатель устанет "
            "от серьёзных. Для решения задач необходимо владеть основами "
            "Python: переменные, условные предложения, циклы, функции."
        ),
    },
    {
        "id": "pb_intro_002",
        "text": (
            "Короткое приветствие читателю. Автор предлагает остановиться "
            "на нескольких важных моментах перед погружением в задачи."
        ),
    },
    {
        "id": "pb_intro_007",
        "text": (
            "К книге прилагается git-репозиторий с заготовками кода и "
            "решениями всех задач. Адрес репозитория: github.com/"
            "MatWhiteside/python-puzzle-book. Клонирование: HTTPS — "
            "`git clone https://github.com/MatWhiteside/python-puzzle-book"
            ".git`; SSH — `git clone git@github.com:MatWhiteside/python-"
            "puzzlebook.git`. Если git не работает или незнаком "
            "пользователю, можно скачать код в виде zip-архива через "
            "GitHub-браузер."
        ),
    },
    {
        "id": "pb_intro_004",
        "text": (
            "Инструкция по установке Python. Шаги: 1) зайти на python.org; "
            "2) перейти в раздел Downloads; 3) выбрать установщик для своей "
            "ОС (Windows, macOS или Linux) и версию Python не ниже 3.10; "
            "4) скачать и следовать инструкциям установщика, согласиться на "
            "установку pip. Проверка установки: команда python --version, "
            "либо python3 --version, либо python3.10 --version."
        ),
    },
]


# Q7 retrieve order from audit_v0.manual.jsonl: pb_intro_007 first.
Q7_CHUNKS = [
    {
        "id": "pb_intro_007",
        "text": (
            "К книге прилагается git-репозиторий с заготовками кода и "
            "решениями всех задач. Адрес репозитория: github.com/"
            "MatWhiteside/python-puzzle-book. Клонирование: HTTPS — "
            "`git clone https://github.com/MatWhiteside/python-puzzle-book"
            ".git`; SSH — `git clone git@github.com:MatWhiteside/python-"
            "puzzlebook.git`. Если git не работает или незнаком "
            "пользователю, можно скачать код в виде zip-архива через "
            "GitHub-браузер."
        ),
    },
    {
        "id": "pb_intro_001",
        "text": (
            "Предисловие издательства ДМК Пресс. Контактные адреса для "
            "отзывов (dmkpress@gmail.com, www.dmkpress.com), процедура "
            "сообщения об опечатках, политика по нарушению авторских прав. "
            "Не содержит технического материала."
        ),
    },
    {
        "id": "pb_intro_002",
        "text": (
            "Короткое приветствие читателю. Автор предлагает остановиться "
            "на нескольких важных моментах перед погружением в задачи."
        ),
    },
    {
        "id": "pb_intro_011",
        "text": (
            "Введение к разделу серьёзных задач. Задачи начинаются с "
            "лёгких и постепенно усложняются. В каждой задаче "
            "формулируется задание и приводится заготовка кода. Если "
            "задача не поддаётся, далее в книге есть раздел с указаниями "
            "(рекомендуется обращаться к указаниям прежде, чем смотреть "
            "решение). Важное правило: не импортировать никакие "
            "библиотеки, если в задаче это явно не требуется."
        ),
    },
    {
        "id": "pb_intro_003",
        "text": (
            "Структура книги. Книга состоит из двух частей: «Серьезные "
            "задачи» и «Шуточные задачи». В первой части — 50 (плюс "
            "несколько дополнительных) задач, расположенных по нарастанию "
            "сложности; рекомендуется начинать с задачи 1 и решать по "
            "порядку, ничего не пропуская. Шуточные задачи требуют "
            "творческих способностей и использования предлагаемых Python-"
            "библиотек; их рекомендуется пробовать, когда читатель устанет "
            "от серьёзных. Для решения задач необходимо владеть основами "
            "Python: переменные, условные предложения, циклы, функции."
        ),
    },
]


# ---------------- pretty printer ----------------

def show(state: ThoughtState) -> None:
    g = state.G
    print(f"=== Q: {g['question']} (intent={g['intent']}) ===")
    print(f"Ex: type={state.Ex['type']}, "
          f"forbidden={state.Ex['forbidden']}")
    print(f"H initial weights: {[(h['id'], h['_base'], h['_role'], h['reading']) for h in state.H]}")
    print()

    for i, step in enumerate(state.history, 1):
        iters = step.get("inner_iters", "?")
        relabel = step.get("K_relabelled_count", 0)
        print(f"--- step {i}: observed {step['obs_id']} "
              f"(inner_iters={iters}, K_relabelled={relabel}) ---")
        kl = step["K_last"]
        verdict = kl.get("evidence_verdict")
        finding = kl.get("finding")
        print(f"  noticed: {finding}")
        print(f"  -> verdict: {verdict}")
        print(f"  H now: " + ", ".join(
            f"{h['id']}={h['w']:.2f}/{h['s']}" for h in step["H"]))
        if step["T"]:
            for t in step["T"]:
                print(f"  T: [{t['sev']}] {t['kind']}: {t['what']}")
        else:
            print("  T: (none)")
        e = step["E"]
        print(f"  E: {e['kind']} (progress={e['progress']}) — {e['note']}")
        print()

    print("=== final ===")
    print(f"  next_action(): {next_action(state)}")
    print(f"  H final: " + ", ".join(
        f"{h['id']}={h['weight']:.2f}/{h['status']}" for h in state.H))


if __name__ == "__main__":
    import sys

    which = sys.argv[1] if len(sys.argv) > 1 else "q7"
    if which == "q22":
        s = initial_state_q22()
        chunks = CHUNKS
    elif which == "q7":
        s = initial_state_q7()
        chunks = Q7_CHUNKS
    else:
        sys.exit(f"unknown question id: {which} (use q7 or q22)")

    for chunk in chunks:
        s = think_step(s, chunk)
    show(s)
