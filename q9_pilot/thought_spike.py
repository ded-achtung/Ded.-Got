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

# pattern_class registry — narrow enum derived empirically from Q22+Q7.
# is_disambiguating=False means the class supports multiple competing H
# symmetrically; such entries give no direct H contribution and instead
# emit un_disambiguating tension. Each class also defines its base
# support_strength (used by revise_hypotheses for first-instance contrib).
PATTERN_CLASSES = {
    # when-intent
    "raw_year_in_prose":    {"is_disambiguating": True,  "support_strength": 0.20},
    "year_in_python_version": {"is_disambiguating": True, "support_strength": 0.10},
    "numeric_off_topic":    {"is_disambiguating": True,  "support_strength": 0.10},
    # who-intent
    "name_with_relation":   {"is_disambiguating": True,  "support_strength": 0.20},
    "name_in_url":          {"is_disambiguating": False, "support_strength": 0.10},
    "anonymous_attribution": {"is_disambiguating": False, "support_strength": 0.10},
    "publisher_org":        {"is_disambiguating": True,  "support_strength": 0.10},
    # what-intent (Q1 — version question)
    "version_with_min_phrase": {"is_disambiguating": True,  "support_strength": 0.20},
    "versioned_command":       {"is_disambiguating": True,  "support_strength": 0.15},
    "python3_command":         {"is_disambiguating": False, "support_strength": 0.10},
    # what-intent (Q2 — pip modules question)
    "pip_install_with_module": {"is_disambiguating": True,  "support_strength": 0.20},
    "pip_mention_no_modules":  {"is_disambiguating": True,  "support_strength": 0.05},
    # both intents
    "no_marker":            {"is_disambiguating": True,  "support_strength": 0.10},
}


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

# what-intent regexes (Q1: minimum Python version)
VERSION_MIN_PHRASE_RE = re.compile(
    r"(?:версию\s+Python\s+не\s+ниже\s+|"
     r"Python\s+(?:версии\s+)?не\s+ниже\s+|"
     r"требуется\s+Python\s+|"
     r"минимум\s+Python\s+)"
    r"(\d+(?:\.\d+)+)",
    re.IGNORECASE,
)
VERSIONED_CMD_RE = re.compile(r"\bpython(\d+\.\d+)\b")
PYTHON3_CMD_RE = re.compile(r"\bpython3\b(?!\.\d)")

# what-intent regexes (Q2: pip-installable modules)
PIP_INSTALL_MODULE_RE = re.compile(
    r"pip\s+install\s+([A-Za-z][A-Za-z0-9_]+)",
    re.IGNORECASE,
)
PIP_MENTION_RE = re.compile(
    r"\b(?:менеджер\s+пакетов\s+pip|"
     r"установк[уи]\s+pip|"
     r"наличие\s+pip|"
     r"через\s+pip)\b",
    re.IGNORECASE,
)


# ---------------- update_knowledge (dispatch on intent) ----------------

