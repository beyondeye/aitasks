---
Task: t1149_2_config_status_panel.md
Parent Task: aitasks/t1149_chatlink_config_wizard_tui.md
Sibling Tasks: aitasks/t1149/t1149_3_config_wizard_flow.md, aitasks/t1149/t1149_4_wizard_docs_rewrite.md, aitasks/t1149/t1149_5_live_discord_validation.md, aitasks/t1149/t1149_6_manual_verification_chatlink_config_wizard_tui.md
Archived Sibling Plans: aiplans/archived/p1149/p1149_1_preflight_module.md
Worktree: (current branch — fast profile, no worktree)
Branch: current
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-17 11:36
---

# p1149_2 — Config-status panel in the chatlink TUI

## Context

Part of t1149 (chatlink config wizard TUI). The `ait chatlink` TUI
(`.aitask-scripts/chatlink/chatlink_app.py`) is a minimal read-only status
view (status line from audit mtime, sessions DataTable, audit tail) and is
config-blind: a broken gateway config just shows "no audit log yet (gateway
never started?)". This child renders the t1149_1 preflight results as a
visual checklist so config state (config file, intake channel, allowlist,
token, explore-relay agent command, docker binary + image) is visible at a
glance. Panel copy describes configuring **the current Discord bug-report
intake / explore-relay flow**, not all future ChatLink operations.

**Plan verified against source this session (no drift):**
- `chatlink_app.py` — `REFRESH_INTERVAL_S = 2.0` (`:35`), `on_mount` sets the
  interval (`:106-112`), `_refresh_view` (`:121-126`), `action_refresh`
  (`:114`), `r` binding with label "Refresh" (`:64`), I/O-free `__init__`
  with injected `clock` + lazy `_resolve()` (`:83-97`), `--smoke` path
  (`:176-181`). Absolute imports only (shortcut-scope sweep loads the file
  as a top-level module).
- `preflight.py` (t1149_1, shipped) — `run_cheap_checks() -> CheapChecks`
  (`results`/`config`/`config_warnings`; poll-safe, no subprocess),
  `check_explore_relay_agent_command(resolver=…, timeout=…) -> (CheckResult,
  argv)`, `check_docker_binary()`, `check_docker_image(timeout=…)`,
  `run_expensive_checks(agent_timeout=AGENT_PROBE_TIMEOUT_S,
  docker_timeout=DOCKER_PROBE_TIMEOUT_S, resolver=None) ->
  list[CheckResult]`; `CheckResult(id, category, severity, message,
  fix_hint, daemon_refuse_message)`; categories `transport`/`runtime`/
  `operation`; severities `pass`/`warn`/`fail`; ids `config_file`,
  `config_yaml`, `intake_channel`, `allowlist`, `token`,
  `config_key:<key>` (warn, only when config loads), `docker_binary`,
  `docker_image`, `explore_relay_agent_command`.
- `tests/test_chatlink_tui.sh` — smoke + Pilot render assertions + daemon
  import guard; heredoc style with `check(label, cond)` helper.

## Pinned contracts (parent plan aiplans/p1149_chatlink_config_wizard_tui.md)

1. **Cost boundary:** the existing 2s poll runs ONLY
   `preflight.run_cheap_checks()` — never a subprocess. Expensive checks
   (agent dry-run, docker binary, docker image) run on a Textual thread
   worker with the explicit `AGENT_PROBE_TIMEOUT_S` / `DOCKER_PROBE_TIMEOUT_S`
   timeouts; results are CACHED and refreshed only on-demand (`r` refresh +
   one-shot kick on mount) — never per poll tick. Panel shows cached
   expensive results with an age / "checking…" state.
2. `__init__` stays I/O-free (`--smoke` contract; lazy resolution).
3. Read-only wrt the daemon — the panel observes, never commands.
4. Assertable rendering: plain glyph prefixes, `markup=False`
   (render-level test convention: assert `.plain` / text content).

## Implementation steps

All changes in `.aitask-scripts/chatlink/chatlink_app.py` +
`tests/test_chatlink_tui.sh`.

1. **Panel widget.** Add `Static(id="preflight_panel", markup=False)` to
   `compose()` above the sessions table. CSS: `height: auto; padding: 0 1;
   border-bottom: solid $primary;`. Import `from chatlink import preflight`
   (absolute import).

2. **Constructor seams (I/O-free).** Extend `__init__` with
   `cheap_runner=None, expensive_runner=None` (stored as-is — explicit,
   deterministic test seams; no I/O). At call time resolve
   `self._cheap_runner or preflight.run_cheap_checks` (ditto expensive) so
   module-level monkeypatching also keeps working. Add state:
   `self._expensive_cache: dict[str, tuple[CheckResult, float]] = {}`,
   `self._expensive_running = False`, `self._expensive_error = False`.

