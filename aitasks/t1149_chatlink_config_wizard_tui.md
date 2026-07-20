---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [tui]
gates: [risk_evaluated]
children_to_implement: [t1149_4]
created_at: 2026-07-15 10:36
updated_at: 2026-07-20 12:37
boardidx: 50
---

## Goal

Add a configuration wizard to the `ait chatlink` TUI so the gateway can be configured intuitively instead of hand-editing files, plus config-status visuals in the TUI, with per-step validation that surfaces configuration errors as the user goes.

Replaces the manual steps documented in `website/content/docs/workflows/bug-report-intake.md` from the "Configure the gateway" section onward (hand-editing the seeded YAML, the mkdir/chmod/printf token dance, unverified docker image build).

## Current state (exploration findings)

**Config surface to manage:**
- `aitasks/metadata/chatlink_config.yaml` — checked-in; seeded fully commented-out from `seed/chatlink_config.yaml`. Keys: `intake_channel` (provider/workspace_id/conversation_id), `allowed_user_ids`, `allowed_role_ids`, `deny_message_mode`, `repo_name`, 6 sandbox ceilings, `sandbox_env_passthrough`.
- Bot token: gitignored per-machine `aitasks/metadata/chatlink_sessions/bot_token` (0600). Helper **`paths.write_token()` already exists** (`.aitask-scripts/chatlink/paths.py:93`) with correct 0700/0600 handling — the wizard token step should call it.
- Docker sandbox image `ait-chatlink-agent`: manual build, never verified anywhere today (missing image only surfaces as a failed session).

**Validation logic exists but only at daemon startup:**
- `serve()` in `.aitask-scripts/chatlink/daemon.py` (~line 737) runs the full refuse chain: config path resolvable → YAML parses → `intake_channel` valid → token present → explore-relay agent resolvable (`ait codeagent invoke explore-relay --headless --dry-run`) → docker present (warn-only). Each refusal has a distinct message.
- `config.py::load_config` per-key warnings go to stderr and are lost — nothing structured a TUI can display.

**TUI today:** `.aitask-scripts/chatlink/chatlink_app.py` is minimal read-only (status line from audit mtime, sessions DataTable, audit tail). Zero config awareness — broken config just shows "no audit log yet (gateway never started?)".

**Reusable patterns:** `settings/settings_app.py` has ModalScreen + Input + FuzzySelect + multi-step screen patterns. TUI rules in `aidocs/framework/tui_conventions.md` apply (TuiSwitcherMixin, ShortcutsMixin, launcher script conventions).

## Proposed shape

1. **Shared preflight module** (e.g., `chatlink/preflight.py`): extract the daemon's startup check chain + `load_config` per-key warnings into structured per-check results (id, severity pass/warn/fail, message, fix hint). Consumed by BOTH the daemon refuse-path (behavior-preserving: same messages, same exit codes) and the TUI. This is the step-check engine for the wizard.
2. **Config-status panel in the TUI**: render preflight results as a visual checklist (config file, intake channel, allowlist non-empty, token, agent command, docker binary + image) so the current config state is visible at a glance in `ait chatlink`.
3. **Wizard flow** (new Textual screens, launched from the TUI, e.g. key `w`): step through intake channel → allowlist → deny mode / repo name → ceilings (defaults pre-filled) → token entry (via `paths.write_token()`) → final preflight run. Each step validates before advancing and shows the specific error.
4. **YAML writing strategy** — decide during planning: generate a clean file vs. comment-preserving in-place edit. Note the file is checked in and shared with the team; the wizard writes via `./ait git` semantics if committing.
5. **Optional live Discord validation step**: `DiscordAdapter.connect(token)` (`.aitask-scripts/chat/discord_adapter.py:632`) can verify live: token validity, privileged intents (Message Content / Server Members), channel visibility, bot permissions — catching the top rows of the docs troubleshooting table at config time. Both Textual and discord.py are asyncio. Scope/depth to decide at planning time (may be a child task).
6. **Docs update**: rewrite the "Configure the gateway" + walkthrough sections of `bug-report-intake.md` around the wizard (keep hand-edit path documented as the fallback).

## Constraints

- The TUI stays read-only with respect to the *daemon* (never commands it); the wizard writes config/token files only.
- Daemon remains Textual-import-free (guard-tested) — the preflight module must not import Textual.
- Fail-closed semantics of `load_config` must not change.
- This is a large task — expect decomposition into children at planning time (preflight module, status panel, wizard, live checks, docs).
