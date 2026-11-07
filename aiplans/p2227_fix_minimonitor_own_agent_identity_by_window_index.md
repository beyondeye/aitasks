---
Task: t2227_fix_minimonitor_own_agent_identity_by_window_index.md
Base branch: main
Output branch: main
---

# t2227 — Resolve the minimonitor's followed agent by pane id, not window_index

## Context

A live minimonitor (window `aitasks:12 agent-pick-1981_3`) showed the
neighbouring agent's (`agent-pick-1893_6`) name and title in its docked
"this agent" panel, next to the real agent's phase line. Three causes:

1. `_find_own_agent_snapshot` / `_find_own_window_snapshot`
   (`.aitask-scripts/monitor/minimonitor_app.py:2377-2424`) match
   `snap.pane.window_index == self._own_window_index`. `renumber-windows on`
   shifts the index whenever an earlier window closes.
2. The index (`_update_own_window_info`, a per-tick `display-message`) and the
   snapshots (`capture_all_async`, or an even older shared-server scan) are read
   at different moments. A renumber between the two reads pairs a fresh index
   with stale ones.
3. `_maybe_build_own_agent_panel` freezes the name and title from the first
   snapshot it resolves and never rechecks them.

**The bug recurs; it is not a one-off.** The user reports it has appeared
several times. A second live instance was observed during planning, in this
pick's own window. Read-only evidence from 2026-11-07:
- Window `aitasks:10 agent-pick-2227` (`@227`) has minimonitor `%514`, started
  19:36:21, and agent `%513`.
- Its docked panel reads `☆ agent-explore-1`. No window by that name exists in
  session `aitasks` now; the `agent-explore-*` windows that do exist are in
  other sessions (`thinking_back`, `thinkingapp`).
- The general list correctly leaves out pick-2227, so the *current* lookup
  resolves; only the frozen panel is wrong.
- t2227 was created at 19:34 by an explore session. The likely sequence: the
  explore window (in `aitasks`) launched this pick and then closed, so this
  window renumbered into the index the explore window had just held. The
  panel's one-shot build caught the pre-close snapshot.

**Trigger confirmed by the user:** starting a new pick from a window while that
**origin window is killed at the same time**. The sequence:
1. The new pick window opens at index N+1, after the origin at N.
2. The origin is killed, and `renumber-windows` moves the new window to N.
3. The new minimonitor's tick reads its own index as N. The snapshots come from
   a scan taken before the kill, possibly by the shared status server, and still
   have the origin agent at N.
4. The one-shot panel freezes the origin's name. The identity-dependent actions
   (`k`/`n`/`e`/`E`/`I`) target the origin pane, if it still exists, for as long
   as the stale snapshot is served.

No framework code issues that kill (a grep for `kill-window` near the launch
paths finds none), so it comes from outside the launcher. The fix does not
depend on who kills the window. This is a routine workflow, not an exotic
race. The regression
fixture below mirrors exactly that shape. Minimonitors that are already
running keep the old code and must be restarted after the fix lands.

About 14 action sites (`k` kill, `n` next, `e`/`E` shadow, `I`, capture pin…)
go through `_find_own_agent_snapshot`, so a bad tick can also *act* on the
neighbour. The same bug class sits in `monitor_core.py`, which the user chose to
fold into this task. There, a cached snapshot's `window_index` is reused as a
tmux target:
- `_collapse_window_for` (`:4125`) decides whether `k` kills the whole window,
  so a stale index can turn a pane kill into a wrong window kill;
- `switch_to_pane`'s `select-window` (`:4007`);
- `find_companion_pane_id` (`:4021`).

The merged t1693 also asks to retire Tier 1d of
`tests/test_multi_session_minimonitor.sh`. That tier asserts a predicate copied
into the test, not the source. The task also asks for an audit of the file's
other tiers.

**Approach chosen:** stable ids, with no protocol change. Pane ids (`%N`) and
window ids (`@N`) never change for an object's lifetime. tmux resolves a pane id
given as a *window* target to that pane's current window. This already works in
production: `kill_window` runs `kill-window -t %N` (`monitor_core.py:4076`).
So:
- the minimonitor learns the **set of pane ids in its own window** each tick;
- it matches snapshots by `pane_id ∈ that set`;
- monitor_core targets pane ids instead of `=session:index`.