3. **Cheap rows each tick.** `_refresh_view` additionally calls the cheap
   runner and re-renders the panel via a pure helper
   `_render_preflight(cheap_results, now) -> str` that groups rows by
   category bucket (`transport` / `runtime` / `operation` section labels),
   prefixes severity glyphs (`✓` pass, `!` warn, `✗` fail), and appends
   `— <fix_hint>` on non-pass rows. **The three expensive ids are a fixed
   row set** — `EXPENSIVE_IDS = ("explore_relay_agent_command",
   "docker_binary", "docker_image")` — ALWAYS rendered in their buckets
   regardless of cache/worker state, with exactly one of three states per
   row: cached result + age (`(<N>s ago)` from `self._clock`; suffixed
   `(re-checking…)` while `_expensive_running`), `… checking`
   (`_expensive_running`, uncached), or `not checked yet` (idle, uncached).
   If `_expensive_error` is set, append a panel-level warn line
   `! expensive checks failed — press r to retry`.

4. **Thread worker.** `_kick_expensive()` — debounce: return if
   `_expensive_running`; set the flag; **re-render the panel immediately**
   (so "checking…" / "(re-checking…)" appears the moment the kick happens,
   not on the next 2s tick); then `self.run_worker(self._run_expensive,
   thread=True)`. `_run_expensive()` calls the expensive runner (defaults
   pass `AGENT_PROBE_TIMEOUT_S`/`DOCKER_PROBE_TIMEOUT_S` via
   `run_expensive_checks`'s own defaults) inside try/except and posts back
   `self.call_from_thread(self._apply_expensive, results_or_None)` —
   `None` on exception. `_apply_expensive(results)` (UI thread — the ONLY
   cache/flag mutation site): on success, stamp `{r.id: (r,
   self._clock())}` for the returned ids and clear `_expensive_error`;
   on `None` (failure), **keep the previous cache untouched** and set
   `_expensive_error = True` — a transient probe failure must never erase
   useful cached results. Either way clear `_expensive_running` and
   re-render. Worker body is pure (no widget access).

5. **Triggers.** `on_mount`: `_kick_expensive()` **before** the existing
   `_refresh_view()` so the very first render already shows the checking
   state. `action_refresh`: `_kick_expensive()` (debounced; re-renders
   itself) then `_refresh_view()`. Keep the `r` binding label "Refresh"
   (still accurate; footer stays coherent per
   `aidocs/framework/tui_conventions.md`).

6. **Tests** (`tests/test_chatlink_tui.sh`, Pilot section):
   - **Render:** construct the app with a fake `cheap_runner` returning a
     synthetic `CheapChecks` (one pass, one warn, one fail with fix hint)
     and a spy `expensive_runner` returning fixed results; assert panel
     `render().plain` (or `str(render())`) contains the glyph-prefixed rows,
     the fix hint, and the bucket labels.
   - **Fixed expensive rows:** before any worker result lands (uncached
     state), assert all three `EXPENSIVE_IDS` rows are present with their
     placeholder state (`… checking` / `not checked yet`) — they must never
     disappear from the panel.
   - **Live worker path (end-to-end):** with the spy `expensive_runner`
     returning fixed results, `pilot.press("r")`, then wait for the real
     worker to complete (`await app.workers.wait_for_complete()` +
     `pilot.pause()`), and assert the panel text changed from the
     placeholder/stale state to the spy's expensive results — proving the
     actual `run_worker` → `call_from_thread` → widget update path, not
     just the seam.
   - **Failure keeps cache:** seed a cached result via one successful
     refresh, swap the spy to raise, refresh again, wait for the worker —
     assert the previously cached row text is still rendered and the
     `expensive checks failed` warn line appears.
   - **NEGATIVE CONTROL (poll never runs expensive):** with the spy counting
     calls, drive several `_refresh_view()` ticks — spy count stays at the
     single `on_mount` kick; then `action_refresh` → count increments.
     Debounce guard: with `_expensive_running=True`, `_kick_expensive()`
     does not invoke the spy.
   - Existing smoke (`--smoke` constructs with zero I/O), Pilot session-table
     assertions, and the daemon import guard stay green unchanged.

## Risk

### Code-health risk: low
- Thread-worker race or stale panel render (worker vs 2s poll) · severity:
  low · → mitigation: in-plan — concurrency safety contract: worker body is
  pure (preflight call only), cache/flag mutation happens ONLY on the UI
  thread via `call_from_thread` (`_apply_expensive`), an explicit
  `_expensive_running` debounce prevents overlap, per-probe timeouts bound
  worker lifetime, worker failure clears the flag fail-closed while keeping
  the previous cache (never erased by a transient probe failure); the
  poll-never-runs-expensive spy is the negative control and a live
  `run_worker`→`call_from_thread` Pilot test proves real delivery.
- Accidental violation of the `--smoke` I/O-free constructor contract ·
  severity: low · → mitigation: in-plan — seams are stored callables only;
  the existing smoke test stays in the suite and must pass.

### Goal-achievement risk: low
- Fixed panel could crowd the sessions table on short terminals · severity:
  low · → mitigation: in-plan — `height: auto` panel (rows only as needed);
  manual check in the t1149_6 verification sibling.

### Planned mitigations
None — all identified risks are low and mitigated in-plan by the pinned
contracts and tests; no separate before/after mitigation tasks proposed.

## Verification

- `bash tests/test_chatlink_tui.sh` — smoke + Pilot render of the checklist + poll-never-runs-expensive negative control + debounce guard + daemon import guard.
- `ait chatlink` with a broken/partial config shows per-check severity and fix hints; with a valid config shows all-pass.
- Panel stays responsive with docker stopped/absent — expensive rows show cached/timeout state, UI never freezes or stutters on poll ticks.

Refer to Step 9 (Post-Implementation) of the task workflow for merge/archival.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, all in
  `.aitask-scripts/chatlink/chatlink_app.py` + `tests/test_chatlink_tui.sh`.
  New `#preflight_panel` `Static(markup=False, height: auto)` above the
  sessions table, titled "config checks — bug-report intake / explore-relay".
  Pure render helper `_render_preflight(cheap_results, now)` groups rows by
  category bucket (`[transport]`/`[runtime]`/`[operation]` labels), glyph
  prefixes `✓`/`!`/`✗`, `— <fix_hint>` on non-pass rows. Fixed expensive row
  set `EXPENSIVE_IDS = (docker_binary, docker_image,
  explore_relay_agent_command)` always rendered with one of three states:
  cached + age via the existing `_age` helper (suffixed `(re-checking…)`
  while a probe is in flight), `… checking`, or `· not checked yet`.
  Cheap checks run on every `_refresh_view` tick via
  `self._cheap_runner or preflight.run_cheap_checks`; expensive probes run in
  `_run_expensive` (pure worker body, `run_worker(..., thread=True)`) posting
  back via `call_from_thread(self._apply_expensive, results_or_None)` —
  `_apply_expensive` is the ONLY cache/flag mutation site (UI thread), keeps
  the previous cache on failure and sets `_expensive_error` (rendered as
  `! expensive checks failed — press r to retry`). `_kick_expensive()` is
  debounced on `_expensive_running` and re-renders immediately so the
  checking state is visible at kick time; triggered from `on_mount` (before
  the first `_refresh_view`) and `action_refresh` (`r` label stays
  "Refresh"). Constructor gains I/O-free seams
  `cheap_runner=None, expensive_runner=None`.
- **Deviations from plan:** None material. Idle-uncached rows use a `·`
  prefix (plan's "not checked yet" state, given a glyph for alignment).
- **Issues encountered:** None — all 25 TUI checks passed first run;
  preflight/daemon/config suites stayed green.
- **Key decisions:** (1) The pre-existing Pilot test app construction now
  passes both fake seams — without them, on_mount would kick REAL expensive
  probes (agent dry-run subprocess) inside the legacy test. (2) Placeholder
  states are asserted through the pure render helper on an unmounted app
  (deterministic — no race against the mount worker), while the live
  `run_worker` → `call_from_thread` → widget delivery is proven end-to-end
  with `await app.workers.wait_for_complete()` after mount and after
  `pilot.press("r")`. (3) Live acceptance run against the real repo config
  rendered fails-with-fix-hints for intake_channel/token and cached passes
  for docker/agent.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** t1149_3 (wizard) can reuse the panel's
  formatting helpers (`_format_row`, severity glyphs) and the seam pattern
  (`cheap_runner`/`expensive_runner` constructor injection) for its final
  preflight screen; `_kick_expensive`/`_apply_expensive` show the sanctioned
  worker/debounce/cache shape for any wizard-side probe. Panel copy is scoped
  to the current Discord bug-report intake / explore-relay flow per the
  parent-plan §1b naming contract. The `EXPENSIVE_IDS`/`_EXPENSIVE_CATEGORY`
  module constants are the place a future operation adds its own probe rows.
