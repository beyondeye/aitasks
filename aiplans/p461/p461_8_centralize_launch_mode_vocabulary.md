---
Task: t461_8_centralize_launch_mode_vocabulary.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/archived/t461/t461_1_*.md .. t461_7_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_1_*.md .. p461_7_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# p461_8 — Centralize `launch_mode` vocabulary

## Context

The valid `launch_mode` vocabulary (`headless`, `interactive`) is currently
duplicated across multiple scattered files with no shared source of truth.
Adding a new mode (e.g. a sandboxed `openshell` mode) would require a
synchronized multi-file edit with no compile-time safety. This task
eliminates that fragility before any new mode ships by introducing a
Python module as the single source of truth, with a tiny shell bridge
that derives the mode list from Python at runtime.

The task description enumerates **5 primary call sites**. Exploration
found **3 additional Python literal usages** that should be migrated at
the same time for a complete single-point-of-change story. One UI site
(`LaunchModePickerScreen`'s two hardcoded buttons) is structurally tied
to a binary choice and is explicitly deferred — it will need UI
redesign the first time a third mode actually ships.

## Scope decision (needs confirmation at ExitPlanMode)

**Primary (task description, mandatory):**
1. `.aitask-scripts/brainstorm/brainstorm_crew.py` — replaces inline
   `VALID_LAUNCH_MODES` (t461_7).
2. `.aitask-scripts/agentcrew/agentcrew_runner.py` — replaces literal
   `"headless"` fallback (t461_1).
3. `.aitask-scripts/aitask_crew_addwork.sh` — replaces `^(headless|interactive)$`.
4. `.aitask-scripts/aitask_crew_setmode.sh` — replaces `^(headless|interactive)$`.
5. `.aitask-scripts/aitask_crew_init.sh` — replaces `(:(headless|interactive))?`
   nested inside the `--add-type` format regex.

**Opportunistic (found during exploration, trivial to include):**
6. `.aitask-scripts/settings/settings_app.py:1615-1616` — vocab
   membership check and literal `"headless"` fallback.
7. `.aitask-scripts/brainstorm/brainstorm_app.py:2366` — `CycleField`
   options list.
8. `.aitask-scripts/lib/agent_model_picker.py:526` —
   `LaunchModePickerScreen.__init__` vocab check and literal fallback
   (the two hardcoded buttons at lines 538-548 are explicitly left
   alone — see Deferred below).

**Deferred (out of scope, requires UI redesign):**
- `LaunchModePickerScreen.compose()` at `agent_model_picker.py:538-548`
  creates one Button per mode with hardcoded IDs (`lm_headless`,
  `lm_interactive`). Extending to N modes needs a dynamic button loop,
  CSS review, and layout verification. Recommended: open a follow-up
  task when a third mode is actually added. Noted in the plan's Final
  Implementation Notes.

## Shell bridge: runtime-shellout vs codegen

The task description presents two options for the shell side:

- **Runtime shellout** (chosen): sourced helper `launch_modes_sh.sh`
  shells out to `python3` once per script run and caches the alternation
  in `LAUNCH_MODES_PIPE`/`LAUNCH_MODES_REGEX`. Single source of truth in
  all states; ~50-100ms one-time python startup cost per script
  invocation (acceptable for interactive CLI).
- **Codegen**: a build step writes a generated `launch_modes_regex.sh`
  checked into the repo. Rejected because it introduces stale-file risk
  (developer adds a mode, forgets to regenerate, shell validation
  silently accepts/rejects the wrong set) and a build-step dependency
  with no obvious hook point.

## Key Files to Modify / Create

### 1. `.aitask-scripts/lib/launch_modes.py` **(new)**

Python source of truth.

```python
"""Single source of truth for agent launch modes.

All call sites that validate, default, or enumerate launch modes must
import from this module. The shell bridge (`launch_modes_sh.sh`) shells
out here at runtime so shell consumers stay in sync automatically.
"""
from __future__ import annotations

VALID_LAUNCH_MODES: frozenset[str] = frozenset({"headless", "interactive"})
DEFAULT_LAUNCH_MODE: str = "headless"


def validate_launch_mode(val: str) -> bool:
    return val in VALID_LAUNCH_MODES


def normalize_launch_mode(
    val: str | None, fallback: str = DEFAULT_LAUNCH_MODE
) -> str:
    if val is None or val not in VALID_LAUNCH_MODES:
        return fallback
    return val


def launch_modes_pipe() -> str:
    """Sorted pipe-separated alternation for shell regex consumers."""
    return "|".join(sorted(VALID_LAUNCH_MODES))
```

Invariant: `DEFAULT_LAUNCH_MODE in VALID_LAUNCH_MODES` (enforced by
unit test).

### 2. `.aitask-scripts/lib/launch_modes_sh.sh` **(new)**

Shell bridge sourced by the three crew shell scripts.

```bash
#!/usr/bin/env bash
# launch_modes_sh.sh - Shell bridge to lib/launch_modes.py.
#
# Sources cleanly into a caller shell script and exports:
#   LAUNCH_MODES_PIPE   - e.g. "headless|interactive" (sorted)
#   LAUNCH_MODES_REGEX  - e.g. "^(headless|interactive)$"
#
# Both values are derived at runtime by shelling out to
# lib/launch_modes.py, so adding a mode there automatically
# propagates to every shell consumer without any shell-side edit.
#
# Test hook: set AIT_LAUNCH_MODES_DIR=/path to override the Python
# module search path (used by test_launch_modes.py extensibility test).

[[ -n "${_AIT_LAUNCH_MODES_LOADED:-}" ]] && return 0
_AIT_LAUNCH_MODES_LOADED=1

_ait_launch_modes_compute_pipe() {
    local dir="${AIT_LAUNCH_MODES_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
    python3 -c "
import sys
sys.path.insert(0, '$dir')
from launch_modes import launch_modes_pipe
sys.stdout.write(launch_modes_pipe())
"
}

if ! LAUNCH_MODES_PIPE="$(_ait_launch_modes_compute_pipe)"; then
    echo "error: failed to load launch_modes vocabulary from lib/launch_modes.py" >&2
    exit 1
fi
LAUNCH_MODES_REGEX="^(${LAUNCH_MODES_PIPE})$"
readonly LAUNCH_MODES_PIPE LAUNCH_MODES_REGEX
unset -f _ait_launch_modes_compute_pipe
```

**Design notes:**
- **No fallback to a literal mode list on Python failure** — a fallback
  would defeat single-source-of-truth by silently masking a broken
  import. Instead, fail loudly with `exit 1`.
- Uses the standard `_AIT_*_LOADED` double-source guard (same pattern
  as `agentcrew_utils.sh`, `archive_scan.sh`, etc.).
- `AIT_LAUNCH_MODES_DIR` env override is a deliberate test hook —
  documented in the header comment.
- `readonly` prevents a caller from accidentally mutating the pipe
  after sourcing.

### 3. `.aitask-scripts/brainstorm/brainstorm_crew.py`

- **Delete** line 47: `VALID_LAUNCH_MODES = frozenset({"headless", "interactive"})`.
- **Add** import near line 27 (next to `from config_utils import ...`):
  ```python
  from launch_modes import VALID_LAUNCH_MODES, DEFAULT_LAUNCH_MODE  # noqa: E402
  ```
  (The sibling `lib/` dir is already on `sys.path` via lines 24-25.)
- Line 75-76: no change — `val in VALID_LAUNCH_MODES` now reads the
  imported frozenset directly.
- Line 80-81: change `{sorted(VALID_LAUNCH_MODES)}` → no change
  required; still works. Keep the warning message format.
- Line 81 also has `info.get('launch_mode', 'headless')` fallback —
  change to `info.get('launch_mode', DEFAULT_LAUNCH_MODE)` for
  consistency.
- **Leave untouched:** `BRAINSTORM_AGENT_TYPES` dict literals at lines
  40-44 — those are per-type default *assignments*, not vocab
  duplication.

### 4. `.aitask-scripts/agentcrew/agentcrew_runner.py`

- **Add** import at line ~35 (next to `from lib.agent_launch_utils import`):
  ```python
  from lib.launch_modes import DEFAULT_LAUNCH_MODE
  ```
- Line 423-427: replace literal `"headless"` fallback:
  ```python
  launch_mode = (
      agent_data.get("launch_mode")
      or type_config.get("launch_mode")
      or DEFAULT_LAUNCH_MODE
  )
  ```
- **Leave untouched:** the `if launch_mode == "headless": ... elif launch_mode == "interactive":` dispatch block (lines 491-595). The
  dispatch encodes *mode-specific launch semantics*, not vocab — each
  branch has fundamentally different code (subprocess vs tmux vs
  terminal fallback). Normalizing this into a registry is a much larger
  refactor and is explicitly out of scope. The existing `else: log(f"WARNING: Unknown launch_mode '{launch_mode}' ...")` branch correctly
  handles any future unrecognized mode.

### 5. `.aitask-scripts/aitask_crew_addwork.sh`

- **Add source** after line 18 (next to other `source "$SCRIPT_DIR/lib/..."`):
  ```bash
  # shellcheck source=lib/launch_modes_sh.sh
  source "$SCRIPT_DIR/lib/launch_modes_sh.sh"
  ```
- **Replace** lines 100-101 (inline validation):
  ```bash
  [[ "$LAUNCH_MODE" =~ $LAUNCH_MODES_REGEX ]] || \
      die "--launch-mode must be one of: ${LAUNCH_MODES_PIPE//|/, } (got '$LAUNCH_MODE')"
  ```
- **Leave help text** at line 47 alone for now — the help docstring is
  frozen prose. Adding dynamic interpolation into a `<<'HELP'`
  heredoc would require reworking the help output. Acceptable staleness
  risk: help text lags by one release when a mode is added; the
  validation error at runtime will always be correct.

### 6. `.aitask-scripts/aitask_crew_setmode.sh`

- **Add source** after line 20:
  ```bash
  # shellcheck source=lib/launch_modes_sh.sh
  source "$SCRIPT_DIR/lib/launch_modes_sh.sh"
  ```
- **Replace** lines 76-77:
  ```bash
  [[ "$MODE" =~ $LAUNCH_MODES_REGEX ]] || \
      die "--mode must be one of: ${LAUNCH_MODES_PIPE//|/, } (got '$MODE')"
  ```
- **Check** `tests/test_crew_setmode.sh` for any exact-string assertion
  on the old error message ("must be 'headless' or 'interactive'") and
  update the assertion string to match the new wording if needed.

### 7. `.aitask-scripts/aitask_crew_init.sh`

- **Add source** after line 20:
  ```bash
  # shellcheck source=lib/launch_modes_sh.sh
  source "$SCRIPT_DIR/lib/launch_modes_sh.sh"
  ```
- **Replace** the `--add-type` format validator at line 86-90:
  ```bash
  local add_type_regex="^[a-z0-9_]+:[^:]+(:(${LAUNCH_MODES_PIPE}))?$"
  for at in "${ADD_TYPES[@]+"${ADD_TYPES[@]}"}"; do
      if ! [[ "$at" =~ $add_type_regex ]]; then
          die "Invalid --add-type format '$at': expected type_id:agent_string[:launch_mode] (launch_mode one of: ${LAUNCH_MODES_PIPE//|/, })"
      fi
  done
  ```
  Note: `local` is fine here because the loop is inside the top-level
  script scope (bash allows it via `set -u` as long as it precedes
  use). If shellcheck complains, hoist to a regular assignment above
  the loop.
- **Check** `tests/test_crew_init.sh` for exact-string assertions on
  the old error message.

### 8. `.aitask-scripts/settings/settings_app.py` (opportunistic)

- Line 1615-1616 currently:
  ```python
  if current_mode not in ("headless", "interactive"):
      current_mode = "headless"
  ```
- Replace with:
  ```python
  from launch_modes import normalize_launch_mode
  current_mode = normalize_launch_mode(current_mode)
  ```
- Import is added near the existing `from config_utils import ...`
  block at line 34. `lib/` is on `sys.path` via the module's standard
  path prelude.

### 9. `.aitask-scripts/brainstorm/brainstorm_app.py` (opportunistic)

- Line 2366 currently: `["headless", "interactive"],`
- Replace with: `sorted(VALID_LAUNCH_MODES),`
- Add import at top of file: `from launch_modes import VALID_LAUNCH_MODES`
  (same sys.path setup as `brainstorm_crew.py`).
- **Verify**: `CycleField` accepts a list of any length — confirmed by
  brief scan of the component's contract (it cycles through a fixed
  list).