The rejected alternative is adding `window_id` to `TmuxPaneInfo`, both
list-panes formats (`monitor_core.py:2802`, `:3098`) and `status_protocol.py`
(`:347`, `:738`, `:807`). It would need a protocol field with
old-server/new-client skew handling, plus positional-parser edits in two
discovery paths. That is more blast radius for the same guarantee.

## Pre-phase (risk mitigations)

1. [probe_pane_id_window_targets] On a **scratch tmux server** (`tmux -L
   t2227probe -f /dev/null`, never the user's server; `kill-server` only on that
   `-L` socket at the end), run with `renumber-windows on`:
   - create windows 0, 1 and 2, with two panes in window 2 (`%A`, `%B`);
   - `kill-window -t :0`, so window 2 renumbers to 1;
   - check that `list-panes -t %A -F '#{pane_id}\t#{window_id}\t#{window_index}\t#{window_name}'`
     lists exactly `%A` and `%B` with the post-renumber index;
   - check that `select-window -t %A` selects that window;
   - check that `list-panes -t %A -F '#{pane_id}\t#{pane_pid}\t#{@aitask_monitor_kind}'`
     works.

   If any of these fails, stop and re-plan: the design depends on it. Record the
   transcript in the Final Implementation Notes.

## Implementation

### 1. Minimonitor: own-window membership from one per-tick query

`.aitask-scripts/monitor/minimonitor_app.py`

- `__init__` (~1539): add `self._own_window_pane_ids: frozenset[str] | None = None`,
  with a comment saying it is the identity source. Read it with
  `getattr(self, "_own_window_pane_ids", None)`, because many tests build the app
  with `__new__`.
- `_update_own_window_info` (~2312): replace the `display-message` with **one**
  call:
  `list-panes -t <TMUX_PANE> -F "#{pane_id}\t#{window_id}\t#{window_index}\t#{window_name}"`.
  Split each row with `split("\t", 3)` so a tab inside the name stays in the
  name. Validate the whole listing before touching any field:
  - rc 0 and non-empty output;
  - every non-blank row has 4 fields, a `%`-prefixed pane id and a
    `@`-prefixed window id;
  - all rows share one `window_id`;
  - `TMUX_PANE` is among the rows.

  On any failure, return `False` and leave every field as it was. This is
  stricter than today, where a two-field reply still updated id and index; that
  case is now just unconfirmed. On success, set `_own_window_id`,
  `_own_window_index` and `_own_window_name` from the **own pane's** row, set
  `_own_window_pane_ids` to the set of row pane ids, and return `True`. Same
  call count per tick as today.

  **Cached membership is for display; actions need confirmed membership.**
  `swap-pane`, `join-pane` and `break-pane` move pane ids between windows, so a
  set from an earlier tick is not proof of what is beside this pane now. Two
  pieces of state:
  - `_own_window_pane_ids`: the last *validated* listing. It is kept across a
    failed query and used **only** by display: the panel build and repaint, and
    the general list's "don't list the followed pane twice" exclusion.
  - `_own_identity_confirmed`: the existing per-tick flag. It is reset to
    `False` at the top of every `_refresh_data` and set from this method's
    return. It now means *this tick's listing validated the name and the
    membership*.

    `_update_own_window_info` returns `True` only on a fully validated listing.
    So a failed or partial query leaves the flag `False`, and every action
    refuses until the next good tick. Reusing the one flag keeps `_capture_pins`
    and the action seam on a single definition of "confirmed".

  Update the docstring.
- `_seed_own_window_info` stays `display-message`, on the ambient socket, and
  only fills empty fields. It must **not** seed membership: it races the first
  tick, and its answer comes from a different socket path. So before the first
  confirmed tick, every snapshot-based action refuses. The only exception is
  the `_find_sibling_pane_id` fallback below, which confirms independently.
