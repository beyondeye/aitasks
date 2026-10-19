---
Task: t2036_crew_branch_delete_push_timeout.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: bound the crew-branch deletion pushes (t2036)

## Context

t2024 bounded every crew **write** to origin through `lib/bounded_run.py`
(`_crew_git_bounded` in `lib/agentcrew_utils.sh`, `git_cmd(..., timeout=)` in
`agentcrew/agentcrew_utils.py`): a hard `AIT_CREW_GIT_TIMEOUT` bound (default
10s), process-group kill, non-interactive env. The three remote-branch
**deletion** pushes were out of its scope and still run bare, so an origin that
is routable but never answers stalls them until the TCP timeout:

| site | call |
|---|---|
| `.aitask-scripts/aitask_crew_cleanup.sh:105` (`ait crew cleanup --delete-branch`; also reached from `aitask_brainstorm_archive.sh` / `_delete.sh`) | `git push origin --delete "$branch_name" 2>/dev/null \|\| true` |
| `.aitask-scripts/aitask_brainstorm_delete.sh:115` (NOT_FOUND / NOT_TERMINAL fallback) | `git push origin --delete "crew-${CREW_ID}" 2>/dev/null \|\| true` |
| `.aitask-scripts/brainstorm/brainstorm_app.py:5959` `_cleanup_stale_crew_branch_and_retry` (InitFailureModal "clean and retry") | `subprocess.run(["git","push","origin","--delete",crew_branch], …)` |

Outcome: each call is bounded and non-interactive; best-effort semantics and
messages are unchanged (a timed-out delete is just a failed delete).

Grep confirms these are the only `push … --delete` sites under `.aitask-scripts/`.

## Implementation

1. **`aitask_crew_cleanup.sh`** — already sources `lib/agentcrew_utils.sh`.
   Replace line 105 with
   ```bash
   # Best-effort remote branch cleanup (silent on failure; bounded, t2036)
   _crew_git_bounded . /dev/null push origin --delete "$branch_name" || true
   ```
   `.` = the repo root (scripts run from it, as the bare call already assumed).
   Output still discarded (`/dev/null` replaces `2>/dev/null`; the helper sends
   both streams there).

2. **`aitask_brainstorm_delete.sh`** — does **not** source agentcrew_utils.sh.
   Add, after the `terminal_compat.sh` source:
   ```bash
   # shellcheck source=lib/agentcrew_utils.sh
   source "$SCRIPT_DIR/lib/agentcrew_utils.sh"
   ```
   **Caveat:** agentcrew_utils.sh reassigns `SCRIPT_DIR` to its lib dir
   ("callers reassign SCRIPT_DIR after sourcing"), and this script uses
   `$SCRIPT_DIR/brainstorm/brainstorm_cli.py` and
   `$SCRIPT_DIR/aitask_crew_cleanup.sh` afterwards. Re-derive it right after the
   source: `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`.
   No `_AIT_RESOLVED_PYTHON` wiring is needed — `require_ait_python` runs in
   `$( )`, so the helper falls back to `python3` exactly as in the crew scripts
   (bounded_run.py is stdlib-only). Then line 115 becomes
   `_crew_git_bounded . /dev/null push origin --delete "crew-${CREW_ID}" || true`,
   keeping the existing comment (+ "bounded").

3. **`brainstorm_app.py` `_cleanup_stale_crew_branch_and_retry`** — already a
   `@work(thread=True)` worker, so it is off the UI thread; it only needs the
   bound. Extend the existing `from agentcrew.agentcrew_utils import (...)` with
   `crew_git_timeout, git_cmd`, and replace the push with
   ```python
   r = git_cmd(".", "push", "origin", "--delete", crew_branch,
               check=False, timeout=crew_git_timeout())
   ```
   The `outputs.append(f"$ git push origin --delete …")` line stays as is; on a
   timeout `r.stderr` carries git_cmd's "timed out after Ns … AIT_CREW_GIT_TIMEOUT"
   text, which lands in the failure modal only when the (local) branch delete
   failed — same as today. `success` remains driven by `git branch -D` only.

## Tests — new `tests/test_crew_branch_delete_bounded.sh`

Follows the hang-fixture pattern of `tests/test_crew_publish_upstream.sh`
Tests 9–15 (its `make_hanging_origin` / `assert_hang_reaped` / `within` helpers
are file-local, so they are reproduced here with a pointer back). Fixture repo:
copy the whole `.aitask-scripts` tree (as `tests/test_crew_cleanup.sh` does) plus
the t999 task file and `codeagent_config.json` that `test_brainstorm_cli.sh`'s
setup uses for `aitask_brainstorm_init.sh`. Git config isolated via
`tests/lib/git_config_isolation.sh`; `AIT_CREW_GIT_TIMEOUT=2
AIT_BOUNDED_RUN_GRACE=1` for hang cells; cleanup trap kills leftover stub pids.

Cells:
1. **Fixture control** — a plain `git push origin --delete x` against the
   hanging origin is still running after 3s.
2. **crew cleanup, reachable origin (positive control)** — crew published to a
   bare remote; `aitask_crew_cleanup.sh --crew c --delete-branch --batch` →
   `CLEANED:c`, local and **remote** branch gone (proves the routed call still
   deletes; `-C .` and argv are right).
3. **crew cleanup, hanging origin** — returns within 10s, `CLEANED:c`, worktree
   and local branch gone, transport reached once and reaped.
4. **brainstorm delete, reachable origin** — `aitask_brainstorm_init.sh 999`,
   publish the crew branch, `aitask_brainstorm_delete.sh 999 --yes` →
   `DELETED:999`, remote branch removed (exercises the fallback push since
   Python delete removes the worktree → crew cleanup reports NOT_FOUND).
5. **brainstorm delete, hanging origin** — bounded, `DELETED:999`, "stale
   crew-brainstorm-999 branch removed", transport reached once, reaped.
6. **TUI clean-and-retry, hanging origin** — `$AITASK_PYTHON` runs
   `BrainstormApp._cleanup_stale_crew_branch_and_retry.__wrapped__(MagicMock(task_num="999"))`
   with cwd = fixture repo (pattern: `tests/test_board_dialog_subprocess_degrade.py`):
   returns within 10s, the first `call_from_thread` target is `notify`
   (success path), local branch gone, reaped. Plus the same call against a
   reachable origin deleting the remote branch.

Each hang cell sits far below the stub's 30s sleep, so an unbounded call fails
the `within` assertion instead of passing slowly.

## Verification

- `bash tests/test_crew_branch_delete_bounded.sh`
- Regressions: `bash tests/test_crew_cleanup.sh`, `bash tests/test_brainstorm_cli.sh`,
  `bash tests/test_crew_publish_upstream.sh`,
  `python3 tests/test_brainstorm_init_failure_modal.py` (via venv python)
- `shellcheck .aitask-scripts/aitask_crew_cleanup.sh .aitask-scripts/aitask_brainstorm_delete.sh tests/test_crew_branch_delete_bounded.sh`
- Step 9 (Post-Implementation): archival via `aitask_archive.sh 2036` after the
  risk_evaluated gate is recorded by the orchestrator.

## Risk

### Code-health risk: low
None identified. (The one sharp edge — agentcrew_utils.sh clobbering
`SCRIPT_DIR` in brainstorm_delete.sh — is handled in step 2 and caught by the
existing `test_brainstorm_cli.sh` Tests 9/9b plus new cells 4–5.)

### Goal-achievement risk: low
None identified. All three sites are covered by a bounded-and-reaped cell and
a reachable-origin control proving the delete still happens.
