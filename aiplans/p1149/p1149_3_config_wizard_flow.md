---
Task: t1149_3_config_wizard_flow.md
Parent Task: aitasks/t1149_chatlink_config_wizard_tui.md
Sibling Tasks: aitasks/t1149/t1149_1_preflight_module.md, aitasks/t1149/t1149_2_config_status_panel.md, aitasks/t1149/t1149_4_wizard_docs_rewrite.md, aitasks/t1149/t1149_5_live_discord_validation.md
Archived Sibling Plans: aiplans/archived/p1149/p1149_*_*.md
Worktree: (per picking profile)
Branch: (per picking profile)
Base branch: main
---

# p1149_3 — Config wizard flow

Textual ModalScreens launched from `ait chatlink` (footer key `w`): intake
channel → allowlist → deny mode / repo name → ceilings (pre-filled) → token →
summary (write + final preflight). Each step validates before advancing and
shows the specific error inline. Depends on t1149_1 only (not on the panel).

## Pinned contracts (parent plan aiplans/p1149_chatlink_config_wizard_tui.md)

1. **Merge, never drop.** Writer: safe_load existing config (if any) →
   overlay wizard-edited keys → carry through VERBATIM every unedited key
   (explicitly `sandbox_env_passthrough` + unknown/future keys) → yaml.dump
   under a fixed curated header comment block. PyYAML only (no ruamel).
   Unit test: pre-existing `sandbox_env_passthrough` survives a save.
2. **Exposed keys:** `intake_channel` (provider/workspace_id/conversation_id
   + optional thread_id), `allowed_user_ids`, `allowed_role_ids`,
   `deny_message_mode`, `repo_name`, six ceilings (`max_concurrent_sandboxes`,
   `intake_rate_per_user_per_hour`, `sandbox_memory`, `sandbox_cpus`,
   `sandbox_pids`, `sandbox_wall_clock_s`). Not exposed but preserved:
   everything else.
3. **Files only — never commits, never commands the daemon** (per
   tui_conventions.md). Config → working tree + `./ait git` commit hint on
   the summary screen. Token → existing `paths.write_token()`
   (chatlink/paths.py:93; 0700 dir / 0600 file); token Input uses
   `password=True`; token presence shown, value never rendered.
4. **Per-step validation** = the config.py/preflight logic: ceiling
   ranges/defaults from config.py:28-42 constants; `deny_message_mode` ∈
   `DENY_MESSAGE_MODES`; `sandbox_memory` matches `SANDBOX_MEMORY_RE`;
   intake_channel required non-empty strings. Invalid input → inline error
   label, modal stays open (never dismiss on bad input).
5. **Summary step runs preflight** (cheap immediately; expensive with
   timeout + progress) and renders results.
6. **No partial writes**: files written ONLY at the summary step; cancel at
   any step aborts cleanly.
7. Writer helper is Textual-free (`chatlink/config_write.py`) so it is
   headlessly unit-testable; wizard screens live in `chatlink/wizard.py`
   imported only by `chatlink_app.py` (daemon stays Textual-free).

## Reference patterns (all .aitask-scripts/settings/settings_app.py)

- ModalScreen shape + dismiss(payload|None): `NewProfileScreen` :982.
- `Input` + `on_input_submitted` routed to the accept method: :995, :1087.
- Step chaining: `push_screen(Screen, callback=…)`, each callback pushes the
  next: :1814-1855.
- Inline validation WITHOUT dismissing: `AssignGroupScreen._accept_new`
  :1119-1129.
- Enum field: `CycleField` (deny_message_mode) / `FuzzySelect` :944.
- Three-way confirm dismiss: `SaveProfileConfirmScreen` :1228.
- Shortcut scope: chatlink module already swept; confirm
  `tests/test_shortcut_scopes.py` stays green.

## Implementation steps

1. `chatlink/config_write.py`: `write_config(path, edits: dict) -> None`
   (merge semantics + curated header). Unit tests: merge preserves
   `sandbox_env_passthrough` and unknown keys; fresh-file path; output
   round-trips through `load_config` with zero warnings for valid input.
2. `chatlink/wizard.py` screens: IntakeChannelScreen, AllowlistScreen,
   DenyRepoScreen, CeilingsScreen, TokenScreen (skippable when
   `paths.read_token()` present), SummaryScreen (writes config via
   config_write; token via `paths.write_token()` only if entered; runs
   preflight; shows results + `./ait git` commit hint).
3. Pre-fill every step from `load_config_with_warnings(paths.config_file())`
   when a config exists (edit flow == create flow); ceilings default from
   config.py constants when unset.
4. ChatlinkApp: `Binding("w", "wizard", "Configure", show=True)` +
   `action_wizard`. Back/cancel navigation per screen; abort leaves both
   files untouched.
5. Injectable config-path (and token-path) params on the wizard entry so
   Pilot tests write to a tmp dir, never the real metadata dir.
6. Tests: Pilot end-to-end walk in `tests/test_chatlink_tui.sh` (fill steps,
   save, assert written YAML content + token file mode); writer unit tests
   (see 1) in `tests/test_chatlink_config.sh` or a new
   `tests/test_chatlink_wizard.sh`.

## Verification

- `bash tests/test_chatlink_tui.sh` — wizard Pilot walk end-to-end writes the expected config.
- Writer unit test — pre-existing `sandbox_env_passthrough: [FOO_KEY]` and an unknown future key survive a ceilings-only save; output parses via `load_config` with the same effective values.
- Manual: `ait chatlink` → `w` → complete flow → config written to working tree, token file 0600, final preflight screen shows results; the TUI made no git commit.
- Aborting mid-wizard leaves the config file and token file untouched.

Refer to Step 9 (Post-Implementation) of the task workflow for merge/archival.
