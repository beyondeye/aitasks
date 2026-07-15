---
Task: t1149_2_config_status_panel.md
Parent Task: aitasks/t1149_chatlink_config_wizard_tui.md
Sibling Tasks: aitasks/t1149/t1149_1_preflight_module.md, aitasks/t1149/t1149_3_config_wizard_flow.md, aitasks/t1149/t1149_4_wizard_docs_rewrite.md, aitasks/t1149/t1149_5_live_discord_validation.md
Archived Sibling Plans: aiplans/archived/p1149/p1149_*_*.md
Worktree: (per picking profile)
Branch: (per picking profile)
Base branch: main
---

# p1149_2 — Config-status panel in the chatlink TUI

Render t1149_1 preflight results as a visual checklist in
`.aitask-scripts/chatlink/chatlink_app.py` so config state (config file,
intake channel, allowlist, token, explore-relay agent command, docker binary
+ image) is visible at a glance. Depends on t1149_1 (result contract pinned
there). Panel copy describes configuring **the current Discord bug-report
intake / explore-relay flow**, not all future ChatLink operations.

**Shipped preflight API (t1149_1 — consume as-is):**
- `run_cheap_checks() -> CheapChecks` (`results: list[CheckResult]`,
  `config`, `config_warnings`) — poll-safe, no subprocess.
- Per-check expensive functions: `check_explore_relay_agent_command(resolver=…,
  timeout=…) -> (CheckResult, argv)`, `check_docker_binary()`,
  `check_docker_image(timeout=…)`; TUI convenience
  `run_expensive_checks(agent_timeout=AGENT_PROBE_TIMEOUT_S,
  docker_timeout=DOCKER_PROBE_TIMEOUT_S, resolver=None)`.
- `CheckResult(id, category, severity, message, fix_hint,
  daemon_refuse_message)`; categories `transport`/`runtime`/`operation`
  (group panel rows by bucket); ids: `config_file`, `config_yaml`,
  `intake_channel`, `allowlist`, `token`, `config_key:<key>`,
  `docker_binary`, `docker_image`, `explore_relay_agent_command`.

## Pinned contracts (parent plan aiplans/p1149_chatlink_config_wizard_tui.md)

1. **Cost boundary:** the existing 2s poll (`REFRESH_INTERVAL_S`,
   `_refresh_view`, chatlink_app.py:106-135) runs ONLY
   `preflight.run_cheap_checks()` — never a subprocess. Expensive checks
   (agent dry-run, docker binary, docker image) run on a Textual thread
   worker with explicit timeouts; results are CACHED and refreshed only
   on-demand (`r` refresh + one-shot kick on mount) — never per poll tick.
   Panel shows cached expensive results with an age / "checking…" state.
2. `__init__` stays I/O-free (`--smoke` contract; lazy `_resolve()` pattern).
3. Read-only wrt the daemon.
4. Assertable rendering: plain glyph prefixes, prefer `markup=False`
   (render-level test convention: assert `.plain` / text content).

## Implementation steps

1. Add a `#preflight_panel` widget to `compose()` (one `Static` rendering all
   rows, or a small `Vertical` of row Statics; fixed height = checks + title).
2. `_refresh_view` renders cheap results each tick; expensive rows come from
   a cache `{check_id: (CheckResult, monotonic_ts)}`, placeholder
   "checking…" while the worker runs.
3. Thread worker `_run_expensive_checks()` (`self.run_worker(…, thread=True)`
   or `@work(thread=True)`) calls `preflight.run_expensive_checks()`,
   updates the cache, requests re-render via `call_from_thread`. Triggered
   from `on_mount` (one-shot) and `action_refresh`; debounced (skip if one is
   already in flight).
4. Keep footer bindings coherent (`r` label may become "Refresh checks");
   follow `aidocs/framework/tui_conventions.md` (show=True labels, scope
   guards via `self.screen.query_one`).
5. Tests in `tests/test_chatlink_tui.sh`: Pilot renders expected rows against
   a synthetic sessions/config dir; NEGATIVE CONTROL — spy/monkeypatch the
   expensive seam and assert poll ticks never invoke it while the on-demand
   path does.

## Verification

- `bash tests/test_chatlink_tui.sh` — smoke + Pilot render of the checklist + poll-never-runs-expensive negative control.
- `ait chatlink` with a broken/partial config shows per-check severity and fix hints; with a valid config shows all-pass.
- Panel stays responsive with docker stopped/absent — expensive rows show cached/timeout state, UI never freezes or stutters on poll ticks.

Refer to Step 9 (Post-Implementation) of the task workflow for merge/archival.
