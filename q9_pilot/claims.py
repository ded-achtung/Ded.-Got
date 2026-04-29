"""
extract_claim for intent=how_many.

Three source-types, each detected by an independent pattern. A single chunk may
yield zero, one, or more typed claims; conflicts between them are NOT resolved
here — that is the job of narrow_hypothesis + P.
"""

import re

NUMERAL_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _to_int(token: str) -> int | None:
    token = token.lower()
    if token.isdigit():
        return int(token)
    return NUMERAL_WORDS.get(token)


def _author_anchor(text: str) -> dict | None:
    # "we implemented N special methods [in addition to X]"
    m = re.search(
        r"\b(?:we\s+)?(?:implemented|implements|defines|provides)\s+"
        r"(\w+)\s+special\s+methods?"
        r"(?:\s+(in\s+addition\s+to|excluding|not\s+counting|besides)\s+"
        r"([^.\n]+?))?[.\n]",
        text, re.IGNORECASE,
    )
    if not m:
        return None
    n = _to_int(m.group(1))
    if n is None:
        return None
    scope = None
    if m.group(2):
        scope = f"{m.group(2).lower()} {m.group(3).strip()}"
    return {
        "value": n,
        "source_type": "author_anchor",
        "scope_operator": scope,
        "evidence": m.group(0).strip(),
    }


def _forward_reference(text: str) -> dict | None:
    # "the special methods __a__, __b__, __c__, and __d__"
    m = re.search(
        r"the\s+special\s+methods?\s+"
        r"((?:__\w+__\s*,\s*)+(?:and\s+)?__\w+__)",
        text, re.IGNORECASE,
    )
    if not m:
        return None
    methods = re.findall(r"__\w+__", m.group(1))
    if not methods:
        return None
    return {
        "value": len(methods),
        "source_type": "forward_reference",
        "scope_operator": None,
        "list": methods,
        "evidence": m.group(0).strip(),
    }


def _code_literal(text: str, kind: str) -> dict | None:
    if kind != "code":
        return None
    methods = re.findall(r"def\s+(__\w+__)\s*\(", text)
    if not methods:
        return None
    return {
        "value": len(methods),
        "source_type": "code_literal",
        "scope_operator": None,
        "list": methods,
        "evidence": f"{len(methods)} dunder def(s) in code body",
    }


def extract_claims(chunk_id: str, chunk: dict) -> list[dict]:
    out: list[dict] = []
    text = chunk["text"]
    kind = chunk.get("kind", "prose")
    for fn in (_author_anchor, _forward_reference):
        c = fn(text)
        if c is not None:
            c["chunk_id"] = chunk_id
            out.append(c)
    c = _code_literal(text, kind)
    if c is not None:
        c["chunk_id"] = chunk_id
        out.append(c)
    return out
