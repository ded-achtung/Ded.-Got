"""
Stage 2: Q4 with the Q9-trained extractors, unmodified.

Predicted result (per the user's analysis): extract_claims does NOT generalise
between intra-class dunder count (Q9) and collection cardinality (Q4). The
_code_literal detector fires on c003 (FrenchDeck class body has three dunder
defs: __init__, __len__, __getitem__) and produces a typed_claim with value=3.
Neither _author_anchor nor _forward_reference matches anything in the Q4
chunks. Result: K has one irrelevant claim; pilot reports 3 with full
confidence (E=supported); no conflict, no narrow_hypothesis call.

This is the silent-wrong failure mode and the test pins it down explicitly.
"""

import unittest

from claims import extract_claims
from corpus import Q4_CHUNKS
from pilot import run_primary

QUESTION = "сколько карт в колоде FrenchDeck в примере 1-1"
QUERY = "FrenchDeck cards count Example 1-1"
EX = "count of cards in FrenchDeck Example 1-1"


class TestQ4Unextended(unittest.TestCase):
    def setUp(self):
        self.state, self.winner = run_primary(
            QUESTION, QUERY, Q4_CHUNKS, extractor=extract_claims, ex=EX,
        )

    def test_q4_chunks_are_retrieved(self):
        retrieved_in_trace = [
            line for line in self.state.trace if line.startswith("step1: retrieve(")
        ]
        self.assertEqual(len(retrieved_in_trace), 1)
        for cid in ("c003", "c033"):
            self.assertIn(cid, retrieved_in_trace[0])

    def test_only_one_claim_extracted(self):
        self.assertEqual(
            len(self.state.K), 1,
            f"expected exactly 1 claim from unextended extractors, "
            f"got {len(self.state.K)}: {list(self.state.K)}",
        )

    def test_only_claim_is_irrelevant_code_literal(self):
        only = next(iter(self.state.K.values()))
        self.assertEqual(only["source_type"], "code_literal")
        self.assertEqual(
            only["value"], 3,
            "c003 has three dunder defs (__init__, __len__, __getitem__); "
            "_code_literal counts those, not the 52 cards",
        )

    def test_no_author_anchor_was_detected(self):
        types = {v["source_type"] for v in self.state.K.values()}
        self.assertNotIn(
            "author_anchor", types,
            "c033 contains 'list made of 52 cards' but the Q9-trained "
            "_author_anchor regex requires 'special methods' phrasing",
        )

    def test_pilot_silently_returns_wrong_answer(self):
        self.assertIsNotNone(self.winner)
        self.assertEqual(self.state.G[0].status, "solved")
        self.assertEqual(self.state.E, "supported")
        self.assertEqual(
            self.winner.value, 3,
            "pilot reports 3 with E=supported; correct answer is 52. "
            "This is the silent-wrong failure mode of unextended extractors.",
        )
        self.assertNotEqual(self.winner.value, 52)

    def test_narrow_hypothesis_was_not_invoked(self):
        self.assertFalse(
            any("narrow_hypothesis" in line for line in self.state.trace),
            "with a single claim there is no conflict, so P never fires",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
