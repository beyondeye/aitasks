---
priority: medium
effort: low
depends: [t461_1]
issue_type: feature
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-13 11:43
updated_at: 2026-04-13 13:26
---

## Context

Parent task t461 adds interactive launch mode for agentcrew code agents
(see t461_1 for the runner change). After t461_1, a new agent can be
marked interactive at creation time via
`ait crew addwork --launch-mode interactive`. This task adds the
**post-creation** mutation path: a new `ait crew setmode` subcommand
that flips the `launch_mode` field on an existing `Waiting` agent before
it launches.

The TUI edit flow (sibling task t461_4) shells out to this script rather
than re-implementing yaml mutation, so the CLI and TUI share one code
path.

## Key Files to Modify

- `.aitask-scripts/aitask_crew_setmode.sh` — NEW. Mirror the style of
  `.aitask-scripts/aitask_crew_addwork.sh` for arg parsing, yaml
  mutation, and auto-commit.
- `ait` — register the new `setmode` subcommand under the `crew` dispatch
  block (currently around lines 180-209 where `addwork`, `status`,
  `command`, `runner`, etc. are wired).

## Reference Files for Patterns

- `.aitask-scripts/aitask_crew_addwork.sh` — model for arg parsing
  (`case "$1" in`), yaml block emission, commit plumbing, and the
  `update_yaml_field` helper it sources (likely from
  `.aitask-scripts/lib/task_utils.sh` or `terminal_compat.sh`).
- `.aitask-scripts/aitask_crew_command.sh` — model for commands that
  target a specific agent inside a specific crew (flags like `--crew`
  and `--name`, agent-file path resolution).
- Existing usage of `./ait git add` / `./ait git commit` for agent
  status file changes (as done in addwork).

## Implementation Plan

1. **Create `.aitask-scripts/aitask_crew_setmode.sh`**:
   - `#!/usr/bin/env bash`, `set -euo pipefail`, source
     `.aitask-scripts/lib/task_utils.sh` and `terminal_compat.sh` as
     other crew scripts do.
   - Parse required flags:
     - `--crew <id>`
     - `--name <agent_name>`
     - `--mode <headless|interactive>`
   - Locate `<crew_dir>/<agent_name>_status.yaml` (same path as addwork).
     `die` if the file does not exist.
   - Read the current `status` field; if it is NOT `Waiting`, `die` with
     a clear message: "Cannot change launch_mode of agent in state
     '<status>' — launch_mode applies only to pending launches".
   - Validate `--mode`: reject anything other than `headless` or
     `interactive`.
   - Call `update_yaml_field "$status_file" launch_mode "$mode"` to
     mutate the field in place.
   - Auto-commit the change via `./ait git add "$status_file" && ./ait
     git commit -m "ait: Set launch_mode=$mode for crew $crew_id agent
     $agent_name"`. Commit only if git is dirty (check `./ait git
     status --porcelain` like addwork does).
   - Print `UPDATED:<agent_name>:<mode>` to stdout on success for
     machine-readable consumption by the TUI.

2. **Wire into `ait` dispatcher**: add a new `setmode)` case under the
   `crew` subcommand block next to `addwork)`, `command)`, etc. Route
   to `exec .aitask-scripts/aitask_crew_setmode.sh "$@"`.

3. **Add help text**: update `ait --help` / `ait crew --help` output (or
   the equivalent inline help strings) to list `setmode` with a short
   description.

4. **Shellcheck compliance**: both the new script and any modified
   lines in `ait` must pass `shellcheck`.

## Verification Steps

1. `shellcheck .aitask-scripts/aitask_crew_setmode.sh` — must pass.
2. Create a test crew with a Waiting agent (via `ait crew addwork`).
   Run `./ait crew setmode --crew <id> --name <agent> --mode
   interactive`. Confirm:
   - Exit code 0.
   - The agent's `_status.yaml` now contains `launch_mode: interactive`.
   - A git commit was created with the expected message.
   - Stdout contains `UPDATED:<name>:interactive`.
3. Run setmode against an agent in `Running` state; confirm it fails
   with a clear error and non-zero exit.
4. Run setmode with an invalid `--mode` value (e.g., `verbose`); confirm
   it fails with a validation error.
5. Run setmode for a non-existent agent; confirm it fails with a clear
   "file not found" message.
6. Run `./ait crew --help` (or equivalent) and confirm `setmode` is
   listed.

## Dependencies

- Depends on t461_1 for the schema convention (`launch_mode` field
  shape, validation set).
