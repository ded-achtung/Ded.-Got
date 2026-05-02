"""Probe H: minimal Russian numeric extractor on the live audit corpus.

Goal: measure whether ANY numeric claim survives from real Russian chunks
when the regex is rewritten for Russian. This is NOT a polished claims.py
replacement — it is a deliberately permissive probe to bound capacity.

Pipeline:
  TF-IDF retrieve (best of three from G2) -> top-4 chunks
  -> _ru_numeric_phrase extractor (digits + cardinal numerals 1-100)
  -> dump all (value, noun, evidence) tuples

What we measure:
  Q14 'Сколько параметров принимает filter_strings_containing_a':
    expect 'один параметр' to surface with value=1 from pb_t01_001
  Q5  'Сколько серьёзных задач в книге':
    expect a numeric phrase about задач to surface from pb_intro chunks

What we do NOT do:
  - intent-aware filtering (forbidden by REPORT.md discipline note)
  - integration with run_primary or P (extract is the only thing under test)
  - any claim-pruning by relevance to the question's noun
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

# Cardinal numerals in nominative + most common oblique forms a reader would
# write inline. Covers 1-10 fully, then a sparse selection of 11-100.
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

DIGIT_RE = re.compile(r"\b(\d{1,4})\s+([а-яё]+)", re.IGNORECASE)
WORD_RE = re.compile(
    r"\b(" + "|".join(sorted(NUMERAL_WORDS_RU, key=len, reverse=True)) + r")\s+([а-яё]+)",
    re.IGNORECASE,
)


def extract_ru_numeric(chunk_id: str, text: str) -> list[dict]:
    """All (numeric, noun-following) pairs. Permissive on purpose — produces
    high-recall low-precision claim list. No intent filter.
    """
    out: list[dict] = []
    for m in DIGIT_RE.finditer(text):
        out.append({
            "chunk_id": chunk_id,
            "value": int(m.group(1)),
            "noun": m.group(2).lower(),
            "evidence": m.group(0),
            "form": "digit",
        })
    for m in WORD_RE.finditer(text):
        word = m.group(1).lower()
        out.append({
            "chunk_id": chunk_id,
            "value": NUMERAL_WORDS_RU[word],
            "noun": m.group(2).lower(),
            "evidence": m.group(0),
            "form": "word",
        })
    return out


# ---------------- retrieval (TF-IDF, copied from G2) ----------------

def load_chunks() -> list[dict]:
    with CHUNKS_PATH.open() as f:
        return [json.loads(line) for line in f]


def load_questions() -> list[dict]:
    with QUESTIONS_PATH.open() as f:
        return [json.loads(line) for line in f]


def tfidf_retrieve(question: str, rows: list[dict], top_k: int = TOP_K):
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


def probe(qid: str, question: str, rows: list[dict]) -> dict:
    top = tfidf_retrieve(question, rows)
    all_claims = []
    per_chunk = {}
    for cid, text, score in top:
        cs = extract_ru_numeric(cid, text)
        per_chunk[cid] = len(cs)
        all_claims.extend(cs)
    return {
        "qid": qid,
        "question": question,
        "retrieved": [(cid, round(score, 3)) for cid, _, score in top],
        "claims_per_chunk": per_chunk,
        "K_size": len(all_claims),
        "claim_values": [c["value"] for c in all_claims],
        "value_set": sorted(set(c["value"] for c in all_claims)),
        "claims": all_claims,
    }


if __name__ == "__main__":
    rows = load_chunks()
    questions = load_questions()
    targets = [q for q in questions if q.get("intent") == "how_many"]

    for q in targets:
        result = probe(q["qid"], q["question"], rows)
        print(f"=== {result['qid']}: {result['question']} ===")
        print(f"  retrieved: {result['retrieved']}")
        print(f"  claims/chunk: {result['claims_per_chunk']}")
        print(f"  K_size: {result['K_size']}")
        print(f"  value set: {result['value_set']}")
        print(f"  claims sample (first 12):")
        for c in result["claims"][:12]:
            print(f"    {c['chunk_id']:<18} v={c['value']:<4} "
                  f"noun='{c['noun']}' [{c['form']}] '{c['evidence']}'")
        print()
