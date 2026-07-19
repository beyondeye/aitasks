---
Task: t1149_3_config_wizard_flow.md
Parent Task: aitasks/t1149_chatlink_config_wizard_tui.md
Sibling Tasks: aitasks/t1149/t1149_4_wizard_docs_rewrite.md, aitasks/t1149/t1149_5_live_discord_validation.md, aitasks/t1149/t1149_6_manual_verification_chatlink_config_wizard_tui.md
Archived Sibling Plans: aiplans/archived/p1149/p1149_1_preflight_module.md, aiplans/archived/p1149/p1149_2_config_status_panel.md
Worktree: (current branch — fast profile, no worktree)
Branch: current
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-19 08:24
---

# p1149_3 — Config wizard flow

Textual ModalScreens launched from `ait chatlink` (footer key `w`): intake
channel → allowlist → deny mode / repo name → ceilings (pre-filled) → token →
summary (write + final preflight). Each step validates before advancing and
shows the specific error inline. Depends on t1149_1 only (not on the panel).

**Plan verified against source this session (no drift):**
- `chatlink/config.py` — ceiling constants/ranges `:28-39`,
  `SANDBOX_MEMORY_RE` `:33`, `DENY_MESSAGE_MODES` `:41`,
  `load_config_with_warnings` `:193` (collect-only), `load_config` `:301`
  (replays). Intake required keys `provider`/`workspace_id`/`conversation_id`
  (`_INTAKE_REQUIRED` `:51`), `thread_id` str-or-None.
- `chatlink/paths.py` — `write_token()` `:93` (0700 dir / 0600 file),
  `read_token()` `:109` (None when missing), `config_file()` `:118` (may
  return `None` when absent — the wizard's write path then defaults to
  `project_root() / CONFIG_DEFAULT_REL`).
- `chatlink/preflight.py` (t1149_1, shipped) — `run_cheap_checks() ->
  CheapChecks` (`results`/`config`/`config_warnings`),
  `run_expensive_checks(agent_timeout=AGENT_PROBE_TIMEOUT_S,
  docker_timeout=DOCKER_PROBE_TIMEOUT_S, resolver=None)`,
  `CheckResult(id, category, severity, message, fix_hint,
  daemon_refuse_message)`, categories `transport`/`runtime`/`operation`,
  operation id `explore_relay_agent_command`.
- `chatlink/chatlink_app.py` — key `w` is FREE (bindings: switcher chords,
  shortcuts, `q`, `r`). Panel (t1149_2) ships `_format_row` + severity
  glyphs, constructor seams `cheap_runner`/`expensive_runner` (I/O-free,
  stored callables), and the sanctioned worker shape
  (`_kick_expensive`/`_run_expensive`/`_apply_expensive`: pure worker body,
  `call_from_thread`, UI-thread-only mutation, debounce flag).
- `settings/settings_app.py` reference patterns all present at the cited
  lines: `NewProfileScreen` `:982`, `Input`+`on_input_submitted` routed to
  the accept method `:995,:1017`, step chaining `push_screen(...,
  callback=…)` `:1814-1855`, inline validation without dismissing
  (`AssignGroupScreen._accept_new` `:1119-1129`), `CycleField`/`FuzzySelect`
  enum fields, `SaveProfileConfirmScreen` `:1228`.
- `seed/chatlink_config.yaml` — source for the curated header comment
  block's content (condensed, not duplicated).
- `tests/test_chatlink_tui.sh` — heredoc style with `check(label, cond)`,
  fake `cheap_runner` + spy `expensive_runner` construction pattern, Pilot
  `run_test()` + `workers.wait_for_complete()` idiom to extend.

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
   ranges/defaults from config.py:28-39 constants; `deny_message_mode` ∈
   `DENY_MESSAGE_MODES`; `sandbox_memory` matches `SANDBOX_MEMORY_RE`;
   intake_channel required non-empty strings. Invalid input → inline error
   label, modal stays open (never dismiss on bad input).
5. **Summary step runs preflight** (cheap immediately; expensive with
   timeout + progress) and renders results via the shipped t1149_1 API
   (see verification notes above). Wizard copy describes configuring
   **the current Discord bug-report intake / explore-relay flow**, not all
   future ChatLink operations.
6. **No partial writes**: files written ONLY at the summary step; cancel at
   any step aborts cleanly.
7. Writer helper is Textual-free (`chatlink/config_write.py`) so it is
   headlessly unit-testable; wizard screens live in `chatlink/wizard.py`
   imported only by `chatlink_app.py` (daemon stays Textual-free).

## Design decisions (this session)

