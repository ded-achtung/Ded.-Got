"""Probe L: minimal tension-driven think-loop. Diagnostic, not prescriptive.

What's broken today (per pilot.py):
  run_primary is one-shot. retrieve once, extract once, evaluate once,
  return answer-or-refuse. T (tensions) is computed but never read as
  a re-entry condition. K=0 -> halt, period.

What this probe does:
  Wrap the existing parts in a bounded while-loop (max 3 iterations).
  After each iteration, if T['evidence_gap']=='HIGH' (i.e. K=0), pick
  ONE additional action and re-enter the loop. The actions are added
  one at a time so we can attribute *which* action sets Q5 free.

Three actions, applied cumulatively across iterations:

  iter 1: STANDARD       — pilot retrieve + permissive RU extractor (probe H)
  iter 2: PERMISSIVE_RE  — same retrieve, but extractor allows a
                           parenthetical / clause between number and noun
                           (the L2 brittleness fix observed empirically)
  iter 3: NOUN_FOCUS     — same chunks, extractor returns only claims whose
                           following-noun stem matches a noun in the question
                           ('задач' -> stems 'задач')

Goal: see whether Q5 (K=0 with single-pass standard extractor in probe H)
converges on value=50 once we hand the loop the missing actions.

This is exploratory. The probe is intentionally over-permissive on
extractor matching to surface signal; tightening is a later session.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path("/home/user/Ded.-Got/audits/puzzlebook35")
CHUNKS_PATH = ROOT / "audit_v0.chunks.jsonl"
QUESTIONS_PATH = ROOT / "audit_v0.questions.jsonl"
TOP_K = 4
MAX_ITER = 3

# Reuse numerals from probe H.
NUMERAL_WORDS_RU: dict[str, int] = {
    "один": 1, "одна": 1, "одно": 1, "одного": 1,
    "два": 2, "две": 2, "двух": 2,
    "три": 3, "трёх": 3, "трех": 3,
    "четыре": 4, "четырёх": 4, "четырех": 4,
    "пять": 5, "пяти": 5,
    "шесть": 6, "шести": 6,
    "семь": 7, "семи": 7,
    "восемь": 8, "восьми": 8,
    "девять": 9, "девяти": 9,
    "десять": 10, "десяти": 10,
    "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13,
    "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16,
    "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19,
    "двадцать": 20, "тридцать": 30, "сорок": 40,
    "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70,
    "восемьдесят": 80, "девяносто": 90, "сто": 100,
}

NUM_WORDS_ALT = "|".join(sorted(NUMERAL_WORDS_RU, key=len, reverse=True))

# Action 1 (STANDARD): same as probe H.
RE_DIGIT_STD = re.compile(r"\b(\d{1,4})\s+([а-яё]+)", re.IGNORECASE)
RE_WORD_STD = re.compile(rf"\b({NUM_WORDS_ALT})\s+([а-яё]+)", re.IGNORECASE)

# Action 2 (PERMISSIVE_RE): allow ONE parenthetical OR comma clause between
# number and noun. This targets exactly the Q5 failure: "50 (плюс несколько
# дополнительных) задач".
RE_DIGIT_PERMISSIVE = re.compile(
    r"\b(\d{1,4})\s+(?:\([^)]{0,80}\)\s+|—\s+|,\s+[^.,]{0,40}\s+)?([а-яё]+)",
    re.IGNORECASE,
)
RE_WORD_PERMISSIVE = re.compile(
    rf"\b({NUM_WORDS_ALT})\s+(?:\([^)]{{0,80}}\)\s+|—\s+|,\s+[^.,]{{0,40}}\s+)?([а-яё]+)",
    re.IGNORECASE,
)

QUESTION_NOUN_RE = re.compile(r"\b([а-яё]{4,})", re.IGNORECASE)


def load_chunks() -> list[dict]:
    with CHUNKS_PATH.open() as f:
        return [json.loads(line) for line in f]


def load_questions() -> list[dict]:
    with QUESTIONS_PATH.open() as f:
        return [json.loads(line) for line in f]


def tfidf_topk(question: str, rows: list[dict], top_k: int = TOP_K):
    docs = [r["content"] for r in rows]
    vec = TfidfVectorizer(
        lowercase=True, analyzer="word",
        token_pattern=r"(?u)\b\w\w+\b",
        ngram_range=(1, 1), norm="l2", sublinear_tf=False,
    )
    X = vec.fit_transform(docs)
    q = vec.transform([question])
    sims = cosine_similarity(q, X).ravel()
    pairs = [(rows[i]["chunk_id"], rows[i]["content"], float(sims[i]))
             for i in range(len(rows))]
    pairs.sort(key=lambda p: (-p[2], p[0]))
    return pairs[:top_k]


def extract(text: str, chunk_id: str, *, permissive: bool) -> list[dict]:
    rd = RE_DIGIT_PERMISSIVE if permissive else RE_DIGIT_STD
    rw = RE_WORD_PERMISSIVE if permissive else RE_WORD_STD
    out = []
    for m in rd.finditer(text):
        out.append({
            "chunk_id": chunk_id, "value": int(m.group(1)),
            "noun": m.group(2).lower(), "evidence": m.group(0).strip(),
            "form": "digit",
        })
    for m in rw.finditer(text):
        word = m.group(1).lower()
        out.append({
            "chunk_id": chunk_id, "value": NUMERAL_WORDS_RU[word],
            "noun": m.group(2).lower(), "evidence": m.group(0).strip(),
            "form": "word",
        })
    return out


def question_noun_stems(question: str) -> set[str]:
    """Take 4+ char Cyrillic words from the question, strip last 2 chars to
    approximate stems (joke-level: enough to match 'задач' to 'задачи',
    'параметр' to 'параметров')."""
    out = set()
    for m in QUESTION_NOUN_RE.finditer(question):
        w = m.group(1).lower()
        out.add(w[:-2] if len(w) > 5 else w)
    return out


def noun_match(claim_noun: str, stems: set[str]) -> bool:
    return any(claim_noun.startswith(s[:4]) for s in stems if s)


def think(qid: str, question: str, rows: list[dict]) -> dict:
    """Bounded loop. Add one new capability per iteration; halt when K>0
    after a noun-matched filter (i.e. we have a relevant claim) OR exhausted.
    """
    top = tfidf_topk(question, rows)
    stems = question_noun_stems(question)
    iterations = []

    K_all = []  # cumulative claims across iterations

    # iter 1: STANDARD
    K1 = []
    for cid, text, _ in top:
        K1.extend(extract(text, cid, permissive=False))
    iterations.append({
        "iter": 1, "action": "STANDARD",
        "K_size": len(K1),
        "values": sorted(set(c["value"] for c in K1)),
        "noun_matched": [c for c in K1 if noun_match(c["noun"], stems)],
    })
    K_all = K1

    # iter 2: PERMISSIVE_RE (only if iter 1 noun-matched K is empty)
    if not iterations[-1]["noun_matched"]:
        K2 = []
        for cid, text, _ in top:
            K2.extend(extract(text, cid, permissive=True))
        iterations.append({
            "iter": 2, "action": "PERMISSIVE_RE",
            "K_size": len(K2),
            "values": sorted(set(c["value"] for c in K2)),
            "noun_matched": [c for c in K2 if noun_match(c["noun"], stems)],
        })
        K_all = K2

    # iter 3: NOUN_FOCUS — already implicit; just record final filtered K
    final_relevant = [c for c in K_all if noun_match(c["noun"], stems)]
    if final_relevant or len(iterations) == 1:
        iterations.append({
            "iter": len(iterations) + 1, "action": "NOUN_FOCUS_FILTER",
            "K_size_after_filter": len(final_relevant),
            "values": sorted(set(c["value"] for c in final_relevant)),
            "claims": final_relevant,
        })

    # Verdict — what the loop would "answer".
    if final_relevant:
        # majority vote on value
        from collections import Counter
        vc = Counter(c["value"] for c in final_relevant)
        winner_value, winner_count = vc.most_common(1)[0]
        verdict = {
            "answer": winner_value,
            "support_count": winner_count,
            "all_values_with_counts": dict(vc),
        }
    else:
        verdict = {"answer": None, "reason": "no claims with question-noun stem"}

    return {
        "qid": qid, "question": question,
        "stems": sorted(stems),
        "retrieved_top": [(cid, round(score, 3)) for cid, _, score in top],
        "iterations": iterations,
        "verdict": verdict,
    }


if __name__ == "__main__":
    rows = load_chunks()
    questions = load_questions()
    targets = [q for q in questions if q.get("intent") == "how_many"]

    for q in targets:
        result = think(q["qid"], q["question"], rows)
        print(f"=== {result['qid']}: {result['question']} ===")
        print(f"  question stems: {result['stems']}")
        print(f"  retrieved: {result['retrieved_top']}")
        for it in result["iterations"]:
            print(f"  --- iter {it['iter']}: {it['action']} ---")
            for k, v in it.items():
                if k in ("iter", "action"):
                    continue
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    for c in v[:6]:
                        print(f"      {c['chunk_id']:<18} v={c['value']:<4} "
                              f"noun='{c['noun']}' '{c['evidence']}'")
                else:
                    print(f"      {k}: {v}")
        print(f"  VERDICT: {json.dumps(result['verdict'], ensure_ascii=False)}")
        print()
