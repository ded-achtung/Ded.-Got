"""
Stage 3: Q4 with extended extractors. Three scenarios.

3A  full extractor set + full Q4 corpus
    -> K has three claims (c003 code_literal=3, c033 author_anchor=52,
       c004 code_literal=52); E=conflicting; P fires rule_1; answer=52.

3B1 author phrase detector disabled + corpus restricted to c004 only
    -> K has one claim (c004 code_literal=52); E=supported; no narrow
       needed. Demonstrates that an absent top-priority source does not
       break the pilot when no within-type conflict exists.

3B2 author phrase detector disabled + corpus = {c003, c004}
    -> K has two code_literal claims with values 3 and 52; E=conflicting;
       P fires rule_3, but the within-type bucket is ordered by retrieve
       rank, so c003 (irrelevant dunder count = 3) wins over c004 (52).
       This is a discovered boundary: P resolves cross-type conflicts
       but NOT within-type. Documented here as a silent-wrong outcome.
"""

import unittest

from claims_extended import (
    extract_claims_extended,
    extract_claims_no_author_phrase,
)
from corpus import Q4_CHUNKS
from pilot import run_primary

QUESTION = "сколько карт в колоде FrenchDeck в примере 1-1"
QUERY = "FrenchDeck cards count Example 1-1"
EX = "count of cards in FrenchDeck Example 1-1"


class TestQ4ExtendedAll(unittest.TestCase):
    """3A — full extractor + full corpus, expect P rule_1 to fire."""

    def setUp(self):
        self.state, self.winner = run_primary(
            QUESTION, QUERY, Q4_CHUNKS,
            extractor=extract_claims_extended, ex=EX,
        )

    def test_three_typed_claims_in_K(self):
        self.assertEqual(len(self.state.K), 3)

    def test_both_source_types_present(self):
        types = {v["source_type"] for v in self.state.K.values()}
        self.assertEqual(types, {"author_anchor", "code_literal"})

    def test_conflict_detected(self):
        self.assertTrue(
            any("E=conflicting" in line for line in self.state.trace),
            "expected E=conflicting at step2",
        )

    def test_rule_1_fired(self):
        fired = [line for line in self.state.trace if "fired=" in line]
        self.assertEqual(len(fired), 1)
        self.assertIn("fired=author_anchor", fired[0])
        self.assertIn("rule_1", fired[0])

    def test_winner_is_author_52(self):
        self.assertIsNotNone(self.winner)
        self.assertEqual(self.winner.source_type, "author_anchor")
        self.assertEqual(self.winner.value, 52)
        self.assertEqual(self.state.G[0].status, "solved")


class TestQ4ExtendedFallbackClean(unittest.TestCase):
    """3B1 — author phrase detector off, corpus = {c004}.

    Single claim path: no conflict, no P invocation needed; answer=52.
    """

    def setUp(self):
        minimal = {"c004": Q4_CHUNKS["c004"]}
        self.state, self.winner = run_primary(
            QUESTION, QUERY, minimal,
            extractor=extract_claims_no_author_phrase, ex=EX,
        )

    def test_only_one_claim(self):
        self.assertEqual(len(self.state.K), 1)

    def test_no_author_anchor_present(self):
        types = {v["source_type"] for v in self.state.K.values()}
        self.assertEqual(types, {"code_literal"})

    def test_E_supported_no_conflict(self):
        self.assertEqual(self.state.E, "supported")

    def test_narrow_hypothesis_not_called(self):
        self.assertFalse(
            any("narrow_hypothesis" in line for line in self.state.trace),
            "single-claim path bypasses P",
        )

    def test_answer_is_52(self):
        self.assertEqual(self.winner.value, 52)
        self.assertEqual(self.winner.source_type, "code_literal")


class TestQ4ExtendedFallbackDirty(unittest.TestCase):
    """3B2 — author phrase detector off, corpus = {c003, c004}.

    Both claims are code_literal (3 vs 52). P walks past empty author and
    forward buckets, fires rule_3, then picks the FIRST claim in the
    code_literal bucket. Retrieve scoring puts c003 ahead of c004, so
    pilot returns 3 — wrong answer with full confidence.

    This test pins the discovered boundary: P does not resolve within-type
    conflicts. The expected fix is intent-aware extraction (so c003's
    dunder count never enters K when the question asks about cards) or a
    secondary tie-break rule.
    """

    def setUp(self):
        two = {"c003": Q4_CHUNKS["c003"], "c004": Q4_CHUNKS["c004"]}
        self.state, self.winner = run_primary(
            QUESTION, QUERY, two,
            extractor=extract_claims_no_author_phrase, ex=EX,
        )

    def test_two_claims_both_code_literal(self):
        self.assertEqual(len(self.state.K), 2)
        types = {v["source_type"] for v in self.state.K.values()}
        self.assertEqual(types, {"code_literal"})

    def test_values_3_and_52(self):
        values = sorted(v["value"] for v in self.state.K.values())
        self.assertEqual(values, [3, 52])

    def test_rule_3_fires(self):
        fired = [line for line in self.state.trace if "fired=" in line]
        self.assertEqual(len(fired), 1)
        self.assertIn("fired=code_literal", fired[0])
        self.assertIn("rule_3", fired[0])

    def test_winner_is_wrong_answer_3(self):
        # Documented silent-wrong outcome — P alone cannot disambiguate
        # within a single source_type. Retrieve order determines the pick.
        self.assertEqual(self.winner.value, 3)
        self.assertNotEqual(self.winner.value, 52)
        self.assertEqual(self.state.E, "supported")
        self.assertEqual(self.state.G[0].status, "solved")


if __name__ == "__main__":
    unittest.main(verbosity=2)