- **Malformed existing YAML degrades to explicit conflict, never silent
  replace.** `write_config` raises `ConfigWriteError` when the existing file
  is unparseable YAML or a non-mapping (merge is impossible). The wizard
  catches it at the summary step and shows an explicit confirm ("existing
  file is not valid YAML — Save will REPLACE it entirely"); only on that
  confirmation does it re-call with `allow_replace=True`. An empty /
  fully-commented file safe_loads to `None` → treated as `{}` (normal fresh
  path, no confirm).
- **Nested merge for mapping values — `intake_channel.metadata` and
  unknown subkeys survive.** The merge-never-drop contract extends one
  level into mappings: when a key exists in both the base config and the
  edits and BOTH values are mappings, `write_config` merges per-subkey
  (edited subkeys overlaid, all other subkeys carried through verbatim)
  instead of replacing the whole mapping. Concretely: the wizard edits
  only `provider`/`workspace_id`/`conversation_id`/`thread_id` inside
  `intake_channel`, so a pre-existing `intake_channel.metadata` (supported
  data — `config.py:177-183` normalizes it) and any future
  provider-specific nested field survive a wizard save untouched.
  Regression test pinned in step 4.
- **Failure-aware save sequence (config first, then token) with visible
  per-item state and idempotent retry.** The summary Save runs each write
  in its own try/except and renders a per-item outcome (`config: written`
  / `token: FAILED — <reason>`). If `token_writer` raises after the config
  `os.replace` landed, the wizard does NOT pretend the save failed
  atomically: it stays open in a recoverable error state that says exactly
  what persisted, and Save retries — re-writing the config is idempotent
  (same merged content), then the token write is re-attempted. Preflight
  runs only after all writes succeed. Test pinned in step 4.
- **`write_config` creates `path.parent`** (`mkdir(parents=True,
  exist_ok=True)`) before the tmp-file write, so a first-run or custom
  `chatlink.config` path with an absent parent directory works instead of
  crashing the tmp-file creation.
- **Navigation contract:** every step screen has Back / Next buttons plus
  Escape. `Next` validates then `dismiss(payload_dict)`; `Back` →
  `dismiss(BACK)` sentinel (previous screen re-pushed, state retained);
  Escape / Cancel button → `dismiss(None)` = abort the whole wizard (no
  writes — writes happen only at the summary step). Wizard state
  accumulates in a plain dict owned by the chaining controller.
- **Wizard-side probes reuse the app seams.** `action_wizard` threads the
  app's `_cheap_runner`/`_expensive_runner` (plus config-path/token seams)
  into the wizard so Pilot tests inject everything through the existing
  constructor-seam pattern; the SummaryScreen owns its own thread worker
  with the same pure-body / `call_from_thread` / debounce shape as the
  panel (`_run_expensive`/`_apply_expensive` idiom).
- **Shared row formatting lives in a new Textual-free
  `chatlink/preflight_render.py` — no circular import.** `chatlink_app.py`
  will import `wizard.py`, so `wizard.py` cannot import `ChatlinkApp` back
  to reuse `_format_row`. The glyph map (`SEVERITY_GLYPHS`) and
  `format_row(res) -> str` (current `ChatlinkApp._format_row` body) move
  into `preflight_render.py`; `chatlink_app.py` deletes its module-level
  `_SEVERITY_GLYPHS` and delegates `_format_row` to (or directly calls)
  `preflight_render.format_row`, and `wizard.py` imports the same helper.
  Textual-free (importable headlessly — covered by the writer suite's
  import path and the existing daemon/textual import guard pattern); the
  existing panel Pilot render assertions prove the extraction is
  behavior-preserving (rendered rows unchanged).
- **Writer test location:** new `tests/test_chatlink_wizard.sh` (headless —
  no Textual required) for `config_write.py` + `preflight_render.py`; the
  Pilot wizard walk extends `tests/test_chatlink_tui.sh`.

## Implementation steps

0. **`chatlink/preflight_render.py`** (NEW, Textual-free): `SEVERITY_GLYPHS`
   dict + `format_row(res: preflight.CheckResult) -> str` — moved verbatim
   from `chatlink_app.py` (`_SEVERITY_GLYPHS` :42, `_format_row` :212-218).
   `chatlink_app.py` imports it and delegates (its `_format_row` becomes a
   thin call or is replaced at call sites); `wizard.py` imports the same
   helper for the summary preflight rows. No Textual import (module is
   consumed by tests headlessly).
1. **`chatlink/config_write.py`** (Textual-free, PyYAML only):
   - `HEADER` — fixed curated comment block (condensed from
     `seed/chatlink_config.yaml`: what the file is, token-not-here note,
     pointer to the seed/docs for full key comments).
   - `class ConfigWriteError(Exception)` — carries a reason string.
   - `write_config(path, edits: dict, *, allow_replace: bool = False) ->
     None`: read existing file if present (`OSError` → treat as absent);
     `yaml.safe_load` → `None`→`{}`; parse error or non-mapping →
     `ConfigWriteError` unless `allow_replace` (then base = `{}`); merge
     `edits` onto the base mapping — top-level keys overlay, EXCEPT when
     both the base value and the edit value are mappings, which merge one
     level deep (edited subkeys overlaid, unedited subkeys — e.g.
     `intake_channel.metadata`, future provider fields — carried through
     verbatim); `path.parent.mkdir(parents=True, exist_ok=True)`; then
     `yaml.dump(merged, default_flow_style=False, sort_keys=False)` written
     under `HEADER` atomically (tmp file + `os.replace` in the target dir).
2. **`chatlink/wizard.py`** — module imported only by `chatlink_app.py`:
   - `BACK` sentinel; `WizardSeams` dataclass (config_path, token_reader,
     token_writer, cheap_runner, expensive_runner — all defaulting to the
     production `paths`/`preflight` functions at resolution time).
   - Step screens (each a `ModalScreen` shaped like `NewProfileScreen`:
     `Container(id="edit_dialog")`, title `Label`, fields, error `Label`,
     Back/Next/Cancel buttons, `BINDINGS` escape→cancel,
     `on_input_submitted` → same accept path as Next):
     - `IntakeChannelScreen` — Inputs: provider (pre-filled `discord`),
       workspace_id, conversation_id, thread_id (optional). Validation:
       three required non-empty (strip); inline error names the exact
       missing field.
     - `AllowlistScreen` — two Inputs, comma/space-separated ids for
       `allowed_user_ids` / `allowed_role_ids`. Both-empty is VALID
       (deny-by-default) but shows an inline warning line before advancing
       (mirrors the preflight `allowlist` warn copy).
     - `DenyRepoScreen` — `CycleField` for `deny_message_mode`
       (`DENY_MESSAGE_MODES`), Input for `repo_name` (optional; empty →
       key omitted from edits, not written as null).
     - `CeilingsScreen` — six Inputs pre-filled from current config or
       `config.py` defaults; validate ints against the `RANGE_*` bounds and
       `sandbox_memory` against `SANDBOX_MEMORY_RE`; inline error names the
       offending field and its range.
     - `TokenScreen` — `Input(password=True)`. If
       `seams.token_reader()` is non-None, show "token already present —
       leave empty to keep it" and allow empty submit (skip). Value is
       never echoed anywhere.
     - `SummaryScreen` — shows the collected values (token shown as
       "(will write)" / "(kept)" only), Save / Back / Cancel. On Save
       (failure-aware sequence per the design decision above):
       `config_write.write_config` in try/except (on `ConfigWriteError` →
       explicit replace-confirm sub-screen, then retry with
       `allow_replace=True` or abort back to summary); then
       `seams.token_writer(token)` in its own try/except, only if a token
       was entered — a token failure after the config landed renders
       `config: written` / `token: FAILED — <reason>` and keeps Save as a
       retry (config re-write idempotent); when all writes succeed, run
       preflight — cheap results rendered
       immediately, expensive via its own thread worker (progress line
       "… running expensive checks") with the `AGENT_PROBE_TIMEOUT_S` /
       `DOCKER_PROBE_TIMEOUT_S` defaults — rendered with
       `preflight_render.format_row` (step 0; same glyphs as the panel,
       no ChatlinkApp import); final copy
       shows the `./ait git add aitasks/metadata/chatlink_config.yaml &&
       ./ait git commit` hint. Explicit note this configures the Discord
       bug-report intake / explore-relay flow.
   - `start_wizard(app, seams)` — chaining controller: pre-fills state via
     `load_config_with_warnings(seams.config_path)` when the file exists
     (edit flow == create flow), then `push_screen(step,
     callback=…)`-chains the six steps, handling `BACK`/`None`/payload.
3. **`chatlink/chatlink_app.py`**: `Binding("w", "wizard", "Configure",
   show=True)` + `action_wizard` building `WizardSeams` from constructor
   seams (add I/O-free `wizard_config_path=None, token_reader=None,
   token_writer=None` params, resolved at call time like the existing
   runner seams) and calling `wizard.start_wizard(self, seams)`.
4. **Tests:**
   - NEW `tests/test_chatlink_wizard.sh` (headless writer suite): **import
     guard — `import chatlink.config_write` and
     `import chatlink.preflight_render` load without `textual` appearing
     in `sys.modules`; `preflight_render.format_row` output matches the
     glyph/fix-hint row shape the panel tests assert**;
     ceilings-only save preserves pre-existing `sandbox_env_passthrough:
     [FOO_KEY]` AND an unknown future key verbatim; **nested-merge
     regression: an intake_channel edit (new conversation_id) preserves
     pre-existing `intake_channel.metadata` and an unknown intake_channel
     subkey verbatim**; fresh-file path writes header + edits; **fresh path
     with a nonexistent parent directory succeeds (parent created)**;
     output round-trips through `load_config` with zero warnings for valid
     input; malformed existing YAML raises `ConfigWriteError` and leaves
     the file untouched; `allow_replace=True` replaces;
     empty/fully-commented file merges as `{}` without error.
   - `tests/test_chatlink_tui.sh` (Pilot walk, tmp-dir seams — never the
     real metadata dir): press `w` → fill every step via
     `pilot.press`/Input.value → Save → assert written YAML content
     (yaml.safe_load the file), token file exists with mode 0600, summary
     shows injected preflight results and the commit hint; invalid input
     keeps the modal open with the inline error; abort mid-wizard (Escape
     at step 3) leaves config + token files untouched; Back returns to the
     previous step with state retained; **token-writer failure path: a
     raising `token_writer` seam after Save → config file IS written, the
     summary renders the `token: FAILED` state and stays open, and a
     second Save with the seam fixed completes (config content unchanged,
     token written)**.
   - `tests/test_shortcut_scopes.py` stays green (chatlink module already
     swept; new ModalScreens own no customizable shortcuts).

## Risk

### Code-health risk: low
- Writer silently drops/clobbers unedited keys in the team-shared,
  checked-in config — including nested `intake_channel` subkeys
  (`metadata`, future provider fields) the UI does not expose · severity:
  medium · → mitigation: in-plan — pinned merge-never-drop contract
  extended one level into mappings, preservation unit tests
  (`sandbox_env_passthrough` + unknown top-level key + nested
  intake_channel regression), malformed-YAML degrades to explicit
  replace-confirm (never a silent guess), atomic tmp+`os.replace` write
  with parent-dir creation.
- Save-time partial failure (config landed, token write raised) leaves a
  half-applied save presented as all-or-nothing · severity: medium · →
  mitigation: in-plan — failure-aware per-item save state on the summary
  screen (exactly what persisted is shown), idempotent Save retry,
  token-writer-failure Pilot test.
- Token mishandling (value rendered somewhere, wrong file modes) ·
  severity: medium · → mitigation: in-plan — `password=True` Input,
  presence-only display everywhere, reuse of `paths.write_token()`
  (0700/0600), Pilot test asserts the 0600 mode and that the value never
  appears in rendered text.
- Wizard-side expensive-probe worker racing the panel worker / freezing
  the UI · severity: low · → mitigation: in-plan — SummaryScreen owns its
  own worker with the panel's proven pure-body / `call_from_thread` /
  debounce shape and explicit probe timeouts; runners injected in tests.
- Pilot tests writing to the real metadata dir · severity: low · →
  mitigation: in-plan — all paths/writers injected via `WizardSeams`;
  abort-leaves-files-untouched assertion.

### Goal-achievement risk: low
- Multi-step modal UX misses expectations (back-navigation, pre-fill,
  error placement) in ways only visible interactively · severity: low ·
  → mitigation: in-plan — explicit Back/Escape navigation contract +
  state-retained Back test; the existing t1149_6 manual-verification
  sibling walks the full flow live.

### Planned mitigations
None — all identified risks are mitigated in-plan by the pinned contracts
and tests; the pre-existing t1149_6 manual-verification sibling already
covers the live-flow "after" verification, so no separate before/after
mitigation tasks are proposed.

## Verification

- `bash tests/test_chatlink_wizard.sh` — writer suite: preservation (`sandbox_env_passthrough` + unknown top-level key + nested `intake_channel.metadata`/unknown-subkey survive), fresh file (incl. absent parent dir), round-trip via `load_config` with zero warnings, malformed-YAML conflict path, `allow_replace`, atomicity; Textual-free import guard for `config_write` + `preflight_render`.
- `bash tests/test_chatlink_tui.sh` — wizard Pilot walk end-to-end writes the expected config + 0600 token; inline-error keeps modal open; abort leaves files untouched; Back retains state; token-writer failure renders per-item state and retries; existing smoke/panel/daemon-guard checks stay green (panel rows unchanged proves the `preflight_render` extraction is behavior-preserving).
- `python tests/test_shortcut_scopes.py` — chatlink scope sweep stays green.
- Manual: `ait chatlink` → `w` → complete flow → config written to working tree, token file 0600, final preflight screen shows results; the TUI made no git commit.

Refer to Step 9 (Post-Implementation) of the task workflow for merge/archival.
