---
Task: t573_2_cli_proposal_file_flag.md
Parent Task: aitasks/t573_import_initial_proposal_in_brainstrom.md
Sibling Tasks: aitasks/t573/t573_1_*.md, aitasks/t573/t573_3_*.md, aitasks/t573/t573_4_*.md
Archived Sibling Plans: aiplans/archived/p573/p573_*_*.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7 @ 2026-04-23 12:05
---

# t573_2 — CLI: `ait brainstorm init --proposal-file` (verified)

## Context

Parent task t573 adds support for importing an external markdown proposal at
brainstorm-init time. Child t573_1 (already completed, archived to
`aiplans/archived/p573/p573_1_*.md`) landed the `initializer` agent type,
`register_initializer(...)`, `init_session(..., initial_proposal_file=...)`,
and `apply_initializer_output(...)`.

This child wires the **CLI entry point** so the import feature is usable from
the shell, which in turn unblocks t573_3 (TUI modal) because t573_3 will shell
into this CLI.

## Verification against current codebase (2026-04-23)

All referenced code targets in the existing plan are still accurate **with one
correction** (runner-auto-start wiring):

| Plan reference | Current state | Match? |
|---|---|---|
| `brainstorm_cli.py:35-47` (`cmd_init`) | same | ✓ |
| `brainstorm_cli.py:146-151` (subparser) | same | ✓ |
| `aitask_brainstorm_init.sh:50-69` (argparse) | same | ✓ |
| `aitask_brainstorm_init.sh:128-134` (`--add-type` list, 5 types) | same | ✓ |
| `aitask_brainstorm_init.sh:150-156` (python invocation) | same | ✓ |
| `register_initializer(...)` in `brainstorm_crew.py:680` | present | ✓ |
| `init_session(..., initial_proposal_file=None)` in `brainstorm_session.py:40-45` | present | ✓ |
| Runner auto-start via `aitask_crew_run.sh --id ... --detach` | **does not exist** | ✗ |

**Runner-auto-start correction:** The canonical runner helper is
`.aitask-scripts/aitask_crew_runner.sh` (note: `runner`, not `run`); its
argparse takes `--crew <id>` and has **no `--detach` flag** (the runner is a
long-running orchestrator). The existing, battle-tested way to start it
detached is `start_runner(crew_id)` in
`.aitask-scripts/agentcrew/agentcrew_runner_control.py:67` — it wraps
`subprocess.Popen([ait, "crew", "runner", "--crew", crew_id],
start_new_session=True)`. This is exactly what the brainstorm TUI uses
(`brainstorm_app.py:2853`). We will call the same helper from
`brainstorm_cli.py cmd_init` rather than shelling out from bash.

## Implementation steps

### 1. `brainstorm_cli.py` — argparser (`p_init`, ~line 150)

Add one argument to the existing `p_init` block:

```python
p_init.add_argument(
    "--proposal-file",
    default="",
    help="Optional markdown file to use as initial proposal (analyzed by initializer agent)",
)
```

### 2. `brainstorm_cli.py` — `cmd_init` (~line 35-47)

Extend `cmd_init` to plumb the flag, register the initializer agent, and
auto-start the runner when a proposal file is provided:

```python
def cmd_init(args: argparse.Namespace) -> None:
    spec = ""
    if args.spec_file:
        spec = Path(args.spec_file).read_text(encoding="utf-8")

    proposal_file = args.proposal_file or None

    wt = init_session(
        task_num=args.task_num,
        task_file=args.task_file,
        user_email=args.email or "",
        initial_spec=spec,
        initial_proposal_file=proposal_file,
    )
    print(f"SESSION_PATH:{wt}")

    if proposal_file:
        from brainstorm.brainstorm_crew import register_initializer
        from agentcrew.agentcrew_runner_control import start_runner

        crew_id = f"brainstorm-{args.task_num}"
        agent_name = register_initializer(
            session_dir=wt,
            crew_id=crew_id,
            imported_path=str(Path(proposal_file).resolve()),
            task_file=args.task_file,
            group_name="bootstrap",
            launch_mode="interactive",
        )
        print(f"INITIALIZER_AGENT:{agent_name}")

        if start_runner(crew_id):
            print(f"RUNNER_STARTED:{crew_id}")
        else:
            print(f"RUNNER_START_FAILED:{crew_id}", file=sys.stderr)
```

