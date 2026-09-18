---
Task: t1829_fix_brainstorm_wizard_config_step_help_hint_and_mandate_loss.md
Base branch: main
Output branch: main
---

# t1829 — Brainstorm wizard: focus-aware op-help hint + keep the mandate on step-back

## Context

While reproducing t1816, two defects in `ActionsWizardScreen`
(`.aitask-scripts/brainstorm/brainstorm_app.py`) were confirmed in the live TUI:

1. **Misleading "(H for details)" hint.** `_mount_op_context_header` (≈l.931)
   always renders `(<help_key> for details)`. While a `TextArea` (Exploration
   Mandate, Merge Rules, …) or an `Input` (FuzzyCheckList filter on the
   compare/synthesize config step) has focus, Textual delivers the key to the
   focused widget first; `TextArea._on_key` / `Input` consume every printable
   key, so `H` types a literal "H" and `action_op_help` never runs. The `w`/`l`
   preview toggles were already scoped around this via `check_action`; the
   H hint was not.
2. **Mandate lost on step-back.** `on_key` Esc at step > 1 calls
   `_render_wizard_step(prev)`. For explore with sections, Esc on config
   (step 3/4) → `section_select`; Next re-renders config via
   `_config_explore_no_node`, which mounts `TextArea("")` — the typed mandate
   is gone with no confirmation. The same happens coming back from the confirm
   step (Esc or the Back button): `_actions_collect_config` stored
   `mandate`/`parallel` in `_wizard_config`, but the re-render ignores them.
   Also, `_actions_show_section_select` re-mounts its checkboxes unchecked, so
   the section choice made before is lost on the same round-trip.

Intended outcome: the hint never promises a key the focused widget swallows,
and stepping back and forward through the explore wizard keeps what was typed.

## Implementation

All changes in `.aitask-scripts/brainstorm/brainstorm_app.py`, class
`ActionsWizardScreen`.

### 1. Focus-aware op-help hint

- Split the hint text out of `_mount_op_context_header` into a helper
  `_op_context_text(self) -> str | None`:
  - `help_key = resolve_key(self._shortcuts_scope, "op_help", "H") or "H"`
  - if `isinstance(self.focused, (TextArea, Input))` →
    `f"Tab out, then {help_key} for details"`, else `f"{help_key} for details"`
  - returns `f"[dim]{label_text} — {desc}  ({hint})[/dim]"` (None if op has
    no `_OP_LABELS` entry).
- `_mount_op_context_header` mounts `Label(self._op_context_text(), classes="actions_op_context")`.
- New `_refresh_op_context_hint(self)`: for each `Label.actions_op_context`
  in the screen, `label.update(self._op_context_text())` (no-op if none / text None).
- Call it from the existing `on_descendant_focus` (already fires on every focus
  change and already calls `refresh_bindings()` for w/l), and additionally
  handle `on_descendant_blur` the same way so focus leaving an input to nothing
  reverts the hint.
- No binding change: `H` keeps working whenever a non-text widget is focused.

### 2. Preserve the explore config across step-back

- New helper `_stash_config_draft(self)`: when
  `self._wizard_step_id == "config"` and `self._wizard_op == "explore"`, read
  the mounted `TextArea` text (unstripped) into `self._wizard_config["mandate"]`
  and the `CycleField` value into `self._wizard_config["parallel"]`
  (wrapped in `try/except` like neighbouring queries — widgets may not be
  mounted yet because `_mount_config_with_preview` fills the left pane via
  `call_after_refresh`).
- Call `_stash_config_draft()` before `_render_wizard_step(prev)` in both
  step-back paths: `on_key` Esc branch and `_on_actions_back`.
- `_config_explore_no_node`: mount `TextArea(self._wizard_config.get("mandate", ""))`
  and `CycleField(..., initial=str(self._wizard_config.get("parallel", 2)))`
  (fall back to `"2"` if the value is not one of the options).
- Confirm→config path is covered too: `_actions_collect_config` already writes
  `mandate`/`parallel` into `_wizard_config`, and the renderer now reads them.
- Node change still discards the draft: `_actions_show_node_select` resets
  `_wizard_config = {}`, which is correct (new base node → new mandate).
  `_actions_collect_config` rebuilds `config` from widgets, so a stale stash can
  never override what is on screen.
- `_actions_show_section_select`: mount each checkbox with
  `value=s.name in (self._wizard_config.get("target_sections") or [])` so the
  prior section choice survives the same round-trip.

Scope note: only explore's mandate is preserved (the reported defect). The
other text-bearing configs (synthesize merge rules, module_decompose plan,
module_sync instructions) follow the same re-render pattern; they will be listed
under upstream defects in the final notes rather than silently widened here.

### 3. Tests — `tests/test_brainstorm_wizard_nav_consolidation.py`

Reuse the existing `_WizardHost` / `WizardNavTests._drive` harness:

- `test_op_help_hint_follows_focus`: `has_sections=False` → config step;
  focus the `TextArea` → the `.actions_op_context` label text contains
  "Tab out, then H"; focus `#preview_proposal_content` → text contains
  "(H for details)" and not "Tab out".
- `test_mandate_survives_esc_back_and_forward`: `has_sections=True` →
  section_select; check the first section, press Next (`_on_actions_next`) →
  config; set TextArea text to "keep me" and cycle the parallel field; press
  `escape` → back on section_select with the first checkbox still checked;
  Next → config: TextArea text == "keep me", parallel preserved.
- `test_mandate_survives_confirm_back`: config with mandate filled →
  `_on_actions_next` → confirm; `escape` → config TextArea still holds the text.

### Post-phase (risk mitigations)

- **wizard_hint_focus_regression_test** — ensure `test_op_help_hint_follows_focus`
  covers both TextArea and a non-text widget, and that no exception escapes the
  focus/blur handlers (app still running after focus churn).
- **mandate_roundtrip_negative_control** — run the two mandate tests against a
  scratch copy with `_config_explore_no_node` mounting `TextArea("")`; both must
  fail, then pass with the fix.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir <tmp dir containing the test file>`
  or directly `~/.aitask/venv/bin/python -m pytest tests/test_brainstorm_wizard_nav_consolidation.py tests/test_brainstorm_guarded_dismiss.py tests/test_brainstorm_proposal_preview.py -q`.
- Negative control: the two mandate tests must fail with the renderer change
  reverted (temporarily, in a scratch copy — not via git restore).
- Manual (optional): `ait brainstorm`, explore a node with sections, type a
  mandate, Esc, Next → text preserved; hint reads "Tab out, then H…" while
  typing.

## Step 9 (Post-Implementation)

Current-branch profile: commit code + plan separately in Step 8, then run the
Step 9 gate orchestrator and archive via `aitask_archive.sh 1829`.

## Risk

### Code-health risk: low
- Focus handlers now update a Label on every focus change inside the wizard; an exception there would break focus handling · severity: low · → mitigation: inline post-phase wizard_hint_focus_regression_test

### Goal-achievement risk: low
- Mandate stash depends on reading widgets that are filled via `call_after_refresh`; an Esc before the left pane mounts would stash nothing (acceptable — nothing was typed) · severity: low · → mitigation: inline post-phase mandate_roundtrip_negative_control

### Planned mitigations
- timing: post-phase | name: wizard_hint_focus_regression_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: focus-handler exception risk | desc: Focus-hint regression test incl. focus churn stability
- timing: post-phase | name: mandate_roundtrip_negative_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: mandate stash timing risk | desc: Prove mandate round-trip tests fail without the renderer fix
