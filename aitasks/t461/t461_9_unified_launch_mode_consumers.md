---
priority: medium
effort: medium
depends: [t461_8]
issue_type: refactor
status: Implementing
labels: [agentcrew, refactor]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-15 09:27
updated_at: 2026-04-15 12:01
---

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
