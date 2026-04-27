---
Task: t653_3_agentcrew_terminal_push_and_recover.md
Parent Task: aitasks/t653_brainstorm_import_proposal_hangs.md
Sibling Tasks: aitasks/t653/t653_4_*.md, aitasks/t653/t653_5_*.md
Archived Sibling Plans: aiplans/archived/p653/p653_1_*.md, aiplans/archived/p653/p653_2_*.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-27 08:07
---

# Plan: t653_3 — Push terminal status from cmd_set + relax Error→Running

## Context (recap)

Two structural issues in agentcrew status machinery (surfaced by t653 investigation):

1. `cmd_set` in `agentcrew_status.py` writes `_status.yaml` but never pushes the worktree. Runner pushes once per iteration, but if it has already exited (graceful shutdown, SIGKILL, network blip), the agent's local Completed write never reaches remote.

2. `AGENT_TRANSITIONS["Error"]` blocks falsely-Error'd agents from self-correcting to Running mid-flight. The validator forces a `--reset` first (Error → Waiting), then re-launch (Waiting → Ready → Running → Completed). Brittle for the heartbeat-watchdog false-positive case.

After parent t650 lands, the false-Error path becomes rare — but both gaps remain real for any runner-exit scenario. Defense-in-depth.

## Verification findings (2026-04-26)

Verified the plan against current code; updates baked into the steps below:

- `agentcrew_utils.py:26-37` — `AGENT_TRANSITIONS` now lives here (was 23-32). Current `Error` value is **already** `["Waiting", "Completed"]` (partial extension landed via another change). A new `MissedHeartbeat` status exists in the dict — preserve it. **Remaining work:** add `"Running"` to the Error list.
- `agentcrew_runner.py:136-139` — `git_cmd` defined here.
- `agentcrew_runner.py:142-146` — `git_pull` defined here, also uses `git_cmd`.
- `agentcrew_runner.py:149-158` — `git_commit_push_if_changes` defined here, uses `git_cmd`.
- Runner per-iteration push at line 1032 (was 979). Other in-runner callers of `git_commit_push_if_changes`: lines 879, 915, 937, 1032 — all stay in runner.
- No subprocess shell-out from runner to `ait crew status set` — the runner uses `update_yaml_field` directly. **Therefore the runner does NOT need `--no-push` plumbing.** The `--no-push` flag stays as a public option for future batched callers but is not consumed in this task.
- `agentcrew_status.py:87-130` — `cmd_set` location confirmed (plan said 87-129). Insertion point after `_recompute_crew_status(wt)` at line 129.
- `agentcrew_status.py:263-265` — `set_p` argparse subparser. Add `--no-push` here.
- `resolve_crew` → `crew_worktree_path` builds `.aitask-crews/crew-<id>/`. Tests must use this layout (the plan's earlier sketch with `crew/test_crew/` would not pass `resolve_crew`'s `os.path.isdir` check).
- Existing tests already use BSD-portable `mktemp -d "${TMPDIR:-/tmp}/foo_XXXXXX"` (e.g. `tests/test_agentcrew_pythonpath.sh`). Use it as the fixture model.

## Approach

1. Add `"Running"` to `AGENT_TRANSITIONS["Error"]` (final value: `["Waiting", "Running", "Completed"]`). Aborted stays terminal.
2. Move the git helpers `git_cmd`, `git_pull`, and `git_commit_push_if_changes` from runner to utils as a cohesive group. Runner re-imports from utils.
3. After `cmd_set` flips status to a terminal state (`Completed`/`Aborted`/`Error`) and recomputes crew status, call `git_commit_push_if_changes` with a descriptive commit message. Add a `--no-push` argparse flag for future batched callers. The runner itself does not call `cmd_set` so no caller change is needed in the runner this round.

## Step-by-step

### S1. Extend `AGENT_TRANSITIONS["Error"]` (`agentcrew_utils.py:26-37`)

Replace:
```python
"Error": ["Waiting", "Completed"],
```
with:
```python
# Error is recoverable: a heartbeat-watchdog timeout does not prove the agent
# failed. An agent that gets falsely Error'd may still write Completed at end
# of work, or resume Running mid-flight. Aborted is intentionally terminal —
# Aborted is always user-initiated, not a watchdog accident.
"Error": ["Waiting", "Running", "Completed"],
```

Leave `MissedHeartbeat` and all other entries untouched.

### S2. Move git helpers into utils

**Cut from `agentcrew_runner.py` lines 136-158** (three contiguous helpers):
- `git_cmd(worktree, *args, check=True)` (136-139)
- `git_pull(worktree, batch=False)` (142-146)
- `git_commit_push_if_changes(worktree, message, batch=False)` (149-158)

**Paste into `agentcrew_utils.py`** above the YAML helpers section (after `crew_worktree_path` and other small helpers near the top, but cleanly grouped — drop a `# Git helpers` section comment so the file structure stays readable).

