---
Task: t461_8_centralize_launch_mode_vocabulary.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/archived/t461/t461_1_*.md .. t461_7_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_1_*.md .. p461_7_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_6 @ 2026-04-15 09:26
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
found **additional Python literal usages** that should be migrated at
the same time for a complete single-point-of-change story. Two UI sites
(`LaunchModePickerScreen` and `AgentModeEditModal`, each with two
hardcoded buttons) are structurally tied to a binary choice and are
explicitly deferred — they will be handled in a follow-up sibling task
(t461_9, created at the start of this task's implementation).

**Openshell as a canary mode:** As part of this task, `openshell` is
added as a third mode in `VALID_LAUNCH_MODES` from day one — *without*
implementing real launch semantics for it. The rationale: any call site
that still hardcodes the two-mode vocabulary will surface as a runtime
mismatch (validator reject, dropdown missing an option, dispatch
warning), acting as a canary during the smoke-test phase. The actual
launch semantics for `openshell` (subprocess sandboxing, etc.) are out
of scope here and belong to a separate task when the feature is
actually wanted.

## Scope

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
6. `.aitask-scripts/settings/settings_app.py:1638-1639` — vocab
   membership check and literal `"headless"` fallback.
7. `.aitask-scripts/settings/settings_app.py:1910-1912` — framework
   default literal `"headless"` fallback inside `_emit_launch_mode_rows`.
8. `.aitask-scripts/brainstorm/brainstorm_app.py:2366` — `CycleField`
   options list.
9. `.aitask-scripts/brainstorm/brainstorm_app.py:128` —
   `_brainstorm_launch_mode_default` literal `"headless"` fallback.
10. `.aitask-scripts/brainstorm/brainstorm_app.py:1715` —
    `_edit_agent_mode` reads current mode with literal fallback.
11. `.aitask-scripts/brainstorm/brainstorm_app.py:2562, 2572` — wizard
    `launch_mode` literal fallbacks.
12. `.aitask-scripts/lib/agent_model_picker.py:523-526` —
    `LaunchModePickerScreen.__init__` vocab check and literal fallback.

**Deferred to follow-up sibling task t461_9** (see appendix):
- `LaunchModePickerScreen.compose()` at `agent_model_picker.py:538-548`
  — hardcoded two-button UI.
- `AgentModeEditModal` at `brainstorm_app.py:270-333` — second hardcoded
  two-button modal.
- `agentcrew_runner.py` launch dispatch block at lines 491-595 — the
  `if launch_mode == "headless": ... elif "interactive": ... else:
  WARNING` chain needs a launcher-registry refactor before `openshell`
  (or any future mode) can actually launch.
- `brainstorm_crew.py` function signature defaults
  `launch_mode: str = "headless"` at lines 107, 358, 400, 436, 474, 510
  — cosmetic consistency with `DEFAULT_LAUNCH_MODE`.
- Help-text heredocs in `aitask_crew_addwork.sh`, `aitask_crew_init.sh`,
  and `aitask_crew_setmode.sh` that statically mention
  `headless|interactive` — staleness risk, low priority.

**Also left untouched in both tasks** (not vocab duplication):
- `BRAINSTORM_AGENT_TYPES` dict literals at `brainstorm_crew.py:40-44`
  — per-type default assignments, not vocab.

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

Note: `openshell` is present in the vocabulary as a canary/placeholder.
Real launch semantics for it are not implemented yet — the runner
dispatch in agentcrew_runner.py will warn and skip on encounter. The
placeholder exists to exercise the single-source-of-truth refactor and
make missed call sites visible at runtime. Actual `openshell` support
is a follow-up task (see t461_9).
"""
from __future__ import annotations

VALID_LAUNCH_MODES: frozenset[str] = frozenset(
    {"headless", "interactive", "openshell"}
)
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
  (The sibling `lib/` dir is already on `sys.path` via line 25.)
- Line 75-76: no change — `val in VALID_LAUNCH_MODES` now reads the
  imported frozenset directly.
- Line 80-81: the warning message format (`{sorted(VALID_LAUNCH_MODES)}`)
  still works. Change the trailing fallback
  `info.get('launch_mode', 'headless')` → `info.get('launch_mode', DEFAULT_LAUNCH_MODE)`
  for consistency.
- **Leave untouched:** `BRAINSTORM_AGENT_TYPES` dict literals at lines
  40-44; function signature defaults `launch_mode: str = "headless"` at
  lines 107, 358, 400, 436, 474, 510 (documented rationale above).

### 4. `.aitask-scripts/agentcrew/agentcrew_runner.py`

- **Add** import near line 35 (next to `from lib.agent_launch_utils import`):
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
  frozen prose inside a `<<'HELP'` heredoc. Adding dynamic
  interpolation would require reworking the help output. Acceptable
  staleness risk: help text lags by one release when a mode is added;
  the validation error at runtime will always be correct.
- **Note:** `LAUNCH_MODE="headless"` default at line 27 is a pure
  initializer — left as a literal to avoid sourcing the bridge before
  arg parsing. The validation regex above is what enforces membership.

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
- **Replace** the `--add-type` format validator at lines 86-90:
  ```bash
  add_type_regex="^[a-z0-9_]+:[^:]+(:(${LAUNCH_MODES_PIPE}))?$"
  for at in "${ADD_TYPES[@]+"${ADD_TYPES[@]}"}"; do
      if ! [[ "$at" =~ $add_type_regex ]]; then
          die "Invalid --add-type format '$at': expected type_id:agent_string[:launch_mode] (launch_mode one of: ${LAUNCH_MODES_PIPE//|/, })"
      fi
  done
  ```
  Note: hoist `add_type_regex` above the loop (not `local` — this is
  top-level script scope, not a function).
- **Check** `tests/test_crew_init.sh` (and any related tests) for exact
  error-message assertions.

### 8. `.aitask-scripts/settings/settings_app.py` (opportunistic)

Two sites in this file:

**Site A — line 1638-1639:**
```python
if current_mode not in ("headless", "interactive"):
    current_mode = "headless"
```
Replace with:
```python
current_mode = normalize_launch_mode(current_mode)
```
And at line 1635, change the literal fallback:
```python
current_mode = str(project_defaults.get(key, DEFAULT_LAUNCH_MODE))
```

**Site B — line 1910-1912 (inside `_emit_launch_mode_rows`):**
```python
framework_default = BRAINSTORM_AGENT_TYPES.get(atype, {}).get(
    "launch_mode", "headless"
)
```
Replace the literal `"headless"` with `DEFAULT_LAUNCH_MODE`.

**Import:** Add near the existing `from config_utils import ...` block
(after line 48) so it sits with the other lib imports:
```python
from launch_modes import DEFAULT_LAUNCH_MODE, normalize_launch_mode  # noqa: E402
```
The `.aitask-scripts/lib` path is already pushed onto `sys.path` at
line 19.

### 9. `.aitask-scripts/brainstorm/brainstorm_app.py` (opportunistic)

Multiple sites — use a shared import and replace literals.

**Import (add near the existing `from config_utils import ...` or
`from brainstorm.brainstorm_crew import ...` blocks):**
```python
from launch_modes import DEFAULT_LAUNCH_MODE, VALID_LAUNCH_MODES  # noqa: E402
```
(The module must already push `.aitask-scripts/lib` onto `sys.path`;
verify before importing.)

**Sites:**
- **Line 128** — inside `_brainstorm_launch_mode_default`:
  ```python
  ).get("launch_mode", "headless")
  ```
  → `).get("launch_mode", DEFAULT_LAUNCH_MODE)`
- **Line 1715** — inside `_edit_agent_mode`:
  ```python
  current_mode = data.get("launch_mode", "headless")
  ```
  → `current_mode = data.get("launch_mode", DEFAULT_LAUNCH_MODE)`
- **Line 2366** — `CycleField` options list:
  ```python
  ["headless", "interactive"],
  ```
  → `sorted(VALID_LAUNCH_MODES),`
  **Verify**: `CycleField` accepts a list of any length — confirmed by
  brief scan (it cycles through a fixed list).
- **Line 2562** — wizard config fallback:
  ```python
  self._wizard_config["launch_mode"] = "headless"
  ```
  → `self._wizard_config["launch_mode"] = DEFAULT_LAUNCH_MODE`
- **Line 2572** — wizard op runner:
  ```python
  launch_mode = cfg.get("launch_mode", "headless")
  ```
  → `launch_mode = cfg.get("launch_mode", DEFAULT_LAUNCH_MODE)`

**Left alone:** the `AgentModeEditModal` class at lines 270-333 (two
hardcoded buttons, same rationale as `LaunchModePickerScreen`).

### 10. `.aitask-scripts/lib/agent_model_picker.py` (opportunistic)

- Lines 523-526 `LaunchModePickerScreen.__init__`:
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
      from launch_modes import normalize_launch_mode
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
        self.assertIn("openshell", launch_modes.VALID_LAUNCH_MODES)

    def test_validate(self):
        self.assertTrue(launch_modes.validate_launch_mode("headless"))
        self.assertTrue(launch_modes.validate_launch_mode("interactive"))
        self.assertTrue(launch_modes.validate_launch_mode("openshell"))
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
            (sandbox / "launch_modes.py").write_text(textwrap.dedent("""
                VALID_LAUNCH_MODES = frozenset(
                    {"headless", "interactive", "openshell", "futuremode"}
                )
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
            self.assertIn("futuremode", result.stdout)
            self.assertIn("headless", result.stdout)
            self.assertIn("interactive", result.stdout)
            self.assertIn("openshell", result.stdout)
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

## Step-by-step implementation order

0. **Create follow-up task t461_9** (see appendix for full content). Use
   the Batch Task Creation Procedure with `aitask_create.sh --batch`
   mode=child parent=461. Commit with `./ait git`.
1. Create `lib/launch_modes.py` (with `openshell` in the frozenset) +
   `lib/launch_modes_sh.sh`.
2. Add `tests/test_launch_modes.py`; run it to confirm the module +
   bridge + extensibility pass **before** touching any call sites.
3. Migrate Python call sites (5 files):
   - `brainstorm/brainstorm_crew.py`
   - `agentcrew/agentcrew_runner.py`
   - `settings/settings_app.py` (two sites)
   - `brainstorm/brainstorm_app.py` (five sites)
   - `lib/agent_model_picker.py`
4. Migrate shell call sites (3 files):
   - `aitask_crew_addwork.sh`
   - `aitask_crew_setmode.sh`
   - `aitask_crew_init.sh`
5. Run regression suite:
   - `python3 tests/test_launch_modes.py`
   - `python3 tests/test_brainstorm_crew.py`
   - `bash tests/test_crew_setmode.sh`
   - `bash tests/test_crew_init.sh` (if present)
6. `shellcheck .aitask-scripts/aitask_crew_*.sh .aitask-scripts/lib/launch_modes_sh.sh`.
7. **Openshell canary smoke tests** — with `openshell` now in the
   vocabulary, exercise each call site to confirm it accepts the new
   mode (or, where it can't, fails in the expected way):
   - `./ait crew init --id smoketest --add-type impl:claudecode/opus4_6:openshell --batch`
     → expect success.
   - `./ait crew addwork --crew smoketest --name w1 --work2do /dev/null --type impl --launch-mode openshell --batch`
     → expect success.
   - `./ait crew setmode --crew smoketest --name w1 --mode openshell`
     → expect success.
   - Launch via `./ait crew run --crew smoketest` → expect the
     `else: WARNING: Unknown launch_mode 'openshell'` branch to fire in
     `agentcrew_runner.py` (this is the expected behavior until t461_9
     implements real dispatch). Confirm the warning appears and the
     agent is skipped without crashing.
   - Open the brainstorm TUI wizard for a new design op → expect the
     `CycleField` launch-mode widget to now include `openshell` among
     its cycleable options.
   - Open the settings TUI agent-defaults tab → expect the
     brainstorm-*-launch-mode rows to list `openshell` as a valid
     choice in the picker (the picker itself stays two-button due to
     the deferred `LaunchModePickerScreen.compose()` refactor; this is
     expected and documented in t461_9).
   - Clean up: `git worktree remove .aitask-crews/crew-smoketest` and
     delete the branch.
8. **Any site that fails to accept `openshell`** (other than the
   explicitly deferred ones above) indicates a missed migration — fix
   it before moving on.

## Verification

- [ ] `python3 tests/test_launch_modes.py` — module, bridge parity,
      extensibility test all pass
- [ ] `python3 tests/test_brainstorm_crew.py` — existing launch_mode
      tests unchanged
- [ ] `bash tests/test_crew_setmode.sh` — setmode validation passes;
      update string assertions if message wording changed
- [ ] `shellcheck .aitask-scripts/aitask_crew_*.sh .aitask-scripts/lib/launch_modes_sh.sh`
      clean
- [ ] Manual: `ait crew addwork --launch-mode bogus` errors with
      wording that includes the full mode list
- [ ] Manual: `ait crew addwork --launch-mode interactive` still works
- [ ] Grep negative check — only allowed matches for
      `"headless".*"interactive"` / `headless|interactive`:
      - `BRAINSTORM_AGENT_TYPES` dict literals in `brainstorm_crew.py`
        (per-type defaults)
      - `brainstorm_crew.py` function signature defaults (rationale
        documented)
      - Docstrings / help text that weren't rewritten
      - `LaunchModePickerScreen.compose()` button constructors
        (deferred)
      - `AgentModeEditModal` compose/dispatch (deferred)
      - `launch_modes.py` itself (the source of truth)

## Reference to Step 9

After user approval and commit, continue with Step 9 (Post-Implementation):
clean up, run archive script, push. This is a child task so the archived
plan will serve as the primary reference for any future sibling task.

## Appendix — Follow-up sibling task t461_9

Create this task at the start of implementation (Step 0 above) via the
Batch Task Creation Procedure. Target directory: `aitasks/t461/`.
Filename: `t461_9_unified_launch_mode_consumers.md`.

**Frontmatter:**
```yaml
---
priority: medium
effort: medium
depends: [t461_8]
issue_type: refactor
status: Ready
labels: [agentcrew, refactor]
---
```

**Description:**

```markdown
## Context

Sibling task t461_8 centralized the `launch_mode` vocabulary into
`.aitask-scripts/lib/launch_modes.py` and migrated every call site that
could be trivially updated without structural changes. Several
consumers were deliberately left alone because they require either a
UI redesign, a launcher-registry refactor, or a broader touch — doing
them in t461_8 would have ballooned the diff and mixed structurally
distinct changes.

As part of t461_8 a third mode `openshell` was added to
`VALID_LAUNCH_MODES` as a canary. Everything in this task is a consumer
that still cannot *fully* handle `openshell` (or any future third
mode) end-to-end, and needs further work.

## Goal

Finish the single-source-of-truth migration so that every consumer of
launch modes — UIs, dispatch tables, help text, function defaults —
handles an arbitrary mode list driven by `VALID_LAUNCH_MODES` alone,
with `openshell` as the first real target for end-to-end support.

## In scope

1. **`LaunchModePickerScreen.compose()` in
   `.aitask-scripts/lib/agent_model_picker.py:538-548`** — rewrite the
   two hardcoded `Button(...)` constructors into a dynamic loop over
   `sorted(VALID_LAUNCH_MODES)`. Generate button IDs via
   `f"lm_{mode}"`, update the dispatch in `on_button_pressed`, and
   adjust the CSS (`#lm_buttons Button { margin: 0 1; }`) to
   accommodate variable button counts. Add a Textual snapshot test or
   manual verification.

2. **`AgentModeEditModal` in
   `.aitask-scripts/brainstorm/brainstorm_app.py:270-333`** — same
   structural rewrite as above: dynamic button loop, dispatch via a
   single `on(Button.Pressed)` handler that reads the pressed button's
   ID prefix, CSS adjustment. The `current_mode` highlight logic needs
   to generalize too.

3. **`agentcrew_runner.py` launch dispatch** (`launch_agent`,
   roughly lines 491-595) — replace the `if launch_mode == "headless":
   ... elif "interactive": ... else: WARNING` chain with a launcher
   registry (`LAUNCHERS: dict[str, Callable]`) so a new mode only
   needs to register a function. As part of this, implement real
   `openshell` launch semantics (sandboxed subprocess — exact approach
   TBD during planning).

4. **`brainstorm_crew.py` function signature defaults** at lines 107,
   358, 400, 436, 474, 510 (`launch_mode: str = "headless"`) — replace
   the string literal with `DEFAULT_LAUNCH_MODE` for consistency.
   Requires importing the module at the top level (check import
   ordering — this file already imports from `config_utils` so the
   `sys.path` plumbing is in place).

5. **Help-text heredocs** in `aitask_crew_addwork.sh`,
   `aitask_crew_init.sh`, and `aitask_crew_setmode.sh` that statically
   enumerate `headless|interactive` — refactor to inject
   `${LAUNCH_MODES_PIPE}` into the heredoc at print time, OR leave as
   documented staleness risk (decide during planning).

6. **Any test files that hardcode the two-mode vocabulary** — e.g.
   `tests/test_crew_setmode.sh`, `tests/test_brainstorm_crew.py` —
   should be audited and updated to use the canonical set or at least
   tolerate additions.

## Out of scope

- Adding additional new modes beyond `openshell`.
- Any non-`launch_mode` refactoring in the affected files.
- Changes to the shared `lib/launch_modes.py` module (already shipped
  in t461_8).

## Dependencies

- **t461_8** — must be complete; this task depends on
  `lib/launch_modes.py` and the `DEFAULT_LAUNCH_MODE` / bridge
  infrastructure.

## Acceptance

- `openshell` can be picked in both picker modals and launches via the
  runner registry (or is explicitly documented as not yet implemented
  with a tracked follow-up).
- No `grep -rn '"headless".*"interactive"\|headless|interactive'
  .aitask-scripts/` matches remain outside `launch_modes.py`,
  `BRAINSTORM_AGENT_TYPES`, or pure human docs/comments.
- `python3 tests/test_launch_modes.py` and
  `python3 tests/test_brainstorm_crew.py` pass.
- Adding a hypothetical fourth mode to `VALID_LAUNCH_MODES` is a
  one-line change and flows through to every UI, dispatch, and
  validator with no other edit.
```

This appendix text is the source for the new child task file. During
implementation Step 0, feed it into `aitask_create.sh --batch` (via
the `--desc-file -` flag or a heredoc) to materialize
`aitasks/t461/t461_9_unified_launch_mode_consumers.md`, then `./ait git
add` / commit.
