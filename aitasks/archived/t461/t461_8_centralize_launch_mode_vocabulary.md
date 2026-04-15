---
priority: medium
effort: medium
depends: [t461_7, t461_7]
issue_type: refactor
status: Done
labels: [agentcrew, refactor]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-14 12:49
updated_at: 2026-04-15 10:37
completed_at: 2026-04-15 10:37
---

## Context

This task follows up on t461_7, which added a config-overlay layer for
brainstorm `launch_mode` defaults (`brainstorm-<type>-launch-mode` keys
in `codeagent_config.json`). After t461_7, the valid launch-mode
vocabulary (`headless`, `interactive`) is now duplicated across **five**
scattered locations with no shared source of truth:

- `.aitask-scripts/aitask_crew_addwork.sh` — shell regex
- `.aitask-scripts/aitask_crew_setmode.sh` — shell regex
- `.aitask-scripts/aitask_crew_init.sh` — shell regex
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — Python literal
- `.aitask-scripts/brainstorm/brainstorm_crew.py::get_agent_types()` — `VALID_LAUNCH_MODES`

The project plans to add new launch modes beyond `headless`/`interactive`
(e.g., a sandboxed `openshell` mode, possibly `monitored`, etc.). Adding
a new mode today requires a synchronized five-file edit with no
compile-time safety net — that's exactly the kind of fragility we want
to eliminate before shipping any new mode.

## Goal

Create a single source of truth for the valid launch-mode set plus
validation helpers, consumed by all five current call sites.

## Proposed implementation

1. Add a new module `.aitask-scripts/lib/launch_modes.py` exporting:
   - `VALID_LAUNCH_MODES: frozenset[str]` (initially `{"headless", "interactive"}`)
   - `DEFAULT_LAUNCH_MODE = "headless"`
   - `validate_launch_mode(val: str) -> bool`
   - `normalize_launch_mode(val: str | None, fallback: str = DEFAULT_LAUNCH_MODE) -> str`

2. Migrate Python call sites:
   - `brainstorm/brainstorm_crew.py::get_agent_types()` — replace the inline `VALID_LAUNCH_MODES` set from t461_7.
   - `agentcrew/agentcrew_runner.py` — replace the inline validation added by t461_1.

3. Migrate shell call sites (`aitask_crew_addwork.sh`,
   `aitask_crew_setmode.sh`, `aitask_crew_init.sh`):
   - Since shell cannot directly import Python, generate a
     shell-compatible regex via a small helper. Two options to
     evaluate in the plan phase:
     - **Runtime**: a helper script (e.g., `.aitask-scripts/lib/launch_modes_sh.sh`)
       that shells out to `python -c "from launch_modes import
       VALID_LAUNCH_MODES; print('^(' + '|'.join(sorted(VALID_LAUNCH_MODES)) + ')$')"`
       at script startup and stores the result in a local variable.
     - **Codegen**: a build step that writes the regex into a
       generated `.aitask-scripts/lib/launch_modes_regex.sh` file
       committed to the repo.
   - The follow-up task should pick one approach and justify it.

4. **Extensibility test**: include a test demonstrating that adding a
   new mode (e.g., `sandbox_openshell`) to `VALID_LAUNCH_MODES` is
   picked up by all five call sites without any other file edit.

## Acceptance

- All five current call sites read the valid mode set from the new
  `launch_modes` module (directly or via the generated shell regex).
- `python3 tests/test_brainstorm_crew.py` still passes.
- `shellcheck .aitask-scripts/aitask_*.sh` still clean.
- New test(s) demonstrate single-point-of-change extensibility.

## Dependencies

- **t461_7** (brainstorm launch_mode settings TUI) — this task's
  config-overlay layer establishes the complete inventory of call
  sites to migrate.
