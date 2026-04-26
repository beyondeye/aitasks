---
Task: t653_3_agentcrew_terminal_push_and_recover.md
Parent Task: aitasks/t653_brainstorm_import_proposal_hangs.md
Sibling Tasks: aitasks/t653/t653_1_*.md, aitasks/t653/t653_2_*.md
Archived Sibling Plans: (none yet)
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
---

# Plan: t653_3 — Push terminal status from cmd_set + relax Error→Completed

## Context (recap)

Two structural issues in the agentcrew status machinery, surfaced by the t653 investigation:

1. `cmd_set` in `agentcrew_status.py:87` writes the `_status.yaml` file but **never pushes** the worktree. The runner pushes once per iteration (`agentcrew_runner.py:979`), so as long as the runner is alive, the agent's local Completed write reaches remote on the next iteration. But session 635's `_runner_alive.yaml` shows `status: stopped` at 09:57:16 while the agent's `completed_at` is 10:04:59 — the runner exited mid-cycle (after thinking everyone reached terminal state via the false-Error). No one ever pushed Completed.

2. `AGENT_TRANSITIONS["Error"] = ["Waiting"]` (`agentcrew_utils.py:30`) blocks an agent that was falsely Error'd from calling `ait crew status set --status Completed` to self-correct. The validator says no; the agent must be `--reset` first. Brittle for the heartbeat-watchdog false-positive case.

After parent t650 lands the false-Error path becomes rare, but both gaps are still real for any other runner-exit scenario (SIGKILL, machine reboot, network blip mid-iteration). Defense-in-depth.

## Approach

1. Extend `AGENT_TRANSITIONS["Error"]` to `["Waiting", "Running", "Completed"]`. (Aborted stays terminal — Aborted is user-initiated, never a watchdog accident.)
2. Move `git_commit_push_if_changes` from `agentcrew_runner.py` into `agentcrew_utils.py` so both the runner and the status command import it from one place.
3. After `cmd_set` flips status to a terminal state (`Completed`/`Aborted`/`Error`) and recomputes crew status, call `git_commit_push_if_changes` with a descriptive commit message. Add a `--no-push` argparse flag for callers that want to batch (the runner itself uses `update_yaml_field` directly, not `cmd_set`, so it does not need the flag — but the option is there for any future caller).

## Step-by-step

### S1. Extend `AGENT_TRANSITIONS["Error"]` (`agentcrew_utils.py:23-32`)

Replace:
```python
"Error": ["Waiting"],
```
with:
```python
# Error is recoverable: a heartbeat-watchdog timeout does not prove the agent
# failed. An agent that gets falsely Error'd may still write Completed at end
# of work, or resume Running mid-flight. Aborted is intentionally terminal —
# Aborted is always user-initiated, not a watchdog accident.
"Error": ["Waiting", "Running", "Completed"],
```

### S2. Move `git_commit_push_if_changes` into utils

Cut from `agentcrew_runner.py:149-158`:
```python
def git_commit_push_if_changes(worktree: str, message: str, batch: bool = False) -> None:
    """Stage all changes in worktree, commit and push if there are changes."""
    git_cmd(worktree, "add", "-A", check=False)
    result = git_cmd(worktree, "diff", "--cached", "--quiet", check=False)
    if result.returncode != 0:
        git_cmd(worktree, "commit", "-m", message, check=False)
        push_result = git_cmd(worktree, "push", check=False)
        ...
```

Paste into `agentcrew_utils.py` (above the YAML helpers section). Verify `git_cmd` itself is also accessible from utils — if it lives in the runner, move it as well, or leave both helpers in runner and have utils import them. **Pick the cleaner option after grepping**: `grep -n "def git_cmd" .aitask-scripts/agentcrew/`. If `git_cmd` is only used inside runner, the cleanest move is: utils gains a small standalone `_git()` helper, runner keeps its own subprocess call. Do not add a circular import.

Update `agentcrew_runner.py` to import `git_commit_push_if_changes` from utils. Verify nothing else imports the runner's copy: `grep -rn "git_commit_push_if_changes" .aitask-scripts/`.

### S3. Push from `cmd_set` on terminal transitions (`agentcrew_status.py:87-129`)

After `_recompute_crew_status(wt)`:

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

`current` is the previous status, captured before `data["status"] = new_status`. The helper is idempotent (no-op when there are no changes), so accidental double-calls are safe.

Add the flag to `cmd_set`'s argparse subparser (find via `grep -n "set_p\b\|set_parser" agentcrew_status.py`):

