"""Probe V: anatomy of Q14 (the only zero-tension question) and health
audit of the other 34.

Q14 anatomy ('Сколько параметров принимает filter_strings_containing_a'):

  C1 intent_supported       intent=how_many is the only intent the
                            current extractor handles
  C2 multi_source           3 distinct chunk_ids (pb_t01_001, t03_001,
                            t04_001) each contribute a relevant claim
  C3 regular_surface        STANDARD extractor matched (no PERMISSIVE_RE
                            fallback needed — no parenthetical or
                            clausal insert between numeral and noun)
  C4 noun_alignment         claim noun ('параметр') stems to a noun in
                            the question ('параметров')
  C5 retrieve_concentration top-1 (pb_t01_001=0.234) at >=1.5x top-2
                            (0.142) — clear winner
  C6 value_coherence        all 3 relevant claims agree on value=1;
                            modal share = 100%

A health score 6/6 means: there is no work for a future think-loop
to do, no reformulation, no corroboration-seeking, no tension-driven
re-entry. The question is converged from the first pass.

This probe scores the other 34 questions on the same 6 axes. The
goal is not 'fix the failures' — it's to enumerate which axes fail
and how often, so any future architectural work has a target list
of conditions to engineer for.
"""

from __future__ import annotations

import json
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

SUPPORTED_INTENTS = {"how_many"}


def health(question: str, intent: str, rows: list[dict]) -> dict:
    top = tfidf_topk(question, rows)
    stems = question_noun_stems(question)

    # Run STANDARD first; record whether it sufficed.
    K_std = []
    for cid, text, _ in top:
        K_std.extend(extract(text, cid, permissive=False))
    rel_std = [c for c in K_std if noun_match(c["noun"], stems)]

    # If STANDARD failed, try PERMISSIVE.
    K_perm = []
    if not rel_std:
        for cid, text, _ in top:
            K_perm.extend(extract(text, cid, permissive=True))
    rel_perm = [c for c in K_perm if noun_match(c["noun"], stems)]
    relevant = rel_std or rel_perm

    top_scores = [s for _, _, s in top]
    distinct_chunks = len({c["chunk_id"] for c in relevant})
    values = [c["value"] for c in relevant]
    modal_share = (Counter(values).most_common(1)[0][1] / len(values)
                   if values else 0)

    c1 = intent in SUPPORTED_INTENTS
    c2 = distinct_chunks >= 3
    c3 = bool(rel_std)  # STANDARD sufficed
    c4 = bool(relevant)
    c5 = (len(top_scores) >= 2 and top_scores[1] > 0
          and top_scores[0] / max(top_scores[1], 1e-9) >= 1.5)
    c6 = modal_share == 1.0 and bool(values)

    return {
        "C1_intent_supported": c1,
        "C2_multi_source": c2,
        "C3_regular_surface": c3,
        "C4_noun_alignment": c4,
        "C5_retrieve_concentration": c5,
        "C6_value_coherence": c6,
        "score": sum([c1, c2, c3, c4, c5, c6]),
        "details": {
            "intent": intent,
            "K_std": len(K_std),
            "rel_std": len(rel_std),
            "rel_perm": len(rel_perm),
            "distinct_chunks": distinct_chunks,
            "values": values,
            "top_scores": [round(s, 3) for s in top_scores],
        },
    }


def main():
    rows = load_chunks()
    questions = load_questions()

    results = []
    for q in questions:
        h = health(q["question"], q.get("intent", "?"), rows)
        results.append({**q, **h})

    print("=== Health score distribution (out of 6) ===")
    score_dist = Counter(r["score"] for r in results)
    for s in range(7):
        print(f"  {s}/6: {score_dist.get(s, 0)}")
    print()

    print("=== Q14 anatomy ===")
    q14 = next(r for r in results if r["qid"] == "Q14")
    for c in ("C1_intent_supported", "C2_multi_source", "C3_regular_surface",
              "C4_noun_alignment", "C5_retrieve_concentration",
              "C6_value_coherence"):
        flag = "PASS" if q14[c] else "FAIL"
        print(f"  {c:<28} {flag}")
    print(f"  details: {json.dumps(q14['details'], ensure_ascii=False)}")
    print()

    print("=== Per-condition pass rate across all 35 ===")
    for c in ("C1_intent_supported", "C2_multi_source", "C3_regular_surface",
              "C4_noun_alignment", "C5_retrieve_concentration",
              "C6_value_coherence"):
        n = sum(1 for r in results if r[c])
        print(f"  {c:<28} {n}/35")
    print()

    print("=== Top scorers (>=4/6) ===")
    for r in sorted(results, key=lambda r: -r["score"]):
        if r["score"] >= 4:
            failed = [c for c in ("C1_intent_supported", "C2_multi_source",
                                  "C3_regular_surface", "C4_noun_alignment",
                                  "C5_retrieve_concentration",
                                  "C6_value_coherence") if not r[c]]
            print(f"  {r['qid']:<5} intent={r['intent']:<10} "
                  f"score={r['score']}/6  fails={failed}")
    print()

    print("=== Near-misses (5/6) — what one fix would unlock ===")
    for r in results:
        if r["score"] == 5:
            failed = next(c for c in ("C1_intent_supported", "C2_multi_source",
                                      "C3_regular_surface", "C4_noun_alignment",
                                      "C5_retrieve_concentration",
                                      "C6_value_coherence") if not r[c])
            print(f"  {r['qid']}  intent={r['intent']}  missing: {failed}")
            print(f"    details: {json.dumps(r['details'], ensure_ascii=False)}")
    print()

    print("=== Q5 (correct but unhealthy) — diagnostic of borderline answers ===")
    q5 = next(r for r in results if r["qid"] == "Q5")
    for c in ("C1_intent_supported", "C2_multi_source", "C3_regular_surface",
              "C4_noun_alignment", "C5_retrieve_concentration",
              "C6_value_coherence"):
        flag = "PASS" if q5[c] else "FAIL"
        print(f"  {c:<28} {flag}")
    print(f"  Q5 answers correctly (50) but scores {q5['score']}/6 — fragile.")


if __name__ == "__main__":
    main()
