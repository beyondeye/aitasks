---
Task: t2034_2_monitor_producer_client_agnostic_settings.md
Parent Task: aitasks/t2034_monitor_status_server.md
Sibling Tasks: aitasks/t2034/t2034_3_monitor_status_protocol.md, aitasks/t2034/t2034_6_monitor_classifier_crosscheck_python_go.md
Archived Sibling Plans: aiplans/archived/p2034/p2034_*_*.md
Base branch: main
Output branch: main
---

# t2034_2: make the `TmuxMonitor` producer client-agnostic

## Context

Parent t2034 replaces the per-instance tmux scanning in monitor, minimonitor and
applink with one shared status server. t2034_1 measured the payoff: about 0.9–1.0
core, mostly from deduplicating the tmux server's work. Before one producer can
serve many clients, four per-client settings have to leave `TmuxMonitor`
(`.aitask-scripts/monitor/monitor_core.py:1958`). This task is the in-process
refactor only. No server is built here (that is t2037), and a single monitor or
minimonitor must behave exactly as before.

Decisions settled with the user during planning:

| Setting | Decision |
|---|---|
| `exclude_pane` (defaults to `$TMUX_PANE`) | Removed from the producer. Each client filters its own pane. |
| Multi-session toggle `M` | The live producer always scans every session. The client filters by session, and `M` flips only client view state. |
| Parked agents | **Global, with per-client capture pins.** Which agents are parked is global: one store-derived set (per-user marks store plus session→project map), identical for every client. Whether a parked agent is still *captured* is client-dependent today and stays so: a minimonitor **keeps live capture of the agent it follows** (docked panel, `L` recheck, `c` concerns, shadow readiness — t1685 §7), and with an unconfirmed identity it pins *everything* (fail-safe). The producer skips `global_parked − ∪ pins`. Each client's view turns a live snapshot of a parked agent it does not pin into the parked placeholder. In-process (one client) this gives exactly today's published sets and snapshots. |
| Compare-mode override | **One shared per-pane setting, owned by the producer** (as the code does today). Behaviour change once clients share a producer (t2037): `d` in one client, or applink's `cycle_compare_mode`, changes that pane's idle verdict for every client. |

The protocol doc these should be recorded in (`aidocs/framework/monitor_status_protocol.md`)
is owned by t2034_3 and does not exist yet. The decisions are therefore recorded in
`TmuxMonitor`'s docstring here, and t2034_3 gets a note (Step 8e) to carry them into
its spec.

Findings that shape the design:
- Both apps always construct their monitor multi-session (`main()` never passes
  `multi_session`), so single-session mode exists only after pressing `M`.
- The client's own pane is normally dropped already by the companion filter
  (`_is_companion_pane`, marker `@aitask_monitor_kind`). Exclusion only matters for
  an unmarked pane, and for applink's own pane.
- `exclude_pane=""` does **not** disable exclusion today: `exclude_pane or
  os.environ.get("TMUX_PANE")` falls back to the env var. `lib/agent_freeze.py:957`
  and several tests pass `""` meaning "none" and silently get "exclude the caller's
  pane". For freeze-all that accidental exclusion is what stops `ait freeze --all`
  run from an agent pane from respawning its own pane. It is preserved by making
  it explicit.
- The base parked set comes from `MarksView.parked_windows()` (the per-user store
  `~/.config/aitasks/agent_marks.json`) plus `_session_root_map`, which comes from
  all-session discovery (`get_session_to_project_mapping_async`). That base is
  global. But `MiniMonitorApp._parked_agent_pairs` (`minimonitor_app.py:2016`)
  subtracts its followed agent `(self._session, self._own_window_name)` and
  publishes an empty set until `_own_identity_confirmed`. That behaviour is pinned
  by the seven `OwnAgentStaysCapturedTests` (`tests/test_minimonitor_own_mark.py:794`).
  The published *skip* set is therefore client-dependent, and that has to be
  modelled, not erased.
- applink never marks its own pane (no `mark_monitor_pane` / `@aitask_monitor_kind`
  in `applink/`), so the producer's `TMUX_PANE` exclusion is what keeps it out of
  `_pane_cache` today. Every cache-backed applink route depends on that:
  explicit-list `subscribe` (not checked against the roster), `history`
  (`pusher._drain_history` → `get_pane` + `capture_pane_content_async`), the
  `restart_task` idle gate (`capture_pane`), `focus` (`switch_to_pane`), and
  `kill` (`kill_agent_pane_smart` takes the smart path only for cached panes).

