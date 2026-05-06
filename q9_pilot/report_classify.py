"""report_classify.py — chunk-level diff between regex-based and
examples-based pattern_class assignment.

Runs the new spike (which uses classify() from examples) and computes
what the OLD regex-based extractor would have produced on each chunk.
For each step shows: regex_class(es), examples_class(es), match?,
H weights, state_predicate.

The regex_baseline_* functions below mirror the labelling logic from
commit 14a90f6 (before classification-by-examples). They are the
chunk-level expectation; they don't run inside the spike. The spike
itself only uses classify().

Run: python report_classify.py
"""

from __future__ import annotations

from thought_spike import (
    initial_state_q22, initial_state_q7, initial_state_q1, initial_state_q2,
    CHUNKS, Q7_CHUNKS, Q1_CHUNKS, Q2_CHUNKS,
    think_step, compute_state_predicate,
    YEAR_RE, PYTHON_VERSION_RE, PATH_DIGIT_RE,
    URL_RE, LATIN_CAMEL_RE, NAME_CYR_RE, ORG_CYR_RE, AUTHOR_KW_RE,
    VERSIONED_CMD_RE, PYTHON3_CMD_RE,
    PIP_INSTALL_MODULE_RE, PIP_MENTION_RE,
)


# ---------------- regex baselines (mirror commit 14a90f6 labelling) ----------------

def regex_baseline_when(text: str) -> list[str]:
    out = []
    years = YEAR_RE.findall(text)
    py_versions = PYTHON_VERSION_RE.findall(text)
    py_version_digits = {tok for v in py_versions for tok in v.split(".")}
    if years:
        for y_str in years:
            in_py = y_str in py_version_digits or any(
                pv in text for pv in (f"Python {y_str}", f"Python-{y_str}")
            )
            out.append("year_in_python_version" if in_py else "raw_year_in_prose")
    elif py_versions or PATH_DIGIT_RE.search(text):
        out.append("numeric_off_topic")
    if not out:
        out.append("no_marker")
    return out


def regex_baseline_who(text: str) -> list[str]:
    out = []
    url_m = URL_RE.search(text)
    if url_m and LATIN_CAMEL_RE.search(url_m.group(0)):
        out.append("name_in_url")

    kw_m = AUTHOR_KW_RE.search(text)
    if kw_m:
        after = text[kw_m.end():kw_m.end() + 60]
        cyr_name = NAME_CYR_RE.search(after)
        if cyr_name and cyr_name.group(0).strip().lower() not in (
            "программист", "разработчик", "автор", "пользоват",
        ):
            out.append("name_with_relation")
        else:
            out.append("anonymous_attribution")

    if not out:
        org_m = ORG_CYR_RE.search(text)
        publisher_context = (
            "издательств" in text.lower()
            or "пресс" in text.lower()
            or "press" in text.lower()
        )
        if org_m and publisher_context:
            out.append("publisher_org")

    if not out:
        out.append("no_marker")
    return out


import re as _re
# Narrow VERSION_MIN_PHRASE_RE — preserved here for baseline comparison
# only. The spike's fragment finder is now PYTHON_VERSION_NEAR_RE
# (wide). The narrow form is kept here so we can show, per chunk,
# what the pre-widening regex labelling would have produced.
_NARROW_VERSION_MIN_PHRASE_RE = _re.compile(
    r"(?:версию\s+Python\s+не\s+ниже\s+|"
     r"Python\s+(?:версии\s+)?не\s+ниже\s+|"
     r"требуется\s+Python\s+|"
     r"минимум\s+Python\s+)"
    r"(\d+(?:\.\d+)+)",
    _re.IGNORECASE,
)


def regex_baseline_what_version(text: str) -> list[str]:
    out = []
    for _ in _NARROW_VERSION_MIN_PHRASE_RE.finditer(text):
        out.append("version_with_min_phrase")
    for _ in VERSIONED_CMD_RE.finditer(text):
        out.append("versioned_command")
    for _ in PYTHON3_CMD_RE.finditer(text):
        out.append("python3_command")
    if not out:
        out.append("no_marker")
    return out


def regex_baseline_what_pip(text: str) -> list[str]:
    out = []
    install_count = sum(1 for _ in PIP_INSTALL_MODULE_RE.finditer(text))
    for _ in range(install_count):
        out.append("pip_install_with_module")
    if not install_count and PIP_MENTION_RE.search(text):
        out.append("pip_mention_no_modules")
    if not out:
        out.append("no_marker")
    return out


REGEX_BASELINE = {
    "q22": regex_baseline_when,
    "q7":  regex_baseline_who,
    "q1":  regex_baseline_what_version,
    "q2":  regex_baseline_what_pip,
}


QUESTIONS = {
    "q22": (initial_state_q22, CHUNKS),
    "q7":  (initial_state_q7, Q7_CHUNKS),
    "q1":  (initial_state_q1, Q1_CHUNKS),
    "q2":  (initial_state_q2, Q2_CHUNKS),
}


