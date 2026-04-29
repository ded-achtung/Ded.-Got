"""
Pilot: 7-slot ThoughtState + tension-driven think_step.

Parametrised over (question, query, chunks, extractor) so the same loop
runs for Q9 (Vector special methods) and Q4 (FrenchDeck cards).
"""

from __future__ import annotations

from typing import Callable

from claims import extract_claims
from corpus import Q4_CHUNKS, Q9_CHUNKS
from state import Goal, Hypothesis, ThoughtState

PREFERENCES: dict[str, list[str]] = {
    "how_many": ["author_anchor", "forward_reference", "code_literal"],
}

Extractor = Callable[[str, dict], list[dict]]


def _score(query: str, chunk: dict) -> int:
    q = {t.lower() for t in query.split() if len(t) > 2}
    text = chunk["text"].lower()
    return sum(1 for t in q if t in text)


def retrieve(query: str, chunks: dict[str, dict], top_k: int = 4) -> list[tuple[str, dict]]:
    ranked = sorted(
        chunks.items(),
        key=lambda kv: _score(query, kv[1]),
        reverse=True,
    )
    return [(cid, c) for cid, c in ranked[:top_k] if _score(query, c) > 0]


def extract_into(
    state: ThoughtState,
    retrieved: list[tuple[str, dict]],
    extractor: Extractor,
) -> None:
    for cid, chunk in retrieved:
        for claim in extractor(cid, chunk):
            key = f"{cid}:{claim['source_type']}"
            state.K[key] = claim
            label = f"count={claim['value']}/{claim['source_type']}"
            if not any(h.label == label for h in state.H):
                state.H.append(Hypothesis(
                    label=label,
                    source_type=claim["source_type"],
                    value=claim["value"],
                    scope_operator=claim.get("scope_operator"),
                    support=[key],
                ))


def evaluate(state: ThoughtState) -> None:
    active = [h for h in state.H if h.active]
    if not active:
        state.E = "unsupported"
    elif len({h.value for h in active}) > 1:
        state.E = "conflicting"
    else:
        state.E = "supported"


def recompute_tensions(state: ThoughtState) -> None:
    state.T.clear()
    if not state.K:
        state.T["evidence_gap"] = "HIGH"
    active = [h for h in state.H if h.active]
    if state.E == "conflicting":
        state.T["unresolved_ambiguity"] = "HIGH"
    elif len(active) > 1:
        state.T["unresolved_ambiguity"] = "MEDIUM"


def narrow_hypothesis(state: ThoughtState) -> tuple[Hypothesis | None, str]:
    """Return (winner, source_type_chosen). source_type_chosen names which P
    rule actually fired (rule_1 / rule_2 / rule_3) so traces can record fallback.
    """
    order = state.P.get(state.intent, [])
    if not order:
        return None, ""
    active = [h for h in state.H if h.active]
    by_priority = {st: [] for st in order}
    for h in active:
        if h.source_type in by_priority:
            by_priority[h.source_type].append(h)
    for st in order:
        bucket = by_priority[st]
        if bucket:
            winner = bucket[0]
            for h in state.H:
                if h is not winner:
                    h.active = False
            return winner, st
    return None, ""


def refine_Ex(state: ThoughtState, clarified: str) -> None:
    state.Ex = clarified


def initial_state(question: str, ex: str) -> ThoughtState:
    s = ThoughtState()
    s.intent = "how_many"
    s.G.append(Goal(
        question=question,
        expected_form="number with optional scope clause",
    ))
    s.Ex = ex
    s.H.append(Hypothesis(
        label="single count exists in canonical form",
        source_type="unknown",
        value=None,
    ))
    s.E = "unknown"
    s.T = {"evidence_gap": "HIGH"}
    s.P = PREFERENCES.copy()
    s.log("step0: initial state seeded; P loaded from registry")
    return s