## Design

**Producer (`TmuxMonitor`)**
- Drop the `exclude_pane` parameter and attribute, and the `TMUX_PANE` read. The
  `_parse_list_panes` check at `monitor_core.py:2634` goes away.
- Rename `multi_session` to `all_sessions: bool = True`. It is a
  **construction-time scan scope for one-shot callers only**: freeze-all's
  per-session discovery, the debug CLI, benchmarks and tests. Live clients never
  pass it and never mutate it. The rename makes any missed client reader fail
  with `AttributeError` instead of reading a stale value. Its readers are
  `discover_panes` and `discover_panes_with_shadows_async`
  (`monitor_core.py:2805,2825`).
- `switch_to_pane` (`:3704`): drop the `self.multi_session and` gate. The
  condition becomes `pane.session_name and pane.session_name != self.session`.
  This is equivalent: under a single-session view the client only offers its own
  session's panes.
- Update the `_SESSIONS_CACHE_TTL` comment, which says `M` invalidates the cache.
- Add a "Client-agnostic contract (t2034_2)" paragraph to the class docstring
  stating all four rows. Extend the `get_compare_mode` / `set_compare_mode` and
  `set_parked_agents` docstrings with the shared/global semantics. Keep the
  publish-before-capture rule verbatim.

**Client view (new pure helpers in `monitor_core.py`, beside `TmuxMonitor`)**
```python
def client_admits_pane(pane, *, own_pane=None, home_session=None, multi_session=True) -> bool:
    if own_pane and pane.pane_id == own_pane:
        return False
    if not multi_session and pane.session_name != home_session:
        return False
    return True

def client_view_snapshots(snapshots, *, own_pane=None, home_session=None, multi_session=True) -> dict:
    return {pid: s for pid, s in snapshots.items()
            if client_admits_pane(s.pane, own_pane=own_pane,
                                  home_session=home_session, multi_session=multi_session)}
```
These are pure, so t2037's socket client reuses them unchanged.

**Parked (global set + per-client capture pins)**:
- `lib/agent_marks.py`: a new pure function `parked_session_windows(parked_windows,
  session_roots) -> frozenset[(session, window)]`, the store-derived **global**
  set. It canonicalizes roots through `mark_key(root, "")[0]` exactly as
  `_root_for_session` does.
- `monitor_core.py`: `CAPTURE_PIN_ALL` (a sentinel) and a pure
  `parked_capture_skip(global_parked, pin_sets) -> frozenset`, which returns
  `global_parked` minus the union of the pin sets, or `frozenset()` if any pin set
  is `CAPTURE_PIN_ALL`. In-process the app passes one pin set; t2037's server
  passes one per subscriber.
- `monitor_shared.AgentMarksMixin` gets three methods:
  - `_global_parked_pairs()` → `parked_session_windows(self._marks_view.parked_windows(), self._session_root_map)`.
  - `_capture_pins()` → `frozenset()` by default.
  - `_parked_agent_pairs()` → `parked_capture_skip(self._global_parked_pairs(), [self._capture_pins()])`. It keeps its name, because it is what `_publish_parked_agents` sends.
  All three are still derived from the store and the map only, never from
  `_snapshots`.
- `MiniMonitorApp`: its `_parked_agent_pairs` override becomes a `_capture_pins`
  override. It returns `CAPTURE_PIN_ALL` when the identity is unconfirmed or the
  name is empty, and `{(self._session, self._own_window_name)}` otherwise. The
  docstring (t1685 §7, fail-safe rationale) moves with it. The output of
  `_parked_agent_pairs()` is identical to today in every branch.
- Client view: `client_view_snapshots` gains `parked_pairs=frozenset()` and
  `pins=frozenset()`. For an AGENT snapshot that is neither `frozen` nor already
  `parked`, whose `(session_name, window_name)` is in `parked_pairs` and not
  pinned (with `CAPTURE_PIN_ALL` pinning everything), it substitutes
  `_parked_snapshot(snap.pane, now)`. Frozen precedence is kept. In-process this
  is a no-op, because the producer already skipped exactly those panes; under a
  shared producer it is what keeps another client's pin from leaking live data
  into this client's parked rows. Both apps pass `self._global_parked_pairs()` and
  `self._capture_pins()`.