def update_knowledge(state: "ThoughtState", obs: dict) -> list:
    """Dispatch by G.extractor_pack (set in initial_state). Each pack is
    a question-class-specific extractor; they share the verdict
    vocabulary so revise_hypotheses and recompute_tensions stay generic.
    Falls back to G.intent for backward compat."""
    pack = state.G.get("extractor_pack") or state.G.get("intent")
    if pack in ("when", "when_publication_date"):
        return _update_when(state, obs)
    if pack in ("who", "who_authorship"):
        return _update_who(state, obs)
    if pack in ("what_python_version",):
        return _update_what_version(state, obs)
    if pack == "what_pip_modules":
        return _update_what_pip(state, obs)
    if pack == "what":
        return _update_what_version(state, obs)  # Q1 default
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
                    "evidence_verdict": "rejected_type_mismatch", "pattern_class": "year_in_python_version",
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
                    "pattern_class": "raw_year_in_prose",
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
            "pattern_class": "numeric_off_topic",
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
            "pattern_class": "no_marker",
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
                "pattern_class": "name_in_url",
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
                "pattern_class": "name_with_relation",
                "links_to_Ex": True,
                "supports_H": [h_single] if h_single else [],
                "weakens_H": [no_answer] if no_answer else [],
                "opposes_H": [no_answer] if no_answer else [],
            })
        else:
            # Anonymous self-reference: 'автор' without follow-up name
            # Treated as symmetric: 'an author entity exists' (h_single)
            # but 'unnamed in this corpus' (no_answer). Non-disambiguating.
            new.append({
                "from": cid,
                "finding": (f"'{kw_m.group(0)}' present but no named entity "
                             "follows — anonymous self-reference; suggests "
                             "an author entity exists somewhere but unnamed"),
                "evidence_verdict": "weak_candidate",
                "pattern_class": "anonymous_attribution",
                "links_to_Ex": False,
                "supports_H": [h_single, no_answer] if (h_single and no_answer) else [],
                "weakens_H": [],
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
                "pattern_class": "publisher_org",
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
            "pattern_class": "no_marker",
            "links_to_Ex": False,
            "supports_H": [no_answer] if no_answer else [],
            "weakens_H": candidate_hyps,
            "opposes_H": [],
        })

    return state.K + new


def _update_what_version(state: "ThoughtState", obs: dict) -> list:
    """Q1-class extractor: minimum Python version. Multiple K entries
    can be produced from one chunk (a chunk may contain a min-version
    phrase AND versioned commands AND a generic python3 command — each
    is a distinct piece of evidence with its own pattern_class)."""
    text = obs.get("text", "")
    cid = obs.get("id", "?")
    H = state.H
    leader = max(H, key=lambda h: h["weight"]) if H else None
    leader_id = leader["id"] if leader else None
    convergence_active = any(t["kind"] == "convergence" for t in state.T)
    no_answer = _no_answer_id(H)
    candidate_hyps = _candidate_ids(H)
    h_specific = candidate_hyps[0] if candidate_hyps else None
    h_general = candidate_hyps[1] if len(candidate_hyps) > 1 else None

    new = []

    # 1) Explicit minimum-version phrase ("версию Python не ниже 3.10")
    for m in VERSION_MIN_PHRASE_RE.finditer(text):
        new.append({
            "from": cid,
            "verbatim": m.group(0),
            "value": m.group(1),
            "finding": (f"explicit minimum-version phrase: "
                        f"'{m.group(0).strip()}' -> {m.group(1)}"),
            "evidence_verdict": "candidate",
            "pattern_class": "version_with_min_phrase",
            "links_to_Ex": True,
            "supports_H": [h_specific] if h_specific else [],
            "weakens_H": [h_general, no_answer] if (h_general and no_answer) else [],
            "opposes_H": [no_answer] if no_answer else [],
        })

    # 2) Versioned command (pythonN.M)
    for m in VERSIONED_CMD_RE.finditer(text):
        new.append({
            "from": cid,
            "verbatim": m.group(0),
            "value": m.group(1),
            "finding": (f"versioned python command: '{m.group(0)}' "
                        f"-> minor {m.group(1)}"),
            "evidence_verdict": "candidate",
            "pattern_class": "versioned_command",
            "links_to_Ex": True,
            "supports_H": [h_specific] if h_specific else [],
            "weakens_H": [no_answer] if no_answer else [],
            "opposes_H": [no_answer] if no_answer else [],
        })

    # 3) Generic python3 command (no minor) — symmetric between
    #    h_specific and h_general
    for m in PYTHON3_CMD_RE.finditer(text):
        new.append({
            "from": cid,
            "verbatim": m.group(0),
            "finding": (f"generic 'python3' command: '{m.group(0)}' "
                        "— constrains to Python 3.x but not specific minor"),
            "evidence_verdict": "weak_candidate",
            "pattern_class": "python3_command",
            "links_to_Ex": False,
            "supports_H": [h_specific, h_general] if (h_specific and h_general) else [],
            "weakens_H": [],
            "opposes_H": [],
        })

    # 4) Fallback — chunk has none of the above
    if not new:
        if convergence_active and leader_id == no_answer:
            verdict = "absent_confirming_leader"
            note = f"another empty chunk after {no_answer} dominant"
        else:
            verdict = "absent_extending_gap"
            note = "no version info found"
        new.append({
            "from": cid,
            "finding": (f"no version markers; topic={_sniff_topic(text)}; "
                        f"{note}"),
            "evidence_verdict": verdict,
            "pattern_class": "no_marker",
            "links_to_Ex": False,
            "supports_H": [no_answer] if no_answer else [],
            "weakens_H": candidate_hyps,
            "opposes_H": [],
        })

    return state.K + new


