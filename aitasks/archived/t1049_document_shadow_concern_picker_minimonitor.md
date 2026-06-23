---
priority: medium
effort: low
depends: [t1037_5]
issue_type: documentation
status: Done
labels: [shadow, tui, aitask_monitormini, web_site]
assigned_to: dario-e@beyond-eye.com
anchor: 1037
created_at: 2026-06-22 11:19
updated_at: 2026-06-23 14:40
completed_at: 2026-06-23 14:40
---

## Origin

Documentation follow-up for t1037_4 (minimonitor shadow concern-picker wiring),
which closed the t1037 loop: the **minimonitor TUI** can now forward a shadow
agent's structured concerns to the followed code-agent. The website pages that
describe the shadow agent and the minimonitor TUI do not yet mention this flow.

Created from the implementing session at the user's request. **Gated behind
t1037_5** (manual verification) so the docs describe the final, verified
behavior — the implementation may still change during testing.

## Goal

Document the shadow concern-picker feature on the website pages that refer to the
shadow agent and the minimonitor TUI. Follow `aidocs/framework/
documentation_conventions.md` (current-state-only prose, no version history;
genericize agent names) and keep `diffviewer` out of TUI lists per CLAUDE.md.

Pages to update (verify against the live source before writing):

- `website/content/docs/workflows/shadow-agent.md` — the shadow emits a
  structured, machine-parseable concern block (an `===AITASK-CONCERNS===` /
  `===END-CONCERNS===` fenced list of `- [priority | region] body` items)
  alongside its prose, which the user can selectively forward to the followed
  agent from minimonitor.
- `website/content/docs/tuis/minimonitor/_index.md` and
  `website/content/docs/tuis/minimonitor/how-to.md` — document the new `c`
  keybinding ("pick shadow concerns" -> checklist modal -> copy the selected
  concerns to the clipboard with a preamble), the proactive auto-offer toast
  ("Shadow raised concerns - press 'c' to pick") that fires once per fresh
  concern block, and the one-shadow-per-followed-agent guard (a second `e` is
  refused). Update any keybinding list/table to include `c`.

## Reference

- Implementation: `.aitask-scripts/monitor/minimonitor_app.py`
  (`action_pick_concerns`, `_maybe_offer_concerns`, `_find_shadow_pane_for`,
  duplicate-shadow guard in `action_launch_shadow`); `aitask_shadow_capture.sh`
  (`-J`); parser `.aitask-scripts/monitor/concern_parser.py`; modal
  `ConcernPickerModal` in `.aitask-scripts/monitor/monitor_shared.py`.
- Format spec: `aidocs/framework/shadow_concern_format.md`.
- Shadow binding semantics: `aidocs/framework/shadow_agent.md`.
- Implemented plan (archived): `aiplans/archived/p1037/p1037_4_minimonitor_trigger_capture_wiring.md`.

## Verification

- `cd website && hugo build --gc --minify` succeeds.
- The shadow-agent and minimonitor pages describe the concern-picker `c` flow and
  the auto-offer; minimonitor keybinding lists include `c`.
