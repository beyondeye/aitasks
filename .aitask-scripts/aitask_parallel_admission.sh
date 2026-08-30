#!/usr/bin/env bash

# aitask_parallel_admission.sh - The shared parallel-admission checker (t1569_3).
#
# The single definition of "safe" for starting work alongside other active
# tasks. Two consumers call THIS script (or its pure core) and nowhere else
# computes a collision verdict: t1569_4 wires it into task-workflow as a
# required preflight; t1569_5 imports lib/parallel_admission.py directly for the
# roadmap's advisory preview.
#
#   check  --candidate <id> --from plan|origin|auto [--plan <path>]
#          --lock-freshness require-fresh|allow-cached
#          [--max-lock-age <s>] [--max-claim-age <s>] [--hub-threshold <n>]
#   replay --candidates <file|-> [same flags]   -> RATES:/CAUSE_RATE: over a population
#
# EXIT STATUS: every *content* state exits 0 -- CLEAR, CLEAR_CAVEATED, CONFLICT
# and UNCHECKABLE are all answers, and the caller reads VERDICT:. CLI misuse
# (unknown flag, missing --candidate, a --plan target that does not exist) exits
# 2, because a silent verdict for a typo is the "silent-skip masks a broken
# implementation" hazard (aitask_verification_stale.sh:26-32).
#
# CLEAR MEANS "no known conflict at check time", never "safe to run in
# parallel": this checker observes, it does not reserve. Overlapping work can
# begin the instant after it passes. The residual closes only when t1343's
# declared-claims backend lands.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

exec "$PYTHON" "$SCRIPT_DIR/lib/parallel_admission_collect.py" "$@"