Preserve the existing happy path byte-for-byte when `proposal_file` is `None`
(no new stdout lines, no agent registered, no runner start).

### 3. `aitask_brainstorm_init.sh` — flag parsing (after line 50 block)

Initialize `PROPOSAL_FILE=""` alongside `TASK_NUM=""`. Inside the `while`
loop, add the option branches before the `-*` unknown-option branch:

```bash
        --proposal-file)
            [[ $# -ge 2 ]] || die "--proposal-file requires an argument."
            PROPOSAL_FILE="$2"; shift 2 ;;
        --proposal-file=*)
            PROPOSAL_FILE="${1#*=}"; shift ;;
```

After the existing `[[ -z "$TASK_NUM" ]] && die ...` check, validate when
non-empty:

```bash
if [[ -n "$PROPOSAL_FILE" ]]; then
    [[ -f "$PROPOSAL_FILE" ]] || die "Proposal file not found: $PROPOSAL_FILE"
    [[ -r "$PROPOSAL_FILE" ]] || die "Proposal file not readable: $PROPOSAL_FILE"
    [[ -s "$PROPOSAL_FILE" ]] || die "Proposal file is empty: $PROPOSAL_FILE"
    case "$PROPOSAL_FILE" in
        *.md|*.markdown) ;;
        *) warn "Proposal file has no .md/.markdown extension; continuing." ;;
    esac
    # Resolve to absolute path (python3 fallback for macOS portability).
    PROPOSAL_FILE="$("$PYTHON" -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$PROPOSAL_FILE")"
fi
```

### 4. `aitask_brainstorm_init.sh` — crew init with six types (line 129-133)

Append a sixth `--add-type` line for the initializer, after the `patcher`
line, so the new agent type is known to the crew:

```bash
    --add-type "patcher:$(_get_brainstorm_agent_string patcher):$(_get_brainstorm_launch_mode patcher)" \
    --add-type "initializer:$(_get_brainstorm_agent_string initializer):$(_get_brainstorm_launch_mode initializer)" \
```

