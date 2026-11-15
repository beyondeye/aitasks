---
Task: t2305_fix_brainstorm_apply_subcommand_help.md
Base branch: main
Output branch: main
---

# t2305 — `--help` for the brainstorm `apply-*` subcommands

## Context

`ait brainstorm --help` says "Run 'ait brainstorm <subcommand> --help' for
subcommand-specific help", and `init` / `status` / `archive` / `delete` honour
that. The three `apply-*` scripts read positional arguments only:

- `apply-initializer --help` takes `--help` as the task number and fails with
  `APPLY_FAILED:No initializer output at .aitask-crews/crew-brainstorm---help/…` (exit 1).
- `apply-explorer --help` / `apply-synthesizer --help` print a one-line usage to
  stderr and exit 2.

Separately, two comments in `brainstorm_app.py` name the Running-tab group
retry-apply key as `S`, but `on_key` binds `i` (around line 2775,
`_retry_group_apply`).

Goal: each apply script prints full help on `--help`/`-h` (exit 0), rejects
unknown options and wrong argument counts with a usage hint, and the stale
comments name `i`.

Callers: only the `ait` dispatcher (`exec … "$@"`, lines 306-308) and
`tests/test_brainstorm_apply_created_by_group.sh`, which passes two positional
arguments. The TUI calls the Python `apply_*_output` functions directly, not
these scripts.

## Implementation

### 1. `.aitask-scripts/aitask_brainstorm_apply_initializer.sh`
Follow `aitask_brainstorm_delete.sh` (`show_help` heredoc + `while/case` loop):

- Add `show_help()`: Usage `ait brainstorm apply-initializer <task_num>`;
  a description (re-parses `initializer_bootstrap_output.md` and rewrites
  `n000_init` and its proposal; **overwrites an edited first node with no
  confirmation**, the same as the TUI's Ctrl+R); Arguments (`<task_num>`, also
  accepted as `brainstorm-<task_num>`); Output (`APPLIED:n000_init` on stdout,
  `APPLY_FAILED:<error>` on stderr with exit 1, plus the
  `initializer_bootstrap_apply_error.log` note); Example.
- Parse arguments **before** `require_ait_python` / the pyyaml check, so help
  works even when the Python setup is broken:
  - `--help|-h` → `show_help; exit 0`
  - `-*` → stderr `Unknown option: $1. Run 'ait brainstorm apply-initializer --help' for usage.`, exit 2
  - first positional → `SESSION`; another positional → stderr `Unexpected argument: $1` + the hint, exit 2
  - no positional → stderr one-line usage + the hint, exit 2 (same exit code as today)
- Keep `NUM="${SESSION#brainstorm-}"` and the Python heredoc unchanged.

A local `usage_error()` helper (prints a message plus the `--help` hint to
stderr, exits 2) keeps exit 2 for usage errors. `die` from
`terminal_compat.sh` exits 1, and exit 1 already means `APPLY_FAILED` here.

### 2. `aitask_brainstorm_apply_explorer.sh` and `aitask_brainstorm_apply_synthesizer.sh`
Same structure, with two positionals `<task_num> <agent_name>`:
- `show_help()` covers what each one creates (explorer: a node parented as its
  NODE_YAML says; synthesizer: a merged node parented on every source node),
  arguments, `APPLIED:<new_node_id>` / `APPLY_FAILED:<error>` plus the
  `<agent_name>_apply_error.log` note, and an example
  (`ait brainstorm apply-explorer 42 explorer_001`).
- Same parse loop, with up to two positionals: a third is `Unexpected
  argument`, and fewer than two is a usage error (exit 2).
- The Python heredoc is unchanged.

### 3. `.aitask-scripts/brainstorm/brainstorm_app.py`
Change the two stale comments from `S` to `i`:
- line ~2351: "group-scoped `S` action on the Running-tab GroupRow" → `i`
- lines ~2363-2365: "Running-tab GroupRow `S` action" → `i`

Comments only, no behaviour change.

### 4. Test: new `tests/test_brainstorm_apply_help.sh`
Self-contained and top-level (no `( … )` subshells, so no file-backed
counters). It starts from `scratch_cwd.sh` / `enter_scratch_cwd`, sources
`tests/lib/asserts.sh`, and calls scripts by absolute path from `PROJECT_DIR`.
None of these cases reach Python.
For each of the three scripts:
- `--help` and `-h` exit 0; stdout contains `Usage: ait brainstorm apply-<x>`,
  `APPLIED:` and `APPLY_FAILED:`; the output has no `APPLY_FAILED:No initializer`
  (the regression)
- `--help` after a positional (`42 --help`) still prints help, exit 0
- `--bogus` exits 2, and stderr contains `Unknown option` and `--help`
- no arguments exits 2 with `Usage:`
- too many positionals exits 2 with `Unexpected argument`

