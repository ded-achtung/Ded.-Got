"""Validator for fitcheck_v1 re-scored runs (delegates to baseline_v0
schemas, locates fitchk1 artifacts)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
V0_DIR = REPO / "audits" / "puzzlebook35" / "baseline_v0"
sys.path.insert(0, str(V0_DIR))

import validate_outputs as v0v  # noqa: E402

RUNS_DIR = REPO / "audits/puzzlebook35/runs"
MANIFESTS_DIR = REPO / "audits/puzzlebook35/manifests"


def find_latest_runs() -> list[tuple[Path, Path]]:
    out = []
    for suffix in ("v0_fitchk1", "v1_fitchk1"):
        candidates = sorted(RUNS_DIR.glob(f"*_{suffix}.jsonl"))
        if not candidates:
            continue
        rp = candidates[-1]
        mp = MANIFESTS_DIR / f"{rp.stem}.manifest.json"
        if not mp.exists():
            raise FileNotFoundError(mp)
        out.append((rp, mp))
    if not out:
        raise FileNotFoundError(f"No fitchk1 runs under {RUNS_DIR}")
    return out


def main() -> int:
    runs = find_latest_runs()
    rc = 0
    for rp, mp in runs:
        v0v.find_latest_run = lambda rp=rp, mp=mp: (rp, mp)
        print(f"--- validating {rp.name} ---")
        rc |= v0v.main()
    return rc


if __name__ == "__main__":
    sys.exit(main())
