"""Probe: coverage gaps left open by experiments/thoughtstate_pilot_001.

Two limits from REPORT.md probed empirically:

  L3 - rule_2 path: P-fallback to forward_reference when author_anchor is
                    absent and code_literal is not preferred. Pilot never
                    exercised it on Q4. Construct a corpus where the only
                    typed claim is forward_reference, confirm rule_2 fires.

  L2 - extractor brittleness: author-phrase regex is tuned to the exact
                              c033 phrasing. Probe rephrasings that a human
                              reader would treat as equivalent and record
                              hit/miss for each.

This is measurement, not repair. No changes to claims.py / claims_extended.py.
"""

from __future__ import annotations

import json

from claims import _author_anchor, extract_claims
from claims_extended import _author_count_phrase, extract_claims_extended
from pilot import PREFERENCES, run_primary


# -------------------------- Limit 3: rule_2 coverage --------------------------

def _run(label, question, query, chunks):
    state, winner = run_primary(question=question, query=query, chunks=chunks)
    return {
        "scenario": label,
        "K_size": len(state.K),
        "claim_types": sorted({c["source_type"] for c in state.K.values()}),
        "claim_values": sorted({c["value"] for c in state.K.values()}),
        "E": state.E,
        "answer": None if winner is None else winner.value,
        "answer_source": None if winner is None else winner.source_type,
        "P_order": PREFERENCES.get("how_many"),
        "trace_rule": next(
            (line for line in state.trace if "fired=" in line),
            None,
        ),
    }


def probe_rule_2_single_claim():
    """K=1, only forward_reference. Expect single-claim path; narrow_hypothesis
    NOT invoked. This is what the report meant by 'rule_2 not exercised' —
    even with forward_reference present alone the winner comes via the
    'supported' shortcut, not via P fallback.
    """
    chunks = {
        "c001": {
            "text": (
                "The Vector class implements the special methods "
                "__init__, __repr__, __abs__, and __add__. These are "
                "the dunders relevant to this section."
            ),
            "section": "ch.12",
            "kind": "prose",
        },
    }
    return _run(
        "L3a_rule_2_forward_reference_alone",
        "how many special methods does Vector implement",
        "Vector special methods count",
        chunks,
    )


def probe_rule_2_actual_fallback():
    """Force narrow_hypothesis to fall through author_anchor (empty bucket)
    and pick forward_reference over code_literal. Two competing claims with
    DIFFERENT values so E becomes 'conflicting' and P actually runs.
    """
    chunks = {
        "c001": {  # forward_reference: value = 4
            "text": (
                "The Vector class implements the special methods "
                "__init__, __repr__, __abs__, and __add__."
            ),
            "section": "ch.12",
            "kind": "prose",
        },
        "c002": {  # code_literal: value = 6 (different)
            "text": (
                "Vector special methods source listing:\n"
                "    def __init__(self): ...\n"
                "    def __repr__(self): ...\n"
                "    def __abs__(self): ...\n"
                "    def __add__(self): ...\n"
                "    def __mul__(self): ...\n"
                "    def __eq__(self): ...\n"
            ),
            "section": "ch.12",
            "kind": "code",
        },
    }
    return _run(
        "L3b_rule_2_actual_p_fallback",
        "how many special methods does Vector implement",
        "Vector special methods count",
        chunks,
    )


# -------------------------- Limit 2: extractor brittleness --------------------