(Without this, `_run_addwork` inside `register_initializer` would fail because
the crew doesn't know the `initializer` type.)

### 5. `aitask_brainstorm_init.sh` — pass flag to python CLI (line 150-156)

Restructure the python invocation to include the optional flag:

```bash
init_args=(
    --task-num "$TASK_NUM"
    --task-file "$TASK_FILE"
    --email "$USER_EMAIL"
    --spec-file "$SPEC_FILE"
)
if [[ -n "$PROPOSAL_FILE" ]]; then
    init_args+=(--proposal-file "$PROPOSAL_FILE")
fi

init_output=$("$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" init "${init_args[@]}") || {
    die "Failed to initialize brainstorm session: $init_output"
}
echo "$init_output"
```

Echo `init_output` so the user sees `SESSION_PATH:` and (when relevant)
`INITIALIZER_AGENT:` / `RUNNER_STARTED:` on stdout.

### 6. `aitask_brainstorm_init.sh` — hint line when runner started

After the `echo "$init_output"`, detect `INITIALIZER_AGENT:` / `RUNNER_STARTED:`
and print a one-line hint:

```bash
if [[ -n "$PROPOSAL_FILE" ]] && grep -q '^INITIALIZER_AGENT:' <<<"$init_output"; then
    crew_id="brainstorm-${TASK_NUM}"
    if grep -q '^RUNNER_STARTED:' <<<"$init_output"; then
        info "Initializer agent started in interactive mode."
        info "Attach with: ait crew runner --crew $crew_id --check  (or open 'ait brainstorm $TASK_NUM' TUI)"
    else
        warn "Initializer agent registered but runner did not auto-start. Run manually: ait crew runner --crew $crew_id"
    fi
fi
```

### 7. `--help` text update

Extend the `show_help()` HEREDOC block near line 33-47 to document the new
flag. One-line addition to the Arguments section.

## Update help signature

The updated usage string for `show_help()`:
```
Usage: ait brainstorm init <task_num> [--proposal-file <path>]
```

Arguments addition:
```
  --proposal-file <path>   Optional markdown file to use as the initial proposal.
                           Triggers the initializer agent to reformat the file into
                           the brainstorm node format (n000_init).
```

## Automated tests

### 8a. Python unit tests — extend `tests/test_brainstorm_cli_python.py`

Add a new `TestInitWithProposalFile(CLITestBase)` class. The existing harness
already patches `AGENTCREW_DIR` to a scratch dir and creates the crew worktree,
so `init_session` succeeds. We patch `register_initializer` and `start_runner`
to avoid touching the real crew machinery:

```python
class TestInitWithProposalFile(CLITestBase):
    """Tests for --proposal-file flag on `brainstorm_cli init`."""

    def _make_proposal(self, body: str = "# Example proposal\n\nBody line.\n") -> Path:
        """Auto-generate a test proposal markdown file in the scratch tmpdir."""
        p = Path(self.tmpdir) / "imported_proposal.md"
        p.write_text(body, encoding="utf-8")
        return p

    def test_happy_path_emits_markers_and_records_path(self):
        proposal = self._make_proposal()

        with patch("brainstorm.brainstorm_crew.register_initializer",
                   return_value="initializer_bootstrap") as mock_reg, \
             patch("agentcrew.agentcrew_runner_control.start_runner",
                   return_value=True) as mock_start:
            out, _ = self._capture_cli([
                "init",
                "--task-num", str(self.task_num),
                "--task-file", f"aitasks/t{self.task_num}_test.md",
                "--email", "test@example.com",
                "--proposal-file", str(proposal),
            ])

        # Stdout markers — exact strings the TUI / sibling tasks parse.
        self.assertIn("SESSION_PATH:", out)
        self.assertIn("INITIALIZER_AGENT:initializer_bootstrap", out)
        self.assertIn(f"RUNNER_STARTED:brainstorm-{self.task_num}", out)

        # Session metadata records the absolute resolved proposal path.
        session = read_yaml(str(self.wt_path / SESSION_FILE))
        self.assertEqual(session["initial_proposal_file"], str(proposal.resolve()))

        # n000_init.md is a placeholder pending the initializer agent.
        placeholder = (self.wt_path / PROPOSALS_DIR / "n000_init.md").read_text()
        self.assertIn(proposal.name, placeholder)
        self.assertIn("Awaiting initializer agent output", placeholder)

        # Register + runner called exactly once with the resolved path.
        mock_reg.assert_called_once()
        reg_kwargs = mock_reg.call_args.kwargs
        self.assertEqual(reg_kwargs["imported_path"], str(proposal.resolve()))
        self.assertEqual(reg_kwargs["crew_id"], f"brainstorm-{self.task_num}")
        mock_start.assert_called_once_with(f"brainstorm-{self.task_num}")

    def test_runner_start_failure_emits_stderr_warning(self):
        proposal = self._make_proposal()
        with patch("brainstorm.brainstorm_crew.register_initializer",
                   return_value="initializer_bootstrap"), \
             patch("agentcrew.agentcrew_runner_control.start_runner",
                   return_value=False):
            out, err = self._capture_cli([
                "init",
                "--task-num", str(self.task_num),
                "--task-file", f"aitasks/t{self.task_num}_test.md",
                "--proposal-file", str(proposal),
            ])
        self.assertIn("INITIALIZER_AGENT:initializer_bootstrap", out)
        self.assertNotIn("RUNNER_STARTED:", out)
        self.assertIn(f"RUNNER_START_FAILED:brainstorm-{self.task_num}", err)

    def test_missing_proposal_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self._capture_cli([
                "init",
                "--task-num", str(self.task_num),
                "--task-file", f"aitasks/t{self.task_num}_test.md",
                "--proposal-file", "/does/not/exist.md",
            ])

    def test_backward_compat_no_flag(self):
        """Without --proposal-file, no new markers and no agent registration."""
        with patch("brainstorm.brainstorm_crew.register_initializer") as mock_reg, \
             patch("agentcrew.agentcrew_runner_control.start_runner") as mock_start:
            out, _ = self._capture_cli([
                "init",
                "--task-num", str(self.task_num),
                "--task-file", f"aitasks/t{self.task_num}_test.md",
            ])

        self.assertIn("SESSION_PATH:", out)
        self.assertNotIn("INITIALIZER_AGENT:", out)
        self.assertNotIn("RUNNER_STARTED:", out)

        session = read_yaml(str(self.wt_path / SESSION_FILE))
        self.assertNotIn("initial_proposal_file", session)

        mock_reg.assert_not_called()
        mock_start.assert_not_called()
```

Note: the proposal markdown is **auto-generated at test time** by
`_make_proposal()` (no fixture file in the repo). The body is deliberately
minimal — the initializer agent's reformat logic is exercised by
`test_apply_initializer_output.sh`, not here. This test is scoped to CLI
wiring.

### 8b. Bash input-validation tests — new `tests/test_brainstorm_init_proposal_file.sh`

Follows the inline-helpers style of `tests/test_apply_initializer_output.sh`.
Tests only the bash-level validation branches — these `die` **before**
reaching `aitask_crew_init.sh`, so no crew is created and no cleanup of
real project state is needed.

```bash
#!/usr/bin/env bash
set -euo pipefail
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$THIS_DIR/.." && pwd)"
cd "$REPO_ROOT"

PASS=0; FAIL=0
assert_dies_with() {
    local desc="$1" needle="$2"; shift 2
    local out exitcode=0
    out=$("$@" 2>&1) || exitcode=$?
    if [[ $exitcode -eq 0 ]]; then
        echo "FAIL: $desc — expected non-zero exit"; FAIL=$((FAIL+1)); return
    fi
    if [[ "$out" != *"$needle"* ]]; then
        echo "FAIL: $desc — expected '$needle' in output, got: $out"; FAIL=$((FAIL+1)); return
    fi
    PASS=$((PASS+1))
}

# We target task number 0 which does not exist; all validation branches
# die before the task-resolve step anyway, but we still pass a clearly
# non-existent id so a future code path that moves the proposal-file
# validation after task resolution keeps failing loudly.

# 1. Missing file
assert_dies_with "missing proposal file" "Proposal file not found" \
    ./.aitask-scripts/aitask_brainstorm_init.sh 999999 --proposal-file /nonexistent/path.md

# 2. Empty file
EMPTY="$(mktemp "${TMPDIR:-/tmp}/br_empty_XXXXXX.md")"
trap 'rm -f "$EMPTY"' EXIT
assert_dies_with "empty proposal file" "Proposal file is empty" \
    ./.aitask-scripts/aitask_brainstorm_init.sh 999999 --proposal-file "$EMPTY"

# 3. Missing value after --proposal-file
assert_dies_with "missing argument" "requires an argument" \
    ./.aitask-scripts/aitask_brainstorm_init.sh 999999 --proposal-file

echo "---"
echo "PASSED: $PASS"
echo "FAILED: $FAIL"
[[ $FAIL -eq 0 ]]
```

Verification:
- `bash tests/test_brainstorm_init_proposal_file.sh` prints `PASSED: 3 / FAILED: 0`.
- `shellcheck tests/test_brainstorm_init_proposal_file.sh` clean.
- `python3 -m unittest tests.test_brainstorm_cli_python -v` — the new
  `TestInitWithProposalFile` class shows 4 tests, all pass, and existing
  tests stay green.

## Verification

1. **Invalid input:**
   - `ait brainstorm init 99999 --proposal-file /does/not/exist` → dies with
     "Proposal file not found", exit 1, no crew directory created.
   - `ait brainstorm init 99999 --proposal-file /etc/hosts` → warns about
     missing extension, then probably dies at crew init (reasonable).

2. **Happy path** (with a scratch `.md` file and a fresh task):
   - `ait brainstorm init <fresh_task_num> --proposal-file /tmp/ex.md`
   - stdout contains `SESSION_PATH:...`, `INITIALIZER_AGENT:initializer_bootstrap`,
     and `RUNNER_STARTED:brainstorm-<N>`.
   - `br_session.yaml` has `initial_proposal_file: <abs path>`.
   - `br_proposals/n000_init.md` contains the placeholder
     ("Awaiting initializer agent output for `ex.md`.\n").
   - The crew registers 6 agent types (verify via
     `cat .aitask-scripts/crew-worktrees/brainstorm-<N>/agent-types.yaml` or
     equivalent).
   - The runner process is visible in `ps` (or at least `_runner_alive.yaml`
     appears in the crew worktree within a few seconds).
   - The hint line is printed.

3. **Backward-compat:** `ait brainstorm init <fresh_task_num>` (no flag) →
   unchanged stdout (only `SESSION_PATH:` plus the existing `INITIALIZED:`
   trailer), no initializer agent registered, no runner auto-start, crew has
   5 agent types (not 6).

4. **shellcheck:** `shellcheck .aitask-scripts/aitask_brainstorm_init.sh` clean.

5. **Python smoke:** `python3 -c "import sys;
   sys.path.insert(0, '.aitask-scripts');
   from brainstorm.brainstorm_cli import cmd_init; print('ok')"` — confirms
   no import-time errors (new `from agentcrew.agentcrew_runner_control import
   start_runner` inside the function body is lazy-imported so no top-level
   change).

## Notes for sibling tasks (t573_3 / t573_4 / t573_5)

- `INITIALIZER_AGENT:initializer_bootstrap` and `RUNNER_STARTED:brainstorm-<N>`
  are the canonical stdout markers. t573_3 (TUI) must parse these exactly to
  know when it can start polling `initializer_bootstrap_status.yaml`.
- Runner auto-start uses `start_runner()` from
  `agentcrew.agentcrew_runner_control`, not a bash shell-out — t573_3 should
  either call `start_runner()` directly (it is already a Python module) or
  shell to the updated CLI. Either path starts the runner identically.
- The bash `info`/`warn` hint text is user-facing; tweak wording if t573_4
  (docs) surfaces a different canonical incantation.

## Step 9 (Post-Implementation)

After user approval in Step 8, follow the shared workflow's Step 9:
`./.aitask-scripts/aitask_archive.sh 573_2`. Plan file will be archived to
`aiplans/archived/p573/` and serve as reference material for t573_3 / t573_4.

## Final Implementation Notes

- **Actual work done:** All 8 planned items landed as designed:
  1. `brainstorm_cli.py` — `cmd_init` now accepts `--proposal-file`, lazily
     imports `register_initializer` and `start_runner`, emits the three
     stdout markers (`SESSION_PATH:`, `INITIALIZER_AGENT:...`,
     `RUNNER_STARTED:...`) on the happy path and `RUNNER_START_FAILED:` on
     stderr when the runner auto-start fails.
  2. `brainstorm_cli.py` argparse — `--proposal-file` added to the `p_init`
     subparser with default `""`.
  3. `aitask_brainstorm_init.sh` — `--proposal-file <path>` and
     `--proposal-file=<path>` parsing branches; `PROPOSAL_FILE` init'd to `""`.
  4. Validation block after `TASK_NUM` check: file-not-found / not-readable /
     empty / extension-warn, then realpath via python3 for macOS portability.
  5. 6th `--add-type` line for `initializer` in the crew-init invocation.
  6. Python CLI invocation restructured to use a `init_args=(…)` array so
     `--proposal-file` is only appended when set. `init_output` is echoed so
     users see the new marker lines.
  7. Hint-line block after the echo: parses stdout for
     `INITIALIZER_AGENT:` / `RUNNER_STARTED:` and prints `info`/`warn` guidance.
  8. `show_help()` updated with the new flag, the new output markers, and a
     second `Example:` line.

- **Tests added:**
  - `tests/test_brainstorm_cli_python.py` — new `TestInitWithProposalFile`
    class with 4 tests (happy path, runner-start failure, missing file,
    backward compat). Uses `_make_proposal()` to auto-generate the test
    proposal markdown in the scratch tmpdir — no fixture in the repo. The
    tests patch `register_initializer` and `start_runner` so they don't spawn
    real crew processes.
  - `tests/test_brainstorm_init_proposal_file.sh` (new) — 3 bash-level
    validation tests (missing file / empty file / missing argument). All
    exercise `die` branches that execute before `aitask_crew_init.sh`, so no
    project state is mutated.

- **Deviations from plan:** None. The one plan-correction (the plan file
  already identified during verification) — using `start_runner()` from
  `agentcrew.agentcrew_runner_control` instead of a non-existent
  `aitask_crew_run.sh --detach` — was implemented as designed.

- **Issues encountered:** The pre-existing `tests/test_brainstorm_cli.sh`
  fails on Test 1 ("brainstorm init basic") because its scratch-repo setup
  does not copy `lib/archive_utils.sh`. Verified via `git stash` that this
  failure exists on `main` without my changes — not caused by this task. Not
  in scope to fix here; noting for a follow-up.

- **Key decisions:**
  - **Lazy import of `start_runner` and `register_initializer` inside
    `cmd_init`** (not at module top-level): keeps the `init` command
    import-light for callers that never set `--proposal-file`, and avoids
    making `agentcrew_runner_control` a hard dependency of the `brainstorm`
    package for other subcommands (status / list / finalize / archive / etc.).
  - **`info`/`warn` used in the hint block** instead of `echo`: matches the
    existing `terminal_compat.sh` helpers used throughout the script.
  - **Error marker on stderr (`RUNNER_START_FAILED:`)**: stdout stays a clean
    marker-stream for the TUI to parse while errors surface on stderr, which
    is where `subprocess.run(...).stderr` will capture them in t573_3.

- **Notes for sibling tasks (t573_3 / t573_4 / t573_5):**
  - **Canonical stdout markers (DO NOT rename):**
    - `SESSION_PATH:<abs path>` — always emitted by `cmd_init`.
    - `INITIALIZER_AGENT:initializer_bootstrap` — emitted only when
      `--proposal-file` is provided.
    - `RUNNER_STARTED:brainstorm-<N>` — emitted only on successful runner
      auto-start. If absent, the bash wrapper falls back to a `warn` line
      telling the user to run `ait crew runner --crew <id>` manually.
  - **Canonical stderr marker:** `RUNNER_START_FAILED:brainstorm-<N>` when
    `start_runner()` returns False.
  - **Runner start path:** `agentcrew.agentcrew_runner_control.start_runner`
    — same entry point the TUI's `btn_runner_start` button uses
    (`brainstorm_app.py:2853`). t573_3 should prefer calling this helper
    directly from Python rather than shelling into `ait brainstorm init`,
    since the TUI already has the crew-worktree and can skip re-running
    `crew init`.
  - **Runner helper script name:** the canonical runner CLI is
    `./.aitask-scripts/aitask_crew_runner.sh --crew <id>` (note: `runner`,
    not `run`, and `--crew`, not `--id`). There is no `--detach` flag;
    detachment is handled by `subprocess.Popen(start_new_session=True)` in
    `agentcrew_runner_control.start_runner`.
  - **6-agent-type crew:** after this child, all brainstorm crews have 6
    agent types (explorer, comparator, synthesizer, detailer, patcher,
    initializer). Existing crews that were initialized before t573_2 only
    have 5 — t573_4 (docs) should mention this backward-compat implication.
  - **Placeholder n000_init body:** when `--proposal-file` is set,
    `init_session` seeds `n000_init.md` with `"Awaiting initializer agent
    output for `<basename>`.\n"`. The initializer agent overwrites this when
    it completes (via `apply_initializer_output` from t573_1). t573_3's TUI
    should show a "pending" state while this placeholder is present.

- **Verification results:**
  - `bash tests/test_brainstorm_init_proposal_file.sh` — 3/3 PASS
  - `shellcheck -x` on both the modified `aitask_brainstorm_init.sh` and the
    new `test_brainstorm_init_proposal_file.sh` — clean
  - `python3 -m unittest tests.test_brainstorm_cli_python -v` — 14/14 PASS
    (4 new, 10 existing)
  - `python3 -m unittest discover -s tests -p 'test_brainstorm*.py'` —
    108/108 PASS (full brainstorm suite)
  - `bash tests/test_apply_initializer_output.sh` — 8/8 PASS (sibling test)
  - `ait brainstorm init --help` — new flag documented, new output markers
    listed, second example shown.
