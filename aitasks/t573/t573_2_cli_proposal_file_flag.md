---
priority: high
effort: low
depends: [t573_1]
issue_type: feature
status: Ready
labels: [ait_brainstorm]
created_at: 2026-04-23 11:00
updated_at: 2026-04-23 11:00
---

## Context

Parent task t573 is about importing an external markdown proposal at
brainstorm init time. This child wires the **CLI entry point** so the
feature is usable from the shell and (later, via t573_3) from the TUI.

Depends on t573_1 which adds the `initializer` agent type,
`register_initializer(...)`, `init_session(..., initial_proposal_file=...)`,
and `apply_initializer_output(...)`.

## Key Files to Modify

- `.aitask-scripts/aitask_brainstorm_init.sh` — new `--proposal-file
  <path>` CLI flag.
- `.aitask-scripts/brainstorm/brainstorm_cli.py` — new CLI arg on
  `cmd_init`; plumb through to `init_session(...)` and register the
  initializer agent when provided.

## Reference Files for Patterns

- Existing CLI: `.aitask-scripts/brainstorm/brainstorm_cli.py:35-47`
  (`cmd_init`) and `146-151` (subparser wiring).
- Existing bash argparse: `.aitask-scripts/aitask_brainstorm_init.sh:50-69`
  (`--help`, positional parsing, `die`).
- Runner-start idiom — search existing bash scripts for `ait crew run`
  invocations for the correct flag set (the codebase has an
  `aitask_crew_*.sh` family).
- `register_initializer` signature — from t573_1, to be called right
  after `init_session` succeeds (stay inside `brainstorm_cli.py`; do
  NOT move that logic into the shell script).

## Implementation Plan

1. **`aitask_brainstorm_init.sh`** — accept `--proposal-file <path>`:
   - Validate: file exists, is readable, is non-empty, has `.md`
     or `.markdown` extension (warn-only for extension).
   - Resolve to absolute path with `realpath` (portable fallback
     using `python3 -c 'import os; print(os.path.realpath(...))'`
     if needed — check `terminal_compat.sh` first).
   - Propagate the absolute path to the python CLI via
     `--proposal-file "$ABS_PATH"`.
   - Add the argument to `_get_brainstorm_agent_string` / crew-init
     flag list so the new `initializer` type is registered (see
     lines 128-134 for the five existing `--add-type` lines; add a
     sixth for `initializer`).

2. **`brainstorm_cli.py cmd_init`** — add `--proposal-file` argument:
   ```python
   p_init.add_argument("--proposal-file", default="",
                       help="Optional markdown file to use as initial proposal")
   ```
   In `cmd_init(args)`:
   - Pass `initial_proposal_file=args.proposal_file or None` to
     `init_session(...)`.
   - Return-early unchanged when `--proposal-file` is empty.
   - When non-empty: after `init_session(...)` succeeds, call
     `register_initializer(...)` with `imported_path=args.proposal_file`
     and `task_file=args.task_file`, then print
     `INITIALIZER_AGENT:<name>` on its own line on stdout (mirrors the
     existing `SESSION_PATH:` line).

3. **`aitask_brainstorm_init.sh`** — after the python CLI returns,
   detect `INITIALIZER_AGENT:` in its stdout. If present:
   - Start the crew runner via the existing crew-run helper:
     `bash "$SCRIPT_DIR/aitask_crew_run.sh" --id "brainstorm-${TASK_NUM}"
     --detach` (or whichever subcommand exists — consult the helper
     file before wiring). Print a one-line hint:
     `"Initializer agent started in interactive mode. Attach with
     'ait crew attach brainstorm-${TASK_NUM}' or open the TUI with
     'ait brainstorm ${TASK_NUM}'."`.

4. **No behaviour change when `--proposal-file` is omitted.** The
   existing happy path (task-file → n000_init) must remain
   byte-for-byte identical so existing users see no regression.

## Verification

- `ait brainstorm init 9999 --proposal-file /does/not/exist` fails
  with a clear "file not found" message, exit code 1. No crew
  directory is created.
- `ait brainstorm init <fresh_task> --proposal-file /tmp/ex.md`
  (for a valid `.md` file):
  - Creates the crew with six agent types registered (explorer,
    comparator, synthesizer, detailer, patcher, initializer).
  - Prints both `SESSION_PATH:...` and
    `INITIALIZER_AGENT:initializer_bootstrap` on stdout.
  - `br_session.yaml` has `initial_proposal_file` set.
  - `br_proposals/n000_init.md` contains the placeholder text.
  - Runner-start hint line is printed.
- `ait brainstorm init <fresh_task>` (without flag) behaves
  identically to today's behaviour — no new stdout lines, no
  initializer agent registered.
- `shellcheck .aitask-scripts/aitask_brainstorm_init.sh` is clean.