- `_find_own_agent_snapshot(*, confirmed_only: bool = True)` (~2377): keep the
  AGENT-only scope.
  - It matches `snap.pane.pane_id in members`, where `members` is
    `_own_window_pane_ids`. With `confirmed_only`, it also requires
    `_own_identity_confirmed`; otherwise it returns `None`.
  - Drop the window_index and session predicate: pane ids are server-unique, so
    a cross-session agent can no longer collide.
  - `members` falsy → `None`.
  - Iteration stays first-match in discovery order, which keeps
    `WithinWindowOrderInvarianceTests` meaningful.

  The **default is the action seam**, so every existing caller stays safe
  unless it explicitly opts into display. Rewrite the docstring.
- `_find_own_window_snapshot(*, confirmed_only: bool = False)` (~2398) is the
  presentation seam. It passes `confirmed_only` through to the agent lookup,
  and its fallback candidates are `pane_id in members` (gated the same way).
  Keep the `min(pane_index)` tiebreak.
- **Call-site classification.** Each call site is classified and checked in
  review.
  - *Display (cached membership):*
    - `_maybe_build_own_agent_panel`
    - `_build_list_entries` (own-pane exclusion)
    - `_refresh_own_live_state`, which passes `confirmed_only=False`; a single
      failed tick must not flicker the glyph off.
  - *Action (confirmed only, the default):*
    - `action_kill_own_agent`
    - `action_pick_next_for_own`
    - `action_pick_task_by_number`
    - `action_launch_shadow`
    - `action_launch_shadow_pick`
    - `action_open_scratchpad`
    - `action_toggle_review_loop`
    - `action_pick_concerns`
    - `_maybe_offer_concerns`
    - `action_show_own_task_info`
    - `_current_agent_snapshot`, which feeds `sitrep_close.py` and
      `monitor_shared.py:1398`
    - `action_toggle_mark`
    - `_switcher_selected_session`, which falls back to the own session when
      unconfirmed, as it does today
    - `_find_sibling_pane_id`'s first rung, which calls
      `_find_own_window_snapshot(confirmed_only=True)`
- **`_find_sibling_pane_id` fallback (~3847-3873; it drives Tab focus and Enter
  forwarding).** Today it runs `list-panes -t <cached or seeded _own_window_id>`
  and takes the first non-self, non-helper pane, without checking that this pane
  is in the listing. New rule: the fallback must **confirm independently**.
  - List with `-t <TMUX_PANE>`, not the cached window id, so tmux resolves the
    window this pane is in *now*.
  - Refuse ("Own window not confirmed") unless one of the listing's raw records
    is `TMUX_PANE`. Check the raw records, not `classify_window_panes`' output:
    confirm during implementation whether the classifier drops the
    self/companion row.
  - Only then pick the first non-self, non-helper pane.

  This removes the dependency on `_own_window_id` here entirely, so a seeded
  window id from another socket can no longer steer it.
- Leave `_own_window_index` in place for display and diagnostics only. Grep to
  confirm that no identity decision still reads it.

### 2. Docked panel follows the resolved pane id

- Add `self._own_panel_pane_id: str | None = None` in `__init__`.
- `_maybe_build_own_agent_panel` (~3313): resolve `own_snap` first. If the panel
  is already built:
  - `own_snap is None` → return. A transient miss does not tear the panel down.
  - same `pane_id` as `_own_panel_pane_id` → return. A real rename of the same
    pane keeps the old header, as designed.
  - different `pane_id` → fall through and rebuild, which replaces the panel's
    children.

  Set `_own_panel_pane_id` on build. Rewrite the docstring: the panel is one-shot
  **per resolved pane**.

`_refresh_own_live_state` already reads the current lookup, so after a rebuild
the glyph and the phase line agree with the identity text.

### 3. monitor_core: pane-id window targets

`.aitask-scripts/monitor/monitor_core.py`

- `_collapse_window_for` (~4141): `list-panes -t <pane_id>` instead of
  `tmux_window_target(session, pane.window_index)`. Keep the cache-presence
  check: it is the "decidable" gate.
