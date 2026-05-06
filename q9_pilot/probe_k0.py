"""Probe: refuse-gate behaviour under K=0 and adjacent low-evidence regimes.

Three scenarios, all use the existing run_primary loop unchanged:

  S1 - K=0 strict       : empty chunks dict
  S2 - K=0 via extractor: chunks exist, extractor returns nothing
  S3 - K=1 spurious     : one shaky claim, no second source to corroborate

S1, S2 should halt with answer=None. S3 currently does NOT halt: a single
unsupported claim becomes an "supported" E and the loop returns it as the
winner. This probe records what the loop does today, so any subsequent
refuse-gate work has a baseline.
"""

from __future__ import annotations

from pilot import run_primary
from state import ThoughtState


def _summary(label: str, state: ThoughtState, winner) -> dict:
    return {
        "scenario": label,
        "K_size": len(state.K),
        "H_active": sum(h.active for h in state.H),
        "E": state.E,
        "T": dict(state.T),
        "answer": None if winner is None else winner.value,
        "answer_source": None if winner is None else winner.source_type,
        "trace_tail": state.trace[-1],
    }


def s1_empty_corpus():
    state, winner = run_primary(
        question="how many widgets in the example",
        query="widgets example count",
        chunks={},
    )
    return _summary("S1_empty_corpus", state, winner)


def s2_chunks_no_claims():
    chunks = {
        "c001": {
            "text": (
                "This widgets example is about iteration patterns. "
                "It avoids enumerating concrete counts on purpose."
            ),
            "section": "intro",
        },
        "c002": {
            "text": (
                "The reader is invited to count widgets themselves. "
                "No author phrase, no doctest, no dunder methods listed."
            ),
            "section": "intro",
        },
    }
    state, winner = run_primary(
        question="how many widgets in the example",
        query="widgets example count",
        chunks=chunks,
    )
    return _summary("S2_chunks_no_claims", state, winner)


def s3_single_spurious_claim():
    """Single code_literal claim, no author anchor, no forward reference.

    The chunk is a code snippet from elsewhere in the book that defines exactly
    one dunder method, but it is NOT the Vector example. Loop has no way to
    know that — `_code_literal` just counts `def __X__(` patterns.
    """
    chunks = {
        "c001": {
            "text": (
                "# special methods example for Vector class\n"
                "class Vector:\n"
                "    def __abs__(self):\n"
                "        return 0\n"
            ),
            "section": "appendix",
            "kind": "code",
        },
    }
    state, winner = run_primary(
        question="how many special methods does Vector implement",
        query="Vector special methods count",
        chunks=chunks,
    )
    return _summary("S3_single_spurious_claim", state, winner)


def s4_single_authoritative_but_wrong():
    """One author_anchor claim, no corroboration. The phrasing matches the
    regex perfectly, but the source is the WRONG example (different chapter,
    different class). Loop has no scope check — the question says 'Vector',
    the chunk talks about 'Polygon', but the regex doesn't care.
    """
    chunks = {
        "c001": {
            "text": (
                "In a Vector-adjacent example we implemented seven "
                "special methods.\nThis was for the Polygon class, not "
                "Vector itself."
            ),
            "section": "ch.99",
        },
    }
    state, winner = run_primary(
        question="how many special methods does Vector implement",
        query="Vector special methods count",
        chunks=chunks,
    )
    return _summary("S4_single_authoritative_wrong_scope", state, winner)


if __name__ == "__main__":
    import json

    probes = (
        s1_empty_corpus,
        s2_chunks_no_claims,
        s3_single_spurious_claim,
        s4_single_authoritative_but_wrong,
    )
    for fn in probes:
        result = fn()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("-" * 60)
