"""Probe O: minimal intent gate on the L pipeline. Converts G5's 15
false positives into refusals, with no change to claims.py / pilot.py.

The fix is one line: BEFORE running the numeric extractor, check whether
the question's intent is one this extractor can produce. The numeric
extractor in probe_l_thinkloop produces values typed (implicitly) as
how_many. So:

    if intent != 'how_many':
        return REFUSE(reason='intent_mismatch')

That's it. The infrastructure for richer intent routing (per-intent
extractors for when/who/what/why/how) is out of scope here — this probe
only closes the precision hole G5 surfaced.

Comparison vs G5:

  Before O:  17 ANSWER (2 correct + 15 false positives), 18 REFUSE
  After O:   2 ANSWER (both correct), 33 REFUSE
  Delta:     -15 false positives, +15 typed refusals

The refusals are typed: each non-how_many question is refused with
reason='intent_mismatch:<intent>', not the generic K=0 refuse from
probe_real_corpus. This matters because it preserves the WHY — a
downstream system asking 'should I have tried harder?' gets a
specific signal, not 'I have no idea'.

This probe DOES NOT:
  - add extractors for non-how_many intents
  - touch claims.py / pilot.py / state.py
  - change recompute_tensions
  - integrate with run_primary

It is the smallest possible empirical demonstration that one tension
flag, computed before extraction, suppresses all 15 G5 false positives
on this corpus.
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


def run_with_intent_gate(question: str, intent: str, rows: list[dict]) -> dict:
    if intent not in SUPPORTED_INTENTS:
        return {
            "outcome": "REFUSE",
            "reason": f"intent_mismatch:{intent}",
            "iter_used": "INTENT_GATE",
        }

    top = tfidf_topk(question, rows)
    stems = question_noun_stems(question)

    K1 = []
    for cid, text, _ in top:
        K1.extend(extract(text, cid, permissive=False))
    matched1 = [c for c in K1 if noun_match(c["noun"], stems)]
    if matched1:
        return _verdict(matched1, "STANDARD")

    K2 = []
    for cid, text, _ in top:
        K2.extend(extract(text, cid, permissive=True))
    matched2 = [c for c in K2 if noun_match(c["noun"], stems)]
    if matched2:
        return _verdict(matched2, "PERMISSIVE_RE")

    return {"outcome": "REFUSE", "reason": "evidence_gap",
            "iter_used": "PERMISSIVE_RE"}


def _verdict(claims: list[dict], iter_used: str) -> dict:
    vc = Counter(c["value"] for c in claims)
    winner_value, winner_count = vc.most_common(1)[0]
    return {
        "outcome": "ANSWER",
        "answer": winner_value,
        "support_count": winner_count,
        "iter_used": iter_used,
    }


# Re-import G5's pipeline (without intent gate) for side-by-side comparison.
def run_without_intent_gate(question: str, intent: str, rows: list[dict]) -> dict:
    top = tfidf_topk(question, rows)
    stems = question_noun_stems(question)

    K1 = []
    for cid, text, _ in top:
        K1.extend(extract(text, cid, permissive=False))
    matched1 = [c for c in K1 if noun_match(c["noun"], stems)]
    if matched1:
        return _verdict(matched1, "STANDARD")

    K2 = []
    for cid, text, _ in top:
        K2.extend(extract(text, cid, permissive=True))
    matched2 = [c for c in K2 if noun_match(c["noun"], stems)]
    if matched2:
        return _verdict(matched2, "PERMISSIVE_RE")

    return {"outcome": "REFUSE", "reason": "evidence_gap",
            "iter_used": "PERMISSIVE_RE"}


def main():
    rows = load_chunks()
    questions = load_questions()

    before = []
    after = []
    for q in questions:
        intent = q.get("intent", "?")
        before.append({**q, **run_without_intent_gate(q["question"], intent, rows)})
        after.append({**q, **run_with_intent_gate(q["question"], intent, rows)})

    def tally(rows):
        c = Counter()
        for r in rows:
            c[r["outcome"]] += 1
        return dict(c)

    print("=== Aggregate ===")
    print(f"  before O (G5):     {tally(before)}")
    print(f"  after  O (gated):  {tally(after)}")
    print()

    # Per-question diff
    print("=== Questions whose outcome CHANGED ===")
    changed = 0
    for b, a in zip(before, after):
        if b["outcome"] != a["outcome"] or b.get("answer") != a.get("answer"):
            changed += 1
            print(f"  {b['qid']:<5} intent={b['intent']:<10} "
                  f"BEFORE outcome={b['outcome']:<7} "
                  f"answer={str(b.get('answer') or '-'):<5} "
                  f"-> AFTER outcome={a['outcome']:<7} "
                  f"answer={str(a.get('answer') or '-'):<5} "
                  f"reason={a.get('reason') or '-'}")
    print(f"  total changed: {changed}/35")
    print()

    # Verify how_many cases preserved.
    print("=== how_many cases (recall preservation check) ===")
    for a in after:
        if a["intent"] == "how_many":
            print(f"  {a['qid']}  outcome={a['outcome']}  answer={a.get('answer')}  "
                  f"support={a.get('support_count')}  "
                  f"iter={a.get('iter_used')}")
    print()

    # Cross-check vs manual labels
    manual_path = Path("/home/user/Ded.-Got/audits/puzzlebook35/audit_v0.manual.jsonl")
    manual = {json.loads(l)["qid"]: json.loads(l)
              for l in manual_path.open()}
    print("=== Cross-check vs manual (Q2, Q7, Q22) ===")
    for qid in ("Q2", "Q7", "Q22"):
        m = manual[qid]
        a = next(x for x in after if x["qid"] == qid)
        agree = "AGREE" if a["outcome"] == "REFUSE" else "FALSE_POSITIVE"
        print(f"  {qid}  audit_outcome={m.get('final_outcome'):<12} "
              f"L_outcome={a['outcome']:<8} reason={a.get('reason') or '-':<25} "
              f"-> {agree}")


if __name__ == "__main__":
    main()