- **Every client write into `_snapshots` goes through one projection.** There are
  exactly three write sites today:
  - `monitor_app.py:1074` (bulk refresh);
  - `minimonitor_app.py:1828` (bulk refresh);
  - `monitor_app.py:1366` (`_fast_preview_refresh`, single pane).

  The fast-preview route receives the producer's result for one pane. Under a
  shared producer that result is live whenever *another* client pins a parked
  agent, so storing it raw would overwrite this client's parked placeholder with
  `parked=False` and live content. Each app gets one `_project_snapshots(snaps) ->
  dict` method. It calls `client_view_snapshots` with the app's own pane, home
  session, multi flag, `_global_parked_pairs()` and `_capture_pins()`, and all
  three sites use it. On the single-pane route,
  `projected = self._project_snapshots({pane_id: snap})`:
  - pane not admitted → nothing is stored (and the preview is not updated);
  - pane admitted → the stored value is `projected[pane_id]`, which may be the
    parked placeholder.

  Producer bookkeeping (`commit_snapshot`) still runs first and unchanged. The
  projection is a pure read of its result.
- The publish-down `set_parked_agents` API and its publish-before-capture ordering
  are unchanged. Its docstring states that the value is a capture *skip* set
  (global minus pins), not "the parked set".

**Compare mode (shared)**: no code change. The override dict stays in the producer,
keyed by pane and reaped by the producer's all-session discovery (`_clean_stale`),
never by a client's view. Pinned by tests.

## Steps

### Pre-phase (risk mitigations)
0. **baseline_affected_tests** — before editing, run the affected test files (list
   in Verification) on the current tree and record any failures that already
   exist, so new red results can be attributed. Read-only: never stash or
   restore other sessions' dirty files.

### Main steps
1. **`monitor/monitor_core.py`**: producer changes as above, plus the two pure
   helpers and the docstrings.
