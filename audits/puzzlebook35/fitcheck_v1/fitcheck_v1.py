"""fit_check v1 — hybrid trigger-window (A) + alignment-floor + section-gate (B).

API mirrors baseline_v0/retriever.py::fit_check so it can be slotted into
the same pipeline shape: returns (fit_status, fit_expected_type, fit_details).

Inputs:
  intent           — one of {when, who, how_many, what, why, how, ...}
  question         — the natural-language question text
  topk_chunk_ids   — list of chunk_ids in retrieval order
  chunks_by_id     — {chunk_id -> dict with content + section_path}
  downstream_k     — only the first downstream_k chunks are inspected (default 4)

Outputs:
  fit_status        — one of {match, partial, mismatch, skipped}
  fit_expected_type — short label, free text
  fit_details       — dict with diagnostics (kept small, deterministic)

Determinism: all lexicons are sorted/frozenset; tokenization is regex;
no randomness; no LLM; no embeddings.
"""
from __future__ import annotations

import re
from typing import Iterable

from lexicons import (
    CARDINAL_WORDS,
    INTENT_TRIGGERS,
    OUT_OF_SCOPE_SECTION_PREFIXES,
    OUT_OF_SCOPE_TERMS,
    RU_INTERROGATIVES,
    RU_STOP,
    stem,
)

DEFAULT_DOWNSTREAM_K = 4
WIN_INTENT = 12   # ±tokens window for intent_trigger near candidate
WIN_QKW = 25      # ±tokens window for question_kw near candidate
ALIGN_FLOOR_MATCH = 2     # ≥N question content tokens overlap → match
ALIGN_FLOOR_PARTIAL = 1   # ≥N → partial; <N → mismatch

YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
NUMBER_RE = re.compile(r"\b\d+\b")
NAME_RE = re.compile(r"\b[А-ЯA-Z][а-яa-zё]+(?:[\s\-][А-ЯA-Z][а-яa-zё]+)?\b")
TOKEN_RE = re.compile(r"\b\w+\b", flags=re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def question_keywords(question: str) -> list[str]:
    """Question content tokens with stop-words and interrogatives removed,
    stemmed."""
    out = []
    for tok in tokenize(question):
        if tok in RU_STOP or tok in RU_INTERROGATIVES:
            continue
        if len(tok) < 3:
            continue
        out.append(stem(tok))
    return out


def chunk_content_tokens(text: str) -> list[str]:
    """Lowercased tokens, stop-filtered, stemmed."""
    out = []
    for tok in tokenize(text):
        if tok in RU_STOP:
            continue
        if len(tok) < 3:
            continue
        out.append(stem(tok))
    return out


def trigger_present_near(
    tokens: list[str],
    center: int,
    triggers: Iterable[str],
    window: int,
) -> str | None:
    """Return the first trigger string found within ±window tokens of center."""
    lo = max(0, center - window)
    hi = min(len(tokens), center + window + 1)
    for i in range(lo, hi):
        tok = tokens[i]
        for trig in triggers:
            if tok.startswith(trig):
                return trig
    return None


def first_keyword_near(
    tokens: list[str],
    center: int,
    keywords: Iterable[str],
    window: int,
) -> str | None:
    lo = max(0, center - window)
    hi = min(len(tokens), center + window + 1)
    kws = list(keywords)
    for i in range(lo, hi):
        tok = tokens[i]
        for kw in kws:
            if kw and (tok.startswith(kw) or kw.startswith(tok)):
                return kw
    return None


def find_token_indices(content: str, pattern: re.Pattern) -> list[int]:
    """Find token-index positions where pattern.match() fires.

    Returns indices into the lowercased token list produced by tokenize().
    Approximates by tokenizing first, then re-checking each token against
    the pattern (case-insensitive)."""
    raw_tokens = TOKEN_RE.findall(content)
    out = []
    for i, t in enumerate(raw_tokens):
        if pattern.match(t):
            out.append(i)
    return out


def out_of_scope_signal(
    question: str,
    topk_chunk_ids: list[str],
    chunks_by_id: dict,
    downstream_k: int,
) -> str | None:
    """If question asks for an excluded answer category, return the trigger
    term; else None.

    Heuristic: the OOS term must appear within ±5 tokens of a digit in the
    question (i.e., near a task/section number reference). This filters
    gerund usages like 'в решении задач' (Q13) where 'решение' is the act
    of solving, not the solution artifact.
    """
    qtoks = tokenize(question)
    qtoks_raw = TOKEN_RE.findall(question)
    digit_positions = [i for i, t in enumerate(qtoks_raw) if t.isdigit()]
    matched_term = None
    for i, tok in enumerate(qtoks):
        for term in OUT_OF_SCOPE_TERMS:
            if tok.startswith(term):
                if any(abs(i - dp) <= 5 for dp in digit_positions):
                    matched_term = term
                    break
        if matched_term:
            break
    if matched_term is None:
        return None
    for cid in topk_chunk_ids[:downstream_k]:
        ch = chunks_by_id.get(cid)
        if ch is None:
            continue
        for prefix in OUT_OF_SCOPE_SECTION_PREFIXES:
            sp = ch.get("section_path", [])
            if len(sp) >= len(prefix) and tuple(sp[: len(prefix)]) == prefix:
                return None
    return matched_term


def fit_check_when(
    question: str, topk_chunk_ids: list[str], chunks_by_id: dict, k: int
) -> tuple[str, str, dict]:
    qkw = question_keywords(question)
    triggers = INTENT_TRIGGERS["when"]
    candidates_total = 0
    valid_hits: list[dict] = []
    for cid in topk_chunk_ids[:k]:
        ch = chunks_by_id.get(cid)
        if ch is None:
            continue
        content = ch["content"]
        idxs = find_token_indices(content, YEAR_RE)
        if not idxs:
            continue
        candidates_total += len(idxs)
        toks = tokenize(content)
        for i in idxs:
            trig = trigger_present_near(toks, i, triggers, WIN_INTENT)
            kw = first_keyword_near(toks, i, qkw, WIN_QKW) if qkw else None
            if trig and (kw or not qkw):
                valid_hits.append({"chunk_id": cid, "year_token": toks[i], "trigger": trig, "qkw": kw})
    if valid_hits:
        return "match", "year+temporal_context", {"valid_hits": valid_hits[:5], "candidates_total": candidates_total}
    return "mismatch", "year+temporal_context", {"candidates_total": candidates_total, "reason": "no year+trigger conjunction in downstream-k"}


def fit_check_who(
    question: str, topk_chunk_ids: list[str], chunks_by_id: dict, k: int
) -> tuple[str, str, dict]:
    qkw = question_keywords(question)
    triggers = INTENT_TRIGGERS["who"]
    valid_hits: list[dict] = []
    candidates_total = 0
    for cid in topk_chunk_ids[:k]:
        ch = chunks_by_id.get(cid)
        if ch is None:
            continue
        content = ch["content"]
        idxs = find_token_indices(content, NAME_RE)
        if not idxs:
            continue
        candidates_total += len(idxs)
        toks = tokenize(content)
        for i in idxs:
            trig = trigger_present_near(toks, i, triggers, WIN_INTENT)
            if trig:
                kw = first_keyword_near(toks, i, qkw, WIN_QKW) if qkw else None
                valid_hits.append({"chunk_id": cid, "name_token": toks[i], "trigger": trig, "qkw": kw})
    if valid_hits:
        return "match", "person_name+authorship_context", {"valid_hits": valid_hits[:5], "candidates_total": candidates_total}
    return "mismatch", "person_name+authorship_context", {"candidates_total": candidates_total, "reason": "no name+trigger conjunction in downstream-k"}


def fit_check_how_many(
    question: str, topk_chunk_ids: list[str], chunks_by_id: dict, k: int
) -> tuple[str, str, dict]:
    qkw = question_keywords(question)
    if not qkw:
        return "mismatch", "count+counting_noun", {"reason": "no question keywords to anchor count"}
    valid_hits: list[dict] = []
    candidates_total = 0
    for cid in topk_chunk_ids[:k]:
        ch = chunks_by_id.get(cid)
        if ch is None:
            continue
        content = ch["content"]
        idxs = find_token_indices(content, NUMBER_RE)
        toks = tokenize(content)
        # Also: spelled-out cardinals near keyword count as candidates
        for i, tok in enumerate(toks):
            if tok in CARDINAL_WORDS:
                idxs.append(i)
        idxs = sorted(set(idxs))
        if not idxs:
            continue
        candidates_total += len(idxs)
        for i in idxs:
            kw = first_keyword_near(toks, i, qkw, WIN_QKW)
            if kw:
                valid_hits.append({"chunk_id": cid, "num_token": toks[i], "qkw": kw})
    if valid_hits:
        return "match", "count+counting_noun", {"valid_hits": valid_hits[:5], "candidates_total": candidates_total}
    return "mismatch", "count+counting_noun", {"candidates_total": candidates_total, "reason": "no count+question_kw co-occurrence in downstream-k"}


def fit_check_alignment(
    intent: str,
    question: str,
    topk_chunk_ids: list[str],
    chunks_by_id: dict,
    k: int,
    extra_triggers: Iterable[str] | None = None,
) -> tuple[str, str, dict]:
    qkw = set(question_keywords(question))
    if not qkw:
        return "mismatch", f"{intent}+alignment_floor", {"reason": "no question content tokens"}
    best_overlap = 0
    best_chunk = None
    triggers_seen: list[str] = []
    extras = list(extra_triggers) if extra_triggers else []
    for cid in topk_chunk_ids[:k]:
        ch = chunks_by_id.get(cid)
        if ch is None:
            continue
        ctoks = set(chunk_content_tokens(ch["content"]))
        overlap = len(qkw & ctoks)
        if overlap > best_overlap:
            best_overlap = overlap
            best_chunk = cid
        if extras:
            for tok in tokenize(ch["content"]):
                for tr in extras:
                    if tok.startswith(tr) and tr not in triggers_seen:
                        triggers_seen.append(tr)
    label = f"{intent}+alignment_floor"
    details = {
        "best_chunk": best_chunk,
        "best_overlap": best_overlap,
        "qkw_count": len(qkw),
        "triggers_seen": triggers_seen,
    }
    if best_overlap >= ALIGN_FLOOR_MATCH:
        return "match", label, details
    if best_overlap >= ALIGN_FLOOR_PARTIAL:
        return "partial", label, details
    return "mismatch", label, details


def fit_check(
    intent: str,
    question: str,
    topk_chunk_ids: list[str],
    chunks_by_id: dict,
    downstream_k: int = DEFAULT_DOWNSTREAM_K,
) -> tuple[str, str, dict]:
    """Top-level dispatcher. Returns (fit_status, fit_expected_type, fit_details)."""
    oos = out_of_scope_signal(question, topk_chunk_ids, chunks_by_id, downstream_k)
    if oos is not None:
        return "mismatch", "out_of_scope_within_topic", {
            "reason": "answer category excluded from active_corpus",
            "oos_term": oos,
        }
    if intent == "when":
        return fit_check_when(question, topk_chunk_ids, chunks_by_id, downstream_k)
    if intent == "who":
        return fit_check_who(question, topk_chunk_ids, chunks_by_id, downstream_k)
    if intent == "how_many":
        return fit_check_how_many(question, topk_chunk_ids, chunks_by_id, downstream_k)
    if intent == "what":
        return fit_check_alignment("what", question, topk_chunk_ids, chunks_by_id, downstream_k)
    if intent == "why":
        return fit_check_alignment(
            "why", question, topk_chunk_ids, chunks_by_id, downstream_k,
            extra_triggers=INTENT_TRIGGERS["why"],
        )
    if intent == "how":
        return fit_check_alignment(
            "how", question, topk_chunk_ids, chunks_by_id, downstream_k,
            extra_triggers=INTENT_TRIGGERS["how"],
        )
    return "skipped", "unhandled_intent", {"intent": intent}


def final_outcome(fit_status: str, intent: str) -> str:
    """v1: any non-match status with a recognized intent → fit_refuse;
    match → hit; skipped → hit (legacy)."""
    if fit_status == "match":
        return "hit"
    if fit_status == "partial":
        return "hit"
    if fit_status == "skipped":
        return "hit"
    if fit_status == "mismatch":
        return "fit_refuse"
    return "hit"


def stop_reason(fit_status: str, intent: str, outcome: str, fit_details: dict) -> str:
    if outcome == "fit_refuse":
        reason = fit_details.get("reason", f"fit_check rejected top-k for intent={intent}")
        return f"fit_check_v1 (status={fit_status}, intent={intent}): {reason}"
    if fit_status == "skipped":
        return f"fit_check_v1 skipped (intent={intent} not handled); top-k returned"
    return f"fit_check_v1 status={fit_status} for intent={intent}; top-k returned as material"
