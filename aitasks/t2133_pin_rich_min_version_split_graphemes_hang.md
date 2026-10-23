---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [setup, minimonitor, tui, python_deps]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-23 11:25
updated_at: 2026-10-23 11:27
---

# Pin rich >= 14.3.3: `split_graphemes` hangs TUIs on a leading zero-width char

## Symptom (observed 2026-10-23, consumer project thinking_backend)

The minimonitor in tmux window `thinking_back:9` (`agent-pick-185`) froze for good.
Its main thread (pid 3133, `minimonitor_app.py`) was at 100% CPU and the screen
stopped redrawing. The last painted frame was the `p` "Pick Task by Number" prompt
with `147` typed. After Enter, `_on_pick_number_entered` pushes
`TaskPickConfirmDialog(narrow=True)`, which renders the task body as Textual
`Markdown` in the ~40-column pane. Its layout never finishes, so the event loop
never yields: Esc/q do nothing and the only way out is to kill the process.

## Root cause

**Upstream bug in rich 14.3.2's `rich.cells.split_graphemes`.** When a
zero-width character comes before any visible one in the segment, the code takes
the `elif spans:` branch. `spans` is still empty, so that branch is false, and
`index` never advances, so the `while index < codepoint_count` loop spins forever:

```python
if character_width := get_character_cell_size(character, unicode_version):
    ...
elif spans:            # empty -> no branch taken, index never advances
    ...
```

A leading U+FE0F with no measured character before it hits the same bug through the
`continue` path. Minimal repro: `rich.cells.split_graphemes("‎")` never
returns on 14.3.2. **rich 14.3.3 fixed it**: the new `else:` branch appends a
zero-width span and advances. 14.3.4 and 15.0.0 have the fix too (checked by
reading `rich/cells.py` in each wheel).

Call path in the hang (faulthandler dump of a headless repro):
`Screen._refresh_layout` → nested `height: auto` vertical arrange →
`GridLayout.arrange` (Markdown table) → `Content.get_height` →
`_wrap_and_format` → `Content.truncate` → `rich.cells.set_cell_size` →
`_split_text` → `split_graphemes`.

Trigger data: thinking_backend `aitasks/t147_hebrew_question_corrections_from_russian_translation_review.md`
has a 90-row, 5-column table. In row 19, two cells start with U+200E LEFT-TO-RIGHT
MARK (`‎____ are you going?`), which is common in RTL (Hebrew/Arabic) text.
Headless timings with Textual 8.2.7 / rich 14.3.2: rows 1–18 at 40 columns render
in 0.37 s, row 19 alone hangs, and the full body at 120 columns renders in 0.68 s.
The truncation only runs when the cell has to be narrowed, so the hang depends on width.

## Why the framework lets this happen

`.aitask-scripts/aitask_setup.sh` `AIT_PIP_SPECS_COMMON` pins only
`'textual>=8.2.7,<9'`. Textual 8.2.7 requires `rich>=14.2.0`, so a venv created
earlier keeps the buggy 14.3.2 forever. That's what this machine had:
`~/.aitask/venv` (CPython; runs minimonitor/monitor/board fallback) had **rich
14.3.2**, while `~/.aitask/pypy_venv` happened to have 15.0.0.

t940 already hit this bug class: the codebrowser hung in `set_cell_size` /
`split_graphemes` on raw control bytes. That fix sanitized input only in
`codebrowser/code_viewer.py`, not the dependency, so every other Textual surface
(minimonitor/monitor `i` and `p` dialogs, board task detail, brainstorm,
diffviewer, ...) is still exposed to any task/plan body containing a zero-width
character.

## Fix

1. Add `'rich>=14.3.3'` to `AIT_PIP_SPECS_COMMON` in `aitask_setup.sh` (both the
   CPython and PyPy venvs install COMMON). Keep the `textual` pin unchanged.
2. Confirm that the existing `verify_venv_specs` check makes an **already-installed**
   venv with rich 14.3.2 upgrade on the next `ait setup` / `ait upgrade`.
   Otherwise the pin only protects fresh installs. If it doesn't, make it do so.
3. Regression test (follow the repo testing conventions, no sleeps, bounded by a
   timeout or a subprocess with a timeout so a regression fails instead of hanging the suite):
   - `rich.cells.split_graphemes("‎")` and `"️"` return;
   - a headless `App.run_test(size=(40, 30))` rendering `TaskDetailDialog`
     (or bare `Markdown`) whose body has a table row with a `‎`-prefixed
     cell completes.
4. Decide whether the t940 control-char sanitizer in `code_viewer.py` is still
   needed with the pin. It also handles display of raw control bytes, so it
   probably stays. Record the decision.

## Operator remediation on an affected machine (not part of the code change)

`~/.aitask/venv/bin/python -m pip install 'rich>=14.3.3'`, then kill and relaunch
any hung TUI. Already-running TUIs keep the old rich loaded until they restart.