- `switch_to_pane` (~4007): `select-window -t <pane_id>`. For the companion,
  call `find_companion_pane_id(pane.window_index, target_session,
  window_target=pane_id)`.
- `find_companion_pane_id`: add a keyword-only `window_target: str | None = None`.
  When it is given, it is used verbatim as the `-t`. The positional form is
  unchanged, so `status_client.GATEWAY_NAMES` and the existing
  `FindCompanionPaneIdTests` are untouched.
- Update the tests that pin the old argv (`=session:idx`) for these three paths
  to the pane-id form. Find them with a grep for `select-window` /
  `list-panes` stubs in `test_multi_session_monitor.sh`,
  `test_monitor_companion_filter.py`, `test_session_root_resolution.py` and the
  kill tests. Update only what these three call sites produce.

**Checked and not changed:** `monitor_app.py`'s `window_index` uses are display
and sort only. Shadow pairing keys on the `@aitask_shadow_target` pane id.
`status_protocol` carries the index for display and sort only.

**Handed off (new task at Step 8):** `tui_switcher.py:1532` passes a
listing-time `target.window_index` into `agent_launch_utils` companion spawning
and `select-window` (`:2537`, `:2695-2874`). That is the same stale-index class,
but in a different subsystem: the switcher and launcher, not the monitor.

### 4. Tests

**New `tests/test_minimonitor_own_identity_renumber.py`** (unittest). It drives
the real `MiniMonitorApp` methods on a `__new__`-built app, with a fake panel in
the `_FakePanel` style of `tests/test_minimonitor_own_mark.py`. Fixture:
- own pane `%10`, followed agent `%9` (window `@5`, now at index `11`, name
  `agent-pick-1981_3`);
- neighbour agent `%20` (`agent-pick-1893_6`), whose **pre-renumber** snapshot
  carries window_index `11`;
- the followed agent's snapshot carries its old index `12`;
- the fake `tmux_run_async` answers the real `_update_own_window_info` with the
  post-renumber `list-panes` rows for `%9` and `%10`.

A second fixture mirrors the confirmed trigger: launch from an origin window
that is killed at the same moment. Window `agent-explore-1` is at
own index `10` in the pre-close snapshot, the own window `agent-pick-2227` is at
`11` in that snapshot, and the membership query answers post-close (index
`10`, members `%513`/`%514`). Run (a), (b) and (d) against both fixtures.

Cases:
- (a) after the real `_update_own_window_info`, `_maybe_build_own_agent_panel`'s
  identity text names `agent-pick-1981_3`, not `1893_6`;
- (b) lookups: `_find_own_agent_snapshot()` and `_find_sibling_pane_id()`
  return `%9`, never `%20`. This is direct-lookup coverage, kept separate from
  (b2).
- (b2) **real action handlers, asserting the dispatched pane id.** Both renumber
  fixtures put the real and neighbouring agents in the **same session**, so a
  session-only result proves nothing. `_switcher_selected_session` is therefore
  not used as action evidence.
  - `action_kill_own_agent`: stub `push_screen` to record the `KillConfirmDialog`
    and its callback. Invoke the callback with `True` against a recording fake
    `monitor.kill_agent_pane_smart`, and assert it was called with `%9`.
  - `_send_enter_to_sibling` (Enter forwarding): a recording fake
    `monitor.send_keys` asserts `("%9", "Enter")`.
- (c) **failed first query with a seeded window id.** The seed set
  `_own_window_id="@5"` and `_own_window_index`, and the first tick's listing
  failed.
  - `action_kill_own_agent` pushes no dialog and dispatches nothing.
  - `_send_enter_to_sibling` dispatches nothing when the fallback listing lacks
    `TMUX_PANE`. Its positive control: with `TMUX_PANE` present, it dispatches
    to the agent row.
  - The fallback's `list-panes` target is `TMUX_PANE`, never the seeded `@5`.
