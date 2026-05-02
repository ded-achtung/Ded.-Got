"""Validator for baseline_v1_bm25 outputs (delegates to baseline_v0 validator
schemas, but locates v1 run + manifest)."""
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


def find_latest_run() -> tuple[Path, Path]:
    candidates = sorted(RUNS_DIR.glob("*_v1_bm25.jsonl"))
    if not candidates:
        raise FileNotFoundError(f"No *_v1_bm25.jsonl under {RUNS_DIR}")
    runs_path = candidates[-1]
    manifest_path = MANIFESTS_DIR / f"{runs_path.stem}.manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest missing: {manifest_path}")
    return runs_path, manifest_path


v0v.find_latest_run = find_latest_run

if __name__ == "__main__":
    sys.exit(v0v.main())
