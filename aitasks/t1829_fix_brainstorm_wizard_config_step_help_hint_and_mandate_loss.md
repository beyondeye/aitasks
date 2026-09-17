---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [ait_brainstorm, tui, textual]
gates: [risk_evaluated]
anchor: 1816
followup_kind: upstream_defect
created_at: 2026-09-17 12:17
updated_at: 2026-09-17 12:17
---

## Origin

Spawned from t1816 during Step 8b review.

## Upstream defect

- `.aitask-scripts/brainstorm/brainstorm_app.py:1290` — the wizard's "(H for details)" op-help hint is wrong on the explore config step: Tab focuses the Mandate TextArea, which swallows printable keys, so H types a literal H instead of opening help (check_action scopes w/l this way but H keeps an unconditional hint)
- `.aitask-scripts/brainstorm/brainstorm_app.py:574` — Esc on the explore config step (step 3 of 4) steps back via `_render_wizard_step`, which rebuilds the step and silently discards the typed Exploration Mandate with no confirmation and no restore on stepping forward

## Diagnostic context

Both were found while reproducing the t1816 crash (`H` then rapid `Esc` on the explore wizard's config step) in the live TUI (`crew-brainstorm-1812`, tmux, 200x55), and both were verified there. t1816 fixed the stale-dismiss crash (every brainstorm screen now derives from `lib/guarded_dismiss.GuardedModalScreen`) and the leaked 30s status-refresh timer. It deliberately left these two defects, which need key-scope and state-preservation design:

1. The `w`/`l` preview toggles are already scoped away from the focused TextArea through `ActionsWizardScreen.check_action`. `H` is not scoped the same way, yet its on-screen hint is unconditional, so while typing the hint promises a key that the TextArea swallows.
2. `ActionsWizardScreen.on_key` handles `escape` at step > 1 by calling `_render_wizard_step(prev)`. The config step is re-rendered from scratch, so the typed mandate is lost.

## Suggested fix

1. Make the hint follow focus (hide or reword it while the TextArea has focus, e.g. "Tab out, then H"), or give op-help a key the TextArea does not consume.
2. Save the mandate text into `_wizard_config` before stepping back and restore it when the config step re-renders, or ask for confirmation before discarding non-empty text.
