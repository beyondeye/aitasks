---
Task: t461_2_crew_setmode_cli.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/t461/t461_1_*.md, aitasks/t461/t461_3_*.md, aitasks/t461/t461_4_*.md, aitasks/t461/t461_5_*.md, aitasks/t461/t461_6_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_1_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# p461_2 — `ait crew setmode` CLI for existing agents

## Goal

Add a small bash script and `ait` subcommand that mutates the `launch_mode`
field on a `Waiting` agent's status yaml. Used both from the command line
and from the brainstorm TUI status-tab edit flow (sibling t461_4 will shell
out to this script rather than re-implementing the yaml mutation).

## Files

### New
1. `.aitask-scripts/aitask_crew_setmode.sh` — the new CLI script.
2. `tests/test_crew_setmode.sh` — automated bash test suite (9 scenarios,
   21 assertions).

### Modified
3. `ait` — register `setmode` in three places inside the `crew)` dispatch
   block (lines 180–211): dispatch case (after `addwork`), `--help` listing,
   and the unknown-subcommand error message.
4. `CLAUDE.md` — list `bash tests/test_crew_setmode.sh` in the Testing
   section.

## Implementation steps

### 1. Script: `.aitask-scripts/aitask_crew_setmode.sh`

Mirror the shape of `aitask_crew_addwork.sh` and `aitask_crew_command.sh`:

- Source `lib/terminal_compat.sh` and `lib/agentcrew_utils.sh` (the latter
  provides `validate_crew_id`, `validate_agent_name`, `resolve_crew`,
  `read_yaml_field`, and the `AGENT_STATUS_WAITING` constant).
- Parse required flags `--crew`, `--name`, `--mode` plus `--help`/`-h`.
- Validate `--mode` against `^(headless|interactive)$`.
- Resolve the worktree via `WT_PATH="$(resolve_crew "$CREW_ID")"`.
- Locate `$WT_PATH/${AGENT_NAME}_status.yaml` and `die` if missing.
- Read the current `status` field via `read_yaml_field`. If it is not
  `$AGENT_STATUS_WAITING`, `die` with a clear message: "Agent '<name>' is
  in state '<status>' — launch_mode only applies to pending launches".
- Mutate the `launch_mode` line in place via a tmpfile rewrite loop (same
  pattern as `aitask_crew_command.sh:155-176`). The line is always present
  in status files emitted by t461_1's addwork, but the script handles the
  missing-line case by appending the field defensively.
- Auto-commit inside the crew worktree using plain `git`, mirroring
  `aitask_crew_addwork.sh:294-304` (crew files live on a separate
  `crew-<id>` branch — `./ait git` does not manage that branch). The commit
  is guarded by `git diff --quiet -- "${AGENT_NAME}_status.yaml"` so a
  no-op call (e.g. setting the mode that is already in the file) does not
  create an empty commit. The commit message is `crew: Set
  launch_mode=<mode> for agent '<name>' in crew '<id>'`.
- Print `UPDATED:<agent>:<mode>` to stdout for machine consumption (parsed
  by sibling t461_4).
- `chmod +x` the script.

### 2. Wire `ait` dispatcher

Inside the `crew)` block (lines 180–211):

- Add `setmode)   exec "$SCRIPTS_DIR/aitask_crew_setmode.sh" "$@" ;;`
  immediately after the `addwork)` line.
- Add `echo "  setmode     Change launch_mode of a Waiting agent (headless|interactive)"`
  to the `--help` listing, between the `addwork` and `status` lines.
- Add `setmode` to the unknown-subcommand `Available: …` error message.

### 3. Test suite: `tests/test_crew_setmode.sh`

Mirror `tests/test_launch_mode_field.sh` (file-based counters,
`setup_test_repo` / `cleanup_test_repo`, `assert_contains` /
`assert_not_contains` / `assert_eq` / `assert_exit_nonzero`). The setup
function provisions an isolated repo with `crew_init.sh`, `crew_addwork.sh`,
and the new `crew_setmode.sh`. A helper `seed_crew_with_agent` initializes
a crew and adds one Waiting agent (default headless `launch_mode`).

Test scenarios:

