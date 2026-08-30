---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1569
followup_kind: upstream_defect
created_at: 2026-08-30 19:32
updated_at: 2026-08-30 22:42
---

## Origin

Spawned from t1569_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_lock.sh:416,421,427,437` — `list_locks()` writes four
  degenerate informational strings ("No locks (no remote configured)", "No locks
  (branch not initialized)", "No locks", "No active locks") to **stdout** via
  `info()`, which is `echo -e "${BLUE}$1${NC}"` in
  `.aitask-scripts/lib/terminal_compat.sh:19` — i.e. non-record prose **with ANSI
  escape sequences** on a machine-readable stream. Its sibling `warn()` correctly
  redirects to stderr (`>&2`).

## Diagnostic context

Surfaced while building the shared parallel-admission checker (t1569_3), which
needs a machine-readable list of locked tasks. Any parser of `ait lock --list`
must currently strip ANSI escapes *and* pattern-match the record shape
`t<id>: locked by <email> on <host> since <ts>`, treating everything else as "no
record" — otherwise a degenerate line is read as a lock. t1569_3 sidestepped the
problem entirely by reading the `origin/aitask-locks` tree directly rather than
parsing the CLI, so the defect is not blocking anything today; it is a latent
trap for the next consumer.

Note `aitask_board.py::refresh_lock_map` also consumes this surface.

## Suggested fix

Route the four degenerate messages through `warn()`/stderr, or emit nothing at
all and let the empty stdout mean "no locks" (the record protocol already makes
absence unambiguous). Either way, keep stdout reserved for records. Check
`check_lock()` at the same time: it prints the whole lock YAML to stdout, which
is a separate but related shape question.