def _update_what_pip(state: "ThoughtState", obs: dict) -> list:
    """Q2-class extractor: which two external Python modules are
    pip-installed in setup. Each `pip install <name>` produces one
    K entry (so a single chunk with two install commands yields two
    K entries — same pattern_class). A bare `pip` mention without a
    module name is a separate (much weaker) class.
    """
    text = obs.get("text", "")
    cid = obs.get("id", "?")
    H = state.H
    leader = max(H, key=lambda h: h["weight"]) if H else None
    leader_id = leader["id"] if leader else None
    convergence_active = any(t["kind"] == "convergence" for t in state.T)
    no_answer = _no_answer_id(H)
    candidate_hyps = _candidate_ids(H)
    h_pair = candidate_hyps[0] if candidate_hyps else None

    new = []

    # 1) `pip install <module>` — strong differentiating evidence
    for m in PIP_INSTALL_MODULE_RE.finditer(text):
        new.append({
            "from": cid,
            "verbatim": m.group(0),
            "value": m.group(1),
            "finding": (f"pip install command names module '{m.group(1)}' "
                        "in setup context — direct candidate piece"),
            "evidence_verdict": "candidate",
            "pattern_class": "pip_install_with_module",
            "links_to_Ex": True,
            "supports_H": [h_pair] if h_pair else [],
            "weakens_H": [no_answer] if no_answer else [],
            "opposes_H": [no_answer] if no_answer else [],
        })

    # 2) Bare pip mention without specific module names — weak signal
    #    that pip-context exists but no list yet
    if not new and PIP_MENTION_RE.search(text):
        new.append({
            "from": cid,
            "finding": ("pip mentioned in setup context but no module names "
                        "given — corpus discusses pip but list isn't here"),
            "evidence_verdict": "weak_candidate",
            "pattern_class": "pip_mention_no_modules",
            "links_to_Ex": False,
            "supports_H": [],   # neither favors h1 nor h2 specifically
            "weakens_H": [no_answer] if no_answer else [],
            "opposes_H": [],
        })

    # 3) Fallback: nothing pip-related
    if not new:
        if convergence_active and leader_id == no_answer:
            verdict = "absent_confirming_leader"
            note = f"another empty chunk after {no_answer} dominant"
        else:
            verdict = "absent_extending_gap"
            note = "no pip / module info found"
        new.append({
            "from": cid,
            "finding": (f"no pip context, no module names; "
                        f"topic={_sniff_topic(text)}; {note}"),
            "evidence_verdict": verdict,
            "pattern_class": "no_marker",
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
    """Pattern-class aware aggregation. Same-class repetition produces
    diminishing returns for candidate H (1.0, 0.3, 0.1, 0.0). For the
    no_answer H, support stays linear: each additional empty chunk is
    additional evidence the corpus doesn't contain the answer.

    Non-disambiguating classes (e.g., name_in_url, anonymous_attribution
    on Q7) contribute ZERO directly to any H — they only generate
    un_disambiguating tension via recompute_tensions.

    Weakening from candidate-weakens stays linear (each new "no
    answer here" makes the candidate less plausible)."""
    from collections import defaultdict
    H = state.H
    K = state.K
    T = state.T
    convergence_active = any(t["kind"] == "convergence" for t in T)
    leader_id = _leader_id(H)

    def _dim_candidate(n: int) -> float:
        if n <= 0: return 0.0
        if n == 1: return 1.0
        if n == 2: return 0.3
        if n == 3: return 0.1
        return 0.0

    out = []
    for h in H:
        hid = h["id"]
        base = h.get("_base", h["weight"])
        step_initial = h.get("_step_initial", h["weight"])
        is_no_answer = h.get("_role") == "no_answer"

        support_classes: dict[str, int] = defaultdict(int)
        weaken_classes: dict[str, int] = defaultdict(int)
        for k in K:
            klass = k.get("pattern_class", "_unknown")
            class_meta = PATTERN_CLASSES.get(klass, {"is_disambiguating": True,
                                                       "support_strength": 0.10})
            if hid in k.get("supports_H", []):
                if class_meta.get("is_disambiguating", True):
                    support_classes[klass] += 1
                # non-disambiguating: skip; surfaces in T instead
            if hid in k.get("weakens_H", []):
                weaken_classes[klass] += 1

        # Support contribution
        support = 0.0
        for klass, n in support_classes.items():
            strength = PATTERN_CLASSES.get(klass, {}).get("support_strength", 0.10)
            if is_no_answer:
                support += strength * n   # linear: each new empty chunk adds
            else:
                support += strength * _dim_candidate(n)   # diminishing

        # Weakening: linear for candidates, irrelevant for no_answer
        weaken = 0.0 if is_no_answer else sum(0.05 * n for n in weaken_classes.values())

        # opposed (kept for backward-compat with verdict 'candidate'
        # which sets opposes_H = [no_answer])
        opposed = sum(1 for k in K if hid in k.get("opposes_H", []))
        oppose_pull = 0.10 * opposed

        target = max(0.0, min(1.0,
            base + support - weaken - (oppose_pull if is_no_answer else 0),
        ))

        # status
        if convergence_active and hid != leader_id:
            status = "fading"
        elif target > step_initial + 0.005:
            status = "growing"
        elif target < step_initial - 0.005:
            status = "weakening"
        elif (weaken_classes and any(
                hid in k.get("supports_H", []) and k.get("evidence_verdict") == "candidate"
                for k in K)):
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

    # un_disambiguating: each non-disambiguating pattern_class present
    # in K becomes its own tension, recording which H it would have
    # supported symmetrically. Deduplicated by class+H-set.
    from collections import defaultdict
    non_dis: dict[str, set] = defaultdict(set)
    for k in K:
        klass = k.get("pattern_class", "")
        if not PATTERN_CLASSES.get(klass, {}).get("is_disambiguating", True):
            non_dis[klass].update(k.get("supports_H", []))
    for klass, h_set in non_dis.items():
        T.append({
            "kind": "un_disambiguating",
            "what": (f"pattern_class '{klass}' supports {sorted(h_set)} "
                      "symmetrically — no direct H contribution; "
                      "ambiguity recorded as tension"),
            "severity": "MEDIUM",
            "klass": klass,
            "between": sorted(h_set),
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

    # Capture ALL K entries added during this step (one chunk can produce
    # multiple findings — Q1 step 1 produces 3 from pb_intro_004 alone).
    new_in_this_step = work.K[len(state.K):]
    return ThoughtState(
        G=state.G, Ex=state.Ex,
        K=work.K, H=work.H, T=work.T, E=new_E,
        history=state.history + [{
            "obs_id": obs.get("id"),
            "K_size": len(work.K),
            "K_added_this_step": new_in_this_step,
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
            "extractor_pack": "when_publication_date",
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
            "extractor_pack": "who_authorship",
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


# ---------------- initial_state for Q1 (no audit peeking) ----------------

def initial_state_q1() -> ThoughtState:
    """Q1 'Какую минимальную версию Python требует книга?' — first parse
    without peeking at audit. Honest readings:

      h1 (h_specific): book states a specific minor version (e.g. 3.10)
      h2 (h_general):  book says Python 3 generally, no specific minor
      h3 (no_answer):  no version requirement stated in active corpus

    Q1 is a Q-known-hit candidate in RVP — chosen for the third spike
    because it should have CORROBORATIVE evidence from different
    pattern_classes pointing at the same answer. The spike does not
    consult audit ground-truth; it tests whether the structure
    (pattern_class + diminishing) handles corroboration cleanly."""
    return ThoughtState(
        G={
            "intent": "what",
            "extractor_pack": "what_python_version",
            "target_entity": "minimum Python version",
            "target_relation": "required by the book",
            "question": "Какую минимальную версию Python требует книга?",
        },
        Ex={
            "type": "version_number (X.Y form)",
            "formats": ["X.Y", "X.Y.Z"],
            "must_link_to": ["Python", "minimum/required/'не ниже'"],
            "forbidden": [
                "ISBN-shaped digits",
                "year-shaped tokens (4-digit)",
                "problem-data digits in code examples",
            ],
        },
        H=[
            {"id": "h1", "_role": "candidate",
             "reading": "specific minor version stated (e.g. 3.10)",
             "_base": 0.30, "weight": 0.30, "status": "stable"},
            {"id": "h2", "_role": "candidate",
             "reading": "Python 3 generally, no specific minor",
             "_base": 0.30, "weight": 0.30, "status": "stable"},
            {"id": "h3", "_role": "no_answer",
             "reading": "no version requirement stated in active corpus",
             "_base": 0.40, "weight": 0.40, "status": "stable"},
        ],
        K=[],
        T=[],
        E={"progress": 0.0, "kind": "initial",
           "note": "before any observation"},
        history=[],
    )


# ---------------- initial_state for Q2 (no audit peeking) ----------------

def initial_state_q2() -> ThoughtState:
    """Q2 'Какие два внешних Python-модуля устанавливаются через pip
    согласно подготовке среды?' — fourth spike target.

    The question presupposes a specific pair exists; the system's
    job is to find them. Honest readings:

      h1: a specific named pair stated together in setup section
      h2: multiple modules mentioned scattered across corpus
          (no canonical pair / setup list)
      h3: no answer present in active corpus

    Plural-answer structure is new vs Q1/Q7/Q22 — each piece of the
    pair is a separate K entry. Whether diminishing-per-class breaks
    or holds for 'two pieces of one answer' is part of what this run
    tests.
    """
    return ThoughtState(
        G={
            "intent": "what",
            "extractor_pack": "what_pip_modules",
            "target_entity": "pair of pip-installed external modules",
            "target_relation": "named in setup section",
            "question": ("Какие два внешних Python-модуля устанавливаются "
                          "через pip согласно подготовке среды?"),
        },
        Ex={
            "type": "pair of module names",
            "formats": ["pip install X (twice)", "X и Y", "modules: X, Y"],
            "must_link_to": ["pip context", "module names"],
            "forbidden": [
                "standard library names (os, sys, json, etc.)",
                "IDE names (PyCharm, VS Code, IDLE)",
                "task-specific function names",
                "Python itself as 'module'",
            ],
        },
        H=[
            {"id": "h1", "_role": "candidate",
             "reading": "specific named pair stated in setup section",
             "_base": 0.35, "weight": 0.35, "status": "stable"},
            {"id": "h2", "_role": "candidate",
             "reading": "modules scattered across corpus, no canonical list",
             "_base": 0.25, "weight": 0.25, "status": "stable"},
            {"id": "h3", "_role": "no_answer",
             "reading": "no answer present in active corpus",
             "_base": 0.40, "weight": 0.40, "status": "stable"},
        ],
        K=[],
        T=[],
        E={"progress": 0.0, "kind": "initial",
           "note": "before any observation"},
        history=[],
    )


# Q2 retrieve order (TF-IDF top-4): pb_intro_006 (0.51), pb_intro_004
# (0.173), pb_intro_007 (0.094), pb_t02_001 (0.063).
Q2_CHUNKS = [
    {
        "id": "pb_intro_006",
        "text": (
            "В нескольких задачах используются внешние Python-библиотеки, "
            "устанавливаемые через менеджер пакетов pip. Проверить наличие "
            "pip: `python -m pip --version` (или python3 -m pip --version, "
            "в соответствии с тем, как у пользователя называется python). "
            "Используемые в книге внешние модули устанавливаются командами:"
            "\n  python -m pip install pygame"
            "\n  python -m pip install PythonTurtle"
            "\nСсылка на документацию pip: docs.python.org/3/installing/"
            "index.html."
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
        "id": "pb_t02_001",
        "text": (
            "Задача 2. Определить функцию sum_if_less_than_fifty, "
            "принимающую два параметра num_one и num_two (оба int). "
            "Функция должна возвращать сумму, если она меньше 50, или "
            "None, если сумма >= 50. Заготовка кода: "
            "def sum_if_less_than_fifty(num_one: int, num_two: int) "
            "-> int | None: # ваша реализация. "
            "Примеры: 20+20=40 -> 40; 20+30=50 -> None."
        ),
    },
]


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


# Q1 retrieve order (TF-IDF top-4): pb_intro_004 (0.24), pb_intro_006
# (0.171), pb_intro_003 (0.148), pb_intro_005 (0.08).
Q1_CHUNKS = [
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
    {
        "id": "pb_intro_006",
        "text": (
            "В нескольких задачах используются внешние Python-библиотеки, "
            "устанавливаемые через менеджер пакетов pip. Проверить наличие "
            "pip: `python -m pip --version` (или python3 -m pip --version, "
            "в соответствии с тем, как у пользователя называется python). "
            "Используемые в книге внешние модули устанавливаются командами:"
            "\n  python -m pip install pygame"
            "\n  python -m pip install PythonTurtle"
            "\nСсылка на документацию pip: docs.python.org/3/installing/"
            "index.html."
        ),
    },
    {
        "id": "pb_intro_003",
        "text": (
            "Структура книги. Книга состоит из двух частей: «Серьезные "
            "задачи» и «Шуточные задачи». В первой части — 50 (плюс "
            "несколько дополнительных) задач, расположенных по нарастанию "
            "сложности. Для решения задач необходимо владеть основами "
            "Python: переменные, условные предложения, циклы, функции."
        ),
    },
    {
        "id": "pb_intro_005",
        "text": (
            "Рекомендованные редакторы кода для работы с книгой: IDLE "
            "(входит в комплект поставки Python), Visual Studio Code "
            "(code.visualstudio.com), PyCharm (jetbrains.com/pycharm). "
            "Для книги подойдёт любой; для дальнейшего изучения Python "
            "автор рекомендует более мощные IDE — VS Code или PyCharm."
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
        added = step.get("K_added_this_step") or [step["K_last"]]
        if len(added) > 1:
            print(f"  noticed ({len(added)} findings):")
            for k in added:
                print(f"    [{k.get('pattern_class','?')}] "
                      f"{k.get('finding','?')[:90]}")
        else:
            kl = step["K_last"]
            print(f"  noticed: {kl.get('finding')}")
            print(f"  -> verdict: {kl.get('evidence_verdict')} "
                  f"(class={kl.get('pattern_class','?')})")
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

    which = sys.argv[1] if len(sys.argv) > 1 else "q1"
    if which == "q22":
        s = initial_state_q22()
        chunks = CHUNKS
    elif which == "q7":
        s = initial_state_q7()
        chunks = Q7_CHUNKS
    elif which == "q1":
        s = initial_state_q1()
        chunks = Q1_CHUNKS
    elif which == "q2":
        s = initial_state_q2()
        chunks = Q2_CHUNKS
    else:
        sys.exit(f"unknown question id: {which} (use q1, q2, q7, or q22)")

    for chunk in chunks:
        s = think_step(s, chunk)
    show(s)
