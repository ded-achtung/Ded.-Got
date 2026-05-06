"""fit_check v2 — v1 hybrid + per-intent alignment floor + ё-normalization.

Differences from v1 (see FITCHECK_V2_DESIGN.md):
  * `tokenize()` normalizes ё→е (and Ё→Е) before lowercasing.
  * `fit_check_alignment()` reads the match floor from
    `ALIGN_FLOOR_BY_INTENT[intent]` instead of a global constant
    (what=2 unchanged, why=4 raised, how=4 raised).

Everything else (trigger windows for when/who/how_many, OOS gate,
dispatcher) is reused unchanged from v1.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V1_DIR = HERE.parents[0] / "fitcheck_v1"
sys.path.insert(0, str(V1_DIR))

import fitcheck_v1 as v1  # noqa: E402

ALIGN_FLOORS: dict[str, tuple[int, int]] = {
    # intent -> (match_floor, partial_floor)
    "what": (2, 1),
    "why":  (4, 4),  # below 4 = mismatch (no partial state for why/how)
    "how":  (4, 4),
}


def normalize_yo(s: str) -> str:
    return s.replace("ё", "е").replace("Ё", "Е")


_TOKEN_RE = re.compile(r"\b\w+\b", flags=re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(normalize_yo(text))]


# Patch v1's tokenize so all v1 helpers (question_keywords,
# chunk_content_tokens, find_token_indices, out_of_scope_signal, etc.)
# pick up the ё-normalized tokens transparently.
v1.tokenize = tokenize
v1.TOKEN_RE = _TOKEN_RE


def fit_check_alignment_v2(
    intent: str,
    question: str,
    topk_chunk_ids: list[str],
    chunks_by_id: dict,
    k: int,
    extra_triggers=None,
):
    """Same as v1 but uses per-intent floor."""
    qkw = set(v1.question_keywords(question))
    if not qkw:
        return "mismatch", f"{intent}+alignment_floor", {"reason": "no question content tokens"}
    floor_match, floor_partial = ALIGN_FLOORS.get(intent, (2, 1))
    best_overlap = 0
    best_chunk = None
    triggers_seen: list[str] = []
    extras = list(extra_triggers) if extra_triggers else []
    for cid in topk_chunk_ids[:k]:
        ch = chunks_by_id.get(cid)
        if ch is None:
            continue
        ctoks = set(v1.chunk_content_tokens(ch["content"]))
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
        "floor_match": floor_match,
        "floor_partial": floor_partial,
        "triggers_seen": triggers_seen,
    }
    if best_overlap >= floor_match:
        return "match", label, details
    if best_overlap >= floor_partial:
        return "partial", label, details
    return "mismatch", label, details


def fit_check(
    intent: str,
    question: str,
    topk_chunk_ids: list[str],
    chunks_by_id: dict,
    downstream_k: int = v1.DEFAULT_DOWNSTREAM_K,
):
    oos = v1.out_of_scope_signal(question, topk_chunk_ids, chunks_by_id, downstream_k)
    if oos is not None:
        return "mismatch", "out_of_scope_within_topic", {
            "reason": "answer category excluded from active_corpus",
            "oos_term": oos,
        }
    if intent == "when":
        return v1.fit_check_when(question, topk_chunk_ids, chunks_by_id, downstream_k)
    if intent == "who":
        return v1.fit_check_who(question, topk_chunk_ids, chunks_by_id, downstream_k)
    if intent == "how_many":
        return v1.fit_check_how_many(question, topk_chunk_ids, chunks_by_id, downstream_k)
    if intent == "what":
        return fit_check_alignment_v2("what", question, topk_chunk_ids, chunks_by_id, downstream_k)
    if intent == "why":
        return fit_check_alignment_v2(
            "why", question, topk_chunk_ids, chunks_by_id, downstream_k,
            extra_triggers=v1.INTENT_TRIGGERS["why"],
        )
    if intent == "how":
        return fit_check_alignment_v2(
            "how", question, topk_chunk_ids, chunks_by_id, downstream_k,
            extra_triggers=v1.INTENT_TRIGGERS["how"],
        )
    return "skipped", "unhandled_intent", {"intent": intent}


# Re-export v1's outcome/stop_reason logic unchanged
final_outcome = v1.final_outcome
stop_reason = v1.stop_reason
DEFAULT_DOWNSTREAM_K = v1.DEFAULT_DOWNSTREAM_K
