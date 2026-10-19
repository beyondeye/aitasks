---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [task_attachments]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1065
followup_kind: upstream_defect
created_at: 2026-10-19 10:54
updated_at: 2026-10-19 11:14
---

## Origin

Spawned from t2053 during Step 8b review.

## Upstream defect

- `tests/test_change_surface.sh:90` — `printf '%s\n' "$output" | grep -qxF -- "$line"` under pipefail can return 141 on a PRESENT match (same class as t2053)
- `tests/test_change_surface.sh:100` — same shape
- `tests/test_setup_git.sh:857` — `printf … "$AIT_SETUP_DIRTY_BASELINE" | grep -qxF ".gitignore"` inside `$( )`
- `tests/test_setup_git.sh:894` — `has_line() { printf '%s\n' "$1" | grep -qxF -- "$2" && echo yes || echo no; }`
- `tests/test_restore_flows_live.sh:237` — `printf '%s\n' "$frozen_out" | grep -qxF "FROZEN:$hook_rid"`
- `tests/test_attach_task_delete_decref.sh:175` — `printf '%s\n' "$out_h" | grep -q ":${HND}"` (negative assertion: a 141 here reads as "found" → spurious FAIL)
- `tests/test_runner_python_isolation.sh:60,65` — `printf '%s\n' "$body" | grep -qE …`

## Diagnostic context

t2053 fixed `md_has` in `tests/test_no_unscoped_task_commit.sh`: `printf '%s\n' "${ARR[@]}" | grep -qxF` under `set -o pipefail`. grep -q exits on its first match, the printf writer is still writing, takes SIGPIPE, and the pipeline returns 141 — a present name reads as absent. With ~917 args the race fired 4 of 5 runs; with the needle first plus >64 KiB of padding it fires 20/20.

The sites above all live in files that set pipefail (found by `grep -nE "printf '%s\\\\n' .*\\| *grep -[a-zA-Z]*q"` over pipefail test files). Most pipe ONE string, which bash's printf usually writes in a single write(2) that fits the pipe buffer — so they are probably safe for small inputs, but not proven: a multi-KB value can take several writes and race exactly like t2053. Not verified per site.

## Suggested fix

Per site, decide by input size: replace with a here-string (`grep -qxF -- "$line" <<<"$output"` — no writer process, no SIGPIPE) or a bash loop/`[[ ]]` match. Also sweep the other pipefail tests for `| grep -q` / `| head` over multi-arg printf or command output beyond this pattern.