**Python-free help.** The cases above run with a working interpreter, so they
still pass if the parse loop ends up after `require_ait_python` / the pyyaml
check, and they would not catch that ordering bug. Add a dedicated block:
- In a `mktemp -d` scratch dir (removed by the EXIT trap), write an executable
  stub `python_stub` that appends `called $*` to `$STUB_LOG` and exits 1.
- Run each wrapper with `env -u _AIT_RESOLVED_PYTHON AIT_PYTHON="$stub"
  STUB_LOG="$log"`. `resolve_python` picks `$AIT_PYTHON` first whenever it is
  executable, so the stub is the resolved interpreter, and its failing version
  probe makes `require_ait_python` die.
  - `--help` and `-h` on all three wrappers: exit 0, `Usage:` on stdout, and
    the stub log **stays empty** (the interpreter was never invoked).
- **Positive control** (it stops the block from passing trivially, e.g. if
  resolution never reached the stub): with the same env, run
  `apply-initializer 42` once. It must exit non-zero and the stub log must be
  **non-empty**, which proves the stub really is the interpreter these wrappers
  resolve.

Also check through the dispatcher, in the normal environment:
`"$PROJECT_DIR/ait" brainstorm apply-initializer --help` exits 0 with
`Usage:`. Footer: PASS/FAIL/TOTAL summary, non-zero exit on failure.

### 5. Docs: `website/content/docs/tuis/brainstorm/reference.md` ("Command-line subcommands")
Extend the lead sentence: each subcommand takes the session's task number and
prints its usage with `--help`. Before writing that, check `ait brainstorm
list --help` and `status`, `init`, `archive`. If any of them does not print
help, name only the ones that do. Keep the current-state wording. Then run
`python3 check_links.py --build` in `website/`.

### Not done (judgement call from the task)
No placeholder guard or confirmation on `apply-initializer`. Overwriting is the
intended force-apply recovery path, and the same choice as Ctrl+R's
`force=True`. The help text and the docs both state the overwrite plainly.

## Verification
- `bash tests/test_brainstorm_apply_help.sh` → all PASS
- `bash tests/test_brainstorm_apply_created_by_group.sh` → still passes (positional path unchanged)
- `bash tests/test_brainstorm_cli.sh` → unaffected, sanity
- `shellcheck` on the three scripts and the new test
- Manual: `./ait brainstorm apply-initializer --help; echo $?` → help, 0
- `cd website && python3 check_links.py --build`

## Step 9 (Post-Implementation)
Current-branch mode: commit code (`bug: … (t2305)`) and plan separately, then
archive via the standard Step 9 flow.

## Risk

### Code-health risk: low
None identified. Three small, self-contained wrapper scripts change their
argument parsing only. Their only programmatic caller (one test) passes valid
positionals, and the Python apply bodies are untouched.

### Goal-achievement risk: low
- Help-before-Python ordering could regress unseen, because normal-environment
  tests pass either way · severity: low (residual: addressed in-plan by the
  step 4 stub-interpreter block with its positive control; raised in plan
  review) · → mitigation: in-plan test (step 4, "Python-free help")

Otherwise none identified. The fix addresses every item in the task: initializer
`--help`, explorer/synthesizer `--help`, the `S` → `i` comment, and the optional
doc note.

## Implementation notes

All five steps are done as planned. Deviations and findings:

- **Explorer example name**: the help uses `explorer_001a`. Real explorer
  agent names carry a per-agent suffix (`brainstorm_crew.py`:
  `f"explorer_{seq}{agent_suffix}"`); synthesizer names do not
  (`synthesizer_001`).
- **Test portability**: the test uses plain functions instead of
  `declare -A`, because `tests/lib/asserts.sh` is kept bash-3.2-safe (macOS).
- **Red proof (Python-free block)**: an isolated mutant copy of the initializer
  wrapper had its parse loop moved after `require_ait_python`, in the
  scratchpad with a symlinked `lib/`. Under the stub env, `--help` exited 1 and
  the stub log showed `called -c import sys; …` and `called --version`. In the
  normal env the same mutant exited 0. So the stub assertions catch the
  ordering bug and the normal-environment assertions alone do not.
- **Docs**: before the edit, `./ait brainstorm <sub> --help` exited 0 with a
  `Usage:` line for every subcommand (`init`, `status`, `list`, `archive`,
  `delete`, all three `apply-*`). `list --help` prints `status`'s usage,
  because `list` routes through `status --list`. That is a pre-existing quirk
  outside this task.
- **Pre-existing, unrelated**: `tests/test_cd_guard_lint.sh` fails 1/92 on
  `tests/test_issue_update_ledger.sh:231` (`unconfined-andchain`), a file last
  touched by t2277's commit cddb129c5, not by this change.

