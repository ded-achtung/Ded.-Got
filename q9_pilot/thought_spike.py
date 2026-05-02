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

def update_knowledge(K: list, obs: dict, Ex: dict) -> list:
    """Each new K entry carries: which H it supports, whether it links Ex,
    and an evidence_verdict. If a year-shaped token is present but its
    context fails Ex.forbidden, it lands as `rejected_type_mismatch`,
    NOT silently dropped."""
    text = obs.get("text", "")
    cid = obs.get("id", "?")
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
                    "finding": f"date-shaped token '{y_str}' inside Python "
                                "version reference — type-rejected",
                    "evidence_verdict": "rejected_type_mismatch",
                    "links_to_Ex": False,
                    "supports_H": ["h4"],  # rejection nudges 'not in corpus'
                    "opposes_H": [],
                })
            else:
                new.append({
                    "from": cid,
                    "verbatim": y_str,
                    "finding": f"raw year token '{y}' in prose context",
                    "value": y,
                    "evidence_verdict": "candidate",
                    "links_to_Ex": True,
                    "supports_H": ["h1", "h2", "h3"],
                    "opposes_H": ["h4"],
                })
    elif py_versions or PATH_DIGIT_RE.search(text):
        marker = (f"Python version {py_versions[0]}" if py_versions
                   else "URL path digits")
        new.append({
            "from": cid,
            "finding": f"numeric markers present ({marker}) but type-incompatible",
            "evidence_verdict": "off_topic",
            "links_to_Ex": False,
            "supports_H": ["h4"],
            "opposes_H": [],
        })
    else:
        new.append({
            "from": cid,
            "finding": "no date or year markers; chunk talks about "
                       f"{_sniff_topic(text)}",
            "evidence_verdict": "absent",
            "links_to_Ex": False,
            "supports_H": ["h4"],
            "opposes_H": [],
        })
    return K + new


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

def revise_hypotheses(H: list, K: list, Ex: dict) -> list:
    out = []
    for h in H:
        hid = h["id"]
        prev_w = h["weight"]
        supports_real = sum(
            1 for k in K
            if hid in k.get("supports_H", [])
            and k.get("evidence_verdict") == "candidate"
        )
        supports_indirect = sum(
            1 for k in K
            if hid in k.get("supports_H", [])
            and k.get("evidence_verdict") in ("absent", "off_topic",
                                              "rejected_type_mismatch")
        )
        opposed = sum(1 for k in K if hid in k.get("opposes_H", []))

        # h4 (out-of-corpus) grows when nothing supports h1-h3
        if hid == "h4":
            new_w = min(1.0, prev_w + 0.10 * supports_indirect - 0.20 * opposed)
        else:
            new_w = max(0.0, prev_w + 0.20 * supports_real - 0.05 * supports_indirect)

        # status: distinguish 'fading by elimination' from 'stable'
        if new_w > prev_w + 0.01:
            status = "growing"
        elif supports_indirect >= 2 and supports_real == 0:
            status = "fading"
        elif opposed >= 1 and supports_real >= 1:
            status = "disputed"
        else:
            status = "stable"

        out.append({**h, "weight": round(new_w, 3), "status": status})
    return out


# ---------------- recompute_tensions ----------------

def recompute_tensions(H: list, K: list, Ex: dict, G: dict) -> list:
    T = []

    linked = sum(1 for k in K if k.get("links_to_Ex"))
    if linked == 0 and len(K) >= 1:
        T.append({
            "kind": "gap",
            "what": f"Ex.must_link_to {Ex.get('must_link_to')} unsatisfied "
                     f"after {len(K)} observations; Ex points to a date "
                     "binding to the book entity, none of K provides one",
            "severity": "HIGH" if len(K) >= 3 else "MEDIUM",
        })

    rejects = [k for k in K if k.get("evidence_verdict") == "rejected_type_mismatch"]
    if rejects:
        T.append({
            "kind": "type_mismatch",
            "what": f"{len(rejects)} year-shaped token(s) appeared but in "
                     "Python-version contexts (Ex.forbidden hit) — system "
                     "actively refuses these as decoys, not silently",
            "severity": "MEDIUM",
            "examples": [r.get("verbatim") for r in rejects],
        })

    # drift: last 3 obs added no candidate evidence
    if len(K) >= 3:
        recent = K[-3:]
        if all(k.get("evidence_verdict") != "candidate" for k in recent):
            T.append({
                "kind": "drift",
                "what": "last 3 observations produced no candidate evidence; "
                         "possibility space narrowing toward refuse",
                "severity": "INFORMATIONAL",
            })

    # convergence: h4 dominant
    h4 = next((h for h in H if h["id"] == "h4"), None)
    if h4 and h4["weight"] >= 0.55:
        h_top_other = max(
            (h for h in H if h["id"] != "h4"),
            key=lambda h: h["weight"], default=None,
        )
        if h_top_other and h4["weight"] - h_top_other["weight"] >= 0.15:
            T.append({
                "kind": "convergence",
                "what": f"h4 weight {h4['weight']} dominates next "
                         f"({h_top_other['id']}: {h_top_other['weight']}) "
                         "by margin >=0.15 — refuse becomes the supported "
                         "answer, not a fallback",
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


# ---------------- think_step ----------------

def think_step(state: ThoughtState, obs: Any) -> ThoughtState:
    new_K = update_knowledge(state.K, obs, state.Ex)
    new_H = revise_hypotheses(state.H, new_K, state.Ex)
    new_T = recompute_tensions(new_H, new_K, state.Ex, state.G)
    new_E = self_evaluate(state, new_K, new_H, new_T, obs)

    return ThoughtState(
        G=state.G, Ex=state.Ex,
        K=new_K, H=new_H, T=new_T, E=new_E,
        history=state.history + [{
            "obs_id": obs.get("id"),
            "K_size": len(new_K),
            "K_last": new_K[-1] if new_K else None,
            "H": [{"id": h["id"], "w": h["weight"], "s": h["status"]}
                  for h in new_H],
            "T": [{"kind": t["kind"], "sev": t["severity"],
                   "what": t["what"]} for t in new_T],
            "E": new_E,
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
             "weight": 0.30, "status": "stable"},
            {"id": "h2", "reading": "year of Russian translation",
             "weight": 0.25, "status": "stable"},
            {"id": "h3", "reading": "copyright year of an edition",
             "weight": 0.20, "status": "stable"},
            {"id": "h4", "reading": "answer not present in active corpus",
             "weight": 0.25, "status": "stable"},
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
        print(f"--- step {i}: observed {step['obs_id']} ---")
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