2. **`monitor/monitor_app.py`**:
   - Stop passing `multi_session=` to `TmuxMonitor` (`:860`).
   - Add `self._own_pane_id = os.environ.get("TMUX_PANE")` in `__init__`, with
     class-level floors `_own_pane_id = None` and `_multi_session = False` for
     `__new__`-built test stubs (the minimonitor's existing floor pattern).
   - `_refresh_data` (`:1074`): `self._snapshots = self._project_snapshots(snaps)`.
   - `_fast_preview_refresh` (`:1366`): project the single pane before storing,
     as described in the Design section.
   - Replace every `self._monitor.multi_session` read (`:1142,1717,1911`) with
     `self._multi_session`, keeping the existing `self._monitor is not None`
     guards.
   - `action_toggle_multi_session` (`:3120`): flip `self._multi_session` only, then
     notify and `call_later(self._refresh_data)`. Drop the
     `invalidate_sessions_cache()` call: the producer's scope did not change.
3. **`monitor/minimonitor_app.py`**: the same pattern. Add `_multi_session`
   (`__init__` True; class floor False) and `_own_pane_id`. Add
   `_project_snapshots`, used at `:1828` (its only write site).
   Replace the reads at `:2480,3047`, and change the toggle at `:5629`. Update the
   comment at `:2080` that names `TmuxMonitor.exclude_pane`.
4. **applink**: `server.py:190` drops `multi_session=True` and passes
   `own_pane=os.environ.get("TMUX_PANE")` to `FrameRouter` and `PushScheduler`
   as a new optional kwarg (default `None` = no filter, so existing stubs keep
   working). One rule applies everywhere: **the own pane is admissible on exactly
   the routes that never consulted the producer cache, and on every cache-backed
   route it behaves as it did when it was absent from that cache.** In detail:
   - **Roster subscribe**: `router._discover_pane_ids` (`:734`) drops it.
   - **Explicit subscribe** (`:357`): the own pane is filtered out of
     `payload["panes"]` (and so out of `content_panes`, which intersects with
     that roster), so it never enters `Subscription.panes`. A `history` request
     for it then fails the existing "pane not in subscription" check.
   - **Live push**: in `pusher._run_once` (`:153`), `snaps =
     client_view_snapshots(snaps, own_pane=self._own_pane)`.
   - **`history` drain** (`pusher._drain_history`, `:208`): skip the own pane
     before `get_pane` / `capture_pane_content_async`. This is defence in depth
     for a subscription built before the filter.
   - **`restart_task`** (`:617`): the own pane answers `not_found`, as
     `capture_pane` did on a cache miss.
   - **`focus`** (`:330`): the own pane answers `ok: false`, as `switch_to_pane`
     did on a cache miss.
   - **`kill`** (`:553`): the own pane is routed to plain `kill_pane` (what
     `kill_agent_pane_smart` did on a cache miss), never to the smart
     window-collapse path.
   - `send_enter` / `send_keys` / `forward_key` / `cycle_compare_mode` never read
     the cache and stay unchanged.

   A single router helper `_is_own_pane(pane_id)` backs these, and the pusher
   holds the same `own_pane` value.
5. **`lib/agent_freeze.py:957`**: `TmuxMonitor(session=session, all_sessions=False)`,
   then filter out `os.environ.get("TMUX_PANE")` explicitly, with a comment saying
   this preserves the caller-pane exclusion that `exclude_pane=""` provided by
   accident.
6. **`lib/agent_marks.py`**, **`monitor/monitor_core.py`**, **`monitor/monitor_shared.py`**
   and **`monitor/minimonitor_app.py`**: add `parked_session_windows`,
   `CAPTURE_PIN_ALL` + `parked_capture_skip`, and the
   `_global_parked_pairs` / `_capture_pins` / `_parked_agent_pairs` split. Move the
   minimonitor override to `_capture_pins`. Pass `parked_pairs` and `pins` into
   both apps' `client_view_snapshots` calls. In
   `tests/test_minimonitor_own_mark.py:843`, the control that calls
   `AgentMarksMixin._parked_agent_pairs(app)` to prove the store really holds the
   own pair would now dispatch to the minimonitor's `_capture_pins`. It is
   re-pointed at `app._global_parked_pairs()`, which keeps the same purpose (the
   own pair is parked in the store). The other six tests stay as they are and
   must pass unchanged.
7. **Other `TmuxMonitor(...)` constructors**: `monitor/tmux_monitor.py` (check
   whether its `**config` can carry `multi_session`),
   `aidocs/benchmarks/bench_monitor_refresh.py` (`all_sessions=False`), and the
   bench description line in `aidocs/framework/python_tui_performance.md:186`.
8. **Existing tests**, mechanically:
   - In `TmuxMonitor(` constructor calls, `multi_session=False` becomes
     `all_sessions=False` and `exclude_pane=…` is dropped. Applies to about 15 py
     files and the shell heredocs in `test_list_panes_session_scope_live.sh`,
     `test_freeze_engine_live.sh`, `test_cleanup_rule_parity.sh`,
     `test_scratchpad_spawn_live.sh`, `test_multi_agent_window_substrate.sh`,
     `test_frozenagent_standin_stamp.sh` and `test_tmux_control_resilience.sh`.
   - Fake monitors that drive multi-mode rendering (`multi_session = True` on the
     stub: `test_monitor_agent_marks_action.py`, `test_monitor_refresh_no_sync_tmux.py`,
     `test_monitor_session_divider.py`, `test_monitor_pane_sort_order.py`,
     `test_minimonitor_other_section.py`, `test_monitor_markup_literal_sinks.py`)
     set `app._multi_session` instead. Stubs that only carry an inert
     `multi_session = False` are left alone.
   - `test_multi_session_monitor.sh`: the "exclude_pane still applies in multi
     mode" case becomes a `client_view_snapshots` case. The `multi_session=False`
     discovery case moves to `all_sessions=False`.
   - `test_multi_session_minimonitor.sh`: the toggle assertion becomes "flips the
     app's view flag and leaves the producer untouched", not "invalidates cache".
9. **New `tests/test_monitor_client_agnostic.py`**: one class per row.
   - *exclude*: with `TMUX_PANE=%5` in the env, `_parse_list_panes` returns the
     non-companion `%5` row. `TmuxMonitor` has no `exclude_pane` attribute.
     `client_view_snapshots` drops `own_pane`, and `own_pane=None` keeps
     everything. The `agent_freeze._agent_panes_for` caller-pane exclusion still
     holds.
   - *multi-session*: a default monitor scans all sessions (the stubbed
     `_tmux_async` records `list-panes` for every discovered session). Both apps'
     `action_toggle_multi_session` flip only `app._multi_session`; the stub
     monitor has no `multi_session` attribute, so touching it raises. The view
     filter keeps only the home session when off and everything when on. Both
     apps' refresh path stores the filtered set (stub returning own-pane,
     home-session and other-session snapshots).
   - *parked (global set + pins)*:
     - `parked_session_windows` covers two sessions sharing a root (a pair for
       each), a symlinked root (canonical match), and an unmapped session (none).
     - `parked_capture_skip` covers: no pins → the global set; one pin → the
       global set minus it; pins from two clients → minus their union; any
       `CAPTURE_PIN_ALL` → empty; and a pin on a non-parked pair → inert.
     - A monitor-shaped app and a minimonitor-shaped app over the same store and
       map return **identical `_global_parked_pairs()`**. Their published
       `_parked_agent_pairs()` differ **only** by the minimonitor's followed
       pair. With the identity unconfirmed the minimonitor publishes
       `frozenset()`.
     - **Shared-producer simulation**: one `TmuxMonitor` and two client views.
       Client A follows parked agent X (pins X) and client B pins nothing. The
       producer's skip set is `global − {X}`, so X is captured live. A's view
       shows X live and B's view shows X as a `parked=True` placeholder. A frozen
       X stays `frozen` in both views (precedence).
     - **Fast-preview continuation**: B is a real `MonitorApp` built with `__new__`
       over the same producer. After B's initial filtered view, focus X and
       await B's actual `_fast_preview_refresh()`. The producer returns X live
       (A's pin permits capture), yet `B._snapshots[X].parked` is still `True`,
       and the producer's idle bookkeeping for X still advanced.
     - Controls: with B pinning X, the same call stores the live snapshot. For a
       focused pane that B's view does not admit (own pane / other session with
       `M` off), nothing is stored.
     - The publish-before-capture ordering is already pinned for both apps in
       `test_monitor_parked_capture.py`, and the followed-agent live capture by
       `OwnAgentStaysCapturedTests`. Both are kept green, not duplicated.
   - *compare mode (shared)*: an override set through the producer is what every
     reader gets from `get_compare_mode`. An override on another session's pane
     survives a commit that one client's single-session view would filter out
     (it is reaped only when producer discovery loses the pane). The applink
     router verb and the app action mutate the same dict.
   - *applink* (regression with the own pane **present in the producer cache**,
     i.e. an unmarked own pane seeded into `_pane_cache`):
     - Roster subscribe and an explicit `subscribe{panes:[own, other]}` both
       accept only `other`.
     - A `history` request for own is rejected as not subscribed.
     - `_drain_history`, fed a pending own-pane request directly, makes no
       capture call.
     - The live push never sends own.
     - `restart_task(own)` returns `not_found` and `focus(own)` returns
       `ok: false`.
     - `kill(own)` calls `kill_pane` rather than the smart path.
     - `send_keys(own)` is still allowed.
     - Control: with `own_pane=None`, every one of these admits the pane.