Verification run:
- `tests/test_brainstorm_apply_help.sh`: 79/79 PASS, and it leaves no TMPDIR
  leftovers under `run_shell_test.sh`
- `tests/test_brainstorm_apply_created_by_group.sh`: 1/1 PASS
- `tests/test_brainstorm_cli.sh`: 38/38 PASS
- `shellcheck -S warning` on the three wrappers and the new test: clean
- `brainstorm_app.py` parses (`ast.parse`)
- `website/check_links.py --build`: SWEEP PASSED

## Post-Review Changes

### Change Request 1 (2026-11-15 19:40)
- **Requested by user:** (1) [medium, blocking] the parsers used empty
  values as their positional-slot state, so `apply-initializer "" 42` and
  `apply-explorer 42 "" agent_x` were accepted and reached Python (exit 1)
  instead of being rejected as surplus arguments (exit 2). Before t2305, the
  initializer rejected `"" 42`. (2) [low, blocking] the help text sent
  users to an apply-error log unconditionally, but the initializer writes it
  only for a NODE_YAML parse error, and explorer/synthesizer write none when
  the output file is missing.
- **Verified before changing:** (1) reproduced under the failing
  `AIT_PYTHON` stub with the then-current parser: `init "" 42` → rc=1 and
  `explorer 42 "" agent_x` → rc=1; the pre-t2305 initializer gave rc=2.
  (2) `brainstorm_session.py`: `apply_initializer_output` writes the log
  only in its `yaml.YAMLError` handler; the shared explorer/synthesizer path
  raises `FileNotFoundError` before its logging `try` and logs the rest
  best-effort.
- **Changes made:**
  - All three wrappers collect positionals into a `POSITIONAL=()` array.
    They check the count (missing → usage, surplus → `Unexpected argument:`)
    and then reject empty values (`Empty <task_num> argument` /
    `Empty <agent_name> argument`), all with exit 2 and before Python.
  - The initializer also rejects a bare `brainstorm-` (it strips to an
    empty number).
  - The help Output sections and the script header comments now say which
    failures write a log. `reference.md` / `how-to.md` already hedged
    ("Some failures also leave a log"), so they are unchanged.
  - Test: new "empty / surplus positionals rejected before Python" block
    (17 cases × 3 assertions: exit 2, message, stub never invoked), plus a
    help assertion for the log caveat. 136/136 PASS.
- **Files affected:** the three `aitask_brainstorm_apply_*.sh` wrappers,
  `tests/test_brainstorm_apply_help.sh`.

## Final Implementation Notes
- **Actual work done:**
  - The three `ait brainstorm apply-*` wrappers each gained a `show_help`
    (usage, description, arguments, output lines, a qualified note on when an
    apply-error log is written, and an example) and a `--help|-h` branch that
    exits 0.
  - Unknown options, missing, surplus and empty positionals all exit 2 with a
    `--help` hint. Arguments are parsed before `require_ait_python` and the
    pyyaml check, so help works with a broken interpreter.
  - The two stale `S` → `i` comments in `brainstorm_app.py` are fixed.
  - One sentence in `website/.../brainstorm/reference.md` notes that `--help`
    works on every subcommand.
  - New `tests/test_brainstorm_apply_help.sh` (136 assertions), including a
    failing-`AIT_PYTHON`-stub block with a positive control.
- **Deviations from plan:**
  - The parse loop first used empty-string slots. That accepted `"" 42` as
    the task number 42, so it was replaced by a counted `POSITIONAL=()` array
    that also rejects empty values and a bare `brainstorm-` (Change Request 1).
  - The help's error-log line is qualified per failure type (Change Request 1).
  - The explorer example agent name is `explorer_001a`, the real naming form.
- **Issues encountered:**
  - The plan review flagged that normal-environment tests cannot prove
    "help before Python". The stub block was added, then red-proofed with a
    reordered mutant: under the stub its `--help` gives rc=1 and the stub is
    invoked, while in the normal env it gives rc=0.
  - The test avoids `declare -A` to stay bash-3.2-safe, like `asserts.sh`.
- **Key decisions:**
  - Usage errors keep exit 2 (the pre-existing contract), because exit 1
    means `APPLY_FAILED`.
  - No overwrite guard was added to `apply-initializer`: the force-apply is
    the intended recovery path, the same as Ctrl+R's `force=True`. The help
    states the overwrite plainly.
- **Upstream defects identified:**
  - `tests/test_issue_update_ledger.sh:231` — `unconfined-andchain` cd-guard
    violation (`( cd "$REPO" && … )`) makes `tests/test_cd_guard_lint.sh`
    fail 1/92 on the live tree.
  - `ait:310` — `ait brainstorm list --help` routes to
    `aitask_brainstorm_status.sh --list --help` and prints `status`'s usage
    (`Usage: ait brainstorm status <task_num>`) instead of `list`'s.