**Required imports in utils:** `subprocess` (already imported in runner; verify whether utils already has it — add if missing). The `log()` helper used for warnings — check whether utils has access. Two paths:
- If utils does not import `log`, replace the `log(...)` lines in `git_pull` / `git_commit_push_if_changes` with a simple `print(..., file=sys.stderr)` guarded by `if not batch`.
- If `log` is already in utils, keep it as-is.

**Update runner imports.** Replace the three `def`s with:
```python
from agentcrew.agentcrew_utils import git_cmd, git_pull, git_commit_push_if_changes
```
(or whatever the existing import style is — match the file's prevailing convention).

**Verify no other module has its own copy.** Already grepped: only the runner currently defines and uses these, and no tests or external modules import them. Re-grep at implementation time:
```bash
grep -rn "def git_cmd\|def git_pull\|def git_commit_push_if_changes" .aitask-scripts/
grep -rn "git_commit_push_if_changes\|git_pull\|git_cmd" .aitask-scripts/
```
Confirm post-move that runner is now a consumer-only and there are no circular imports between runner ↔ utils.

### S3. Push from `cmd_set` on terminal transitions

In `agentcrew_status.py:cmd_set` (currently lines 87-130), capture the previous status before mutation so the commit message can describe the transition. After the existing `_recompute_crew_status(wt)` call (line 129), add:

```python
if (args.status in ("Completed", "Aborted", "Error")
        and not getattr(args, "no_push", False)):
    from agentcrew.agentcrew_utils import git_commit_push_if_changes
    git_commit_push_if_changes(
        wt,
        f"agent {args.agent}: {prev_status} -> {args.status}",
        batch=True,
    )
```

`prev_status` must be captured **before** `data["status"] = args.status` (the mutation step inside `cmd_set`). If `cmd_set` does not currently bind `prev_status`, add `prev_status = data.get("status", "Unknown")` immediately after reading the status file and before validation.

`git_commit_push_if_changes` is idempotent (no-op when no diff is staged), so accidental double-calls are safe.

### S4. Add `--no-push` to the `set` subparser

In `agentcrew_status.py` around lines 263-265 (where `set_p = sub.add_parser("set", ...)` is defined and its existing args are added), append:

```python
set_p.add_argument("--no-push", action="store_true",
                   help="Skip git push after writing the status (for batched callers)")
```

The flag is a future-proofing hook — there is no current caller that needs `--no-push` (verified: runner uses direct YAML writes, not subprocess shell-outs to `ait crew status set`). Document this in the function's vicinity with a one-line comment so a future reader does not look for missing callers.

### S5. Tests — `tests/test_agentcrew_terminal_push.sh`

Use `.aitask-crews/crew-<id>/` layout (matches `resolve_crew`). Pattern from `tests/test_agentcrew_pythonpath.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TMPROOT="$(mktemp -d "${TMPDIR:-/tmp}/aitask_test_terminal_push_XXXXXX")"
trap 'rm -rf "$TMPROOT"' EXIT

cd "$TMPROOT"
git init -q
git config user.email "test@example.com"
git config user.name "Test"
git commit -q --allow-empty -m "init"

# Build the crew worktree at the path resolve_crew expects
CREW_DIR=".aitask-crews/crew-test_crew"
mkdir -p "$CREW_DIR"

# Seed an agent _status.yaml in Running state
cat > "$CREW_DIR/foo_status.yaml" <<EOF
agent_name: foo
status: Running
progress: 50
EOF
# Seed _crew_status.yaml so _recompute_crew_status has a target
cat > "$CREW_DIR/_crew_status.yaml" <<EOF
status: Running
updated_at: 2026-04-26T00:00:00Z
progress: 0
EOF
git add -A && git commit -q -m "seed"

# Run cmd_set with terminal transition (no --no-push)
"$ROOT/ait" crew status set --crew test_crew --agent foo --status Completed

# Assertions
grep -q "^status: Completed" "$CREW_DIR/foo_status.yaml" \
    || { echo "FAIL: status did not flip to Completed"; exit 1; }

# A new commit must exist beyond the seed
COMMIT_COUNT="$(git rev-list --count HEAD)"
[[ "$COMMIT_COUNT" -ge 3 ]] \
    || { echo "FAIL: no new commit recorded after terminal transition"; exit 1; }
echo "PASS: terminal push test"

# --- --no-push variant -------------------------------------------------
cat > "$CREW_DIR/bar_status.yaml" <<EOF
agent_name: bar
status: Running
EOF
git add -A && git commit -q -m "seed bar"
HASH_BEFORE="$(git rev-parse HEAD)"

"$ROOT/ait" crew status set --crew test_crew --agent bar --status Completed --no-push

HASH_AFTER="$(git rev-parse HEAD)"
[[ "$HASH_BEFORE" == "$HASH_AFTER" ]] \
    || { echo "FAIL: --no-push made a commit"; exit 1; }
grep -q "^status: Completed" "$CREW_DIR/bar_status.yaml" \
    || { echo "FAIL: --no-push prevented the YAML write"; exit 1; }
echo "PASS: --no-push test"
```

Note: the test does not configure a remote. `git push` inside `git_commit_push_if_changes` will return non-zero, but the helper logs a warning (in non-batch) or stays silent (in batch=True, which is what `cmd_set` passes). The commit still lands locally — the assertion checks `git rev-list --count`, which only counts local commits. If push noise leaks to stdout under any path, redirect or filter as needed.

`tests/test_agentcrew_error_recovery.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
# Same fixture as terminal_push test
# Seed agent in Error state.

# 1. set --status Completed → succeeds (Error → Completed allowed since prior change)
"$ROOT/ait" crew status set --crew test_crew --agent foo --status Completed
grep -q "^status: Completed" "$CREW_DIR/foo_status.yaml" \
    || { echo "FAIL: Error → Completed rejected"; exit 1; }
echo "PASS: Error → Completed allowed"

# 2. Re-seed in Error. set --status Running → succeeds (this is the new transition added in S1)
cat > "$CREW_DIR/foo_status.yaml" <<EOF
agent_name: foo
status: Error
EOF
git add -A && git commit -q -m "reset to Error"
"$ROOT/ait" crew status set --crew test_crew --agent foo --status Running
grep -q "^status: Running" "$CREW_DIR/foo_status.yaml" \
    || { echo "FAIL: Error → Running rejected"; exit 1; }
echo "PASS: Error → Running allowed (new transition)"

# 3. Re-seed in Error. set --status Aborted → fails (Aborted not in Error allow list).
cat > "$CREW_DIR/foo_status.yaml" <<EOF
agent_name: foo
status: Error
EOF
git add -A && git commit -q -m "reset to Error 2"
if "$ROOT/ait" crew status set --crew test_crew --agent foo --status Aborted 2>/dev/null; then
    echo "FAIL: Error → Aborted should have been rejected"
    exit 1
fi
echo "PASS: Error → Aborted correctly rejected"
```

### S6. shellcheck and lint

Run `shellcheck .aitask-scripts/agentcrew/*.sh` to confirm no regression. (No new shell scripts in this child, but verify the existing ones still pass.) The Python files are not shellcheck-targeted; rely on existing tests + manual e2e.

## Files touched

- `.aitask-scripts/agentcrew/agentcrew_utils.py` — `Error` transition extended (1 line + comment); +`git_cmd` / `git_pull` / `git_commit_push_if_changes` (~30 lines moved in)
- `.aitask-scripts/agentcrew/agentcrew_status.py` — push call after `_recompute_crew_status` + capture `prev_status` (~10 lines); `--no-push` argparse flag (~2 lines)
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — three helpers cut, replaced with one import line (net ~−20 lines)
- `tests/test_agentcrew_terminal_push.sh` — new (~65 lines)
- `tests/test_agentcrew_error_recovery.sh` — new (~50 lines)

## Verification

1. **Unit tests:**
   ```bash
   bash tests/test_agentcrew_terminal_push.sh
   bash tests/test_agentcrew_error_recovery.sh
   ```
   Both PASS.

2. **shellcheck:** `shellcheck .aitask-scripts/agentcrew/*.sh` (and any other shell modified) — clean.

3. **No regression in runner-side push frequency.** Sanity-grep that the four runner callers (lines 879, 915, 937, 1032 pre-move) still resolve via the new import. If feasible, run `python -c "from agentcrew.agentcrew_runner import git_commit_push_if_changes"` from the project root to verify the import resolves.

4. **Manual end-to-end recovery:**
   - Contrive a brainstorm crew where an agent ends up in `Error` (`heartbeat_timeout_minutes: 0` in `_crew_meta.yaml` and wait one iteration).
   - Run `ait crew status set --crew <id> --agent <name> --status Completed`.
   - Expect: succeeds, status flips, commit appears in the worktree, `git ls-remote` reflects the push (when run in a real worktree with a remote, not the synthetic test fixture).

## Notes for sibling tasks

- t653_4 and t653_5 do not depend on this child. Land order doesn't matter.
- This child does **not** introduce a new helper script, so the 5-touchpoint whitelist procedure does not apply.
- The Error→Running transition was added so a user can manually `ait crew status set --status Running` on a falsely-Error'd agent to clear the watchdog flag without going through the full reset flow. The error_recovery test covers Error→Running explicitly.
- `MissedHeartbeat` is preserved as-is — that machinery belongs to a different change track and is unaffected by this work.

## Final Implementation Notes

(Filled in at archival time per task-workflow Step 9.)