# Paraphrases of "we implemented N special methods". A human reader would
# accept all of these as the same claim. The regex requires exactly:
#   (we )?(implemented|implements|defines|provides) <numword> special method(s)
# followed by [.\n] or an "in addition to / excluding / besides" scope clause.
AUTHOR_ANCHOR_VARIANTS = [
    # Exact target phrasing — should match.
    ("baseline_exact",
     "We implemented five special methods in addition to the familiar __init__."),
    # Tense / agent variants.
    ("active_voice_no_we",
     "Implemented five special methods for the Vector class."),
    ("present_tense",
     "Vector implements five special methods."),
    # Verb swap inside the supported set.
    ("defines",
     "Vector defines five special methods."),
    # Verb swap OUTSIDE the supported set — should miss.
    ("adds_unsupported_verb",
     "Vector adds five special methods to the protocol."),
    ("includes_unsupported_verb",
     "Vector includes five special methods."),
    # Word order shifts.
    ("count_after_methods",
     "We implemented special methods, five in total."),
    ("passive_voice",
     "Five special methods are implemented by Vector."),
    # Plural / singular drift on the noun "method".
    ("singular_method",
     "Vector implements five special method."),
    # Numeral as digit, not word.
    ("digit_numeral",
     "Vector implements 5 special methods."),
    # Out-of-vocabulary numeral word (>10).
    ("seventeen_word",
     "Vector implements seventeen special methods."),
    # Punctuation: comma instead of period after "methods".
    ("comma_after_methods",
     "Vector implements five special methods, with a clean API."),
    # Typo / hyphenation.
    ("hyphenated",
     "Vector implements five special-methods."),
]


# Same exercise for Q4's _author_count_phrase: "list made of 52 cards" etc.
AUTHOR_COUNT_PHRASE_VARIANTS = [
    ("baseline_exact_q4",
     "FrenchDeck builds a list made of 52 cards."),
    ("deck_of",
     "FrenchDeck builds a deck of 52 cards."),
    ("set_of_items",
     "FrenchDeck builds a set of 52 items."),
    # Variants the regex does NOT cover.
    ("collection_of",
     "FrenchDeck builds a collection of 52 cards."),
    ("contains_n_cards",
     "FrenchDeck contains 52 cards."),
    ("with_n_cards",
     "FrenchDeck is built with 52 cards."),
    ("n_cards_total",
     "FrenchDeck has 52 cards total."),
    ("digit_followed_by_unit",
     "FrenchDeck wraps a list of 52 elements."),
    ("numeral_word_q4",
     "FrenchDeck builds a list made of fifty-two cards."),
    # Reordering.
    ("cards_first",
     "Of 52 cards, the FrenchDeck list is built."),
]


def probe_author_anchor_brittleness():
    rows = []
    for name, text in AUTHOR_ANCHOR_VARIANTS:
        c = _author_anchor(text)
        rows.append({
            "variant": name,
            "text": text,
            "matched": c is not None,
            "value": None if c is None else c["value"],
        })
    return rows


def probe_author_count_phrase_brittleness():
    rows = []
    for name, text in AUTHOR_COUNT_PHRASE_VARIANTS:
        c = _author_count_phrase(text)
        rows.append({
            "variant": name,
            "text": text,
            "matched": c is not None,
            "value": None if c is None else c["value"],
        })
    return rows


def _summarize(rows: list[dict], label: str) -> dict:
    hits = sum(1 for r in rows if r["matched"])
    return {
        "label": label,
        "total": len(rows),
        "hits": hits,
        "miss_rate": round(1 - hits / len(rows), 2),
        "missed_variants": [r["variant"] for r in rows if not r["matched"]],
    }


if __name__ == "__main__":
    print("=== L3a: rule_2 — forward_reference alone (single-claim path) ===")
    print(json.dumps(probe_rule_2_single_claim(), ensure_ascii=False, indent=2))
    print()
    print("=== L3b: rule_2 — actual P fallback (author_anchor empty) ===")
    print(json.dumps(probe_rule_2_actual_fallback(), ensure_ascii=False, indent=2))
    print()

    print("=== L2a: _author_anchor brittleness ===")
    aa_rows = probe_author_anchor_brittleness()
    for r in aa_rows:
        flag = "HIT " if r["matched"] else "MISS"
        print(f"  {flag} {r['variant']:<28s} value={r['value']}")
    print(json.dumps(_summarize(aa_rows, "author_anchor"),
                     ensure_ascii=False, indent=2))
    print()

    print("=== L2b: _author_count_phrase brittleness ===")
    acp_rows = probe_author_count_phrase_brittleness()
    for r in acp_rows:
        flag = "HIT " if r["matched"] else "MISS"
        print(f"  {flag} {r['variant']:<28s} value={r['value']}")
    print(json.dumps(_summarize(acp_rows, "author_count_phrase"),
                     ensure_ascii=False, indent=2))
