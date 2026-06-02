---
Task: t867_manual_verification_fix_userconfig_yaml_writer_style_collisi.md
Base branch: main
plan_verified: []
---

# Auto-Verification Log: userconfig.yaml writer-style collision (t867)

Manual-verification task verifying the t864 fix (writer-style collision in
`aitasks/metadata/userconfig.yaml`). Run autonomously via `/aitask-pick 867`
(profile `fast`). All three checklist items reached a terminal `pass` state.

Verification was performed against **isolated `TASK_DIR` scratch configs** and
**live TUI launches** — the user's real `aitasks/metadata/userconfig.yaml` was
never mutated.

## Execution Log

### Item 1 — board + monitor draw without an import-time ParserError
- **Item text:** Launch ait board (and one other TUI, e.g. ait monitor) on a
  workspace whose userconfig.yaml has both shortcuts and last_used_labels —
  confirm they draw without a yaml ParserError crash at import.
- **Approach:** CLI/import-path inspection + live TUI interaction (tmux).
- **Action run:**
  1. Built an isolated `TASK_DIR` with a both-blocks `userconfig.yaml`
     (flow-style `last_used_labels: [a, b]` + a block `shortcuts:` map for
     `board` and `monitor`) and ran the exact import-time crash site:
     `keybinding_registry.load_user_overrides()` (board AND monitor reach this
     via `tui_switcher`, confirmed at `tui_switcher.py:57`).
  2. Repeated against a **deliberately corrupted** config (the original t864
     orphaned-`- item` continuation shape, confirmed invalid YAML → `ParserError`).
  3. Live-launched `./ait board` and `./ait monitor` in detached tmux sessions
     against the real (valid) config; captured panes.
- **Output (trimmed):**
  - both-blocks → `{'board': {'pick': 'p', 'archive': 'a'}, 'monitor': {'refresh': 'r'}}`, exit 0.
  - corrupted → `keybinding_registry: ignoring malformed … expected <block end>, but found '-'`, returns `{}`, exit 0 (no crash).
  - board drew the full Kanban UI; monitor drew the agent panel — neither pane showed a traceback or `ParserError`.
- **Verdict:** pass

### Item 2 — Python shortcut-save then bash label-write leaves valid YAML
- **Item text:** End-to-end cycle: open the in-TUI shortcut editor and save a
  custom shortcut (Python shortcut_persist writer), then run `ait create` and
  pick labels (bash set_last_used_labels writer); re-launch ait board and
  confirm userconfig.yaml is valid YAML with flow-style last_used_labels and the
  shortcuts block intact.
- **Approach:** Drive the **real** writers against an isolated `TASK_DIR`.
- **Action run:** `shortcut_persist.save_override('board','pick','P')` +
  `save_override('board','archive','X')` (the in-TUI shortcut editor writer),
  then bash `set_last_used_labels "ait_settings,execution_profiles,verification"`
  (the `ait create` writer); then re-read overrides.
- **Output (trimmed):** valid YAML ✓; `last_used_labels: [ait_settings, execution_profiles, verification]` (flow) ✓; `pick: P` / `archive: X` survived ✓; no orphaned `- item` lines ✓; reload → `{'board': {'pick': 'P', 'archive': 'X'}}`.
- **Verdict:** pass

### Item 3 — get_last_used_labels reads back for the ait create pre-fill
- **Item text:** Confirm `ait create`'s interactive label picker pre-fills the
  previously-used labels after the shortcut-save + create cycle
  (get_last_used_labels reads correctly).
- **Approach:** CLI invocation of both read paths.
- **Action run:** bash `get_last_used_labels` and the
  `userconfig_persist.py get-labels` CLI it delegates to.
- **Output (trimmed):** both returned `ait_settings,execution_profiles,verification` (the labels set in item 2).
- **Verdict:** pass

## Corroborating regression suites
- `tests/test_userconfig_writer_collision.sh` — 13/13 pass.
- `tests/test_last_used_labels.sh` — 18/18 pass.

## Cleanup
- Removed scratch dir `${TMPDIR}/auto_verify_867/`.
- Killed tmux sessions `av867_board`, `av867_monitor`.
- No user-owned files mutated (only the checklist task file's state).
