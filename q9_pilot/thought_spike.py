"""thought_spike.py — single-file ThoughtState skeleton.

Spike, not integration. Hand-fed chunks, no retrieve, no benchmark.
Runs over Q22 (when, no_answer), Q7 (who, ambiguous), Q1 (what,
single-answer hit), Q2 (what, plural-answer hit).

This version implements STATE_AS_GRAPH §2-§4: K-entries with typed
pattern_class + within-category relations, T-entries with
back-references and active conditions, convergence as a graph
predicate (refuse/hit/stuck) rather than a threshold on one H.

Run: python thought_spike.py [q22|q7|q1|q2]

TODO/open questions (recorded in code, NOT solved here):
  - pattern_class assignment is currently regex-based and brittle;
    needs separate validation
  - K and T entry lifecycle: when a K-entry is added, can earlier
    K-entries be revised? Currently entries are append-only with
    relations set at insertion time
  - automatic detection of redundant_with / constituent_of relations
    between K-entries — currently EXPLICIT in initial_state /
    extractor logic, with no inference rule
  - automatic derivation of remaining_pattern_classes for Ex —
    currently hardcoded per question in initial_state
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------- Typed structures (STATE_AS_GRAPH §2-§3) ----------------

@dataclass(frozen=True)
class PatternClass:
    """A category of K-evidence. Carries semantics that drive
    aggregation and tension generation. Defined once per question-
    family and referenced by name from K-entries."""
    name: str
    is_disambiguating: bool
    support_strength: float


@dataclass
class KEntry:
    """One piece of evidence pulled from one chunk. Categorized by
    pattern_class; carries explicit references to which H it
    supports/weakens/opposes and to other K-entries (within-category
    relations)."""
    chunk_id: str
    pattern_class: PatternClass
    finding: str
    # H-vector references
    supports_H: list = field(default_factory=list)
    weakens_H: list = field(default_factory=list)
    opposes_H: list = field(default_factory=list)
    # within-category relations to other K-entries (by integer index in K)
    redundant_with: list = field(default_factory=list)
    constituent_of: str = ""   # group label; entries sharing label compose
                                # one structured answer
    # extras for tracing
    verbatim: str = ""
    value: Any = None
    links_to_Ex: bool = False


@dataclass
class TEntry:
    """A noticed tension. Carries back-references to its origin in K
    and the H-set it concerns. The active_condition predicate is
    re-evaluated on each recompute; when it returns False, the
    tension is retired (does not appear in subsequent T)."""
    kind: str                       # gap, drift, type_mismatch, un_disambiguating
    severity: str
    description: str
    # back-references (STATE_AS_GRAPH §3)
    triggered_by_pattern_class: list = field(default_factory=list)
    concerns_H_set: list = field(default_factory=list)
    # active_condition takes the current state and returns True if
    # tension is still relevant. If False, T-entry is retired.
    active_condition: Callable | None = None


# ---------------- ThoughtState ----------------

@dataclass
class ThoughtState:
    G: dict = field(default_factory=dict)        # what we understood
    Ex: dict = field(default_factory=dict)       # evidence contract
    H: list = field(default_factory=list)        # competing readings
    K: list = field(default_factory=list)        # accumulated KEntry instances
    T: list = field(default_factory=list)        # active TEntry instances
    E: dict = field(default_factory=dict)        # last-step self-eval
    history: list = field(default_factory=list)  # move tape


# ---------------- pattern_class registry ----------------

# Each PatternClass instance is referenced by name from KEntry.pattern_class.
# is_disambiguating drives whether the class contributes to H directly
# (True) or only via T un_disambiguating tension (False).
PATTERN_CLASSES: dict[str, PatternClass] = {
    # when-intent
    "raw_year_in_prose":       PatternClass("raw_year_in_prose",       True,  0.20),
    "year_in_python_version":  PatternClass("year_in_python_version",  True,  0.10),
    "numeric_off_topic":       PatternClass("numeric_off_topic",       True,  0.10),
    # who-intent
    "name_with_relation":      PatternClass("name_with_relation",      True,  0.20),
    "name_in_url":             PatternClass("name_in_url",             False, 0.10),
    "anonymous_attribution":   PatternClass("anonymous_attribution",   False, 0.10),
    "publisher_org":           PatternClass("publisher_org",           True,  0.10),
    # what-intent (Q1 — version question)
    "version_with_min_phrase": PatternClass("version_with_min_phrase", True,  0.20),
    "versioned_command":       PatternClass("versioned_command",       True,  0.15),
    "python3_command":         PatternClass("python3_command",         False, 0.10),
    # what-intent (Q2 — pip modules question)
    "pip_install_with_module": PatternClass("pip_install_with_module", True,  0.20),
    "pip_mention_no_modules":  PatternClass("pip_mention_no_modules",  True,  0.05),
    # shared
    "no_marker":               PatternClass("no_marker",               True,  0.10),
}


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


# ---------------- helpers ----------------

def _no_answer_id(H: list) -> str | None:
    return next((h["id"] for h in H if h.get("_role") == "no_answer"), None)


def _candidate_ids(H: list) -> list:
    return [h["id"] for h in H if h.get("_role") != "no_answer"]


def _leader_id(H: list) -> str | None:
    return None if not H else max(H, key=lambda h: h["weight"])["id"]


def _make_K(chunk_id: str, pattern_class_name: str, finding: str,
             *, supports_H=None, weakens_H=None, opposes_H=None,
             redundant_with=None, constituent_of: str = "",
             verbatim: str = "", value=None, links_to_Ex: bool = False) -> KEntry:
    """KEntry constructor that resolves pattern_class name to instance."""
    pc = PATTERN_CLASSES.get(pattern_class_name)
    if pc is None:
        raise KeyError(f"unknown pattern_class: {pattern_class_name}")
    return KEntry(
        chunk_id=chunk_id,
        pattern_class=pc,
        finding=finding,
        supports_H=list(supports_H or []),
        weakens_H=list(weakens_H or []),
        opposes_H=list(opposes_H or []),
        redundant_with=list(redundant_with or []),
        constituent_of=constituent_of,
        verbatim=verbatim,
        value=value,
        links_to_Ex=links_to_Ex,
    )


# ---------------- update_knowledge (dispatch by extractor_pack) ----------------

def update_knowledge(state: "ThoughtState", obs: dict) -> list:
    """Dispatch by G.extractor_pack. Returns a NEW K (list of KEntry
    instances) — state.K extended with whatever this observation
    yields. Each extractor is responsible for setting pattern_class
    plus within-category relations (constituent_of, redundant_with)
    on each KEntry it produces."""
    pack = state.G.get("extractor_pack") or state.G.get("intent")
    if pack in ("when", "when_publication_date"):
        return _update_when(state, obs)
    if pack in ("who", "who_authorship"):
        return _update_who(state, obs)
    if pack in ("what", "what_python_version"):
        return _update_what_version(state, obs)
    if pack == "what_pip_modules":
        return _update_what_pip(state, obs)
    raise KeyError(f"no extractor for pack={pack!r}")


def _update_when(state: "ThoughtState", obs: dict) -> list:
    """Q22-class extractor: years, Python versions, URL paths."""
    text = obs.get("text", "")
    cid = obs.get("id", "?")
    H = state.H
    no_answer = _no_answer_id(H)
    candidate_hyps = _candidate_ids(H)

    new: list[KEntry] = []
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
                new.append(_make_K(
                    cid, "year_in_python_version",
                    finding=(f"date-shaped token '{y_str}' inside Python "
                              "version — type-rejected"),
                    verbatim=y_str,
                    supports_H=[no_answer] if no_answer else [],
                ))
            else:
                new.append(_make_K(
                    cid, "raw_year_in_prose",
                    finding=f"raw year '{y}' in prose context — candidate",
                    verbatim=y_str, value=y, links_to_Ex=True,
                    supports_H=candidate_hyps,
                    weakens_H=[no_answer] if no_answer else [],
                    opposes_H=[no_answer] if no_answer else [],
                ))
    elif py_versions or PATH_DIGIT_RE.search(text):
        marker = (f"Python version {py_versions[0]}" if py_versions
                   else "URL path digits")
        new.append(_make_K(
            cid, "numeric_off_topic",
            finding=(f"numeric markers ({marker}) but type-incompatible "
                      f"with Ex.type=date — decoys for {candidate_hyps}"),
            supports_H=[no_answer] if no_answer else [],
            weakens_H=candidate_hyps,
        ))
    else:
        new.append(_make_K(
            cid, "no_marker",
            finding=(f"no date markers; topic={_sniff_topic(text)}; "
                      "expected date binding, none found"),
            supports_H=[no_answer] if no_answer else [],
            weakens_H=candidate_hyps,
        ))
    return state.K + new


def _update_who(state: "ThoughtState", obs: dict) -> list:
    """Q7-class extractor: person names, author keywords, URL usernames,
    publisher orgs."""
    text = obs.get("text", "")
    cid = obs.get("id", "?")
    H = state.H
    no_answer = _no_answer_id(H)
    candidate_hyps = _candidate_ids(H)
    h_single = candidate_hyps[0] if candidate_hyps else None

    new: list[KEntry] = []

    # 1) URL containing a Latin CamelCase name
    url_m = URL_RE.search(text)
    if url_m:
        url_span = url_m.group(0)
        latin_in_url = LATIN_CAMEL_RE.search(url_span)
        if latin_in_url:
            name = latin_in_url.group(0)
            new.append(_make_K(
                cid, "name_in_url",
                finding=(f"name-shaped token '{name}' inside URL "
                          f"({url_span[:50]}...) — could be author, could "
                          "be username; ambiguous, splits support"),
                verbatim=name,
                supports_H=[h_single, no_answer] if (h_single and no_answer) else [],
            ))

    # 2) Author keyword present
    kw_m = AUTHOR_KW_RE.search(text)
    if kw_m:
        after = text[kw_m.end():kw_m.end() + 60]
        cyr_name = NAME_CYR_RE.search(after)
        if cyr_name and cyr_name.group(0).strip().lower() not in (
            "программист", "разработчик", "автор", "пользоват",
        ):
            # Real candidate: keyword + Cyrillic name in proximity
            new.append(_make_K(
                cid, "name_with_relation",
                finding=(f"'{kw_m.group(0)}' followed by named entity "
                          f"'{cyr_name.group(0)}' — explicit attribution"),
                verbatim=cyr_name.group(0), links_to_Ex=True,
                supports_H=[h_single] if h_single else [],
                weakens_H=[no_answer] if no_answer else [],
                opposes_H=[no_answer] if no_answer else [],
            ))
        else:
            # Anonymous self-reference: 'автор' without follow-up name.
            # Symmetric between h_single and no_answer (non-disambig).
            new.append(_make_K(
                cid, "anonymous_attribution",
                finding=(f"'{kw_m.group(0)}' present but no named entity "
                          "follows — anonymous self-reference"),
                supports_H=[h_single, no_answer] if (h_single and no_answer) else [],
            ))

    # 3) Publisher organization (without authorship verb)
    if not new:
        org_m = ORG_CYR_RE.search(text)
        publisher_context = (
            "издательств" in text.lower()
            or "пресс" in text.lower()
            or "press" in text.lower()
        )
        if org_m and publisher_context:
            new.append(_make_K(
                cid, "publisher_org",
                finding=(f"organization '{org_m.group(0)}' in publisher "
                          "context — publishing is not authoring"),
                verbatim=org_m.group(0),
                supports_H=[no_answer] if no_answer else [],
                weakens_H=candidate_hyps,
            ))

    # 4) Fallback: nothing relevant found
    if not new:
        new.append(_make_K(
            cid, "no_marker",
            finding=(f"no name, no author keyword; "
                      f"topic={_sniff_topic(text)}"),
            supports_H=[no_answer] if no_answer else [],
            weakens_H=candidate_hyps,
        ))

    return state.K + new


def _update_what_version(state: "ThoughtState", obs: dict) -> list:
    """Q1-class extractor: minimum Python version. A single chunk can
    produce multiple KEntries (min-phrase + versioned-cmd + python3-cmd)."""
    text = obs.get("text", "")
    cid = obs.get("id", "?")
    H = state.H
    no_answer = _no_answer_id(H)
    candidate_hyps = _candidate_ids(H)
    h_specific = candidate_hyps[0] if candidate_hyps else None
    h_general = candidate_hyps[1] if len(candidate_hyps) > 1 else None

    new: list[KEntry] = []

    for m in VERSION_MIN_PHRASE_RE.finditer(text):
        new.append(_make_K(
            cid, "version_with_min_phrase",
            finding=(f"explicit minimum-version phrase: "
                      f"'{m.group(0).strip()}' -> {m.group(1)}"),
            verbatim=m.group(0), value=m.group(1), links_to_Ex=True,
            supports_H=[h_specific] if h_specific else [],
            weakens_H=[h for h in (h_general, no_answer) if h],
            opposes_H=[no_answer] if no_answer else [],
        ))

    for m in VERSIONED_CMD_RE.finditer(text):
        new.append(_make_K(
            cid, "versioned_command",
            finding=(f"versioned python command: '{m.group(0)}' "
                      f"-> minor {m.group(1)}"),
            verbatim=m.group(0), value=m.group(1), links_to_Ex=True,
            supports_H=[h_specific] if h_specific else [],
            weakens_H=[no_answer] if no_answer else [],
            opposes_H=[no_answer] if no_answer else [],
        ))

    for m in PYTHON3_CMD_RE.finditer(text):
        new.append(_make_K(
            cid, "python3_command",
            finding=(f"generic 'python3' command: '{m.group(0)}' "
                      "— Python 3.x but not specific minor"),
            verbatim=m.group(0),
            supports_H=[h_specific, h_general] if (h_specific and h_general) else [],
        ))

    if not new:
        new.append(_make_K(
            cid, "no_marker",
            finding=(f"no version markers; topic={_sniff_topic(text)}"),
            supports_H=[no_answer] if no_answer else [],
            weakens_H=candidate_hyps,
        ))

    return state.K + new


def _update_what_pip(state: "ThoughtState", obs: dict) -> list:
    """Q2-class extractor: pair of pip-installed modules. Multiple
    `pip install <name>` entries from the same chunk are marked as
    constituents of the same answer (constituent_of='pip_setup_pair'),
    so revise_hypotheses gives them full contribution per piece
    instead of treating the second as a redundant repeat."""
    text = obs.get("text", "")
    cid = obs.get("id", "?")
    H = state.H
    no_answer = _no_answer_id(H)
    candidate_hyps = _candidate_ids(H)
    h_pair = candidate_hyps[0] if candidate_hyps else None

    new: list[KEntry] = []

    pip_install_matches = list(PIP_INSTALL_MODULE_RE.finditer(text))

    # Multiple pip-install commands in one chunk are constituents of
    # the same setup-pair group. Single one — no group label.
    constituency_label = (
        "pip_setup_pair" if len(pip_install_matches) >= 2 else ""
    )
    for m in pip_install_matches:
        new.append(_make_K(
            cid, "pip_install_with_module",
            finding=(f"pip install command names module '{m.group(1)}' "
                      "in setup context"),
            verbatim=m.group(0), value=m.group(1), links_to_Ex=True,
            supports_H=[h_pair] if h_pair else [],
            weakens_H=[no_answer] if no_answer else [],
            opposes_H=[no_answer] if no_answer else [],
            constituent_of=constituency_label,
        ))

    if not new and PIP_MENTION_RE.search(text):
        new.append(_make_K(
            cid, "pip_mention_no_modules",
            finding=("pip mentioned in setup context but no module names "
                      "given — corpus discusses pip, list not here"),
            supports_H=[],
            weakens_H=[no_answer] if no_answer else [],
        ))

    if not new:
        new.append(_make_K(
            cid, "no_marker",
            finding=(f"no pip context, no module names; "
                      f"topic={_sniff_topic(text)}"),
            supports_H=[no_answer] if no_answer else [],
            weakens_H=candidate_hyps,
        ))

    return state.K + new


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
    """Aggregation reads pattern_class structure (categories) AND
    within-category relations (constituent_of, redundant_with) on KEntry
    instances directly. STATE_AS_GRAPH §2:

    Per H, per pattern_class group of supports:
      - if all entries share a non-empty constituent_of label →
        FULL contribution per piece (parts of one answer compose, not
        repeat)
      - else (default — same class, no constituency) → diminishing
        per repeated entry (1.0, 0.3, 0.1, 0)

    Different classes always stack at full per-class contribution.
    Non-disambiguating classes contribute ZERO directly (their effect
    surfaces in T un_disambiguating).

    For no_answer-role H, support stays linear (each new empty chunk
    is genuine new evidence). Weakening stays linear for candidates.
    """
    from collections import defaultdict
    H = state.H
    K = state.K
    leader_id_now = _leader_id(H)

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

        # Group supporting entries by pattern_class name
        supports_by_class: dict[str, list[KEntry]] = defaultdict(list)
        weakens_by_class: dict[str, int] = defaultdict(int)
        opposed_total = 0
        for k in K:
            klass = k.pattern_class
            if hid in k.supports_H and klass.is_disambiguating:
                supports_by_class[klass.name].append(k)
            if hid in k.weakens_H:
                weakens_by_class[klass.name] += 1
            if hid in k.opposes_H:
                opposed_total += 1

        # Support contribution per class (within-category structure)
        support = 0.0
        for klass_name, entries in supports_by_class.items():
            pc = PATTERN_CLASSES[klass_name]
            strength = pc.support_strength
            # Constituency check: do all entries share the same non-empty
            # constituent_of label? If yes — full per piece.
            labels = {e.constituent_of for e in entries if e.constituent_of}
            all_constituent = (
                len(labels) == 1
                and all(e.constituent_of for e in entries)
            )
            if is_no_answer:
                support += strength * len(entries)   # linear regardless
            elif all_constituent:
                support += strength * len(entries)   # constituency: full per piece
            else:
                support += strength * _dim_candidate(len(entries))

        weaken = 0.0 if is_no_answer else sum(
            0.05 * n for n in weakens_by_class.values()
        )

        target = max(0.0, min(1.0,
            base + support - weaken - (0.10 * opposed_total if is_no_answer else 0),
        ))

        # status (single axis — leadership/2D split is left as local fix
        # per STATE_AS_GRAPH "what this is not")
        if target > step_initial + 0.005:
            status = "growing"
        elif target < step_initial - 0.005:
            status = "weakening"
        else:
            status = "stable"

        out.append({**h, "weight": round(target, 3), "status": status})
    return out


# ---------------- recompute_tensions ----------------

def recompute_tensions(state: "ThoughtState") -> list:
    """Emit TEntry instances with back-references and active_condition
    predicates (STATE_AS_GRAPH §3). T-entries are not accumulated; on
    each call, only those whose active_condition currently returns
    True are emitted. Resolution is therefore a structural property,
    not a separate code branch — when the condition that triggered a
    T-entry no longer holds, the entry simply isn't re-emitted.

    Convergence is no longer a T-entry — it's computed by
    compute_state_predicate as a property of the whole state graph
    (STATE_AS_GRAPH §4).
    """
    from collections import defaultdict
    K = state.K
    Ex = state.Ex
    T: list[TEntry] = []

    # gap — active while no K-entry links to Ex
    if any(_gap_condition_holds(state) for _ in (None,)) and len(K) >= 1:
        T.append(TEntry(
            kind="gap",
            severity="HIGH" if len(K) >= 3 else "MEDIUM",
            description=(f"Ex.must_link_to {Ex.get('must_link_to')} "
                          f"unsatisfied after {len(K)} observations"),
            triggered_by_pattern_class=[],   # gap is Ex-anchored, not class-driven
            concerns_H_set=[h["id"] for h in state.H],
            active_condition=_gap_condition_holds,
        ))

    # un_disambiguating — one per non-disambiguating pattern_class
    # present in K, with H-set = union of supports_H from those entries.
    # active_condition: no DISAMBIGUATING K-entry exists whose
    # supports_H is a strict subset of this H-set (i.e. no
    # differentiating evidence has arrived).
    non_dis: dict[str, set] = defaultdict(set)
    for k in K:
        if not k.pattern_class.is_disambiguating:
            non_dis[k.pattern_class.name].update(k.supports_H)
    for klass_name, h_set in non_dis.items():
        h_set_list = sorted(h_set)
        condition = _make_un_disambig_condition(h_set_list)
        if condition(state):
            T.append(TEntry(
                kind="un_disambiguating",
                severity="MEDIUM",
                description=(f"pattern_class '{klass_name}' supports "
                              f"{h_set_list} symmetrically — no direct "
                              "H contribution; ambiguity recorded"),
                triggered_by_pattern_class=[klass_name],
                concerns_H_set=h_set_list,
                active_condition=condition,
            ))

    # type_mismatch — exists K-entry of class 'year_in_python_version'
    rejects = [k for k in K
               if k.pattern_class.name == "year_in_python_version"]
    if rejects:
        T.append(TEntry(
            kind="type_mismatch",
            severity="MEDIUM",
            description=(f"{len(rejects)} year-shaped token(s) inside "
                          "Python-version context — Ex.forbidden hit"),
            triggered_by_pattern_class=["year_in_python_version"],
            concerns_H_set=[h["id"] for h in state.H if h.get("_role") != "no_answer"],
            active_condition=lambda s: any(
                k.pattern_class.name == "year_in_python_version" for k in s.K
            ),
        ))

    # drift — last 3 observations produced no candidate-class evidence
    if len(K) >= 3:
        recent = K[-3:]
        if all(not _is_candidate_class(k) for k in recent):
            T.append(TEntry(
                kind="drift",
                severity="INFORMATIONAL",
                description=("last 3 observations produced no candidate "
                              "evidence; possibility space narrowing"),
                triggered_by_pattern_class=[],
                concerns_H_set=[h["id"] for h in state.H],
                active_condition=lambda s: (
                    len(s.K) >= 3
                    and all(not _is_candidate_class(k) for k in s.K[-3:])
                ),
            ))

    return T


def _gap_condition_holds(state: "ThoughtState") -> bool:
    return not any(k.links_to_Ex for k in state.K)


def _is_candidate_class(k: KEntry) -> bool:
    """A K-entry counts as candidate-class evidence if its pattern_class
    is disambiguating AND it links to Ex (i.e. it's a real anchor, not
    a decoy or absence)."""
    return k.pattern_class.is_disambiguating and k.links_to_Ex


def _make_un_disambig_condition(h_set: list) -> Callable:
    """Create the active_condition predicate for an un_disambiguating
    T-entry on a specific H-set. The tension stays active as long as no
    disambiguating K-entry exists whose supports_H is a strict subset
    of this H-set (i.e. no differentiating evidence has yet arrived
    that singles out a member of the symmetric group)."""
    h_set_set = set(h_set)
    def _cond(state: "ThoughtState") -> bool:
        for k in state.K:
            if not k.pattern_class.is_disambiguating:
                continue
            supports = set(k.supports_H)
            if supports and supports.issubset(h_set_set) and supports != h_set_set:
                # found a disambiguating entry that supports a strict
                # subset of the symmetric H-set — symmetry broken
                return False
        return True
    return _cond


# ---------------- compute_state_predicate (STATE_AS_GRAPH §4) ----------------

def compute_state_predicate(state: "ThoughtState") -> str:
    """Returns one of: 'refuse', 'hit', 'stuck', 'continuing'.

    A graph-level predicate, not a threshold on one H. Reads the whole
    state — H configuration plus active T (which already encodes the
    'has any path to resolution' question via back-references and
    remaining_pattern_classes in Ex).

    refuse: no_answer-role H is leader by margin >= 0.15
    hit: candidate-role H is leader by margin >= 0.15 AND no active
         un_disambiguating tension concerns the leader's H-set
    stuck: an active un_disambiguating exists AND no remaining
         pattern_classes in Ex could resolve it (i.e. all relevant
         disambiguating classes have already arrived without breaking
         symmetry)
    continuing: anything else
    """
    H = state.H
    if not H:
        return "continuing"
    leader = max(H, key=lambda h: h["weight"])
    others = [h for h in H if h["id"] != leader["id"]]
    margin = leader["weight"] - max((h["weight"] for h in others), default=0.0)
    is_no_answer = leader.get("_role") == "no_answer"

    blocking_un_dis = [
        t for t in state.T
        if t.kind == "un_disambiguating" and leader["id"] in t.concerns_H_set
    ]

    if is_no_answer and margin >= 0.15:
        return "refuse"

    if (not is_no_answer) and margin >= 0.15 and not blocking_un_dis:
        return "hit"

    # stuck: active un_disambig + no remaining class can resolve
    un_dis_active = [t for t in state.T if t.kind == "un_disambiguating"]
    if un_dis_active:
        remaining = state.Ex.get("remaining_pattern_classes", [])
        could_resolve = False
        for cname in remaining:
            pc = PATTERN_CLASSES.get(cname)
            if pc is None:
                continue
            if not pc.is_disambiguating:
                continue
            # A disambiguating class that hasn't arrived yet COULD resolve
            seen = any(k.pattern_class.name == cname for k in state.K)
            if not seen:
                could_resolve = True
                break
        if not could_resolve:
            return "stuck"

    return "continuing"


# ---------------- self_evaluate ----------------

def self_evaluate(prev: ThoughtState, K: list, H: list, T: list,
                  obs: dict, predicate: str) -> dict:
    new_K_count = len(K) - len(prev.K)
    h_shift = sum(abs(h["weight"] - p["weight"])
                   for h, p in zip(H, prev.H))
    prev_T_keys = {(t.kind, t.severity) for t in prev.T}
    cur_T_keys = {(t.kind, t.severity) for t in T}
    opened = cur_T_keys - prev_T_keys
    closed = prev_T_keys - cur_T_keys

    if predicate == "refuse":
        no_answer = next((h for h in H if h.get("_role") == "no_answer"), None)
        leader_id = no_answer["id"] if no_answer else "?"
        return {"progress": 1.0, "kind": "convergence_refuse",
                "note": (f"{leader_id} (no_answer) dominant; refuse is the "
                          "resolved answer")}

    if predicate == "hit":
        leader = max(H, key=lambda h: h["weight"]) if H else None
        leader_id = leader["id"] if leader else "?"
        return {"progress": 1.0, "kind": "convergence_hit",
                "note": (f"{leader_id} (candidate) dominant by margin >=0.15 "
                          "and no blocking un_disambiguating; answer found")}

    if predicate == "stuck":
        return {"progress": 0.5, "kind": "convergence_stuck",
                "note": ("active un_disambiguating with no remaining "
                          "pattern_class that could resolve — system "
                          "acknowledges inability to pick a winner")}

    if new_K_count == 0:
        return {"progress": 0.0, "kind": "stagnant",
                "note": "observation produced no K change"}

    if h_shift >= 0.05:
        last_k = K[-1]
        klass = last_k.pattern_class
        no_answer = next((h for h in H if h.get("_role") == "no_answer"), None)
        no_answer_id = no_answer["id"] if no_answer else "?"
        if klass.is_disambiguating and last_k.links_to_Ex:
            return {"progress": round(h_shift, 3), "kind": "growth",
                    "note": (f"disambiguating {klass.name} "
                              f"({last_k.verbatim or '?'}) lifted candidates")}
        return {"progress": round(h_shift, 3), "kind": "narrowing",
                "note": (f"K grew with class={klass.name}; "
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
    """What 'stable' means: H weights+statuses + active T kind+H-set."""
    return (
        tuple((h["id"], h["weight"], h["status"]) for h in state.H),
        tuple((t.kind, tuple(t.concerns_H_set)) for t in state.T),
        len(state.K),
    )


def think_step(state: ThoughtState, obs: Any) -> ThoughtState:
    """Single observation; K-H-T iterate to fixed-point inside.

    Pass 0: ingest obs into K (extractor sets pattern_class + relations).
    Inner loop:
      - revise H reading K-with-relations
      - recompute T (active_condition predicates re-evaluated; tensions
        whose conditions no longer hold are not re-emitted = retired)
      - repeat until snapshot stable or MAX_INNER_ITERS
    After loop: compute_state_predicate reads whole state for
    refuse/hit/stuck/continuing.
    """
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
        new_H = revise_hypotheses(work)
        work = ThoughtState(
            G=work.G, Ex=work.Ex, K=work.K,
            H=new_H, T=work.T,
            E=work.E, history=work.history,
        )
        new_T = recompute_tensions(work)
        work = ThoughtState(
            G=work.G, Ex=work.Ex, K=work.K,
            H=work.H, T=new_T,
            E=work.E, history=work.history,
        )
        if _snapshot(work) == before:
            break

    predicate = compute_state_predicate(work)
    new_E = self_evaluate(state, work.K, work.H, work.T, obs, predicate)
    new_E["inner_iters"] = iters_run
    new_E["state_predicate"] = predicate

    # Detect retired tensions vs prior step: T-entries that were in the
    # PREVIOUS step's T but aren't in the new T are 'retired' — their
    # active_condition no longer holds.
    prev_T_keys = {(t.kind, tuple(sorted(t.concerns_H_set))) for t in state.T}
    cur_T_keys = {(t.kind, tuple(sorted(t.concerns_H_set))) for t in work.T}
    retired = sorted(prev_T_keys - cur_T_keys)

    new_in_this_step = work.K[len(state.K):]
    return ThoughtState(
        G=state.G, Ex=state.Ex,
        K=work.K, H=work.H, T=work.T, E=new_E,
        history=state.history + [{
            "obs_id": obs.get("id"),
            "K_size": len(work.K),
            "K_added_this_step": new_in_this_step,
            "K_last": work.K[-1] if work.K else None,
            "T_retired_this_step": retired,
            "H": [{"id": h["id"], "w": h["weight"], "s": h["status"]}
                  for h in work.H],
            "T": [{"kind": t.kind, "sev": t.severity, "what": t.description,
                   "concerns": list(t.concerns_H_set),
                   "triggered_by": list(t.triggered_by_pattern_class)}
                  for t in work.T],
            "E": new_E,
            "state_predicate": predicate,
            "inner_iters": iters_run,
        }],
    )


# ---------------- next_action ----------------

def next_action(state: ThoughtState) -> str:
    """Stub. State-predicate-aware: when the graph is in a converged
    configuration, propose the corresponding action. Else either name
    the most actionable tension or continue."""
    predicate = compute_state_predicate(state)
    if predicate == "refuse":
        no_answer = next(
            (h for h in state.H if h.get("_role") == "no_answer"), None,
        )
        if no_answer:
            return (f"refuse(reason=oop_signal_absent, "
                    f"backing_hypothesis={no_answer['id']}, "
                    f"weight={no_answer['weight']})")
    if predicate == "hit":
        leader = max(state.H, key=lambda h: h["weight"])
        return (f"answer(hypothesis={leader['id']}, "
                f"weight={leader['weight']})")
    if predicate == "stuck":
        un_dis = [t for t in state.T if t.kind == "un_disambiguating"]
        if un_dis:
            return (f"acknowledge_stuck(un_disambiguating "
                    f"between={un_dis[0].concerns_H_set})")
        return "acknowledge_stuck"

    severity_rank = {"HIGH": 3, "MEDIUM": 2, "INFORMATIONAL": 1}
    if state.T:
        worst = max(state.T, key=lambda t: severity_rank.get(t.severity, 0))
        return f"address_tension({worst.kind}, sev={worst.severity})"
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
            # remaining_pattern_classes — disambiguating classes the
            # corpus could still produce. For Q22 the discriminating
            # class would be raw_year_in_prose; if it never arrives we
            # can declare refuse (no_answer-leader path) without stuck
            "remaining_pattern_classes": ["raw_year_in_prose"],
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
            # remaining_pattern_classes — disambiguating class that
            # would resolve un_disambiguating tensions. For Q7 it's
            # name_with_relation. If it doesn't arrive while
            # un_disambig classes (name_in_url, anonymous_attribution)
            # accumulate AND the corpus is exhausted, we hit stuck.
            "remaining_pattern_classes": ["name_with_relation"],
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
            # remaining_pattern_classes — disambiguating classes that
            # would resolve un_disambiguating from python3_command.
            # version_with_min_phrase and versioned_command both
            # disambiguate between specific minor and any 3.x.
            "remaining_pattern_classes": [
                "version_with_min_phrase", "versioned_command",
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
            # remaining_pattern_classes for Q2 — pip_install_with_module
            # is THE disambiguating class for the pair. Once arrived
            # with constituent_of marker, h1 grows substantially.
            "remaining_pattern_classes": ["pip_install_with_module"],
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
        retired = step.get("T_retired_this_step") or []
        predicate = step.get("state_predicate", "continuing")
        print(f"--- step {i}: observed {step['obs_id']} "
              f"(inner={iters}, predicate={predicate}) ---")
        added = step.get("K_added_this_step") or ([step["K_last"]] if step["K_last"] else [])
        if len(added) > 1:
            print(f"  noticed ({len(added)} findings):")
            for k in added:
                pc_name = k.pattern_class.name if hasattr(k, "pattern_class") else "?"
                finding = k.finding if hasattr(k, "finding") else "?"
                cof = k.constituent_of if hasattr(k, "constituent_of") else ""
                cof_tag = f" [constituent_of='{cof}']" if cof else ""
                print(f"    [{pc_name}]{cof_tag} {finding[:90]}")
        elif added:
            kl = added[0]
            pc_name = kl.pattern_class.name if hasattr(kl, "pattern_class") else "?"
            finding = kl.finding if hasattr(kl, "finding") else "?"
            print(f"  noticed: {finding}")
            print(f"  -> class={pc_name}")
        if retired:
            for r in retired:
                print(f"  T_RETIRED: {r}")
        print(f"  H now: " + ", ".join(
            f"{h['id']}={h['w']:.2f}/{h['s']}" for h in step["H"]))
        if step["T"]:
            for t in step["T"]:
                trg = t.get("triggered_by") or []
                trg_tag = f" by={trg}" if trg else ""
                print(f"  T: [{t['sev']}] {t['kind']}{trg_tag}: {t['what']}")
        else:
            print("  T: (none)")
        e = step["E"]
        print(f"  E: {e['kind']} (progress={e['progress']}) — {e['note']}")
        print()

    print("=== final ===")
    print(f"  state_predicate: {compute_state_predicate(state)}")
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