- (c2) **confirmed, then moved, then a failed query.** Tick 1 validates
  membership `{%9, %10}`. `swap-pane` then moves `%9` out and `%40` in. Tick 2's
  query fails.
  - `action_kill_own_agent` and `_send_enter_to_sibling` dispatch nothing:
    confirmation was reset, and the stale cached set is not used for actions.
  - The display lookup still resolves `%9` from the cache, and the panel does
    not flicker.
  - Tick 3 validates `{%40, %10}`: actions target `%40`, and the panel rebuilds
    to `%40`'s name.
- (d) panel rebuild: build against `%9`, then switch membership to a new pane
  `%30`; the next `_maybe_build_own_agent_panel` re-mounts with `%30`'s name;
- (e) the same pane renamed → no re-mount (positive control for the rename
  contract);
- validation unit cases for `_update_own_window_info`: a mixed window_id, the
  own pane missing, a short row, a tab in the name.

**monitor_core renumber case** (in `tests/test_monitor_companion_filter.py` or
a kill test): a cache entry with a stale window_index → `_collapse_window_for`
issues `list-panes -t %N`, and the stub answers only for that target.

**Pre-fix controls:**
- `PYTHONPATH` alone does **not** select the baseline. The repo's test
  bootstrap (e.g. `tests/test_minimonitor_own_mark.py:47-50`,
  `tests/test_monitor_companion_filter.py:39-41`) puts
  `<test file's repo>/.aitask-scripts` at the front of `sys.path`. So:
  1. `git worktree add --detach <scratchpad>/t2227_base HEAD`;
  2. **copy** the new regression test files into `<scratchpad>/t2227_base/tests/`;
  3. run them **from inside that tree**, with
     `AITASK_TEST_ASSERT_BASELINE=<scratchpad>/t2227_base`.

  The new test module checks, when that variable is set, that
  `minimonitor_app.__file__` and `monitor_core.__file__` resolve under it, and
  aborts otherwise. That way a run against the fixed code cannot pass as a
  baseline.
- **Fixtures must reach the pre-fix code's behaviour, not crash in setup.**
  - Every fixture also sets `_own_window_index` (post-renumber), which the old
    code reads.
  - The fake `tmux_run_async` answers **both** query shapes: the old
    `display-message` 3-field reply and the new `list-panes` rows, both
    post-renumber.
  - Setting `_own_window_pane_ids` on an old-code instance is a harmless extra
    attribute.
- Record the baseline per assertion. (a), (b), (b2), the stale-index part of
  (d) and the collapse case must fail with an **`AssertionError` naming the
  neighbour's pane or name**. An `AttributeError`, `ImportError` or other setup
  error counts as an invalid control, not a red. Cases (c) and (c2) test new
  refusal semantics and may legitimately fail differently; record the actual
  outcome for each rather than claiming them as reds.
- Also run the new tests with the fix in place, and check that each red case
  maps to its assertion.
- Remove the worktree afterwards. Never stash or restore in the shared
  worktree.

**Existing fixtures:** about 15 test files set `_own_window_index` to make the
lookup resolve (listed by
`grep -rl _own_window_index tests`). Each gets `_own_window_pane_ids =
frozenset({...})` with the pane ids its fixture means as "own window". Where a
test sets `_own_window_index = None` to mean "no followed agent", it also sets
membership to None. Rewrite `OwnWindowInfoConfirmationTests`
(`test_minimonitor_own_mark.py:897`) to the list-panes reply shape, keeping its
cases: full reply confirms; failed and empty do not; a truncated row does not
and now leaves all fields untouched; no `TMUX_PANE` does not.

**t1693 — `tests/test_multi_session_minimonitor.sh`:**
- Delete Tier 1d (the `would_match` mirror). It is superseded by
  `tests/test_minimonitor_focus_in_click.py` (the real `_auto_select_own_window`)
  and by the new file's real-method cross-session/index cases.
- Update the header comment's "Covers" list.
- Tier 1g: move its fixture to membership. Keep `OWN_NOT_CROSS`, which is now
  real behaviour: `%3` is not a member.
- Audit Tiers 1a, 1b, 1c, 1e, 1f, 1g and 1h one by one for self-mirroring. For
  each, record a one-line verdict in the Final Implementation Notes: does it
  call or import the real method, or re-implement it? Fix any mirror found the
  same way.

