#!/usr/bin/env bash
set -euo pipefail

# Architectural boundary enforcement: backends and core types must not
# import GPU-specific crates. Violation = merge blocked.

fail=0

check() {
  local dir="$1"
  local pattern="$2"
  local msg="$3"
  if [ -d "$dir/src" ] && grep -rE "$pattern" "$dir/src" >/dev/null 2>&1; then
    echo "FAIL: $msg"
    grep -rnE "$pattern" "$dir/src"
    fail=1
  fi
}

check "crates/wpe-backend"      '\buse\s+wgpu'   "wpe-backend must not import wgpu"
check "crates/wpe-render-core"  '\buse\s+wgpu'   "wpe-render-core must not import wgpu"
check "crates/wpe-compat"       '\buse\s+wgpu'   "wpe-compat must not import wgpu"

# Phase II: add check for wpe-backend on egl/gl when adapter layer exists.

exit $fail
