---
priority: medium
effort: medium
depends: [t1149_1]
issue_type: feature
status: Implementing
labels: [tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1149
created_at: 2026-07-15 18:44
updated_at: 2026-07-17 10:42
---

## Context

Part of t1149 (chatlink config wizard TUI). The `ait chatlink` TUI (`.aitask-scripts/chatlink/chatlink_app.py`) is a minimal read-only status view (status line from audit mtime, sessions DataTable, audit tail). It is config-blind: a broken gateway config just shows "no audit log yet (gateway never started?)".

This child renders the t1149_1 preflight results as a visual config checklist in the TUI, so config state (config file, intake channel, allowlist, token, explore-relay agent command, docker binary + image) is visible at a glance. Depends on t1149_1 (the preflight module pins the result contract). Panel copy describes configuring the current Discord bug-report intake / explore-relay flow — not all possible future ChatLink operations (t1149_1 scope/naming contract).

## Pinned contracts (from the approved parent plan, aiplans/p1149_chatlink_config_wizard_tui.md)

1. **Cost boundary — the panel must stay passive/responsive.** The existing 2s polling loop (`REFRESH_INTERVAL_S`, `_refresh_view`) runs ONLY `preflight.run_cheap_checks()` (file/YAML/in-memory — never a subprocess). The EXPENSIVE checks (agent dry-run, docker binary, docker image) run on a Textual worker / background thread (`@work(thread=True)` or `run_worker`), with each probe's explicit timeout, and their results are CACHED — refreshed only on-demand (the existing `r` refresh key and a one-shot kick on mount), never on every poll tick. The panel shows the last cached expensive result with an age / "checking..." state so slow/absent Docker or a slow dry-run never blocks the screen.
2. **`__init__` stays I/O-free** (the `--smoke` contract): resolve paths lazily as the existing `_resolve()` does; no preflight call in the constructor.
3. **Read-only wrt the daemon** — the panel observes; it never commands the gateway.
4. **Severity glyph/style**: keep rendering assertable at the text level (prefer `markup=False` and plain glyph prefixes like ok/warn/fail markers) per the TUI render-level verification convention.

## Key files to modify

- `.aitask-scripts/chatlink/chatlink_app.py` — new checklist panel widget (a `Static` per check or one Static rendering all rows), composed above/beside the sessions table; wire cheap checks into `_refresh_view`; add a thread worker for expensive checks triggered from `on_mount` and `action_refresh`.
- `tests/test_chatlink_tui.sh` — extend the Pilot test: panel renders cheap-check rows; a spy/monkeypatched expensive-probe seam proves the poll path never invokes it (negative control), while the on-demand refresh path does.

## Reference patterns

- Existing polling: `chatlink_app.py:106-135` (`on_mount` interval, `_refresh_view`, `_status_text`).
- Preflight API (t1149_1, as shipped): `chatlink/preflight.py` — `run_cheap_checks() -> CheapChecks` (`results`/`config`/`config_warnings`; poll-safe), per-check expensive functions (`check_explore_relay_agent_command`, `check_docker_binary`, `check_docker_image`) + `run_expensive_checks(agent_timeout=AGENT_PROBE_TIMEOUT_S, docker_timeout=DOCKER_PROBE_TIMEOUT_S)`, `CheckResult(id, category, severity, message, fix_hint, daemon_refuse_message)` with categories `transport`/`runtime`/`operation` (group rows by bucket; operation id is `explore_relay_agent_command`).
- Textual worker: `self.run_worker(..., thread=True)` or `@work(thread=True)` — post results back via `call_from_thread` / reactive assignment.
- Render-level test style: assert `widget.render().plain` (or query text content) — see existing `tests/test_chatlink_tui.sh` Pilot section.
- TUI conventions: `aidocs/framework/tui_conventions.md` (footer bindings show=True with labels; scope guards).

## Implementation plan

1. Add a `#preflight_panel` widget to `compose()` with fixed height (rows = number of checks) and a title row.
2. `_refresh_view` additionally renders cheap results each tick; expensive rows render from a cached dict `{check_id: (result, timestamp)}` with "checking..." placeholder while the worker runs.
3. Worker method `_run_expensive_checks()` (thread worker, explicit per-probe timeout from preflight) updates the cache and requests a re-render on completion; triggered from `on_mount` (one-shot) and `action_refresh`.
4. Keep footer `r` binding semantics: refresh now also re-kicks the expensive worker (debounce: ignore if one is already running).
5. Tests: Pilot renders expected row text for a synthetic config dir; spy asserts poll ticks don't call the expensive seam.

## Verification

- `bash tests/test_chatlink_tui.sh` passes (smoke + Pilot render + poll-never-runs-expensive negative control).
- `ait chatlink` against a broken/partial config shows the checklist with per-check severity and fix hints; against a valid config shows all-pass.
- Panel stays responsive with docker stopped/absent (expensive rows show cached/timeout state, UI never freezes).
