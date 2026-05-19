---
Task: t801_aitask_explore_with_codex.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Fix codex/gpt5_5 explore spawn failure from TUI switcher (t801)

## Context

The TUI switcher's `x` shortcut spawns `ait codeagent invoke explore` in a new
tmux window. With `aitasks/metadata/codeagent_config.json` configured to
`"explore": "codex/gpt5_5"`, the resolved command is:

```
python3 .aitask-scripts/aitask_codex_plan_invoke.py --prompt $aitask-explore -- codex -m gpt-5.5
```

`aitask_codex_plan_invoke.py` imports `pexpect` to drive Codex's interactive
TTY (codex CLI does not accept slash commands as argv; it must be typed into
the composer). When `pexpect` is missing, the script exits 127 after
printing:

```
Error: Python package 'pexpect' is required for Codex plan-mode skill
launches. Run 'ait setup' to install project Python dependencies, or
install pexpect for the Python used here.
```

The tmux window briefly shows the error and exits — visible to the user as
"fails to spawn".

**Root cause:** `aitask_setup.sh` installs `textual`, `pyyaml`,
`linkify-it-py`, `tomli`, `minijinja` into both venvs but never installs
`pexpect`. The script's own error message points at `ait setup`, but setup
was never updated when the Codex plan-mode launcher landed (commit
`6a539aca`, t714).

Reproduced locally:

```
$ ./ait codeagent invoke explore
Error: Python package 'pexpect' is required ...
$ ~/.aitask/venv/bin/python -c "import pexpect"
ModuleNotFoundError: No module named 'pexpect'
$ ~/.aitask/venv/bin/pip install pexpect   # manual fix → import works
```

The only consumer of `pexpect` in the framework is
`aitask_codex_plan_invoke.py` (referenced from `aitask_skillrun.sh:238` and
`aitask_codeagent.sh:492-507`).

## Approach

Add `pexpect` to both pip-install lines in `aitask_setup.sh` — alongside
the other unconditional deps. This matches how `pyyaml`, `tomli`, etc. are
installed: unconditional, both venvs, single source of truth. No
conditional / opt-in installation, because the deps already cover features
(e.g. textual TUIs) that not every user touches, and `pexpect` is ~80 KB.

No code change is needed in `aitask_codex_plan_invoke.py` or the TUI
switcher itself — they are correct; they just rely on a dep that setup
forgot to install.

## Files to modify

- `.aitask-scripts/aitask_setup.sh` (2 lines):
  - **Line 574** (PyPy venv install):
    ```bash
    "$PYPY_VENV_DIR/bin/pip" install --quiet 'textual>=8.1.1,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3' 'minijinja>=2.0,<3' 'pexpect>=4.9,<5'
    ```
  - **Line 655** (CPython venv install):
    ```bash
    "$VENV_DIR/bin/pip" install --quiet 'textual>=8.1.1,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3' 'minijinja>=2.0,<3' 'pexpect>=4.9,<5'
    ```

That's the entire fix. Pin matches the version installed locally during
diagnosis (`pexpect-4.9.0`); `>=4.9,<5` accepts the upcoming 4.x point
releases but not a hypothetical 5.x with breaking API.

## Why no changes elsewhere

- **`aitask_codex_plan_invoke.py`**: already has a clean diagnostic when
  pexpect is missing. After setup installs the dep, the script just works.
- **TUI switcher (`lib/tui_switcher.py:730`)**: hardcoded
  `"ait codeagent invoke explore"` is correct — `ait codeagent invoke`
  reads `codeagent_config.json` and resolves the agent string itself
  (`resolve_agent_string`, line 38). The earlier explorer hypothesis that
  the switcher needs to pass `--agent-string` was wrong; resolution flows
  through the config file automatically.
- **`aitask_codeagent.sh` (`build_invoke_command` line 504-508)**: uses
  bare `python3`. Since `~/.aitask/bin` is prepended to PATH by
  `lib/aitask_path.sh`, `python3` resolves to the wrapper
  `~/.aitask/bin/python3 → ~/.aitask/venv/bin/python` — the venv where
  pexpect will land. No change needed.

## Verification

1. Confirm the dry-run is unchanged (sanity check that command shape is
   stable):
   ```
   ./ait codeagent --dry-run invoke explore
   ```
   Expected: `DRY_RUN: python3 ...aitask_codex_plan_invoke.py --prompt $aitask-explore -- codex -m gpt-5.5`

2. Re-run setup and confirm pexpect lands in the venv:
   ```
   ./ait setup
   ~/.aitask/venv/bin/python -c "import pexpect; print(pexpect.__version__)"
   ```
   Expected: prints a version like `4.9.0` (or newer 4.x).

3. End-to-end smoke test from the TUI switcher path:
   ```
   ./ait codeagent invoke explore
   ```
   Expected: Codex CLI launches interactively with `/plan $aitask-explore`
   sent to its composer. The error message is no longer printed.
   (Requires interactive TTY; `aitask_codex_plan_invoke.py:84` aborts on
   non-TTY stdin/stdout.)

4. Optional: launch the TUI switcher, hit `x`, verify a new
   `agent-explore-N` window appears with Codex running rather than
   exiting on the pexpect error.

## Step 9 (Post-Implementation)

- Working on `main` directly (profile 'fast', no worktree). Skip
  worktree/branch cleanup.
- Commit message: `bug: Install pexpect in ait setup for codex explore launches (t801)`.
- Run `verify_build` if configured, then archive task via
  `./.aitask-scripts/aitask_archive.sh 801` and push.

## Final Implementation Notes

(filled in after implementation)