```python
set_p.add_argument("--no-push", action="store_true",
                   help="Skip git push after writing the status (for batched callers)")
```

### S4. Tests — `tests/test_agentcrew_terminal_push.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Build a synthetic git repo + crew worktree under TMPDIR (portable mktemp)
TMPROOT="$(mktemp -d "${TMPDIR:-/tmp}/aitask_test_terminal_push_XXXXXX")"
trap 'rm -rf "$TMPROOT"' EXIT

cd "$TMPROOT"
git init -q
git commit -q --allow-empty -m "init"

# Synthetic crew worktree (just a dir — the test focuses on git ops)
mkdir -p crew/test_crew
cd crew/test_crew
# Seed an agent _status.yaml in Running state
cat >foo_status.yaml <<EOF
agent_name: foo
status: Running
progress: 50
EOF
git add -A && git commit -q -m "seed"

# Run the cmd_set with terminal transition
"$ROOT/ait" crew status set --crew test_crew --agent foo --status Completed

# Assertions
[[ "$(grep '^status:' foo_status.yaml)" == "status: Completed" ]] \
    || { echo "FAIL: status did not flip"; exit 1; }
[[ -n "$(git log -1 --pretty=format:%H)" ]] \
    || { echo "FAIL: no commit recorded"; exit 1; }
echo "PASS: terminal push test"

# --no-push variant
cat >bar_status.yaml <<EOF
agent_name: bar
status: Running
EOF
git add -A && git commit -q -m "seed bar"
HASH_BEFORE="$(git log -1 --pretty=format:%H)"
"$ROOT/ait" crew status set --crew test_crew --agent bar --status Completed --no-push
HASH_AFTER="$(git log -1 --pretty=format:%H)"
[[ "$HASH_BEFORE" == "$HASH_AFTER" ]] \
    || { echo "FAIL: --no-push made a commit"; exit 1; }
echo "PASS: --no-push test"
```

(The above test will need adjustments to use the project's actual `resolve_crew()` semantics — verify the crew dir structure expected by `agentcrew_status.py` and adjust the synthetic seed accordingly. If `resolve_crew` requires `.aitask-crews/crew-<id>/` layout, mirror that.)

`tests/test_agentcrew_error_recovery.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
# Same fixture; agent in Error
# 1. set --status Completed → succeeds (was forbidden before)
# 2. set --status Aborted from Error → fails (Aborted not in new allow list)
```

### S5. shellcheck and lint

`shellcheck .aitask-scripts/aitask_*.sh` — confirm no regressions from any imports we adjusted.

## Files touched

- `.aitask-scripts/agentcrew/agentcrew_utils.py` — extend transition; +`git_commit_push_if_changes` (~30 lines)
- `.aitask-scripts/agentcrew/agentcrew_status.py` — push call + `--no-push` flag (~10 lines)
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — adjusted import (~3 lines)
- `tests/test_agentcrew_terminal_push.sh` — new (~50 lines)
- `tests/test_agentcrew_error_recovery.sh` — new (~30 lines)

## Verification

1. **Unit tests:**
   ```bash
   bash tests/test_agentcrew_terminal_push.sh
   bash tests/test_agentcrew_error_recovery.sh
   ```
   Both PASS.

2. **shellcheck:** `shellcheck .aitask-scripts/aitask_*.sh` — clean.

3. **No regression in runner-side push frequency.** Run a small test crew (or simulate via the runner's `--once --dry-run`); verify the runner log still shows one push per iteration (no double-pushing, no missed pushes).

4. **End-to-end recovery (manual):**
   - Contrive a brainstorm crew where an agent ends up in `Error` (set `heartbeat_timeout_minutes: 0` in `_crew_meta.yaml` and wait one iteration). 
   - Run `ait crew status set --crew <id> --agent <name> --status Completed`.
   - Expect: succeeds, status flips, commit appears in the worktree, `git ls-remote` reflects the push.

## Notes for sibling tasks

- t653_1 and t653_2 do not depend on this child. Land order doesn't matter.
- This child does **not** introduce a new helper script, so the 5-touchpoint whitelist procedure does not apply.
- The Error→Running transition was added so a user can manually `ait crew status set --status Running` on a falsely-Error'd agent to clear the watchdog flag without going through the full reset flow. Tests above only cover Error→Completed; consider adding an Error→Running test if t650's verification reveals it as a useful manual recovery step.

## Final Implementation Notes

(Filled in at archival time per task-workflow Step 9.)
