---
Task: t1149_1_preflight_module.md
Parent Task: aitasks/t1149_chatlink_config_wizard_tui.md
Sibling Tasks: aitasks/t1149/t1149_2_config_status_panel.md, aitasks/t1149/t1149_3_config_wizard_flow.md, aitasks/t1149/t1149_4_wizard_docs_rewrite.md, aitasks/t1149/t1149_5_live_discord_validation.md
Archived Sibling Plans: aiplans/archived/p1149/p1149_*_*.md
Worktree: (per picking profile)
Branch: (per picking profile)
Base branch: main
---

# p1149_1 — Preflight module (foundation)

Extract the daemon's startup check chain + `config.load_config` per-key
warnings into a shared, structured, **Textual-free** `chatlink/preflight.py`,
and rewire `daemon.serve()` onto it **behavior-preserving** (byte-identical
refuse messages + exit codes). This module is the step-check engine consumed
by the t1149_2 status panel and the t1149_3 wizard.

## Pinned contracts (parent plan aiplans/p1149_chatlink_config_wizard_tui.md)

1. `CheckResult`: `id`, `severity` ∈ {pass, warn, fail}, TUI-friendly
   `message`, `fix_hint`, and for fail results `daemon_refuse_message` — the
   EXACT legacy `_refuse()` text. `serve()` emits
   `_refuse(result.daemon_refuse_message)` for the first failing check in the
   legacy order, so refusal text has exactly one definition.
2. Cheap vs expensive probe split: `run_cheap_checks()` (config path, YAML /
   mapping, intake_channel, allowlist non-empty [warn], token present) vs
   `run_expensive_checks(timeout=…)` (agent argv dry-run, docker binary
   [warn], docker image `ait-chatlink-agent` [warn, NEW]). Expensive probes
   take explicit timeouts and fail closed (timeout/OSError → fail/warn
   result, never a hang).
3. `load_config` fail-closed semantics unchanged; add
   `load_config_with_warnings(path) -> (cfg_or_None, list[str])`.
4. No Textual import — guard-tested.

## Implementation steps

1. **`config.py`**: thread an optional warning-collector through the `_warn`
   sites. Simplest shape: module-level `_warn(msg, collect: list|None)` is
   invasive; instead add `load_config_with_warnings(path)` that temporarily
   installs a collector (e.g. pass a `warn` callable parameter down the
   helpers `_clamped_int`/`_str_list`/`_env_name_list`/
   `_normalize_intake_channel`, defaulting to the stderr `_warn`).
   `load_config(path)` delegates to the new function and discards the list.
   All existing callers and tests stay green.
2. **`preflight.py`**: `CheckResult` dataclass; check ids (stable, consumed by
   t1149_2/t1149_3): `config_file`, `config_yaml`, `intake_channel`,
   `allowlist`, `token`, `agent_command`, `docker_binary`, `docker_image`,
   plus per-key warn results `config_key:<key>` from the collector.
3. Move `resolve_explore_relay_argv()` (and its `parse_dry_run_argv` helper,
   `daemon.py:700-734`) into `preflight.py`; add a `timeout` parameter on the
   `subprocess.run` call. `daemon.py` re-imports it (keep a name re-export in
   daemon for any external references; check tests for imports).
4. Docker image check: `docker image inspect ait-chatlink-agent`
   (`subprocess.run`, timeout, capture) — warn severity, fix hint pointing at
   `docker build -t ait-chatlink-agent .aitask-scripts/chatlink/docker/`.
5. **Rewire `serve()`** (`daemon.py:737-784`): run cheap checks, then agent
   check, preserving today's order (config → intake → token → agent);
   first fail → `_refuse(daemon_refuse_message)`; docker warn → same stderr
   warning text as today. The allowlist and docker-image checks are NEW and
   must NOT refuse or add stderr output on the daemon path beyond what exists
   today (allowlist: panel-only info; docker image: panel-only) — the daemon
   consumes only the checks it consumed before, plus prints nothing new.
6. **Tests**: extend `tests/test_chatlink_daemon.sh` (each refusal path:
   byte-identical message + exit code); new `tests/test_chatlink_preflight.sh`
   (result shape; probe split; pinned `daemon_refuse_message` per id;
   timeouts fail closed; Textual-free import guard:
   `import chatlink.preflight` then assert no `textual` in `sys.modules`).

## Verification

- `bash tests/test_chatlink_daemon.sh` — every legacy refusal path byte-identical (message + exit code).
- `bash tests/test_chatlink_preflight.sh` — result shape, probe split, pinned refusal strings, fail-closed timeouts, Textual-free guard.
- `bash tests/test_chatlink_config.sh` — existing config tests still green; `load_config_with_warnings` returns the same warnings `_warn` printed.
- `bash tests/test_chatlink_tui.sh` — daemon import guard intact.

Refer to Step 9 (Post-Implementation) of the task workflow for merge/archival.