## Verification

- `bash tests/test_multi_session_minimonitor.sh`
- `python -m pytest` on the new file plus every touched test file
- `bash tests/test_no_raw_tmux.sh`
- `bash tests/test_multi_session_monitor.sh`
- `tests/test_monitor_client_surface.py`, `tests/test_tmux_run_parity.sh`
- Full suite: `bash tests/run_all_python_tests.sh` (last line only, with
  `set -o pipefail`)
- `shellcheck` on the touched `.sh` tests
- The pre-fix control run recorded above
- Grep: `grep -n "_own_window_index" .aitask-scripts/monitor/minimonitor_app.py`
  shows no identity predicate.

Step 9 (Post-Implementation): commit code and plan separately, archive t2227,
and delete the folded t1693 file during archival.

## Risk

### Code-health risk: medium
- About 15 test fixtures move from index-keyed to membership-keyed identity. A
  mis-migrated fixture shows up as a test failure, not a silent bug, but the
  edit is wide · severity: medium · → mitigation: None (covered by the
  full-suite run)
- The shared `monitor_core` kill and switch paths change their tmux target form
  from `=session:index` to `%N`. This is only safe if tmux resolves a pane id as
  a window target for `list-panes` and `select-window` too, not only for
  `kill-window` · severity: medium · → mitigation: inline pre-phase
  probe_pane_id_window_targets
- About 16 own-lookup call sites are split into display (cached membership) and
  action (confirmed this tick). A misclassified action would act on cached
  membership. Mitigated by design: `confirmed_only=True` is the default, so only
  the three named display sites opt out. The tests in (c) and (c2) pin the
  refusal through real handlers · severity: medium · → mitigation: None (in
  plan)
- The per-tick own-identity query changes from `display-message` to a validated
  `list-panes`. The validation is stricter, so a malformed listing now leaves
  identity unconfirmed for that tick · severity: low · → mitigation: None

### Goal-achievement risk: low
- The window-close event behind the live symptom was not reproduced. The fix
  removes the `window_index` dependency entirely, so it holds whichever race
  occurred · severity: low · → mitigation: None
- The panel can no longer build from the mount-time seed; it waits for the
  first confirmed tick (about one refresh interval) · severity: low ·
  → mitigation: None

### Planned mitigations
- name: probe_pane_id_window_targets · timing: inline pre-phase · inline_risk: low · added_complexity: low

## Final Implementation Notes

- **Actual work done:**
  - `minimonitor_app.py`:
    - New module-level `OWN_WINDOW_LISTING_FORMAT` and
      `parse_own_window_listing()`, which validates the whole listing.
    - `_update_own_window_info` makes one `list-panes -t $TMUX_PANE` call
      (replacing the `display-message`) and records `_own_window_pane_ids`.
    - New `_own_members(confirmed_only)` helper.
    - `_find_own_agent_snapshot(confirmed_only=True)` is the action seam;
      `_find_own_window_snapshot(confirmed_only=False)` is the display seam.
      Both match by pane id. The window_index and session predicates are gone.
    - `_refresh_own_live_state` reads the display seam.
    - `_maybe_build_own_agent_panel` records `_own_panel_pane_id` and rebuilds
      when the resolved pane changes. A same-pane rename still keeps the
      header.
    - `_find_sibling_pane_id`: rung 1 is confirmed-only. Rung 2 lists
      `-t $TMUX_PANE` (never the cached or seeded `_own_window_id`) and refuses
      with "Own window not confirmed" unless a raw record is this pane.
  - `monitor_core.py`:
    - `_collapse_window_for` lists `-t <pane_id>` and returns None
      (undecidable) when the listing lacks that pane.
    - `switch_to_pane` runs `select-window -t <pane_id>`.
    - `find_companion_pane_id` gained a keyword-only `window_target`. The
      positional form and `GATEWAY_NAMES` are unchanged.