### Post-phase (risk mitigations)
10. **pin_no_client_settings_in_producer** — a static pin test (in the new file)
    that asserts `monitor_core.py` never reads `TMUX_PANE`, `TmuxMonitor` has no
    `multi_session` / `exclude_pane` attributes, and `monitor_app.py`,
    `minimonitor_app.py` and `applink/*.py` contain no `_monitor.multi_session` /
    `.exclude_pane` reads. It also asserts that the **only** writes to
    `self._snapshots` in `monitor_app.py` / `minimonitor_app.py` are the three
    projected sites (an AST walk for assignments to `self._snapshots` and
    `self._snapshots[...]`, each of whose value must be a `_project_snapshots`
    call or a subscript of its result). A future single-pane path therefore
    cannot bypass the view. This is needed because test stubs still carry an inert
    `multi_session` attribute, which would hide a missed production reader that
    raises `AttributeError` only live.

## Verification

- New test: `python3 -m pytest tests/test_monitor_client_agnostic.py` (or via the runner's `--test-dir`).
- Affected py tests: `test_monitor_parked_capture`, `test_monitor_parked_filter`,
  `test_monitor_frozen_capture`, `test_monitor_companion_filter`,
  `test_list_panes_arity_characterization`, `test_agent_marks_generation`,
  `test_monitor_shadow_status`, `test_shadow_seam`, `test_monitor_shadow_zone`,
  `test_kill_bound_helpers`, `test_minimonitor_sibling_fallback`,
  `test_minimonitor_auto_close_guard`, `test_minimonitor_startup_input_latency`,
  `test_monitor_finalize_offload`, `test_monitor_refresh_no_sync_tmux`,
  `test_monitor_session_divider`, `test_monitor_pane_sort_order`,
  `test_minimonitor_other_section`, `test_monitor_agent_marks_action`,
  `test_monitor_markup_literal_sinks`, `test_monitor_concern_action`,
  `test_idle_compare_modes`, `test_prompt_detection`, `test_minimonitor_own_mark`
  (all seven `OwnAgentStaysCapturedTests`), and the applink router/pusher tests
  (`grep -l 'FrameRouter\|PushScheduler' tests/`).
- Bash tests individually: `test_multi_session_monitor.sh`,
  `test_multi_session_minimonitor.sh`, `test_list_panes_session_scope_live.sh`,
  `test_freeze_engine_live.sh`, `test_cleanup_rule_parity.sh`,
  `test_scratchpad_spawn_live.sh`, `test_multi_agent_window_substrate.sh`,
  `test_frozenagent_standin_stamp.sh`, `test_tmux_control_resilience.sh`,
  `test_no_raw_tmux.sh`.
- Full suite: `set -o pipefail; bash tests/run_all_python_tests.sh`, reading only
  the final `PYTHON SUITE:` line. Failures that the baseline in step 0 already
  recorded are reported, not attributed to this change.
- `grep -rn 'multi_session=\|exclude_pane' --include=*.py --include=*.sh .aitask-scripts tests aidocs`:
  only the app-level `MonitorApp(multi_session=)` parameter and comments remain.

## Step 9 reference

Post-implementation runs in this order:
1. Step 8: review, then commit (`refactor: … (t2034_2)`).
2. Step 8e: send a note to t2034_3 with the four settled rows and the helper
   names (`client_view_snapshots`, `client_admits_pane`,
   `agent_marks.parked_session_windows`, `parked_capture_skip`,
   `CAPTURE_PIN_ALL`). The note also gives the protocol consequences:
   - the parked-set message becomes a per-client **capture-pin** message
     (`pins: [[session, window], …] | "all"`), not a parked set;
   - the server computes the skip set itself, from the store plus all
     subscribers' pins;
   - parked placeholder substitution is client-side;
   - compare-mode override is one shared per-pane request;
   - applink's own-pane admission rule is part of the client contract.
3. Step 9: archive on `main` (current-branch mode, no merge).

## Risk

### Code-health risk: medium
- Wide mechanical blast radius: two TUIs, applink, freeze, and about 30 test files. A missed `self._monitor.multi_session` reader would pass under test stubs, which still carry the attribute, and raise only live · severity: medium · → mitigation: inline post-phase pin_no_client_settings_in_producer
- Unrelated failures already in the suite, or concurrent sessions' dirty files, could be mistaken for regressions caused by this change · severity: low · → mitigation: inline pre-phase baseline_affected_tests

### Goal-achievement risk: low
- The parked semantics now have two layers: a global set plus per-client pins, with client-side placeholder substitution. A mis-wired pin would either freeze a minimonitor's followed agent (silent) or leak live rows into parked placeholders · severity: medium · → mitigation: covered in-plan by the unchanged `OwnAgentStaysCapturedTests` plus the two-client shared-producer simulation in step 9
- Removing the producer exclusion opens applink's unmarked own pane to cache-backed routes · severity: medium · → mitigation: covered in-plan by the step 4 admission rule and its cache-present regression in step 9
- After `M` turns single-session view on, the producer still scans every session: more tmux load for that instance, and the mark purge also sweeps other enumerated sessions, as a multi-session monitor already does. A home session that `discover_aitasks_sessions` does not recognise would show no panes in single mode (in practice the client's own pane votes the session in) · severity: low · → mitigation: TBD (accepted; documented in the docstring)

### Planned mitigations
- timing: pre-phase | name: baseline_affected_tests | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: pre-existing failures misattributed | desc: run the affected tests on the current tree before editing and record failures that already exist
- timing: post-phase | name: pin_no_client_settings_in_producer | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: missed client-setting reader hidden by stubs | desc: static pin test — no TMUX_PANE read in monitor_core, no multi_session/exclude_pane on TmuxMonitor or read via _monitor in apps/applink

## Post-Review Changes

### Change Request 1 (2026-11-03 18:05)
- **Requested by user:** the applink own-pane `kill_pane` branch called `kill_pane` directly, bypassing the bound-helper sweep (t2088) that the old cache-miss route of `kill_agent_pane_smart` ran after its plain kill — a shadow bound to applink's own pane in another window survived. Preserve the sweep without enabling the window collapse; add a router-level regression on the real cleanup behaviour.
- **Changes made:** `TmuxMonitor.kill_agent_pane_smart` gained `cache_miss: bool = False` — the cache-miss route (plain `kill_pane`, `killed_window=False`) taken even for a cached pane, with the helper sweep still run on success. The router's own-pane branch now calls `kill_agent_pane_smart(pane_id, cache_miss=True)`. New `ApplinkOwnPaneKillSweepTests` drives the REAL `FrameRouter` + `TmuxMonitor` over `tests/lib/tmux_server_model.py`: own pane `%1` (cached), a companion `%4` in its window, a shadow `%3` bound to it in window 9 — own-pane kill leaves `%4`, removes `%1` and `%3`, `killed_window=False`; control (no own pane) collapses the window. Mutants in an isolated copy: the reported bug (plain `kill_pane`), a cache-miss route without the sweep, and the own pane taking the smart path — each fails the new tests.
- **Files affected:** `.aitask-scripts/monitor/monitor_core.py`, `.aitask-scripts/applink/router.py`, `tests/test_monitor_client_agnostic.py`.

## Final Implementation Notes

- **Actual work done:** As planned (four rows, settled with the user: own pane and `M` → client-side; parked → global set + per-client capture pins; compare mode → one shared per-pane setting). Producer (`monitor_core.TmuxMonitor`): `exclude_pane` and the `$TMUX_PANE` read removed; `multi_session` → construction-only `all_sessions`; `switch_to_pane` lost its multi gate; class docstring "Client-agnostic contract (t2034_2)" states all four rows. New pure helpers beside it: `client_admits_pane`, `client_view_snapshots` (own pane, session filter, parked-placeholder substitution with frozen precedence), `parked_capture_skip`, `CAPTURE_PIN_ALL`. `agent_marks.parked_session_windows` is the global parked set. `AgentMarksMixin` gained `_global_parked_pairs` / `_capture_pins` / `_project_snapshots` and the `_own_pane_id` / `_multi_session` floors; `_parked_agent_pairs` = `parked_capture_skip(global, [pins])`. `MiniMonitorApp` overrides `_capture_pins` (followed pair, or `CAPTURE_PIN_ALL` when the identity is unconfirmed) instead of `_parked_agent_pairs` — published sets identical to before in every branch. Both apps route every `_snapshots` write (two bulk refreshes + `_fast_preview_refresh`) through `_project_snapshots`; `M` flips only the app flag. applink: router/pusher take `own_pane` (server passes `$TMUX_PANE`); roster + explicit subscribe drop it, the pusher drops it from live pushes and history drains, `restart_task` → `not_found`, `focus` → `ok: false`, `kill_pane` → `kill_agent_pane_smart(pane_id, cache_miss=True)`. `agent_freeze._agent_panes_for` excludes the caller's `$TMUX_PANE` explicitly.
- **Deviations from plan:** (1) `_project_snapshots` and the view floors live on `AgentMarksMixin` (shared by both apps) rather than duplicated per app. (2) `client_admits_pane` treats an EMPTY `session_name` as the home session — the `("", home)` convention `_find_own_agent_snapshot` already uses — so legacy/stub records are not dropped by the single-session view. (3) Post-review: `kill_agent_pane_smart(cache_miss=True)` was added so the own-pane kill keeps the t2088 helper sweep (Change Request 1). (4) `_project_snapshots` falls back to an empty global parked set if the marks view cannot be read (same "advisory data must never break a tick" stance as `_publish_parked_agents`). (5) `test_monitor_focus_switch.py` (not in the plan's list) needed `MonitorApp(..., multi_session=False)`: it mounts a real app, whose own flag now governs.
- **Issues encountered:** fake monitors in ~10 tests drove multi-mode rendering through `monitor.multi_session`; moved onto `app._multi_session` (scripted for the `SimpleNamespace(multi_session=…)` / `app._monitor.multi_session = …` shapes). `MarksView` needs `.refresh()` before `parked_windows()` returns anything (test fixture gotcha). The working tree held another session's uncommitted t2175_3 sitrep hunks in `monitor_shared.py` and staged sitrep renames in the shared index, so the commit was built from a temporary index with only this task's hunks.
- **Key decisions:** the producer keeps a construction-time scan scope (`all_sessions`) for one-shot callers (freeze-all per-session discovery, benchmarks, tests) — never a runtime client toggle; renamed so a missed reader fails loudly. The static pin test (`NoClientSettingsInProducerTests`) guards what stubs cannot: no `_monitor.multi_session` / `.exclude_pane` reads in apps/applink, no `environ…TMUX_PANE` in `monitor_core`, and every `self._snapshots` write in both apps is a `_project_snapshots` result (AST walk).
- **Verification:** baseline before editing — 1159 affected py tests green; `test_applink_pusher.sh` already failing (see Upstream defects). After: new `tests/test_monitor_client_agnostic.py` 30/30; affected py set 1189 passed; full suite `PYTHON SUITE: PASSED (runner=pytest, exit=0)`; bash `test_multi_session_monitor.sh` 48/48, `test_multi_session_minimonitor.sh` 42/42, `test_list_panes_session_scope_live.sh`, `test_multi_agent_window_substrate.sh`, `test_frozenagent_standin_stamp.sh`, `test_tmux_control_resilience.sh`, `test_no_raw_tmux.sh`, `test_applink_router.sh` (193), `test_applink_content.sh` (115), `test_multi_session_primitives.sh` all green. Not run (live-tmux guarded, CI-box only): `test_freeze_engine_live.sh`, `test_cleanup_rule_parity.sh`, `test_scratchpad_spawn_live.sh` (constructor edits there are mechanical). 11 mutants run in an isolated scratch copy, each caught: raw fast-preview store, no parked substitution, unfiltered explicit subscribe, no follow pin, drain without skip, freeze without exclusion, no session filter, own kill via smart path, plain kill without sweep (the reported bug), cache-miss route without sweep.
- **Upstream defects identified:** `tests/test_applink_pusher.sh:812 — FakePane lacks current_command, so the capture_pane_async case crashes in monitor_core.capture_pane_async (agent_key_from_pane(pane.current_command, …)); the script exits 1 after 98 ok checks — pre-existing since t1467 (0fb8ea25e, 2026-08-13), identical before and after this task`
- **Notes for sibling tasks:**
  - **t2034_3 (protocol):** the parked-set request becomes a per-client **capture-pin** request (`pins: [[session, window], …] | "all"`); the server computes the skip set itself (`parked_capture_skip(agent_marks.parked_session_windows(store, session→root), all subscribers' pins)`), and placeholder substitution is client-side (`client_view_snapshots(parked_pairs=…, pins=…)`). Compare-mode override = one shared per-pane request. Own pane and `M` never reach the server — clients filter with `client_view_snapshots`. applink's own-pane admission rule (cache-backed routes behave as a cache miss; key verbs unaffected) is part of the client contract. Single-pane routes (fast preview) must project too.
  - **t2037 (server):** reuse the pure helpers unchanged; the producer is already constructed with `all_sessions=True` and no exclusion. A client must publish pins, not a skip set.
  - Remaining per-client CPU is rendering (t2034_1 R2/R5): pushing per-pane deltas lets clients skip unchanged cards.