### 10. `.aitask-scripts/lib/agent_model_picker.py` (opportunistic)

- Line 523-526 `LaunchModePickerScreen.__init__`:
  ```python
  def __init__(self, operation: str, current: str = "headless"):
      super().__init__()
      self.operation = operation
      self.current = current if current in ("headless", "interactive") else "headless"
  ```
- Replace with:
  ```python
  def __init__(self, operation: str, current: str | None = None):
      super().__init__()
      from launch_modes import DEFAULT_LAUNCH_MODE, normalize_launch_mode
      self.operation = operation
      self.current = normalize_launch_mode(current)
  ```
  (Import is local to avoid changing the module's top-of-file import
  order, which has intricate Textual-related ordering.)
- **Leave** the two hardcoded `Button(...)` calls at lines 538-548
  alone — they're structurally tied to a two-mode UI.

### 11. `tests/test_launch_modes.py` **(new)**

```python
"""Tests for lib/launch_modes.py and its shell bridge."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / ".aitask-scripts" / "lib"
HELPER_SH = LIB_DIR / "launch_modes_sh.sh"

sys.path.insert(0, str(LIB_DIR))
import launch_modes  # noqa: E402


class TestModule(unittest.TestCase):
    def test_default_in_valid_set(self):
        self.assertIn(launch_modes.DEFAULT_LAUNCH_MODE,
                      launch_modes.VALID_LAUNCH_MODES)

    def test_seed_vocabulary(self):
        self.assertIn("headless", launch_modes.VALID_LAUNCH_MODES)
        self.assertIn("interactive", launch_modes.VALID_LAUNCH_MODES)

    def test_validate(self):
        self.assertTrue(launch_modes.validate_launch_mode("headless"))
        self.assertTrue(launch_modes.validate_launch_mode("interactive"))
        self.assertFalse(launch_modes.validate_launch_mode("bogus"))
        self.assertFalse(launch_modes.validate_launch_mode(""))

    def test_normalize(self):
        self.assertEqual(launch_modes.normalize_launch_mode("headless"),
                         "headless")
        self.assertEqual(launch_modes.normalize_launch_mode(None),
                         launch_modes.DEFAULT_LAUNCH_MODE)
        self.assertEqual(launch_modes.normalize_launch_mode("bogus"),
                         launch_modes.DEFAULT_LAUNCH_MODE)
        self.assertEqual(
            launch_modes.normalize_launch_mode(None, "interactive"),
            "interactive",
        )

    def test_pipe_sorted(self):
        self.assertEqual(
            launch_modes.launch_modes_pipe(),
            "|".join(sorted(launch_modes.VALID_LAUNCH_MODES)),
        )


class TestShellBridgeParity(unittest.TestCase):
    """Shell bridge must stay in sync with the Python module."""

    def _source_and_echo(self, var: str, env: dict | None = None) -> str:
        result = subprocess.run(
            ["bash", "-c",
             f'source "{HELPER_SH}"; printf %s "${{{var}}}"'],
            capture_output=True, text=True, env={**os.environ, **(env or {})},
        )
        self.assertEqual(result.returncode, 0,
                         f"shell bridge failed: {result.stderr}")
        return result.stdout

    def test_pipe_matches_python(self):
        self.assertEqual(
            self._source_and_echo("LAUNCH_MODES_PIPE"),
            launch_modes.launch_modes_pipe(),
        )

    def test_regex_matches_python(self):
        self.assertEqual(
            self._source_and_echo("LAUNCH_MODES_REGEX"),
            f"^({launch_modes.launch_modes_pipe()})$",
        )


class TestExtensibility(unittest.TestCase):
    """Adding a new mode to VALID_LAUNCH_MODES flows to every consumer
    with no other file edits. Uses AIT_LAUNCH_MODES_DIR override to
    avoid mutating the real module on disk."""

    def test_new_mode_propagates_to_shell_bridge(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            sandbox = Path(td)
            # Minimal stand-in launch_modes.py with an added mode.
            (sandbox / "launch_modes.py").write_text(textwrap.dedent("""
                VALID_LAUNCH_MODES = frozenset({"headless", "interactive", "sandbox_openshell"})
                DEFAULT_LAUNCH_MODE = "headless"
                def launch_modes_pipe():
                    return "|".join(sorted(VALID_LAUNCH_MODES))
                def validate_launch_mode(v): return v in VALID_LAUNCH_MODES
                def normalize_launch_mode(v, fb="headless"):
                    return fb if v is None or v not in VALID_LAUNCH_MODES else v
            """))
            env = {"AIT_LAUNCH_MODES_DIR": str(sandbox)}
            result = subprocess.run(
                ["bash", "-c",
                 f'source "{HELPER_SH}"; printf %s "$LAUNCH_MODES_PIPE"'],
                capture_output=True, text=True,
                env={**os.environ, **env},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("sandbox_openshell", result.stdout)
            # All three original modes must still be present (additive).
            self.assertIn("headless", result.stdout)
            self.assertIn("interactive", result.stdout)
            # Sorted order preserved.
            parts = result.stdout.split("|")
            self.assertEqual(parts, sorted(parts))


if __name__ == "__main__":
    unittest.main()
```