- **Pre-phase probe `probe_pane_id_window_targets`:** passed, on the scratch
  socket `tmux -L t2227probe -f /dev/null`, which was killed afterwards:
  - windows w0/w1/w2 were created, with panes `%2`/`%3` in w2, then
    `kill-window w0`;
  - `list-panes -t %2` returned `%2 @2 1 w2` and `%3 @2 1 w2`, the
    post-renumber index;
  - `select-window -t %2` moved the active window from w1 to w2 (rc 0);
  - the companion-format listing `-t %2` returned rc 0.
- **Live evidence (2026-11-07), read-only:** this pick's own window
  `aitasks:10` (`@227`) has minimonitor `%514`, whose panel read
  `☆ agent-explore-1`. That window no longer exists in `aitasks`. The user
  confirmed the trigger: launching a pick from a window while killing that
  window.
- **Pre-fix control (baseline worktree at HEAD a00121816):** the new test file
  was copied into the worktree's `tests/` and run with
  `AITASK_TEST_ASSERT_BASELINE`; the module-origin guard passed. All 18 cases
  fail there:
  - **Behavioural reds, each an `AssertionError` naming the neighbour or the
    stale target:**
    - (a) panel name `☆ agent-pick-1893_6` (fixture A) and `☆ agent-explore-1`
      (fixture B, the exact live symptom);
    - (b) `%20 != %9` and `%400 != %513`;
    - (b2) kill `['%20']` / `['%400']`, Enter `('%20')` / `('%400')`;
    - (d) the panel kept `1893_6`;
    - collapse: `True is not False`, and kill-window was issued instead of
      kill-pane;
    - switch: `select-window -t =s1:4`.
  - **New-semantics cases:**
    - (c): the old code resolved `%20` after a failed first query, because the
      seeded index pointed at the neighbour;
    - the old fallback listed `-t @5`;
    - the old fallback dispatched to `%9` without confirming that this pane
      was in the listing;
    - (c2) and (e) fail at their first identity assertion (the wrong panel
      name).
  - **Invalid as controls:** the 5 parser cases fail with `AttributeError`
    (new API).
  - After the run, the worktree was removed with `git worktree remove`.
- **Deviations from plan:**
  - Fixtures in `test_monitor_pick_launch_sites.py`, `test_applink_router.sh`
    and `test_multi_session_monitor.sh` answered `list-panes` with an empty or
    short listing. The old code read that as "alone in its window"; it is not
    a realistic listing. They now return full `FROZEN_AWARE_PANE_FORMAT` rows
    that include the pane. The `test_multi_session_monitor.sh` Tier 1f stub had
    3-field rows, so its "sibling → kill-pane" path never actually ran; it now
    does, and the tier asserts it.
  - `test_minimonitor_startup_input_latency.py`: the unseeded-window refusal
    now reads "Own window not confirmed", because the fallback no longer
    consults the seeded id.
- **t1693 audit of `tests/test_multi_session_minimonitor.sh`:**
  - **1a:** reads the real `BINDINGS` and checks `hasattr` on the real class.
    Real.
  - **1b:** calls the real `action_toggle_multi_session`. Real.
  - **1c:** calls the real `_start_monitoring` with `TmuxMonitor` patched. It
    was **crashing** (`AttributeError: _monitor_server`, since t2037_3). Under
    `set -e` that aborted the whole file before its summary, so no tier had run
    since then. Repaired the stub, patched the documented
    `build_monitor_client` seam, and added a `CONSTRUCTED:` witness so the two
    kwarg assertions can't pass vacuously.
  - **1d:** deleted, as a self-mirroring copy of a predicate that no longer
    exists. Superseded by `tests/test_minimonitor_focus_in_click.py` and the
    new renumber file.
  - **1e, 1f, 1g:** call the real `_rebuild_pane_list` /
    `_rebuild_session_bar` / lookups / `_maybe_build_own_agent_panel`. Real.
    The 1e and 1g fixtures moved to membership.
  - **1h:** calls the real `_switcher_selected_session`. Real; moved to
    membership.
  - **1i** (was a second "1g"): calls the real `_agent_card_text`. Real.
  - Result: 39/39 pass.
