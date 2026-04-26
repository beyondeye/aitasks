---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [agentcrew]
created_at: 2026-04-26 14:32
updated_at: 2026-04-26 14:32
---

## Context

Bug at Layer D in the t653 chain (see `aiplans/p653_brainstorm_import_proposal_hangs.md`).

After parent t650 lands, the false-Error scenario for brainstorm bootstrap agents becomes rare — but two structural gaps remain:

1. `cmd_set` in `agentcrew_status.py:87` writes the agent status file but **does not push** the worktree. If the runner has already exited (graceful shutdown after thinking all agents are terminal, or any unrelated runner crash) and the agent then writes `Completed`, the local `_status.yaml` flips correctly but remote stays on whatever the runner last pushed (often `Error`). Verified on session 635: agent at `Completed` locally, runner stopped before that write, remote still on `Error`.

2. `AGENT_TRANSITIONS["Error"] = ["Waiting"]` (`agentcrew_utils.py:30`) means a falsely-Error'd agent **cannot** call `ait crew status set --status Completed` to self-correct — the validator rejects it. The agent has to be `--reset` first (Error → Waiting), then re-launched (Waiting → Ready → Running → Completed). For an agent that has already finished its work and just needs to record the final state, this is brittle.

This child:
1. Extends `AGENT_TRANSITIONS["Error"]` to allow `Completed` and `Running` (recovery + resume).
2. Pushes the worktree synchronously when `cmd_set` writes a terminal status, so the agent's own write propagates to remote independently of the runner's iteration loop. Adds a `--no-push` flag for batched callers (the runner itself, which already pushes once per iteration and does not need a per-call push).

## Key Files to Modify

- `.aitask-scripts/agentcrew/agentcrew_utils.py` — extend `AGENT_TRANSITIONS["Error"]`; move `git_commit_push_if_changes` from runner into utils so both modules import it
- `.aitask-scripts/agentcrew/agentcrew_status.py` — `cmd_set` pushes on terminal transition; add `--no-push` argparse flag
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — switch its callers of `git_commit_push_if_changes` to import from utils; pass `--no-push` (or call cmd_set in a way that doesn't double-push) when the runner itself flips agent status (for example in `mark_stale_as_error`)
- `tests/test_agentcrew_terminal_push.sh` — new
- `tests/test_agentcrew_error_recovery.sh` — new

## Reference Files for Patterns

- `git_commit_push_if_changes()` at `agentcrew_runner.py:149-158` — current implementation
- `cmd_set()` at `agentcrew_status.py:87-129` — current strict-validate write-only path
- `AGENT_TRANSITIONS` at `agentcrew_utils.py:23-32` — the transition map
- `mark_stale_as_error()` at `agentcrew_runner.py:310-322` — caller that sets status from runner side
- For test patterns, look at any existing `tests/test_*.sh` that uses git fixtures (e.g., a fresh `git init` in `/tmp/`)

## Implementation Plan

### 1. Extend `AGENT_TRANSITIONS["Error"]`

In `agentcrew_utils.py`:

```python
AGENT_TRANSITIONS: dict[str, list[str]] = {
    "Waiting": ["Ready"],
    "Ready": ["Running"],
    "Running": ["Completed", "Error", "Aborted", "Paused"],
    "Paused": ["Running"],
    "Completed": [],
    "Aborted": [],
    "Error": ["Waiting", "Running", "Completed"],  # Error is recoverable: heartbeat watchdog timeout does not prove the agent failed.
}
```

The expanded list lets a falsely-Error'd agent self-correct (Error → Completed) or resume (Error → Running). `Aborted` stays terminal because Aborted is always user-initiated.

Add a one-line comment above the table explaining the rationale ("Error is recoverable").

### 2. Move `git_commit_push_if_changes` into utils

Cut from `agentcrew_runner.py:149-158`, paste into `agentcrew_utils.py` (above the YAML helpers). Update the import in `agentcrew_runner.py` to pull from utils. Verify nothing else imports the runner's copy (`grep -rn "git_commit_push_if_changes" .aitask-scripts/`).

### 3. Push from `cmd_set` on terminal transitions

In `agentcrew_status.py:cmd_set`, after `_recompute_crew_status(wt)`:

```python
if (args.status in ("Completed", "Aborted", "Error")
        and not getattr(args, "no_push", False)):
    from agentcrew.agentcrew_utils import git_commit_push_if_changes
    git_commit_push_if_changes(
        wt,
        f"agent {args.agent}: {current} -> {args.status}",
        batch=True,
    )
```

`git_commit_push_if_changes` is already idempotent (no-op if no changes), so accidental double-calls are safe.

Add the `--no-push` flag to `cmd_set`'s argparse subparser:

```python
set_p.add_argument("--no-push", action="store_true",
                   help="Skip git push after writing the status (for batched callers)")
```

### 4. Pass `--no-push` from runner-side status flips

In `agentcrew_runner.py:mark_stale_as_error()` (and any other runner-side path that calls `cmd_set` indirectly via subprocess), the runner is already going to call `git_commit_push_if_changes` once per iteration — no need to push twice. Where the runner uses direct `update_yaml_field` writes (which is the case at lines 318-320), no change is needed. Where the runner shells out to `ait crew status set ...` (search for any such call), append `--no-push`.

### 5. Tests

`tests/test_agentcrew_terminal_push.sh`:
1. Create a fresh git repo in `/tmp/`, init a synthetic crew worktree.
2. Run `ait crew status set --crew <id> --agent foo --status Completed` (with the agent in `Running`).
3. Assert: `_status.yaml` shows `Completed` AND a new git commit exists in the worktree with the expected message.
4. Run again with `--no-push`. Assert: status flips but no new commit.

`tests/test_agentcrew_error_recovery.sh`:
1. Same fixture; agent in `Error`.
2. Run `ait crew status set --status Completed`. Assert: succeeds (transition allowed).
3. Run `ait crew status set --status Aborted` from `Error`. Assert: fails (Aborted is not in the new allow list — verifies we did not over-relax the validator).

## Verification Steps

1. **Unit tests:**
   ```bash
   bash tests/test_agentcrew_terminal_push.sh
   bash tests/test_agentcrew_error_recovery.sh
   ```
   Both PASS.

2. **shellcheck:** `shellcheck .aitask-scripts/agentcrew/*.sh` — clean (no new shell scripts in this child, but the existing ones import the modified utils — sanity-check no regressions).

3. **End-to-end (manual):**
   - Trigger a crew where an agent ends up in `Error` (e.g., contrived heartbeat timeout — easy to reproduce by setting `heartbeat_timeout_minutes: 0` in `_crew_meta.yaml` and waiting one iteration).
   - Then call `ait crew status set --crew <id> --agent <name> --status Completed`.
   - Assert: succeeds; status flips locally; `git log` in the worktree shows the new commit; `git ls-remote` shows the push.

4. **No regression in runner-side push frequency.** Verify runner log still shows one push per iteration (runner has not become a no-op pusher, and is not double-pushing).

## Out of scope (intentionally)

- TUI changes (Layer B — owned by sibling t653_1).
- Apply / YAML / prompt changes (Layer C — owned by sibling t653_2).
- Heartbeat fixes (Layer A — owned by parent t650).
- No new helper script — modifications stay within existing `agentcrew_*.py`. (No 5-touchpoint whitelist needed for this child.)
- `Aborted` stays terminal: a user-initiated abort is not a watchdog accident.
