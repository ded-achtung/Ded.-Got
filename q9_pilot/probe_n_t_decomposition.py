"""Probe N: T-decomposition diagnostic. What tensions LIVE in the corpus
that today's recompute_tensions() (two slots: evidence_gap, unresolved_
ambiguity) cannot see?

Today's pilot.py:
  T = {} | {evidence_gap: HIGH} | {unresolved_ambiguity: HIGH | MEDIUM}

This probe defines six richer tensions, computes them across 35 questions,
and shows distribution + which would have caught failures observed in
prior probes (G5 false positives, S4 wrong-scope, K-probe single-claim
acceptance).

Tensions defined here (computed AFTER retrieve + L extractor + noun filter):

  T_evidence_gap       — K_relevant = 0 (no claim with question-noun stem)
  T_scope_mismatch     — K > 0 but K_relevant = 0 (extractor produced
                         numbers but none on-topic)
  T_intent_mismatch    — claim source_type doesn't fit q['intent']:
                         numeric extractor on intent != how_many
  T_single_source      — all relevant claims from one chunk_id
                         (no corroboration)
  T_low_retrieve_sep   — top-1 retrieve score < 0.10 OR top-1 score -
                         top-4 score < 0.03 (no separation = retrieve
                         couldn't distinguish)
  T_oop_signal_absent  — intent in {when, who} AND no year regex match
                         (when) or no capitalized-name match (who) in
                         retrieved top-4 — likely out-of-corpus

For each tension, suggest the action that *would* fire if the loop heeded
it. No action is actually taken. This is measurement of what's missing
from the T slot, not a fix.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from probe_l_thinkloop import (  # noqa: E402
    extract,
    load_chunks,
    load_questions,
    noun_match,
    question_noun_stems,
    tfidf_topk,
)

YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
NAME_RE = re.compile(r"\b[А-ЯA-Z][а-яa-zё]+(?:[\s\-][А-ЯA-Z][а-яa-zё]+)?\b")


def compute_tensions(question: str, intent: str, rows: list[dict]) -> dict:
    top = tfidf_topk(question, rows)
    stems = question_noun_stems(question)

    K = []
    for cid, text, _ in top:
        K.extend(extract(text, cid, permissive=False))
    if not any(noun_match(c["noun"], stems) for c in K):
        K_perm = []
        for cid, text, _ in top:
            K_perm.extend(extract(text, cid, permissive=True))
        K = K_perm

    K_relevant = [c for c in K if noun_match(c["noun"], stems)]
    chunk_ids_in_K_rel = {c["chunk_id"] for c in K_relevant}
    top_scores = [s for _, _, s in top]
    top_text = "\n".join(t for _, t, _ in top)

    T: dict[str, dict] = {}

    # T_evidence_gap
    if not K_relevant:
        T["evidence_gap"] = {
            "level": "HIGH",
            "action_hint": "broaden retrieve / try different extractor",
        }

    # T_scope_mismatch — K > 0 but no relevant
    if K and not K_relevant:
        T["scope_mismatch"] = {
            "level": "HIGH",
            "action_hint": "extractor produced claims but none on-topic; "
                            "filter by question-noun OR refuse",
            "off_topic_count": len(K),
        }

    # T_intent_mismatch — numeric extractor result on non-how_many intent
    if K_relevant and intent != "how_many":
        T["intent_mismatch"] = {
            "level": "HIGH",
            "action_hint": f"intent={intent} expects non-numeric answer; "
                            "numeric claim is type-wrong regardless of noun",
            "claim_count": len(K_relevant),
        }

    # T_single_source — corroboration absent
    if K_relevant and len(chunk_ids_in_K_rel) == 1:
        T["single_source"] = {
            "level": "MEDIUM",
            "action_hint": "all evidence from one chunk; seek corroboration "
                            "in adjacent retrieve ranks",
            "chunk": next(iter(chunk_ids_in_K_rel)),
        }

    # T_low_retrieve_sep
    if top_scores:
        top1 = top_scores[0]
        sep = top_scores[0] - top_scores[-1]
        if top1 < 0.10 or sep < 0.03:
            T["low_retrieve_sep"] = {
                "level": "MEDIUM" if top1 < 0.10 else "LOW",
                "action_hint": "retrieve cannot distinguish top from rest; "
                                "broaden query or expand top_K",
                "top1_score": round(top1, 3),
                "spread": round(sep, 3),
            }

    # T_oop_signal_absent — when/who without domain markers
    if intent == "when" and not YEAR_RE.search(top_text):
        T["oop_signal_absent"] = {
            "level": "HIGH",
            "action_hint": "when-question with zero year markers in top-K → "
                            "likely out-of-corpus; refuse with reason",
            "intent": "when",
        }
    if intent == "who" and not NAME_RE.search(top_text):
        T["oop_signal_absent"] = {
            "level": "HIGH",
            "action_hint": "who-question with zero capitalized names → "
                            "likely out-of-corpus; refuse with reason",
            "intent": "who",
        }

    return {"T": T, "K_size": len(K), "K_relevant": len(K_relevant),
            "top_scores": [round(s, 3) for s in top_scores]}


def main():
    rows = load_chunks()
    questions = load_questions()

    rows_summary = []
    tension_counts: Counter = Counter()
    by_intent_tensions: dict[str, Counter] = {}
    multi_tension = 0

    for q in questions:
        intent = q.get("intent", "?")
        info = compute_tensions(q["question"], intent, rows)
        T = info["T"]
        rows_summary.append({
            "qid": q["qid"], "intent": intent,
            "K": info["K_size"], "K_rel": info["K_relevant"],
            "tensions": list(T.keys()),
            "top_scores": info["top_scores"],
        })
        for t in T:
            tension_counts[t] += 1
            by_intent_tensions.setdefault(intent, Counter())[t] += 1
        if len(T) >= 2:
            multi_tension += 1

    print("=== Tension frequency across 35 questions ===")
    for t, n in tension_counts.most_common():
        print(f"  {t:<22} {n}/35")
    print(f"  multi-tension (>=2)    {multi_tension}/35")
    print()

    print("=== By intent ===")
    for intent in sorted(by_intent_tensions):
        c = by_intent_tensions[intent]
        n = sum(1 for r in rows_summary if r["intent"] == intent)
        print(f"  {intent} ({n} questions):")
        for t, k in c.most_common():
            print(f"    {t:<22} {k}")
    print()

    print("=== What today's T (recompute_tensions) sees vs richer T ===")
    print("  Today's T can ONLY raise:")
    print("    evidence_gap        — when K is empty")
    print("    unresolved_ambiguity — when E='conflicting' or len(active)>1")
    print("  Today's T CANNOT raise (richer probe shows these LIVE in corpus):")
    today_keys = {"evidence_gap"}
    richer_only = [k for k in tension_counts if k not in today_keys]
    for k in richer_only:
        print(f"    {k:<22} fired in {tension_counts[k]}/35 questions")
    print()

    print("=== Multi-tension questions (would benefit most from rich T) ===")
    for r in rows_summary:
        if len(r["tensions"]) >= 2:
            print(f"  {r['qid']:<5} intent={r['intent']:<10} "
                  f"K={r['K']:<3} K_rel={r['K_rel']:<3} "
                  f"T={r['tensions']}")
    print()

    print("=== Per-question summary ===")
    print(f"{'qid':<5} {'intent':<10} {'K':<4} {'K_rel':<6} {'tensions'}")
    for r in rows_summary:
        ts = ",".join(t.replace("T_", "") for t in r["tensions"]) or "-"
        print(f"{r['qid']:<5} {r['intent']:<10} {r['K']:<4} {r['K_rel']:<6} {ts}")


if __name__ == "__main__":
    main()