| # | Scenario | Assertions |
|---|----------|------------|
| 1 | Happy path: headless → interactive | Stdout contains `UPDATED:<n>:interactive`, yaml shows `launch_mode: interactive`, no leftover `launch_mode: headless`, commit message contains `Set launch_mode=interactive` |
| 2 | Round trip: headless → interactive → headless | Final yaml is headless, no leftover interactive, exactly two `Set launch_mode=` commits in the worktree log |
| 3 | Idempotent: setmode interactive twice | Second call still prints the structured success line; commit count is unchanged after the second call |
| 4 | Status gate: yaml manually flipped to `Running` | Non-zero exit, error mentions "launch_mode only applies to pending launches", yaml unchanged |
| 5 | Bad mode (`--mode verbose`) | Non-zero exit, error mentions "must be 'headless' or 'interactive'" |
| 6 | Missing agent (`--name does_not_exist`) | Non-zero exit |
| 7 | Missing crew (`--crew does_not_exist`) | Non-zero exit (from `resolve_crew`) |
| 8 | Missing each required flag | Non-zero exit for each of `--mode`, `--name`, `--crew` |
| 9 | `--help` exits 0 and shows usage with `--mode` listed | Stdout contains `Usage: ait crew setmode` and `--mode` |

`assert_contains`/`assert_not_contains` use `grep -qF -- "$pattern"` so
literal patterns starting with `--` are matched correctly.

### 4. Document the test in `CLAUDE.md`

Add `bash tests/test_crew_setmode.sh` to the enumerated test list in the
Testing section.

## Verification

**Primary (automated):**

1. `shellcheck .aitask-scripts/aitask_crew_setmode.sh` — clean (only the
   pre-existing SC1091 informational "not following sourced file" notes,
   identical to addwork).
2. `shellcheck tests/test_crew_setmode.sh` — clean.
3. `bash tests/test_crew_setmode.sh` — 21/21 PASS.
4. `bash tests/test_launch_mode_field.sh` — 7/7 PASS (no regression in
   addwork).
5. `bash tests/test_crew_init.sh` — 32/32 PASS (no regression in init).

**Manual smoke checks:**

6. `./ait crew --help` lists `setmode` between `addwork` and `status`.
7. `./ait crew setmode --help` prints usage.
8. `./ait crew unknownsub` error message lists `setmode` among the
   available subcommands.

## Dependencies

- t461_1 (merged): defines the `launch_mode` schema, the validation set
  `^(headless|interactive)$`, and the runner's mode-resolution chain that
  reads the field this script writes.

## Notes for sibling tasks

- **t461_4 (brainstorm status edit)** must shell out to this script and
  parse the `UPDATED:<name>:<mode>` line on stdout to confirm success.
  Keep that contract stable.
- **t461_5 (per-type defaults)** does not interact with setmode directly,
  but if it ever introduces a new mode value (e.g. `monitored`), three
  things must be updated in lock-step: the addwork validator regex, the
  runner branch list in `agentcrew_runner.launch_agent()`, and the
  setmode validator regex.
- The launch_mode field stays at its existing position in the status yaml
  (between `group:` and `status:`) because the mutation only rewrites the
  matching line — surrounding fields are preserved verbatim.

## Final Implementation Notes

- **Actual work done:**
  - `.aitask-scripts/aitask_crew_setmode.sh` (~125 lines) — new script
    implementing the full flow described above. Sources
    `lib/agentcrew_utils.sh` for the helpers and the `AGENT_STATUS_WAITING`
    constant. The yaml mutation uses a `while read | tmpfile` loop with a
    `found` flag and a defensive append fallback. Commits inside the crew
    worktree with plain `git`, guarded by `git diff --quiet -- "<file>"`.
    `chmod +x` applied.
  - `ait` — three edits inside the `crew)` block: dispatch case after
    `addwork)`, help-text line between `addwork` and `status`, and
    `setmode` added to the unknown-subcommand `Available:` list.
  - `tests/test_crew_setmode.sh` (~250 lines) — 9 scenarios, 21
    assertions, all PASS. Modeled on `test_launch_mode_field.sh`. Adds an
    `assert_eq` helper (sibling test only had `assert_contains` /
    `assert_not_contains` / `assert_exit_nonzero`) used by the round-trip
    and idempotency tests to compare commit counts. Uses `grep -qF -- ...`
    in `assert_contains`/`assert_not_contains` so literal patterns
    starting with `--` (e.g. `--mode`) match correctly.
  - `CLAUDE.md` — added `bash tests/test_crew_setmode.sh` to the Testing
    section list.

