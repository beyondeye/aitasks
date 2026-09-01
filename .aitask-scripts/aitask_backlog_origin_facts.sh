#!/usr/bin/env bash

# aitask_backlog_origin_facts.sh - Origin risk facts for the roadmap (t1569_5).
#
# The impure half of the background-work roadmap's origin layer. Reads task
# frontmatter -- active files AND archived bundles -- and emits one record per
# (task, origin) pair for lib/roadmap_policy.py to reduce:
#
#   ORIGIN_FACT:<task_id>|<origin_id>|<quality>|<rch>|<rga>|<source>
#
#   quality  exact | topic | unknown   (a property of the TASK, repeated per row)
#   source   active | archived | absent (a property of the ORIGIN)
#
# Fields are `%`-then-`|` encoded and the free-ish field is last. Every field has
# the sentinel `-`, and a task with no resolvable origin still gets exactly one
# row -- never infer a fact from an absent line.
#
# WHY ONE ROW PER ORIGIN. 25 of 89 exact follow-ups carry more than one origin
# (up to 11), 13 of those disagree on a risk level and 6 span mixed sources
# (measured 2026-08-31). Reducing them here would put a policy decision in a
# facts producer; the reduction rule lives in lib/roadmap_policy.py, which is
# pure and therefore testable over frozen fixtures.
#
#   aitask_backlog_origin_facts.sh [--task-dir <d>] [--archived-dir <d>] [<id>...]
#
# With no ids, every active task carrying a `followup_kind:` is reported. Named
# ids are reported whether or not they are follow-ups, so a caller can ask about
# one task without first knowing its kind.
#
# EXIT STATUS: every content state exits 0 -- an unreadable origin is an answer
# (`source=absent`), not a failure. CLI misuse (unknown flag, an option missing
# its value) exits 2, because a silent empty result for a typo is the
# "silent-skip masks a broken implementation" hazard aitask_verification_stale.sh
# documents at :26-32.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

exec "$PYTHON" "$SCRIPT_DIR/lib/roadmap_origin_facts.py" "$@"
