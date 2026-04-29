"""
Pre-registered Q9 checks — exactly the hold/break criteria from the trace.
Stdlib unittest, no external deps.
"""

import unittest

from pilot import run_alternative_q9, run_primary_q9

QUESTION = "сколько специальных методов реализует класс Vector в примере 1-2"


class TestQ9Primary(unittest.TestCase):
    def setUp(self):
        self.state, self.winner = run_primary_q9(QUESTION)

    def test_three_typed_claims_extracted(self):
        types = {v["source_type"] for v in self.state.K.values()}
        self.assertEqual(
            types, {"author_anchor", "forward_reference", "code_literal"},
            f"expected all three source types in K, got {types}",
        )

    def test_three_distinct_values_before_resolution(self):
        values = sorted({v["value"] for v in self.state.K.values()})
        self.assertEqual(
            values, [4, 5, 6],
            f"expected typed claims with values 4/5/6, got {values}",
        )

    def test_conflict_was_detected(self):
        self.assertTrue(
            any("conflicting" in line for line in self.state.trace),
            "expected E=conflicting at some step",
        )

    def test_winner_is_author_anchor(self):
        self.assertIsNotNone(self.winner, "winner must be selected by P")
        self.assertEqual(self.winner.source_type, "author_anchor")
        self.assertEqual(self.winner.value, 5)

    def test_winner_carries_scope(self):
        self.assertIsNotNone(self.winner.scope_operator)
        self.assertIn("__init__", self.winner.scope_operator)

    def test_goal_solved(self):
        self.assertEqual(self.state.G[0].status, "solved")

    def test_only_one_hypothesis_active_after_narrow(self):
        active = [h for h in self.state.H if h.active]
        self.assertEqual(len(active), 1, f"|H_active| must be 1, got {len(active)}")


class TestQ9Alternative(unittest.TestCase):
    def setUp(self):
        self.state, self.winner = run_alternative_q9(QUESTION)

    def test_alternative_path_stalls_without_P(self):
        self.assertIsNone(
            self.winner,
            "refine_Ex + second retrieve must NOT resolve the conflict",
        )
        self.assertEqual(self.state.E, "conflicting")
        self.assertTrue(
            any("STALLED" in line for line in self.state.trace),
            "expected explicit STALLED log line",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
