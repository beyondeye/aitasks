#!/usr/bin/env bash

# aitask_backlog_roadmap.sh - Background-work roadmap driver (t1569_6).
#
# Ranks the background-work backlog into a complete `implementation_trail`
# document. The impure driver behind the `aitask-backlog-roadmap` skill: it
# wires the gatherer (t1569_1), the batch derivation and origin resolution
# (t1569_2), the shared parallel-admission checker (t1569_3) and the scoring /
# lanes / freshness / encoding policy library (t1569_5) into one run.
#
#   aitask_backlog_roadmap.sh --narrative <file.json> --owner <task-ref>
#                             --out <trail.json>
#                             [--title <label>] [--cap <n>]
#                             [--agent-string <s>] [--root <dir>]
#
# --narrative is REQUIRED and carries the skill-authored prose:
# `problem_statement` and `recommendation_summary` (both required, non-empty),
# plus an optional `overview`. Any other key is refused by name -- the trail
# schema is `additionalProperties: false`, so an unexpected key must fail here
# rather than as an opaque validation error after the pipeline has run.
# `method_note` is deliberately NOT accepted: it is composed from the measured
# corpus, because a hand-written one would need counts the caller has not been
# told and would drift from the document it describes.
#
# --cap is a CEILING, not a quota: a corpus smaller than the cap publishes every
# candidate and says so in the method note. It must be an integer >= 1; `--cap
# 0` would reach the encoder as an empty list and report "no candidates" for
# what is really a typo.
#
# EXIT STATUS
#   0  every content state, including an empty corpus -- that is an answer
#   2  CLI misuse (unknown flag, missing/malformed --narrative, bad --cap)
#   3  refusal to publish: the evidence is unsound in a way that CANNOT be
#      hedged per candidate -- an unavailable corpus makes every path
#      classification wrong at once, and a missing ORIGIN_FACT row means the
#      collector broke rather than that a task has no origin. Per-candidate
#      degradation is NOT a refusal: it becomes UNCHECKABLE with named causes,
#      which is already the checker's behaviour.
#
# CLEAR MEANS "no known conflict at check time", never "safe to run in
# parallel". The checker observes; it does not reserve.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh disable=SC1091
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh disable=SC1091
source "$SCRIPT_DIR/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

exec "$PYTHON" "$SCRIPT_DIR/lib/roadmap_run.py" "$@"
