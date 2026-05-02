"""Probe G5: L think-loop on all 35 questions, full intent grid.

Goal: real baseline of the L think-loop on the live audit corpus, not just
the two how_many questions.

For each of 35 questions:
  - run TF-IDF retrieve (top-4)
  - run L's two-iter extractor (STANDARD then PERMISSIVE_RE if needed)
  - apply NOUN_FOCUS filter
  - classify outcome:
      ANSWER  — loop produced a numeric verdict
      REFUSE  — no noun-matched claim survived

Cross-check:
  - Q5/Q14 (the only two how_many): expect ANSWER, value should match probe L
  - Q2 manual: intent=what, expects modules pygame/PythonTurtle. L extractor
    is numeric-only — should REFUSE (no number expected). Spurious ANSWER
    here = false positive.
  - Q22 manual: intent=when, answerable_in_corpus=False, audit found 0 year
    hits. L extractor is numeric — IF it answers, it's a wrong-typed claim.
  - Q7 manual: intent=who, answerable_in_corpus=False. L should REFUSE.

This measures L's behaviour as a generalist; it was designed for how_many
and we want to see how it misfires on other intents.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))

from probe_l_thinkloop import (  # noqa: E402
    extract,
    load_chunks,
    load_questions,
    noun_match,
    question_noun_stems,
    tfidf_topk,
)

MANUAL_PATH = Path("/home/user/Ded.-Got/audits/puzzlebook35/audit_v0.manual.jsonl")


def load_manual() -> dict[str, dict]:
    out = {}
    with MANUAL_PATH.open() as f:
        for line in f:
            row = json.loads(line)
            out[row["qid"]] = row
    return out


def run_loop(question: str, rows: list[dict]) -> dict:
    top = tfidf_topk(question, rows)
    stems = question_noun_stems(question)

    K1 = []
    for cid, text, _ in top:
        K1.extend(extract(text, cid, permissive=False))
    matched1 = [c for c in K1 if noun_match(c["noun"], stems)]
    used = "STANDARD"
    final = matched1
    if not matched1:
        K2 = []
        for cid, text, _ in top:
            K2.extend(extract(text, cid, permissive=True))
        matched2 = [c for c in K2 if noun_match(c["noun"], stems)]
        if matched2:
            used = "PERMISSIVE_RE"
            final = matched2

    if final:
        vc = Counter(c["value"] for c in final)
        winner_value, winner_count = vc.most_common(1)[0]
        return {
            "outcome": "ANSWER",
            "answer": winner_value,
            "support_count": winner_count,
            "iter_used": used,
            "claims": final,
        }
    return {"outcome": "REFUSE", "iter_used": used}


def main():
    rows = load_chunks()
    questions = load_questions()
    manual = load_manual()

    by_intent: dict[str, Counter] = {}
    detail = []

    for q in questions:
        intent = q.get("intent", "?")
        result = run_loop(q["question"], rows)
        by_intent.setdefault(intent, Counter())[result["outcome"]] += 1
        detail.append({
            "qid": q["qid"], "intent": intent,
            "outcome": result["outcome"],
            "answer": result.get("answer"),
            "iter_used": result["iter_used"],
            "support_count": result.get("support_count"),
        })

    print("=== Outcome by intent ===")
    print(f"{'intent':<10} {'ANSWER':>8} {'REFUSE':>8} {'total':>8}")
    for intent in sorted(by_intent):
        c = by_intent[intent]
        print(f"{intent:<10} {c['ANSWER']:>8} {c['REFUSE']:>8} "
              f"{sum(c.values()):>8}")
    print()

    print("=== ANSWER cases — to inspect for false positives ===")
    for d in detail:
        if d["outcome"] == "ANSWER":
            star = " *" if d["intent"] != "how_many" else ""
            print(f"  {d['qid']:<5} intent={d['intent']:<10} "
                  f"answer={d['answer']:<5} support={d['support_count']:<3} "
                  f"({d['iter_used']}){star}")
    print("  * non-how_many ANSWER = likely false positive (numeric extractor "
          "fired on non-numeric intent)")
    print()

    print("=== Cross-check vs manual labels (Q2, Q7, Q22) ===")
    for qid in ("Q2", "Q7", "Q22"):
        m = manual.get(qid)
        d = next(x for x in detail if x["qid"] == qid)
        expected = ("ANSWER" if m.get("answerable_in_corpus")
                    and m.get("intent") == "how_many"
                    else "REFUSE_or_NON_NUMERIC")
        agree = "?"
        if expected == "REFUSE_or_NON_NUMERIC" and d["outcome"] == "REFUSE":
            agree = "AGREE"
        elif expected == "REFUSE_or_NON_NUMERIC" and d["outcome"] == "ANSWER":
            agree = "FALSE_POSITIVE"
        print(f"  {qid:<5} intent={m['intent']:<10} "
              f"answerable={m.get('answerable_in_corpus')!s:<5} "
              f"audit_outcome={m.get('final_outcome'):<12} "
              f"L_outcome={d['outcome']:<8} -> {agree}")
    print()

    print("=== Detailed full table ===")
    print(f"{'qid':<6} {'intent':<10} {'outcome':<8} {'answer':<8} "
          f"{'iter':<14} {'support':<7}")
    for d in detail:
        print(f"{d['qid']:<6} {d['intent']:<10} {d['outcome']:<8} "
              f"{str(d.get('answer') or '-'):<8} {d['iter_used']:<14} "
              f"{str(d.get('support_count') or '-'):<7}")


if __name__ == "__main__":
    main()
