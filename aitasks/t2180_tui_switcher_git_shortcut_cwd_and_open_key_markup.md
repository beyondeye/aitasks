---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui_switcher, tui]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-03 08:19
updated_at: 2026-11-03 09:08
---

## Origin

Spawned from **aitasks_go#t19_2** (the Go port of the TUI switcher overlay) during
Step 8b review. Both defects were found while recording a Pilot oracle of the REAL
`TuiSwitcherOverlay`, at aitasks `cd7ab3b` (framework 0.40.0). Re-check line numbers
against current main.

## Upstream defects

- `.aitask-scripts/lib/tui_switcher.py:1141-1145` (`action_shortcut_git`, at cd7ab3b)
  decides whether git is configured from `_build_tui_list()` called with **no root**.
  That reads the **current working directory's** `aitasks/metadata/project_config.yaml`,
  not the selected session's project. Everywhere else the switcher passes
  `self._selected_project_root()` (t814/t1099). So in a cross-session or cross-repo
  selection the `g` quick-jump can no-op although the selected project configures
  `git_tui`, or switch although it does not.
- `.aitask-scripts/lib/tui_switcher.py:772` (`_render_hint`, at cd7ab3b) interpolates
  `display_form(_OVERLAY_OPEN_KEY)` into Rich markup **unescaped**:
  `f"[{TUI_KEY_HINT_STYLE}]{display_form(_OVERLAY_OPEN_KEY)}/Esc[/] close"`. With the
  open key remapped to `[` (`shortcuts: shared: tui_switcher: "["`), mounting the overlay
  raises `textual.markup.MarkupError: closing tag '[/Esc[/]' does not match any open tag`,
  and the switcher cannot be opened at all.

## Diagnostic context

- The aitasks_go oracle generator (`app/switcher/testdata/gen_overlay_fixture.py` in
  aitasks_go) drives the real overlay with Pilot over 12 shortcut-override cases in
  single- and multi-session mode.
- The `open_bracket` case crashes in `_render_hint`.
- The `g` case's outcome changed with the generator's cwd until the cwd was pinned.
- The Go port reproduces the cwd behaviour faithfully for parity, and renders the `[`
  open key literally. Both are documented in aitasks_go
  `aidocs/porting/switcher_overlay.md` §5.

## Suggested fix

- `action_shortcut_git`: use `_build_tui_list(self._selected_project_root())`.
- `_render_hint`: escape the key (`rich.markup.escape` / `textual.markup.escape`) before
  interpolating. The same audit applies to other key-into-markup sites, e.g. `_hint_segment`
  with a `(` / `[` key.
- Add a regression test for each.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-03T07:08:37Z status=pass attempt=1 type=human
