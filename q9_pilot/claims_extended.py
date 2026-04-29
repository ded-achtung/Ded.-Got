"""
Stage 3 extractors. Adds two new detectors that target Q4-style claims:

  _doctest_output         >>> len(deck) \\n 52     -> code_literal
  _author_count_phrase    list made of 52 cards   -> author_anchor

The Q9 detectors from claims.py are reused unchanged. Two extractor variants
are exposed so test_q4_extended can also probe what happens when the author
phrase detector is unavailable (P fallback path).
"""

import re

from claims import (
    NUMERAL_WORDS,
    _author_anchor,
    _code_literal,
    _forward_reference,
    _to_int,
)


def _doctest_output(text: str) -> dict | None:
    # >>> len(deck)\n52  — captures the literal that follows a len(...) doctest
    m = re.search(r">>>\s*len\([^)]*\)\s*\n\s*(\d+)\b", text)
    if not m:
        return None
    return {
        "value": int(m.group(1)),
        "source_type": "code_literal",
        "scope_operator": None,
        "evidence": m.group(0).strip(),
    }


def _author_count_phrase(text: str) -> dict | None:
    # "list made of 52 cards", "deck of 52 cards", "set of N items"
    m = re.search(
        r"(?:list\s+made\s+of|deck\s+of|set\s+of)\s+(\w+)\s+(?:cards?|elements?|items?)",
        text, re.IGNORECASE,
    )
    if not m:
        return None
    n = _to_int(m.group(1))
    if n is None:
        return None
    return {
        "value": n,
        "source_type": "author_anchor",
        "scope_operator": None,
        "evidence": m.group(0).strip(),
    }


def _attach(chunk_id: str, claim: dict) -> dict:
    claim["chunk_id"] = chunk_id
    return claim


def extract_claims_extended(chunk_id: str, chunk: dict) -> list[dict]:
    """All Q9 detectors + Q4 detectors active."""
    out: list[dict] = []
    text = chunk["text"]
    kind = chunk.get("kind", "prose")

    for fn in (_author_anchor, _author_count_phrase, _forward_reference):
        c = fn(text)
        if c is not None:
            out.append(_attach(chunk_id, c))

    for fn in (_code_literal,):
        c = fn(text, kind)
        if c is not None:
            out.append(_attach(chunk_id, c))

    c = _doctest_output(text)
    if c is not None:
        out.append(_attach(chunk_id, c))

    return out


def extract_claims_no_author_phrase(chunk_id: str, chunk: dict) -> list[dict]:
    """Extended set MINUS _author_count_phrase. Probes the P-fallback path:
    no author_anchor source available, only code_literal candidates.
    """
    out: list[dict] = []
    text = chunk["text"]
    kind = chunk.get("kind", "prose")

    for fn in (_author_anchor, _forward_reference):
        c = fn(text)
        if c is not None:
            out.append(_attach(chunk_id, c))

    c = _code_literal(text, kind)
    if c is not None:
        out.append(_attach(chunk_id, c))

    c = _doctest_output(text)
    if c is not None:
        out.append(_attach(chunk_id, c))

    return out
