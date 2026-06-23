# Plan: Document shadow concern-picker on the website (t1049)

- **Task:** `aitasks/t1049_document_shadow_concern_picker_minimonitor.md`
- **Type:** documentation (low effort)
- **Working dir:** current branch (profile `fast`)
- **Dependency `1037_5`:** archived (manual verification done) — docs may describe final behavior.

## Verified behavior (from live source)

- `c` → `action_pick_concerns` (`Binding("c", "pick_concerns", ...)`, `minimonitor_app.py:202`):
  captures the bound shadow pane, parses its concern block, opens `ConcernPickerModal`,
  on confirm copies selected concerns + preamble to clipboard (`build_clipboard_payload`).
  No shadow → "No shadow agent running — press 'e' to launch one"; no concerns →
  "No concerns detected on the shadow pane".
- Auto-offer `_maybe_offer_concerns` (called on refresh tick, line 442): strict
  `has_concern_block`, de-duped per shadow pane on parsed payload → toast
  "Shadow raised concerns — press 'c' to pick", once per fresh block.
- Duplicate-shadow guard `action_launch_shadow`: `_find_shadow_pane_for_sync` →
  "A shadow is already running for this agent" (second `e` refused).
- Concern format (`aidocs/framework/shadow_concern_format.md`): fenced
  `===AITASK-CONCERNS===` … `===END-CONCERNS===` block of `- [priority | region] body`
  items (priority high|medium|low); additive to the shadow's prose; last block wins.

## Edits

1. `website/content/docs/workflows/shadow-agent.md` — new "Forward concerns to the
   followed agent" subsection under "Interrogate a plan": the structured concern block
   alongside prose, and the minimonitor `c` pick-and-forward-via-clipboard flow
   (advisory-only contract preserved). Cross-link to the minimonitor how-to.
2. `website/content/docs/tuis/minimonitor/_index.md` — extend "Launching a shadow agent"
   with the `c` picker, the auto-offer toast, and the one-shadow-per-agent guard.
3. `website/content/docs/tuis/minimonitor/how-to.md`:
   - "How to Launch a Shadow Agent" — note the one-shadow-per-agent guard (second `e` refused).
   - New "How to Pick Shadow Concerns" section (`c` flow + auto-offer note).
   - Add a `c` row to the Key Bindings Quick Reference table.

## Conventions honored

- Current-state-only prose, no version history; genericized agent names
  (`aidocs/framework/documentation_conventions.md`).
- `diffviewer` stays out of TUI lists (CLAUDE.md) — switcher list untouched.

## Verification

- `cd website && hugo build --gc --minify` succeeds.

## Final Implementation Notes

- **Actual work done:** All three planned pages were edited as designed.
  `shadow-agent.md` gained a "Forward concerns to the followed agent" subsection
  under *Interrogate a plan* (concern-block format + `c` clipboard flow,
  advisory-only contract preserved). `minimonitor/_index.md` extended *Launching
  a shadow agent* with `c`, the auto-offer toast, and the one-shadow-per-agent
  guard. `minimonitor/how-to.md` gained the guard note, a new "How to Pick Shadow
  Concerns" section, and a `c` row in the Key Bindings Quick Reference table.
- **Deviations from plan:** None.
- **Issues encountered:** The `_index.md` "Launching a shadow agent" paragraph is
  a single long sentence (not the two-paragraph shape assumed in the first edit
  draft); matched the real text instead. No other surprises.
- **Key decisions:** Documented the picker as copy-to-clipboard (you paste),
  matching `_on_concerns_picked`/`build_clipboard_payload` — minimonitor never
  types into the followed agent, consistent with the shadow's advisory-only
  contract. Left the TUI-switcher list untouched (no `diffviewer`, per CLAUDE.md).
- **Upstream defects identified:** None.
