"""report_brittleness.py — paraphrase probe.

Q1's pb_intro_004 has 'версию Python не ниже 3.10' replaced with the
semantically equivalent 'требуется Python от 3.10' (Q1_CHUNKS).
Original kept as Q1_CHUNKS_ORIGINAL.

Three measurements:

1. Does the regex finder catch the paraphrase?
2. Does direct classify() on the paraphrase pick version_with_min_phrase?
   (Per-class similarity scores against the 3 candidate classes.)
3. Q1 step 1 H weights on paraphrased vs original chunks.

If (1) misses but (2) succeeds: the issue is in fragment-extraction,
not in classification. Different layers, different fixes.
"""

from __future__ import annotations

from thought_spike import (
    Q1_CHUNKS, Q1_CHUNKS_ORIGINAL,
    initial_state_q1, think_step, compute_state_predicate,
    classify, _char_ngrams, _jaccard,
    PATTERN_CLASSES, WHAT_VERSION_CLASSES,
    PYTHON_VERSION_NEAR_RE, VERSIONED_CMD_RE, PYTHON3_CMD_RE,
    reset_classify_misses, get_classify_misses,
)


PARAPHRASE = "требуется Python от 3.10"
ORIGINAL = "версию Python не ниже 3.10"


def regex_test(fragment: str) -> dict:
    """What each regex finder produces on the fragment."""
    return {
        "PYTHON_VERSION_NEAR_RE": [m.group(0) for m in PYTHON_VERSION_NEAR_RE.finditer(fragment)],
        "VERSIONED_CMD_RE":       [m.group(0) for m in VERSIONED_CMD_RE.finditer(fragment)],
        "PYTHON3_CMD_RE":         [m.group(0) for m in PYTHON3_CMD_RE.finditer(fragment)],
    }


def classify_with_scores(fragment: str) -> tuple:
    """Pick + per-class top-example similarity for this fragment."""
    fg = _char_ngrams(fragment)
    per_class = {}
    for cname in WHAT_VERSION_CLASSES:
        pc = PATTERN_CLASSES[cname]
        scored = sorted(
            ((_jaccard(fg, _char_ngrams(ex)), ex) for ex in pc.examples),
            reverse=True,
        )
        per_class[cname] = scored
    chosen, score = classify(fragment, WHAT_VERSION_CLASSES)
    return chosen, score, per_class


def run_q1(chunks):
    reset_classify_misses()
    state = initial_state_q1()
    trace = []
    for chunk in chunks:
        state = think_step(state, chunk)
        trace.append({
            "chunk_id": chunk["id"],
            "K_classes_added": [
                k.pattern_class.name
                for k in state.history[-1]["K_added_this_step"]
            ],
            "h": {h["id"]: round(h["weight"], 3) for h in state.H},
            "predicate": compute_state_predicate(state),
        })
    return trace, get_classify_misses()


def main():
    print("=" * 72)
    print("REPORT: brittleness probe — paraphrase of version_with_min_phrase")
    print("=" * 72)
    print()

    print(f"ORIGINAL  fragment: {ORIGINAL!r}")
    print(f"PARAPHRASE        : {PARAPHRASE!r}")
    print()

    print("--- (1) Regex finders on the fragment ---")
    print(f"  on ORIGINAL:")
    for k, v in regex_test(ORIGINAL).items():
        print(f"    {k}: {v}")
    print(f"  on PARAPHRASE:")
    for k, v in regex_test(PARAPHRASE).items():
        print(f"    {k}: {v}")
    print()

    print("--- (2) Direct classify() on the paraphrase ---")
    chosen, score, per_class = classify_with_scores(PARAPHRASE)
    print(f"  classify({PARAPHRASE!r}, WHAT_VERSION_CLASSES)")
    print(f"  -> chosen: {chosen}, score: {score:.3f}")
    print(f"  -> threshold: 0.10 — chosen is "
          f"{'far above' if score >= 0.30 else 'above' if score >= 0.10 else 'below'} threshold")
    print()
    print(f"  per-class top examples (max score across examples):")
    for cname, scored in per_class.items():
        top = scored[0]
        print(f"    {cname:<25} top={top[0]:.3f}  ({top[1]!r})")
    print()

    print("--- (3) Q1 step 1 H weights ---")
    print(f"  paraphrased Q1_CHUNKS:")
    paraphrased, p_misses = run_q1(Q1_CHUNKS)
    for r in paraphrased:
        h_str = " ".join(f"{k}={v:.2f}" for k, v in r["h"].items())
        cls_str = ",".join(r["K_classes_added"])
        print(f"    step {paraphrased.index(r)+1:<2} {r['chunk_id']:<15} "
              f"K={cls_str:<55} H: {h_str:<35} pred={r['predicate']}")
    print()
    print(f"  original Q1_CHUNKS_ORIGINAL (re-run for direct comparison):")
    original, o_misses = run_q1(Q1_CHUNKS_ORIGINAL)
    for r in original:
        h_str = " ".join(f"{k}={v:.2f}" for k, v in r["h"].items())
        cls_str = ",".join(r["K_classes_added"])
        print(f"    step {original.index(r)+1:<2} {r['chunk_id']:<15} "
              f"K={cls_str:<55} H: {h_str:<35} pred={r['predicate']}")
    print()

    print("--- (3a) Classify-misses (fragment found by regex but score < threshold) ---")
    print(f"  paraphrased run: {len(p_misses)} miss(es)")
    for m in p_misses:
        print(f"    [{m['where']}] chunk={m['chunk_id']} fragment={m['fragment']!r}")
    print(f"  original run:    {len(o_misses)} miss(es)")
    for m in o_misses:
        print(f"    [{m['where']}] chunk={m['chunk_id']} fragment={m['fragment']!r}")
    print()

    print("--- (4) Step-1 comparison ---")
    p1 = paraphrased[0]
    o1 = original[0]
    p_h = " ".join(f"{k}={v:.2f}" for k, v in p1["h"].items())
    o_h = " ".join(f"{k}={v:.2f}" for k, v in o1["h"].items())
    p_classes = ",".join(p1["K_classes_added"])
    o_classes = ",".join(o1["K_classes_added"])
    print(f"  paraphrased: K={p_classes}")
    print(f"               H: {p_h}  predicate={p1['predicate']}")
    print(f"  original:    K={o_classes}")
    print(f"               H: {o_h}  predicate={o1['predicate']}")
    print()

    print("--- (5) Final-state comparison ---")
    pf = paraphrased[-1]
    of = original[-1]
    p_h = " ".join(f"{k}={v:.2f}" for k, v in pf["h"].items())
    o_h = " ".join(f"{k}={v:.2f}" for k, v in of["h"].items())
    print(f"  paraphrased: H: {p_h}  predicate={pf['predicate']}")
    print(f"  original:    H: {o_h}  predicate={of['predicate']}")
    print()


if __name__ == "__main__":
    main()
