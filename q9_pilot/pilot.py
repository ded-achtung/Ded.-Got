"""
Q9 pilot: 7-slot ThoughtState + tension-driven think_step.

Two traces are exposed:
  run_primary()      retrieve -> extract -> narrow_hypothesis(P)
  run_alternative()  retrieve -> extract -> refine_Ex -> retrieve again
                     (the trace narrative claims this path stalls without P)
"""

from __future__ import annotations

from corpus import CHUNKS
from claims import extract_claims
from state import Goal, Hypothesis, ThoughtState

PREFERENCES: dict[str, list[str]] = {
    "how_many": ["author_anchor", "forward_reference", "code_literal"],
}


def _score(query: str, chunk: dict) -> int:
    q = {t.lower() for t in query.split() if len(t) > 2}
    text = chunk["text"].lower()
    return sum(1 for t in q if t in text)


def retrieve(query: str, top_k: int = 4) -> list[tuple[str, dict]]:
    ranked = sorted(
        CHUNKS.items(),
        key=lambda kv: _score(query, kv[1]),
        reverse=True,
    )
    return [(cid, c) for cid, c in ranked[:top_k] if _score(query, c) > 0]


def extract_into(state: ThoughtState, retrieved: list[tuple[str, dict]]) -> None:
    for cid, chunk in retrieved:
        for claim in extract_claims(cid, chunk):
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


def narrow_hypothesis(state: ThoughtState) -> Hypothesis | None:
    order = state.P.get(state.intent, [])
    if not order:
        return None
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
            return winner
    return None


def refine_Ex(state: ThoughtState, clarified: str) -> None:
    state.Ex = clarified


def initial_state(question: str) -> ThoughtState:
    s = ThoughtState()
    s.intent = "how_many"
    s.G.append(Goal(
        question=question,
        expected_form="number with optional scope clause",
    ))
    s.Ex = "count of dunder methods scoped to Example 1-2"
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


def run_primary(question: str) -> tuple[ThoughtState, Hypothesis | None]:
    s = initial_state(question)

    # step 1: retrieve
    query = "Example 1-2 Vector special methods count"
    hits = retrieve(query)
    s.log(f"step1: retrieve('{query}') -> {[cid for cid, _ in hits]}")
    s.H = [h for h in s.H if h.source_type != "unknown"]
    extract_into(s, hits)
    s.log(f"step1: K populated with {len(s.K)} typed claims; |H|={len(s.H)}")

    # step 2: evaluate
    evaluate(s)
    recompute_tensions(s)
    s.log(f"step2: E={s.E}; T={s.T}")

    # step 3: narrow_hypothesis with P
    if s.E == "conflicting":
        winner = narrow_hypothesis(s)
        if winner is None:
            s.log("step3: narrow_hypothesis FAILED — no priority match")
            return s, None
        s.log(
            f"step3: narrow_hypothesis(P[{s.intent}]) -> "
            f"{winner.label} scope={winner.scope_operator!r}"
        )
        evaluate(s)
        recompute_tensions(s)
        s.log(f"step3: E={s.E}; T={s.T}")
    else:
        winner = next((h for h in s.H if h.active), None)

    # step 4: produce
    if winner is not None:
        for goal in s.G:
            goal.status = "solved"
        s.log(f"step4: answer = {winner.value} (scope={winner.scope_operator!r})")
    return s, winner


def run_alternative(question: str) -> tuple[ThoughtState, Hypothesis | None]:
    """Refine Ex + second retrieve, no P. Should stall at conflict."""
    s = initial_state(question)
    s.P = {}  # explicitly drop P for this run

    hits = retrieve("Example 1-2 Vector special methods count")
    s.log(f"step1: retrieve -> {[cid for cid, _ in hits]}")
    s.H = [h for h in s.H if h.source_type != "unknown"]
    extract_into(s, hits)
    evaluate(s)
    recompute_tensions(s)
    s.log(f"step2: E={s.E}; T={s.T}")

    refine_Ex(s, "explicit author statement of count for Example 1-2")
    hits2 = retrieve("implemented special methods Vector count")
    s.log(f"step3: refine_Ex + retrieve -> {[cid for cid, _ in hits2]}")
    extract_into(s, hits2)
    evaluate(s)
    recompute_tensions(s)
    s.log(f"step3: E={s.E}; T={s.T}")

    if s.E == "conflicting":
        s.log("step4: STALLED — refine_Ex cannot resolve conflict without P")
        return s, None

    winner = next((h for h in s.H if h.active), None)
    return s, winner


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
    q = "сколько специальных методов реализует класс Vector в примере 1-2"
    print("\n--- PRIMARY (with P) ---")
    s, w = run_primary(q)
    _dump(s, w)
    print("--- ALTERNATIVE (refine_Ex, no P) ---")
    s2, w2 = run_alternative(q)
    _dump(s2, w2)