**Why this test is sufficient to demonstrate single-point-of-change
extensibility:**

- The Python side: adding to `VALID_LAUNCH_MODES` directly exercises
  `validate_launch_mode`, `normalize_launch_mode`, and
  `launch_modes_pipe` — the three entry points every Python consumer
  uses.
- The shell side: all three shell scripts derive their regex from the
  same `launch_modes_sh.sh` bridge, which in turn derives from
  `launch_modes.py`. The extensibility test proves that overriding the
  module (via `AIT_LAUNCH_MODES_DIR`) is picked up by the bridge. Since
  the bridge is the sole path for shell consumers, propagation to all
  three shell scripts is guaranteed structurally.

No per-script subprocess smoke tests are needed, because there is no
script-local vocabulary literal to diverge from the bridge — that's
the whole point of the refactor.

## Step-by-step implementation order

1. Create `lib/launch_modes.py` + `lib/launch_modes_sh.sh`.
2. Add `tests/test_launch_modes.py`; run it to confirm the module +
   bridge + extensibility pass **before** touching any call sites.
3. Migrate Python call sites (3 + 5 opportunistic files):
   - `brainstorm/brainstorm_crew.py`
   - `agentcrew/agentcrew_runner.py`
   - `settings/settings_app.py`
   - `brainstorm/brainstorm_app.py`
   - `lib/agent_model_picker.py`