def run_primary(
    question: str,
    query: str,
    chunks: dict[str, dict],
    extractor: Extractor = extract_claims,
    ex: str = "count scoped to the named example",
) -> tuple[ThoughtState, Hypothesis | None]:
    s = initial_state(question, ex)

    hits = retrieve(query, chunks)
    s.log(f"step1: retrieve('{query}') -> {[cid for cid, _ in hits]}")
    s.H = [h for h in s.H if h.source_type != "unknown"]
    extract_into(s, hits, extractor)
    s.log(f"step1: K populated with {len(s.K)} typed claims; |H|={len(s.H)}")

    evaluate(s)
    recompute_tensions(s)
    s.log(f"step2: E={s.E}; T={s.T}")

    winner: Hypothesis | None = None
    if s.E == "conflicting":
        winner, fired = narrow_hypothesis(s)
        if winner is None:
            s.log("step3: narrow_hypothesis FAILED — no priority match")
            return s, None
        priority_index = s.P[s.intent].index(fired)
        rule_id = f"rule_{priority_index + 1}"
        s.log(
            f"step3: narrow_hypothesis(P[{s.intent}]) fired={fired} "
            f"({rule_id}) -> {winner.label} scope={winner.scope_operator!r}"
        )
        evaluate(s)
        recompute_tensions(s)
        s.log(f"step3: E={s.E}; T={s.T}")
    elif s.E == "supported":
        winner = next((h for h in s.H if h.active), None)
        if winner is not None:
            s.log(
                f"step3: single-claim path, no narrow needed -> {winner.label}"
            )
    elif s.E == "unsupported":
        s.log("step3: K empty — extractor produced no claims, halting")
        return s, None

    if winner is not None:
        for goal in s.G:
            goal.status = "solved"
        s.log(f"step4: answer = {winner.value} (scope={winner.scope_operator!r})")
    return s, winner


def run_alternative(
    question: str,
    query: str,
    chunks: dict[str, dict],
    extractor: Extractor = extract_claims,
    ex: str = "count scoped to the named example",
    refined_ex: str = "explicit author statement of count",
    query2: str | None = None,
) -> tuple[ThoughtState, Hypothesis | None]:
    """Refine Ex + second retrieve, no P. Should stall at conflict."""
    s = initial_state(question, ex)
    s.P = {}  # drop P for this run

    hits = retrieve(query, chunks)
    s.log(f"step1: retrieve -> {[cid for cid, _ in hits]}")
    s.H = [h for h in s.H if h.source_type != "unknown"]
    extract_into(s, hits, extractor)
    evaluate(s)
    recompute_tensions(s)
    s.log(f"step2: E={s.E}; T={s.T}")

    refine_Ex(s, refined_ex)
    hits2 = retrieve(query2 or query, chunks)
    s.log(f"step3: refine_Ex + retrieve -> {[cid for cid, _ in hits2]}")
    extract_into(s, hits2, extractor)
    evaluate(s)
    recompute_tensions(s)
    s.log(f"step3: E={s.E}; T={s.T}")

    if s.E == "conflicting":
        s.log("step4: STALLED — refine_Ex cannot resolve conflict without P")
        return s, None

    winner = next((h for h in s.H if h.active), None)
    return s, winner


# Q9 wrappers preserve the original signature used by test_q9.py.

Q9_QUESTION = "сколько специальных методов реализует класс Vector в примере 1-2"
Q9_QUERY = "Example 1-2 Vector special methods count"
Q9_QUERY2 = "implemented special methods Vector count"
Q9_EX = "count of dunder methods scoped to Example 1-2"


def run_primary_q9(question: str = Q9_QUESTION):
    return run_primary(question, Q9_QUERY, Q9_CHUNKS, ex=Q9_EX)


def run_alternative_q9(question: str = Q9_QUESTION):
    return run_alternative(
        question, Q9_QUERY, Q9_CHUNKS,
        ex=Q9_EX,
        refined_ex="explicit author statement of count for Example 1-2",
        query2=Q9_QUERY2,
    )


def _dump(state: ThoughtState, winner: Hypothesis | None) -> None:
    print("=" * 60)
    print(f"Goal:    {state.G[0].question}")
    print(f"Status:  {state.G[0].status}")
    print(f"Intent:  {state.intent}")
    print(f"P:       {state.P}")
    print("Trace:")
    for line in state.trace:
        print(f"  {line}")
    print(f"K size:  {len(state.K)}")
    for k, v in state.K.items():
        print(
            f"  {k}: value={v['value']} type={v['source_type']} "
            f"scope={v.get('scope_operator')!r}"
        )
    print(f"H ({sum(h.active for h in state.H)} active / {len(state.H)} total):")
    for h in state.H:
        flag = "*" if h.active else " "
        print(f"  {flag} {h.label} scope={h.scope_operator!r}")
    print(f"E:       {state.E}")
    print(f"T:       {state.T}")
    if winner is not None:
        print(f"Answer:  {winner.value} (scope={winner.scope_operator!r})")
    else:
        print("Answer:  <none>")
    print()


if __name__ == "__main__":
    print("\n--- Q9 PRIMARY (with P) ---")
    s, w = run_primary_q9()
    _dump(s, w)
    print("--- Q9 ALTERNATIVE (refine_Ex, no P) ---")
    s2, w2 = run_alternative_q9()
    _dump(s2, w2)
