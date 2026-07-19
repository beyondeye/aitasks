---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: high
depends: [t1149_1]
issue_type: feature
status: Implementing
labels: [tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1149
implemented_with: claudecode/fable5
created_at: 2026-07-15 18:45
updated_at: 2026-07-19 08:28
---

## Context

Part of t1149 (chatlink config wizard TUI). Today configuring the gateway means hand-uncommenting `aitasks/metadata/chatlink_config.yaml` and a `mkdir/chmod/printf` token dance. This child adds the configuration wizard itself: Textual ModalScreens launched from the `ait chatlink` TUI (footer key `w`), stepping through intake channel -> allowlist -> deny mode / repo name -> ceilings (defaults pre-filled) -> token entry -> final preflight run. Each step validates before advancing and shows the specific error inline.

Depends on t1149_1 (preflight result contract + `load_config_with_warnings`). Does NOT depend on t1149_2 (the panel); both consume preflight independently.

## Pinned contracts (from the approved parent plan, aiplans/p1149_chatlink_config_wizard_tui.md)

1. **YAML writing = merge, never drop.** The writer: (a) `yaml.safe_load`s the EXISTING config file (if any) into a dict; (b) overlays the wizard-edited keys; (c) carries through VERBATIM every key the wizard did not edit — explicitly including `sandbox_env_passthrough` and any unknown/future key; (d) `yaml.dump`s the merged mapping under a fixed curated header comment block (PyYAML only — no ruamel.yaml; repo has no such dep). A unit test asserts a pre-existing `sandbox_env_passthrough` survives a wizard save untouched.
2. **Field coverage (pinned).** Wizard-exposed keys: `intake_channel` (provider/workspace_id/conversation_id + optional thread_id), `allowed_user_ids`, `allowed_role_ids`, `deny_message_mode`, `repo_name`, and the six ceilings (`max_concurrent_sandboxes`, `intake_rate_per_user_per_hour`, `sandbox_memory`, `sandbox_cpus`, `sandbox_pids`, `sandbox_wall_clock_s`). NOT exposed but preserved: `sandbox_env_passthrough` + unknown keys.
3. **Writes files only — never commits, never commands the daemon.** Per `aidocs/framework/tui_conventions.md` (no auto-commit/push of project config from runtime TUIs): config file written to the working tree; final screen tells the user to review and commit with `./ait git add aitasks/metadata/chatlink_config.yaml && ./ait git commit`. Token written via the EXISTING `paths.write_token()` (`.aitask-scripts/chatlink/paths.py:93` — correct 0700 dir / 0600 file); token file is gitignored, never committed, and the Input for it should use `password=True`.
4. **Per-step validation** uses the same validation logic as config.py/preflight (ranges from `config.py:28-42` constants; intake_channel required non-empty strings; `deny_message_mode` in `DENY_MESSAGE_MODES`; `sandbox_memory` matches `SANDBOX_MEMORY_RE`). Invalid input -> inline error label, modal stays open (never dismiss on bad input).
5. **Final step runs preflight** (cheap checks immediately; expensive checks with timeout, showing progress) and renders the results — the user leaves the wizard knowing whether the gateway would start. Shipped API (t1149_1): `run_cheap_checks() -> CheapChecks` + `run_expensive_checks(agent_timeout=AGENT_PROBE_TIMEOUT_S, docker_timeout=DOCKER_PROBE_TIMEOUT_S)`; `CheckResult(id, category, severity, message, fix_hint, daemon_refuse_message)`, categories `transport`/`runtime`/`operation`, operation id `explore_relay_agent_command`. Wizard copy describes configuring the current Discord bug-report intake / explore-relay flow, not all future ChatLink operations (t1149_1 scope/naming contract).
6. **Daemon stays Textual-free** — wizard code lives in `chatlink_app.py` or a new `chatlink/wizard.py` imported only by it. The YAML-writer helper must be importable without Textual (put it in a non-Textual module, e.g. `chatlink/config_write.py`, so it is unit-testable headlessly).

## Key files to modify

- NEW `.aitask-scripts/chatlink/config_write.py` — merge-and-write YAML helper (Textual-free).
- NEW `.aitask-scripts/chatlink/wizard.py` (Textual screens) OR extend `chatlink_app.py` — wizard ModalScreens + step chaining.
- `.aitask-scripts/chatlink/chatlink_app.py` — `Binding("w", "wizard", "Configure", show=True)` + `action_wizard` pushing the first screen.
- `tests/test_chatlink_tui.sh` — Pilot-driven wizard walk (fill steps, save, assert file content).
- NEW or extended test for the writer (round-trip + preservation), e.g. in `tests/test_chatlink_config.sh` or a dedicated `tests/test_chatlink_wizard.sh`.

## Reference patterns (all in .aitask-scripts/settings/settings_app.py)

- ModalScreen shape: `__init__` data, `BINDINGS` escape->cancel, `Container(id="edit_dialog")`, buttons, `self.dismiss(payload_or_None)` — e.g. `NewProfileScreen` (:982).
- `Input` + `on_input_submitted` routing to the same accept method (:995, :1087).
- Multi-step chaining: `push_screen(Screen(...), callback=self._handle_...)` — each callback pushes the next screen (:1814-1855).
- Inline validation WITHOUT dismissing: `AssignGroupScreen._accept_new` (:1119-1129) — error `Label` updated, return without dismiss.
- Enum fields: `CycleField` (deny_message_mode: ignore/ephemeral) or `FuzzySelect` (:944, :1077).
- Three-way confirm dismiss: `SaveProfileConfirmScreen` (:1228).
- Ceiling ranges/defaults: `chatlink/config.py:28-42` constants.
- Shortcut scope: `chatlink` module is already swept — new sub-screens need `_shortcuts_scope` only if they own customizable shortcuts; verify with `tests/test_shortcut_scopes.py`.

## Implementation plan

1. `config_write.py`: `write_config(path, edits: dict) -> None` implementing the pinned merge semantics + curated header; unit tests (existing-file merge incl. `sandbox_env_passthrough`; fresh file; output round-trips through `load_config` with zero warnings for valid input).
2. Wizard step screens: IntakeChannelScreen, AllowlistScreen, DenyRepoScreen, CeilingsScreen (pre-filled from current config or defaults), TokenScreen (password Input; skip allowed if token already present — show `paths.read_token()` presence, never the value), SummaryScreen (writes config via config_write, token via `paths.write_token()` only if entered, then runs preflight and shows results + the ./ait git commit hint).
3. Pre-fill every step from `load_config_with_warnings(paths.config_file())` when a config exists (edit flow == create flow).
4. `w` binding + action in ChatlinkApp; back-navigation between steps (each screen's cancel returns to previous or aborts wizard cleanly, no partial writes — files written ONLY at the summary step).
5. Tests: Pilot walk end-to-end writing to a tmp config path (inject config path — add an injectable path param to the wizard entry so tests never touch the real metadata dir).

## Verification

- `bash tests/test_chatlink_tui.sh` passes (wizard Pilot walk).
- Writer unit test: pre-existing `sandbox_env_passthrough: [FOO_KEY]` survives a save that edits only ceilings; unknown future key survives; output parses via `load_config` with the same effective values.
- Manual: `ait chatlink` -> `w` -> complete flow -> config file written, token file 0600, final preflight screen shows results; no git commit was made by the TUI.
- Aborting mid-wizard leaves both files untouched.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-19T05:28:11Z status=pass attempt=1 type=human
