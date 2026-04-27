---
Task: t663_import_plan_in_ait_brainstorm_failing.md
Base branch: main
plan_verified: []
---

# Plan: Fix t663 — `ait brainstorm apply-initializer` failing on plan import

## Context

`ait brainstorm init 635 --proposal-file aidocs/gates/aitask-gate-framework.md`
launches an `initializer_bootstrap` agent that should reformat the imported
plan into the brainstorm n000_init node. In t635 the agent process started
but never produced output: it sat as a `claude --model claude-sonnet-4-6 -p
…` process for 5+ minutes with no heartbeat, then was marked
`MissedHeartbeat`. `apply-initializer` then fails because
`initializer_bootstrap_output.md` is still the placeholder template (no
`NODE_YAML_START` / `PROPOSAL_START` blocks).

### Root cause

Regression introduced by **t659** (`0eebeb42 feature: Default brainstorm
code-agents to interactive`). That commit flipped
`BRAINSTORM_AGENT_TYPES[*]['launch_mode']` defaults to `interactive`, but
left a pre-existing optimization in `_run_addwork` intact:

`.aitask-scripts/brainstorm/brainstorm_crew.py` lines 140–144:

```python
type_default = BRAINSTORM_AGENT_TYPES.get(agent_type, {}).get(
    "launch_mode", DEFAULT_LAUNCH_MODE
)
if launch_mode != type_default:
    cmd.extend(["--launch-mode", launch_mode])
```

The optimization assumes `aitask_crew_addwork.sh` will fall back to the
brainstorm-internal type default when no flag is passed. It does not —
`aitask_crew_addwork.sh` line 29 hardcodes `LAUNCH_MODE="headless"`. So when
the caller asks for `interactive` and the brainstorm type default is also
`interactive`, the flag is omitted and the agent is registered as
`headless`.

`_launch_headless` runs `claude -p` without `--dangerously-skip-permissions`
and without an `allowedTools` allowlist that covers `Write` (the project's
`.claude/settings.local.json` only allows specific `Bash(...)` patterns). The
initializer needs to call `Write` to populate `_output.md`, the tool call
blocks waiting for permission, and the agent never heartbeats.

This affects **every** brainstorm code agent (explorer, comparator,
synthesizer, detailer, patcher, initializer) since t659 set them all to
`interactive`. t635 surfaced it via the initializer because the import flow
is the only one where a single-agent failure halts a user-visible operation
end-to-end.

Confirmed by:
- `.aitask-crews/crew-brainstorm-635/initializer_bootstrap_status.yaml` →
  `launch_mode: headless` (should be `interactive`).
- `.aitask-crews/crew-brainstorm-635/_crew_meta.yaml` →
  `agent_types.initializer.launch_mode: interactive` (correct, but ignored
  by `_run_addwork`).
- `.aitask-crews/crew-brainstorm-635/initializer_bootstrap_log.txt` →
  only the static `=== Started ===` header was written; no claude stdout.
- `claude` PID 286186 still alive, in `Sl` state on `do_epo` (epoll wait —
  blocked on permission UI that does not exist in headless mode).

## Fix

### File: `.aitask-scripts/brainstorm/brainstorm_crew.py`

In `_run_addwork`, always forward `--launch-mode <mode>` to
`aitask_crew_addwork.sh`. Drop the broken delta-only optimization.

Replace the block at lines 140–144:

```python
type_default = BRAINSTORM_AGENT_TYPES.get(agent_type, {}).get(
    "launch_mode", DEFAULT_LAUNCH_MODE
)
if launch_mode != type_default:
    cmd.extend(["--launch-mode", launch_mode])
```

with:

```python
cmd.extend(["--launch-mode", launch_mode])
```

This is the minimal, correct change. `aitask_crew_addwork.sh` already
validates the value against `LAUNCH_MODES_REGEX` and always writes it into
`<name>_status.yaml`, so the runner picks up the right mode at launch time.

### File: `tests/test_brainstorm_crew.py`

