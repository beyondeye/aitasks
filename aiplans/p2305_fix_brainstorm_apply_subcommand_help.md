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