# H weights per step from commit 14a90f6 (regex-based extractor),
# captured from the runs reported in SPIKE_FINDINGS/STATE_AS_GRAPH
# session. Step indexed from 1 (after each observation).
PRIOR_H_BY_STEP = {
    "q22": [
        {"h1": 0.25, "h2": 0.20, "h3": 0.15, "h4": 0.35},
        {"h1": 0.20, "h2": 0.15, "h3": 0.10, "h4": 0.45},
        {"h1": 0.15, "h2": 0.10, "h3": 0.05, "h4": 0.55},
        {"h1": 0.10, "h2": 0.05, "h3": 0.00, "h4": 0.65},
        {"h1": 0.05, "h2": 0.00, "h3": 0.00, "h4": 0.75},
    ],
    "q7": [
        {"h1": 0.40, "h2": 0.25, "h3": 0.35},
        {"h1": 0.35, "h2": 0.20, "h3": 0.45},
        {"h1": 0.35, "h2": 0.20, "h3": 0.45},
        {"h1": 0.30, "h2": 0.15, "h3": 0.55},
        {"h1": 0.25, "h2": 0.10, "h3": 0.65},
    ],
    "q1": [
        {"h1": 0.65, "h2": 0.25, "h3": 0.20},
        {"h1": 0.65, "h2": 0.25, "h3": 0.20},
        {"h1": 0.60, "h2": 0.20, "h3": 0.30},
        {"h1": 0.55, "h2": 0.15, "h3": 0.40},
    ],
    "q2": [
        {"h1": 0.75, "h2": 0.25, "h3": 0.20},
        {"h1": 0.75, "h2": 0.25, "h3": 0.20},
        {"h1": 0.70, "h2": 0.20, "h3": 0.30},
        {"h1": 0.65, "h2": 0.15, "h3": 0.40},
    ],
}


def run_question(qid: str):
    init_fn, chunks = QUESTIONS[qid]
    baseline_fn = REGEX_BASELINE[qid]
    state = init_fn()
    prior = PRIOR_H_BY_STEP.get(qid, [])
    rows = []
    for step, chunk in enumerate(chunks, 1):
        regex_classes = baseline_fn(chunk["text"])
        state = think_step(state, chunk)
        added = state.history[-1].get("K_added_this_step", [])
        examples_classes = [k.pattern_class.name for k in added]
        cur_h = {h["id"]: round(h["weight"], 3) for h in state.H}
        prior_h = prior[step - 1] if step - 1 < len(prior) else {}
        h_match = (
            prior_h
            and all(abs(cur_h.get(k, 0) - v) < 0.001 for k, v in prior_h.items())
        )
        rows.append({
            "step": step,
            "chunk_id": chunk["id"],
            "regex": regex_classes,
            "examples": examples_classes,
            "class_match": sorted(regex_classes) == sorted(examples_classes),
            "h_now": cur_h,
            "h_prior": prior_h,
            "h_match": h_match,
            "predicate": compute_state_predicate(state),
        })
    return state, rows


def fmt(rows):
    for r in rows:
        rg = ",".join(r["regex"])
        ex = ",".join(r["examples"])
        cls_tag = "CLS=" + ("OK " if r["class_match"] else "NO ")
        h_tag = "H=" + ("OK " if r["h_match"] else "NO ")
        print(f"  step {r['step']} {r['chunk_id']:<22} "
              f"{cls_tag}  {h_tag}  predicate={r['predicate']}")
        if not r["class_match"]:
            print(f"       regex_class:    {rg}")
            print(f"       examples_class: {ex}")
        if not r["h_match"] and r["h_prior"]:
            now_str = " ".join(f"{k}={v:.3f}" for k, v in r["h_now"].items())
            prior_str = " ".join(f"{k}={v:.3f}" for k, v in r["h_prior"].items())
            print(f"       H now:   {now_str}")
            print(f"       H prior: {prior_str}")
        else:
            now_str = " ".join(f"{k}={v:.3f}" for k, v in r["h_now"].items())
            print(f"       H: {now_str}")


def main():
    summary = []
    for qid in ("q22", "q7", "q1", "q2"):
        state, rows = run_question(qid)
        cls_diffs = sum(1 for r in rows if not r["class_match"])
        h_diffs = sum(1 for r in rows if not r["h_match"])
        summary.append((qid, len(rows), cls_diffs, h_diffs,
                        compute_state_predicate(state)))
        print(f"=== {qid.upper()} ({len(rows)} chunks, "
              f"{cls_diffs} class-diff, {h_diffs} H-diff) ===")
        fmt(rows)
        print(f"  final predicate: {compute_state_predicate(state)}")
        print()

    print("=== summary ===")
    print(f"{'qid':<5} {'steps':<6} {'cls_diff':<10} {'H_diff':<8} predicate")
    for qid, n, cd, hd, pred in summary:
        print(f"{qid:<5} {n:<6} {cd:<10} {hd:<8} {pred}")


if __name__ == "__main__":
    main()