Add a focused regression test verifying that `_run_addwork` (or its
public callers) always passes `--launch-mode` to `./ait crew addwork`,
even when the requested mode equals the brainstorm type default.

Approach: monkey-patch `subprocess.run` inside the
`brainstorm_crew` module to capture the invoked command, call
`register_initializer(..., launch_mode="interactive")`, and assert the
captured command list contains `["--launch-mode", "interactive"]`.

Reuse existing test scaffolding in `tests/test_brainstorm_crew.py`
(`TestRegisterInitializer`-style patterns if present, otherwise a fresh
class with the project root setup helpers already used in that file).

## Recovery for the stuck brainstorm-635 session

After applying the fix, the existing crew is unrecoverable in place because
the dead `claude` process (PID 286186) is still attached and the agent
status is `MissedHeartbeat`. Recovery procedure (manual, by the user, after
the fix is committed):

1. Kill the orphaned claude process: `kill 286186` (verify with
   `ps -p 286186` first).
2. Stop the runner: `ait crew runner --crew brainstorm-635 --stop` (or use
   the brainstorm TUI's "Stop Runner").
3. Remove the failed brainstorm session: `ait brainstorm delete 635`
   (this also tears down the worktree and branch; see commit `35d8ab2f`
   for the prune-worktree fix from t662).
4. Re-run the import:
   `ait brainstorm init 635 --proposal-file aidocs/gates/aitask-gate-framework.md`.
5. Confirm the agent registers as `interactive` by checking
   `.aitask-crews/crew-brainstorm-635/initializer_bootstrap_status.yaml`
   contains `launch_mode: interactive`.
6. Wait for the agent to populate `initializer_bootstrap_output.md` with
   `NODE_YAML_*` and `PROPOSAL_*` blocks; then `ait brainstorm
   apply-initializer 635` should succeed.

## Verification

1. Lint the modified file:
   `shellcheck` is not applicable (Python file). Verify Python imports
   resolve by running the existing brainstorm test:
   `bash tests/test_brainstorm_crew.sh` (or whichever runner the test file
   uses — confirm path during implementation).
2. Run the new regression test and the full `tests/test_brainstorm_crew.*`
   suite.
3. Manual end-to-end check (after recovery):
   - Re-run `ait brainstorm init 635 --proposal-file
     aidocs/gates/aitask-gate-framework.md`.
   - Confirm the launched claude process is in interactive mode (visible
     in tmux as `agent-initializer_bootstrap` window).
   - Once the agent completes, confirm
     `.aitask-crews/crew-brainstorm-635/initializer_bootstrap_output.md`
     contains both delimiter blocks.
   - Run `ait brainstorm apply-initializer 635` and confirm it prints
     `APPLIED:n000_init`.
   - Inspect `br_nodes/n000_init.yaml` and `br_proposals/n000_init.md`
     in the crew worktree to confirm valid imported content.

## Files touched

| File | Change |
|------|--------|
| `.aitask-scripts/brainstorm/brainstorm_crew.py` | Drop delta-only `--launch-mode` optimization in `_run_addwork`; always pass the flag. |
| `tests/test_brainstorm_crew.py` | Add regression test asserting `--launch-mode` is always forwarded to `ait crew addwork`. |

No changes needed to `aitask_crew_addwork.sh`, the runner, the brainstorm
CLI, or `BRAINSTORM_AGENT_TYPES` — those are correct as-is once the
caller behaves.

## Out of scope

- Changing the default in `aitask_crew_addwork.sh` (would touch
  unrelated callers).
- Adding `--dangerously-skip-permissions` plumbing to headless
  `_launch_headless` so it could ever work for write-needing agents
  (separate design question; not what t635 needs).
- Auditing other crew callers for the same optimization pattern; the
  bug is localized to `_run_addwork` in `brainstorm_crew.py`.

## Step 9 (Post-Implementation)

Standard archival per `.claude/skills/task-workflow/SKILL.md` Step 9:
no separate worktree (profile `fast` → current branch), so skip merge
steps; commit code and plan separately, run `aitask_archive.sh 663`,
then push.