- **Not run here:** the live-tmux tests `test_cleanup_rule_parity.sh`,
  `test_frozen_standin_spike.sh`, `test_scratchpad_spawn_live.sh` and
  `test_freeze_engine_live.sh` refuse to run inside a tmux session, by design.
  Run them from a terminal outside tmux.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/tui_switcher.py:1532` — passes a listing-time
    `target.window_index` into `agent_launch_utils` companion spawning and
    `select-window` (`agent_launch_utils.py:2537`, `:2695-2874`). It is the
    same stale-index class as this task, in the switcher/launcher subsystem; a
    renumber between the listing and the action can spawn the companion into,
    or select, the neighbouring window.
  - `tests/test_board_movement.py:1291` —
    `IsolationNegativeControlTests.test_in_process_task_dir_override_reads_the_real_repo`
    asserts against the live repo's active task list. It fails at pure HEAD
    whenever an unexpected task file such as `t2226_*` is present, so it is not
    hermetic.
- **Issues encountered:**
  - `tests/test_multi_session_minimonitor.sh` Tier 1c had been crashing since
    t2037_3. Under `set -e` it aborted the file before its summary, so no tier
    in that file had run. Repaired here.
  - Several kill-path fixtures used empty or short `list-panes` replies, which
    the old collapse decision read as "alone"; they now return realistic rows.
- **Key decisions:**
  - Pane-id membership instead of adding `window_id` to `TmuxPaneInfo` and the
    status protocol: no protocol versioning, same guarantee.
  - The single per-tick `_own_identity_confirmed` flag gates both the capture
    pin and every action. It is withdrawn as soon as a refresh is admitted.
  - Display paths use the last validated membership; actions never do.
  - The Tab/Enter fallback confirms the window independently via
    `-t $TMUX_PANE`.
  - The collapse decision treats a listing without the target pane as
    undecidable, so it falls back to a plain pane kill.
- **Operational note:** minimonitors that are already running keep the old
  code. Restart them, or the windows, to pick up the fix.
- **Review round: confirmation-reset ordering (CONFIRMED, fixed).**
  - **The bug:** `_refresh_data` awaited `get_session_to_project_mapping_async`
    before resetting `_own_identity_confirmed`. So during a suspended refresh,
    `k` and Enter still acted on the previous tick's confirmation, after a
    `swap-pane` had already moved the followed pane out.
  - **The fix:** the reset now runs right after the re-entrancy guard admits
    the refresh (`_refresh_inflight = True`), before the first await. The
    redundant in-tick reset before `_update_own_window_info` is removed.
  - **The test:**
    `RefreshWithdrawsConfirmationTests.test_an_action_during_a_suspended_refresh_refuses`
    holds the REAL `_refresh_data` in its session-mapping await. It asserts
    that the flag is withdrawn, that `k` dispatches nothing, that Enter
    dispatches nothing, and that the cancelled refresh does not strand
    `_refresh_inflight`.
  - **Mutant control:** in an isolated worktree at HEAD with the working
    sources, the reset was moved back after the await. Exactly this test then
    failed (`True is not false : the previous tick's confirmation survived into
    the suspended refresh`); the other 18 passed. The worktree was removed.
- **Full Python suite (before this round's fix):**
  `PYTHON SUITE: FAILED (runner=pytest, exit=1)`, with 6 failures, none caused
  by t2227:
  - 4 in `test_sitrep_window.py` and 1 in `test_metadata_writer_inventory.py`.
    All pass in an isolated worktree at HEAD with only my two monitor sources
    applied, so they come from other sessions' uncommitted edits in the shared
    tree (`helper_panes.py`, `sitrep_*`, `sitrep_open.py`, …).
  - 1 in `test_board_movement.py`
    (`test_in_process_task_dir_override_reads_the_real_repo`). It fails
    identically at pure HEAD, because it reads the live repo's task data.
- **After this round's fix:** 1554 passed in the affected Python set (every
  module touching the changed seams or `_refresh_data`); the only failures were
  the same 4 `test_sitrep_window` cases. The touched shell tests all pass.
- **Code commit:** 434b9d306 (`bug: Resolve the minimonitor's followed agent by pane id, not window index (t2227)`).
