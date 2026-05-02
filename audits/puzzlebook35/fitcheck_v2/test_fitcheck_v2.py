"""v2 tests focus on the four flips and the four no-regressions
pre-registered in FITCHECK_V2_DESIGN.md.

Plus pilot canaries (Q2, Q7, Q22) reused from v1 with v2 dispatcher.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from fitcheck_v2 import fit_check, final_outcome

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CHUNKS = REPO / "audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl"
RUNS_V1_TFIDF = REPO / "audits/puzzlebook35/runs/2026-05-02_v0_baseline.jsonl"
QUESTIONS = REPO / "audits/puzzlebook35/audit_v0.questions.jsonl"


def load_jsonl(p: Path):
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]


CHUNKS_BY_ID = {c["chunk_id"]: c for c in load_jsonl(CHUNKS)}
QUESTIONS_BY_QID = {q["qid"]: q for q in load_jsonl(QUESTIONS)}
TFIDF_RUN_BY_QID = {r["qid"]: r for r in load_jsonl(RUNS_V1_TFIDF)}


def case(qid: str):
    q = QUESTIONS_BY_QID[qid]
    r = TFIDF_RUN_BY_QID[qid]
    return q["intent"], q["question"], r["retrieved_topk_chunk_ids"]


class TestFlips(unittest.TestCase):
    """Per FITCHECK_V2_DESIGN.md REVISION 1: only Q9 and Q13 flip.
    Q16 and Q29 stay match (top-4 contains alignment-4 chunks; for
    Q16 that chunk pb_raw_13 IS the correct answer; for Q29 pb_raw_06
    is topic-related but answer-bearing chunk pb_raw_07 not in top-4).
    """

    def test_q9_flips(self):
        intent, question, topk = case("Q9")
        status, _, _ = fit_check(intent, question, topk, CHUNKS_BY_ID)
        self.assertEqual(status, "mismatch")
        self.assertEqual(final_outcome(status, intent), "fit_refuse")

    def test_q13_flips(self):
        intent, question, topk = case("Q13")
        status, _, _ = fit_check(intent, question, topk, CHUNKS_BY_ID)
        self.assertEqual(status, "mismatch")
        self.assertEqual(final_outcome(status, intent), "fit_refuse")

    def test_q16_stays_match(self):
        # REV1: pb_raw_13 (typing rationale) is in top-4 with alignment 4
        intent, question, topk = case("Q16")
        status, _, _ = fit_check(intent, question, topk, CHUNKS_BY_ID)
        self.assertEqual(status, "match")
        self.assertEqual(final_outcome(status, intent), "hit")

    def test_q29_stays_match(self):
        # REV1: pb_raw_06 in top-4 with alignment 4; topic-related,
        # not answer-bearing — out of v2 scope (deferred to v3)
        intent, question, topk = case("Q29")
        status, _, _ = fit_check(intent, question, topk, CHUNKS_BY_ID)
        self.assertEqual(status, "match")
        self.assertEqual(final_outcome(status, intent), "hit")


class TestNoRegression(unittest.TestCase):
    """Pre-registered: Q1, Q21, Q23, Q32 (and other known-correct) must
    stay match→hit."""

    def test_q1_stays_match(self):
        intent, question, topk = case("Q1")
        status, _, _ = fit_check(intent, question, topk, CHUNKS_BY_ID)
        self.assertEqual(status, "match")
        self.assertEqual(final_outcome(status, intent), "hit")

    def test_q21_stays_match(self):
        intent, question, topk = case("Q21")
        status, _, _ = fit_check(intent, question, topk, CHUNKS_BY_ID)
        self.assertEqual(status, "match")
        self.assertEqual(final_outcome(status, intent), "hit")

    def test_q23_stays_match(self):
        intent, question, topk = case("Q23")
        status, _, _ = fit_check(intent, question, topk, CHUNKS_BY_ID)
        self.assertEqual(status, "match")
        self.assertEqual(final_outcome(status, intent), "hit")

    def test_q32_stays_match(self):
        intent, question, topk = case("Q32")
        status, _, _ = fit_check(intent, question, topk, CHUNKS_BY_ID)
        self.assertEqual(status, "match")
        self.assertEqual(final_outcome(status, intent), "hit")


class TestCanaries(unittest.TestCase):
    """Pre-registered: pilot canaries Q2/Q7/Q22 unchanged from v1."""

    def test_q2_match_hit(self):
        intent, question, topk = case("Q2")
        status, _, _ = fit_check(intent, question, topk, CHUNKS_BY_ID)
        self.assertEqual(status, "match")
        self.assertEqual(final_outcome(status, intent), "hit")

    def test_q7_mismatch_fit_refuse(self):
        intent, question, topk = case("Q7")
        status, _, _ = fit_check(intent, question, topk, CHUNKS_BY_ID)
        self.assertEqual(status, "mismatch")
        self.assertEqual(final_outcome(status, intent), "fit_refuse")

    def test_q22_mismatch_fit_refuse(self):
        intent, question, topk = case("Q22")
        status, _, _ = fit_check(intent, question, topk, CHUNKS_BY_ID)
        self.assertEqual(status, "mismatch")
        self.assertEqual(final_outcome(status, intent), "fit_refuse")


class TestYoNormalization(unittest.TestCase):
    """ё-normalization: серьёзной (question) ↔ серьезные (chunk) should
    share a stem after ё→е mapping."""

    def test_yo_e_share_stem(self):
        chunks = {
            "test_chunk": {
                "chunk_id": "test_chunk",
                "content": "Это серьезные задачи и шуточные задачи.",
                "section_path": ["test"],
            }
        }
        status, _, details = fit_check(
            "what",
            "Чем отличаются серьёзные и шуточные задачи?",
            ["test_chunk"], chunks, downstream_k=1,
        )
        self.assertEqual(status, "match")
        self.assertGreaterEqual(details["best_overlap"], 2)


if __name__ == "__main__":
    unittest.main()