- **Deviations from the original (un-verified) plan:**
  - Original plan said to source `lib/task_utils.sh` and call
    `update_yaml_field` from bash. Actual: `update_yaml_field` exists only
    in Python (`agentcrew/agentcrew_utils.py:64`); the shell-side
    equivalent does not exist. Replaced with a tmpfile rewrite loop using
    helpers that DO exist in `lib/agentcrew_utils.sh`.
  - Original plan said to commit via `./ait git add` / `./ait git commit`.
    Actual: crew worktrees live on a separate `crew-<id>` branch that
    `./ait git` does not manage. Switched to plain `git` inside the
    worktree, mirroring `aitask_crew_addwork.sh`.
  - Original plan hardcoded the crew dir as
    `.aitask-crews/crew-${CREW_ID}`. Replaced with `resolve_crew()` for
    consistency with sibling crew scripts and for the clean
    "crew not found" error path.
  - Original plan parsed the status field with ad-hoc `grep | awk | tr`.
    Replaced with the existing `read_yaml_field` helper. Comparison uses
    the exported `AGENT_STATUS_WAITING` constant rather than the literal
    string `"Waiting"`.
  - Original plan suggested `"$SCRIPT_DIR/.aitask-scripts/aitask_crew_setmode.sh"`
    for the dispatcher wiring. The actual variable name in `ait` is
    `$SCRIPTS_DIR` (set at line 7).

- **Issues encountered:**
  - First test run: 20/21 PASS. The single failure was in test 9 where
    `grep -q "$expected"` interpreted the `--mode` substring as an option
    flag. Fixed by switching `assert_contains`/`assert_not_contains` to
    `grep -qF -- "$pattern"` (also a small robustness improvement: the
    `-F` makes the pattern a fixed string, avoiding regex escaping
    headaches in future tests). After the fix, 21/21 PASS.

- **Key decisions:**
  - **Pure shell, no Python wrapper.** `aitask_crew_status.sh` is a thin
    bash wrapper that execs into a Python module, but the setmode mutation
    is small and self-contained, and the existing
    `aitask_crew_command.sh` already demonstrates the in-shell
    tmpfile-rewrite pattern. Keeping it pure shell removes the Python
    dependency for this surface and makes the test sandbox simpler (no
    need to copy the agentcrew Python package into the test repo).
  - **Idempotent commit guard** (`git diff --quiet -- "<file>"`) instead
    of always committing. This matches the spirit of the plan ("commit
    only if dirty") and is verified by test 3.
  - **Defensive append** for the missing-line case. Even though every
    status file emitted post-t461_1 has `launch_mode`, an older agent
    file (e.g. one created from a stale branch) would silently fail to
    update without this fallback. The cost is a tiny `if ! $found` block.
  - **Constant-based status comparison** (`$AGENT_STATUS_WAITING`) so
    that any future rename in `agentcrew_utils.sh` propagates to setmode
    automatically.

- **Verification results:**
  - `shellcheck .aitask-scripts/aitask_crew_setmode.sh`: 2 SC1091 info
    notes (same pattern as addwork's pre-existing 2 SC1091 notes — they
    are the standard "shellcheck cannot follow sourced file" warning),
    no errors.
  - `shellcheck tests/test_crew_setmode.sh`: clean.
  - `bash tests/test_crew_setmode.sh`: 21/21 PASS.
  - `bash tests/test_launch_mode_field.sh`: 7/7 PASS (sibling regression).
  - `bash tests/test_crew_init.sh`: 32/32 PASS (regression).
  - `./ait crew --help`: lists setmode in the expected position.
  - `./ait crew setmode --help`: prints full usage block.
  - `./ait crew unknownsub`: error message includes setmode in the
    `Available:` list.