4. Migrate shell call sites:
   - `aitask_crew_addwork.sh`
   - `aitask_crew_setmode.sh`
   - `aitask_crew_init.sh`
5. Run regression suite:
   - `python3 tests/test_brainstorm_crew.py`
   - `python3 tests/test_launch_modes.py`
   - `bash tests/test_crew_init.sh`
   - `bash tests/test_crew_setmode.sh`
   - (any other `test_crew_*.sh` that exercise addwork)
6. `shellcheck .aitask-scripts/aitask_crew_*.sh .aitask-scripts/lib/launch_modes_sh.sh`.
7. Manual smoke: `./ait crew init --id smoketest --add-type impl:claudecode/opus4_6:interactive --batch`
   and verify it succeeds. Then clean up with
   `git worktree remove .aitask-crews/crew-smoketest` and delete the
   branch.

## Verification

- [ ] `python3 tests/test_launch_modes.py` — module, bridge parity,
      extensibility test all pass
- [ ] `python3 tests/test_brainstorm_crew.py` — existing launch_mode
      tests unchanged
- [ ] `bash tests/test_crew_setmode.sh` — setmode validation passes;
      update string assertions if message wording changed
- [ ] `bash tests/test_crew_init.sh` — init `--add-type` validation
      still accepts old format
- [ ] `shellcheck .aitask-scripts/aitask_crew_*.sh .aitask-scripts/lib/launch_modes_sh.sh`
      clean
- [ ] Manual: `ait crew addwork --launch-mode bogus` errors with
      wording that includes the full mode list
- [ ] Manual: `ait crew addwork --launch-mode interactive` still works
- [ ] Grep negative check:
      `grep -rn '"headless".*"interactive"\|headless|interactive' .aitask-scripts/`
      returns only:
      - `BRAINSTORM_AGENT_TYPES` dict literals in `brainstorm_crew.py`
        (per-type defaults, not vocab)
      - Docstrings / help text that weren't rewritten
      - `LaunchModePickerScreen.compose()` button constructors
        (deferred, documented)
      - `launch_modes.py` itself (the source of truth)

## Reference to Step 9

After user approval and commit, continue with Step 9 (Post-Implementation):
clean up, run archive script, push. This is a child task so the archived
plan will serve as the primary reference for any future sibling task.
