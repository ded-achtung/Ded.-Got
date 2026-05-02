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


# ---------------- update_knowledge ----------------

def update_knowledge(state: "ThoughtState", obs: dict) -> list:
    """Reads obs IN CONTEXT of state.H (current leader), state.T (open
    tensions), state.K (prior accumulation). The verdict on a new entry,
    and the H it weakens/supports, depends on what the system already
    believes — not just on regex matches in obs.

    Same regexes as before; what changed is that:
      - absence weakens specific H by name (the ones that *expected*
        evidence here), not just supports h4 generically
      - the verdict label distinguishes 'absent_extending_gap' (early
        absences before convergence) from 'absent_confirming_leader'
        (absences after h4 already dominant) — same physical event,
        different epistemic role
      - type-rejection records *what* the rejected token would have
        meant for *which* H if it weren't a decoy
    """
    text = obs.get("text", "")
    cid = obs.get("id", "?")
    H = state.H
    leader = max(H, key=lambda h: h["weight"]) if H else None
    leader_id = leader["id"] if leader else None
    convergence_active = any(t["kind"] == "convergence" for t in state.T)
    candidate_hyps = [h["id"] for h in H if h["id"] != "h4"]

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
                    "supports_H": ["h4"],
                    "weakens_H": [],   # rejection nudges h4 only, doesn't weaken candidates
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
                    "weakens_H": ["h4"],   # candidate weakens out-of-corpus
                    "opposes_H": ["h4"],
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
            "supports_H": ["h4"],
            "weakens_H": candidate_hyps,   # off-topic numbers in chunk that
                                            # COULD have held a date but didn't
            "opposes_H": [],
        })
    else:
        # absence: contextual verdict
        if convergence_active and leader_id == "h4":
            verdict = "absent_confirming_leader"
            note = "another empty chunk after h4 already dominant"
        else:
            verdict = "absent_extending_gap"
            note = "expected date binding, none found"
        new.append({
            "from": cid,
            "finding": (f"no date markers; topic={_sniff_topic(text)}; "
                        f"{note}"),
            "evidence_verdict": verdict,
            "links_to_Ex": False,
            "supports_H": ["h4"],
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
    leader_id = leader["id"] if leader else None

    out = []
    for k in state.K:
        if (k.get("evidence_verdict") == "absent_extending_gap"
                and convergence_active and leader_id == "h4"):
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
        weakened = sum(1 for k in K if hid in k.get("weakens_H", []))
        opposed = sum(1 for k in K if hid in k.get("opposes_H", []))

        if hid == "h4":
            target = max(0.0, min(1.0,
                base + 0.10 * supports_indirect - 0.25 * supports_real,
            ))
        else:
            target = max(0.0, min(1.0,
                base + 0.20 * supports_real - 0.05 * weakened - 0.05 * opposed,
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

    # convergence: h4 dominant AND non-leaders fading
    h4 = next((h for h in H if h["id"] == "h4"), None)
    others = [h for h in H if h["id"] != "h4"]
    if h4 and h4["weight"] >= 0.55:
        top_other = max(others, key=lambda h: h["weight"]) if others else None
        margin = (h4["weight"] - top_other["weight"]) if top_other else 1.0
        non_leader_fading = (
            all(h["status"] in ("fading", "weakening", "stable")
                and h["weight"] < h4["weight"] for h in others)
        )
        if margin >= 0.15 and non_leader_fading:
            T.append({
                "kind": "convergence",
                "what": (f"h4 weight {h4['weight']} dominates next "
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
        return {"progress": 1.0, "kind": "convergence",
                "note": "h4 dominant; refuse is the resolved answer, "
                         "not a fallback when nothing else worked"}

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
        return {"progress": round(h_shift, 3), "kind": "narrowing",
                "note": f"K grew with verdict={verdict}; "
                         "h4 nudges toward refuse"}

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
        return ("refuse(reason=oop_signal_absent, "
                f"backing_hypothesis=h4, weight={state.H[-1]['weight']})")

    severity_rank = {"HIGH": 3, "MEDIUM": 2, "INFORMATIONAL": 1, "RESOLVED": 0}
    if state.T:
        worst = max(state.T, key=lambda t: severity_rank.get(t["severity"], 0))
        return f"address_tension({worst['kind']}, sev={worst['severity']})"
    return "continue_observing"


# ---------------- initial_state for Q22 ----------------

def initial_state() -> ThoughtState:
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
            {"id": "h1", "reading": "year of English original publication",
             "_base": 0.30, "weight": 0.30, "status": "stable"},
            {"id": "h2", "reading": "year of Russian translation",
             "_base": 0.25, "weight": 0.25, "status": "stable"},
            {"id": "h3", "reading": "copyright year of an edition",
             "_base": 0.20, "weight": 0.20, "status": "stable"},
            {"id": "h4", "reading": "answer not present in active corpus",
             "_base": 0.25, "weight": 0.25, "status": "stable"},
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


# ---------------- pretty printer ----------------

def show(state: ThoughtState) -> None:
    g = state.G
    print(f"=== Q: {g['question']} (intent={g['intent']}) ===")
    print(f"Ex: type={state.Ex['type']}, "
          f"forbidden={state.Ex['forbidden']}")
    print(f"H initial: {[(h['id'], h['weight'], h['reading']) for h in state.H[:0] or initial_state().H]}")
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
    s = initial_state()
    for chunk in CHUNKS:
        s = think_step(s, chunk)
    show(s)
