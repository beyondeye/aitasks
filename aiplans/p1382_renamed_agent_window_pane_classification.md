---
Task: t1382_renamed_agent_window_pane_classification.md
Worktree: (none — current branch)
Branch: (current branch)
Base branch: main
Output branch: main
---

# t1382 — Renamed agent window degrades both monitor TUIs

## Context

Renaming a tmux agent window away from the `agent-` prefix (observed live:
window 7 `agent-explore-1` → `noam_bugs`) breaks both monitor TUIs:

- **minimonitor** drops the window entirely — it has no `PaneCategory.OTHER`
  handling at all, so a renamed window becomes invisible.
- **`ait monitor`** shows the window in its `OTHER` section, but **twice**:
  `noam_bugs(1)` (the real codeagent) and `noam_bugs(2)` (the companion
  minimonitor pane, which must never be listed).

Root cause is `TmuxMonitor.classify_pane()`
(`.aitask-scripts/monitor/monitor_core.py:1466`), which classifies purely by
window-name prefix. A rename flips every pane in the window from `AGENT` to
`OTHER` in one step, and each downstream `category == PaneCategory.AGENT` check
silently changes behaviour.

**Direction chosen (the task asks planning to pick one explicitly):** keep
prefix classification and add the `OTHER` fallback. A renamed window is
uncategorized *by design* — the user renamed it to take it out of the agent
rotation — so the fix is to keep it **visible** and keep companion panes
**hidden**. Name-independent agent detection is the durable fix but has a wide
blast radius (`lib/tui_switcher._AGENT_PREFIXES`,
`lib/framework_version.COMPANION_PREFIXES`,
`lib/agent_launch_utils.py:1500`, `monitor_app.py:2976`, and `_TASK_ID_RE` at
`monitor_core.py:2697` all key off the same prefix), needs a stamp at every
launch seam, and cannot recover the task-id binding from a renamed name
anyway. It is filed as a follow-up task (step 6 below).

## Fix A — companion pane leaks into monitor's OTHER list

`.aitask-scripts/monitor/monitor_core.py:1534-1537`:

```python
category = self.classify_pane(window_name)
# Filter companion panes (minimonitor/monitor) in agent windows
if category == PaneCategory.AGENT and _is_companion_process(pane_pid):
    continue
```

`_is_companion_process()` (`monitor_core.py:245`) is already name-independent —
it reads `/proc/<pid>/cmdline` (with a `ps` fallback) for
`_COMPANION_KEYWORDS`. It is the `category == PaneCategory.AGENT` **gate** that
stops it being consulted after a rename. Note the contrast with the
shadow-helper filter 20 lines above (`:1516`), applied unconditionally before
classification.

This is the **only** name-gated companion check in the package — `_parse_list_panes`
is the sole offender. `find_companion_pane` (`:2394`) and
`kill_agent_pane_smart` (`:2453`) already call `_is_companion_process`
unconditionally, so no consumer depends on companion panes surfacing as
`OTHER`.

**Change:** drop the `category == PaneCategory.AGENT and` conjunct.

**Cost control (memoization) — and why a PID-keyed memo alone is wrong.**
Unconditional means one probe per pane per 3 s refresh instead of per *agent*
pane. On Linux that is a `/proc` read; on macOS it is a
`subprocess.run(["ps", ...])` with a 2 s timeout — per shell, vim, lazygit
pane, every tick, **on the event loop** (`_parse_list_panes` runs inline in
both the sync and async discovery paths).

A naive memo keyed on `(pane_id, pane_pid)` would be **incorrect here**,
because a companion pane changes its cmdline *without* changing its PID. The
whole launch chain is `exec`-based:

```
ait:203         exec "$SCRIPTS_DIR/aitask_monitor.sh" "$@"
aitask_monitor.sh:62   exec "$PYTHON" "$SCRIPT_DIR/monitor/monitor_app.py" "$@"
```

so one PID spans the transition while `/proc/<pid>/cmdline` flips from
`bash …/aitask_monitor.sh` — which does **not** contain the
`_COMPANION_KEYWORDS` entry `monitor_app` — to `python …/monitor/monitor_app.py`,
which does. The launcher runs several `"$PYTHON" -c "import …"` preflight
probes before that `exec`, so the window is real, not theoretical. A pane
probed inside it would pin `False` **permanently** and be rendered as a bogus
`OTHER` card forever — reintroducing the exact symptom this task fixes.
(`aitask_minimonitor.sh` is immune only by accident: its own path contains the
substring `minimonitor`.) PID *generation* markers do not help either —
`/proc/<pid>/stat` starttime is unchanged by `exec`.

**Policy: cache confirmed companions only — never cache a negative.** The
transition that matters is `False → True` (a launcher pane exec'ing into
`monitor_app`), and it is exactly the direction a cached negative would hide.
A cached negative is therefore not allowed at *any* TTL: even a
refresh-scale one would list a companion pane for a tick or two, and the
requirement is that it is never listed. Negatives are re-probed every tick on
every platform, so the exec transition is picked up on the next refresh.

The reverse transition (`True → False`) has no plausible trigger — a running
Textual companion does not exec away, and when its process exits the pane
either dies (evicted by absence below) or lingers under `remain-on-exit`, where
staying hidden is the desired outcome anyway. A generous **300 s TTL** is kept
on positives purely as a self-healing backstop, so no verdict can be cached
forever; it also gives the TTL path something to test.

This drops the earlier Linux/macOS split entirely — with negatives uncached
there is no platform-dependent staleness to reason about, and
`_is_companion_process` stays untouched for its two other callers. The saving
is bounded but real: a session with *N* agent windows carries *N* companion
panes, and those are precisely the probes skipped.

```python
_COMPANION_MEMO_TTL = 300.0   # positives only; self-healing backstop
```

```python
# TmuxMonitor.__init__, near self._pane_cache
# pane_id → (pane_pid, session, cached_at) for panes CONFIRMED to be companions.
# Negatives are deliberately absent: a launcher pane execs into monitor_app under
# an unchanged pid, so a cached False would list a companion pane. tmux never
# reuses a pane id within a server lifetime, so (pane_id, pid) identifies one
# process instance; entries are dropped when the pid changes, when the TTL
# lapses, or when the pane leaves its session's list-panes output — so the memo
# cannot outgrow the live pane set.
self._companion_memo: dict[str, tuple[int, str, float]] = {}
self._monotonic = time.monotonic          # injectable clock seam (tests)

def _is_companion_pane(self, pane_id: str, pane_pid: int, session: str) -> bool:
    now = self._monotonic()
    hit = self._companion_memo.get(pane_id)
    if hit is not None and hit[0] == pane_pid and now - hit[2] < _COMPANION_MEMO_TTL:
        return True
    if _is_companion_process(pane_pid):
        self._companion_memo[pane_id] = (pane_pid, session, now)
        return True
    self._companion_memo.pop(pane_id, None)
    return False
```

`_parse_list_panes` calls `self._is_companion_pane(pane_id, pane_pid, session_name)`
and, before returning, evicts this session's stale entries (it is called once
per session per tick, so the sweep must be session-scoped or multi-session mode
would evict its peers):

```python
seen: set[str] = set()          # collected in the loop, for every line reaching
                                # the classify step (shadow panes included)
for key, (_pid, sess, _at) in list(self._companion_memo.items()):
    if sess == session_name and key not in seen:
        del self._companion_memo[key]
```

Leave `find_companion_pane` and `kill_agent_pane_smart` on the direct
`_is_companion_process` call — they are user-action paths, not the refresh loop.

## Fix B — minimonitor OTHER section

`minimonitor_app.py:753-794` (`_rebuild_pane_list`) filters to
`PaneCategory.AGENT` and mounts a flat list of `MiniPaneCard`s with no section
headers. `self._snapshots` already contains every category (`capture_all_async`
does not filter), so this is purely a rendering change.

Mirror `monitor_app.py:1567-1667`, adapted to the ~38-column pane:

1. **Partition** `self._snapshots` into `agents` / `others` on
   `PaneCategory.AGENT` / `.OTHER` (`TUI` panes stay unrendered, as in monitor),
   both excluding the followed pane, both sorted by
   `(session_name, window_index, pane_index)`.

2. **Factor the mount loop.** The multi-session divider block currently inlined
   in the agent loop is needed by both sections — extract a local
   `append_group(snaps, text_fn)` rather than copying it (the divider-count
   assertions in `tests/test_multi_session_minimonitor.sh` exercise it).

3. **Section header**, mounted only when `others` is non-empty, following the
   existing `── x ──` idiom (`.mini-own-header` at `:748`,
   `.mini-session-divider` at `:783`):

   ```python
   Static("[dim]── other ({n}) ──[/]", classes="mini-section-header")
   ```

   Add `.mini-section-header { height: 1; padding: 0 1; color: $text-muted;
   text-style: bold; }` to `MiniMonitorApp.CSS`, alongside `.mini-own-header`
   (`minimonitor_app.py:133-138`). No header is added for the agents section —
   minimonitor deliberately has none today and the session bar already carries
   the count.

4. **`_other_card_text(snap)`**, the narrow analogue of
   `monitor_app._format_other_card_text`:

   ```python
   #   2 (mark column, blank)  + 1 ○ + 1 sp + 20 name + 2 sp + 10 cmd = 36
   #   of the ~38 usable columns (40-wide pane minus `padding: 0 1`). The two
   #   leading blanks align the row under the agent rows' always-on mark glyph.
   ```

   `f"   [dim]○[/] {name}  [dim]{cmd}[/]"` with `name` truncated to 20
   (same cap and ellipsis as `_agent_card_text`, `:668-676`) and
   `current_command` truncated to 10. No mark, dot, shadow, compare-mode glyph,
   status, task title or gate line — matching monitor's one-line OTHER card.

5. **Counting is unchanged.** `_rebuild_session_bar` (`:570`) and
   `_compute_completed_panes` (`:618`) stay AGENT-only — `N agents` must keep
   meaning agents, exactly as monitor's own bar does. `_find_running_agent_line`
   (`:1227`) also stays AGENT-only: it resolves the task id out of the window
   name, which a renamed window no longer carries.

6. **Focus / selection.** `OTHER` rows are `MiniPaneCard`s like agent rows, so
   `_nav` (`:826`), `_restore_focus` (`:537`) and `_auto_select_own_window`
   (`:552`) pick them up with no change — matching monitor, where `OTHER` cards
   are focusable and `s` (switch to that window) is the useful action on them.

7. **Action guards** (the invariant "a `MiniPaneCard` is always an AGENT" is
   what breaks here; monitor already carries the equivalent guard at
   `monitor_app.py:2688`). Re-check inside the action, not via a binding gate:
   - `action_cycle_compare_mode` (`:1624`) — refuse with
     "Idle detection applies to agent panes only"; today it would write a
     compare-mode override for a shell pane that nothing reads.
   - `action_show_task_info` (`:1672`) — refuse with "Not an agent pane";
     today it degrades incidentally to "No task ID in window name".
   - `AgentMarksMixin.action_toggle_mark` (`monitor_shared.py:321`, after the
     `snap is None` return at `:346`) — refuse with "Marks apply to agent panes
     only". **This is the shared sink, so it also changes `ait monitor`:**
     marking a focused shell/lazygit `OTHER` card currently succeeds there.
     That is the same defect class and is fixed deliberately, not incidentally.
   - `s` (`action_switch_to`, `:1609`) is left **unguarded** by design — it is
     the one action that is meaningful on a non-agent pane.
   - `e` / `E` / `k` / `n` / `I` need no guard: they resolve through
     `_find_own_agent_snapshot()`, which stays strictly AGENT-only (below).

## Fix C — own-agent panel in a renamed window

`_find_own_agent_snapshot()` (`:506`) matches `category == PaneCategory.AGENT`
**and** `window_index`. In a renamed window it returns `None`, so
`_maybe_build_own_agent_panel` (`:731`) early-returns at `:743` every cycle and
the docked `#mini-own-agent` panel is **never built**. (A window renamed
*after* the panel built keeps the old name — the panel is static by design and
the task puts that out of scope.)

Under the chosen direction, own-agent-scoped keys (`k`, `n`, `e`, `E`, `I`)
*should* keep refusing in a renamed window — that is what "out of the rotation"
means. What must not happen is the panel silently never appearing. So split the
resolver by role rather than loosening the existing one:

```python
def _find_own_window_snapshot(self) -> PaneSnapshot | None:
    """The pane this minimonitor sits beside, agent or not.

    Identity/presentation seam — deliberately NOT the action seam. Prefers the
    AGENT match so a window holding both an agent and a stray shell resolves to
    the agent; falls back to the lowest-pane_index pane in the same window and
    session (deterministic across ticks). Shadow and companion panes never
    reach `_snapshots`, and this minimonitor's own pane is excluded by
    `exclude_pane`, so the fallback cannot pick a helper.
    """
```

- `_maybe_build_own_agent_panel` (`:742`) resolves through the new helper. When
  the resolved pane is not `PaneCategory.AGENT`, the header reads
  `── this window ──` instead of `── this agent ──`, so the degraded state is
  legible rather than looking like a missing agent.

  **The panel stays one-shot.** `_own_panel_built` (`:237`) is set at `:751`
  and never reset — the panel is built once and is static by design. So the
  `── this window ──` header is reached only by a minimonitor that **starts**
  (or is restarted) in an already-renamed window, which is exactly the defect
  case: today such a minimonitor early-returns at `:743` every cycle and the
  panel is never built at all. A window renamed *after* the panel built keeps
  the old header and the old name; the task puts that explicitly out of scope
  ("that content is captured once and not re-read"), so no
  panel-refresh-on-rename work is added here. The two states cannot collide:
  once the own pane is `OTHER`, `_rebuild_pane_list` excludes it from the OTHER
  section via the same resolver, so it never appears both docked and listed.
  `_own_agent_identity_text` (`:702`) needs no change — its
  `get_task_id_for_pane` lookup already returns `None` for a renamed window and
  it falls through to the bare window name.
- `_rebuild_pane_list` (`:764`) resolves `own_pane_id` through the new helper
  too, so the renamed own pane is excluded from the **OTHER** section (it is
  already shown in the docked panel).
- `_find_sibling_pane_id` (`:840`, backing `tab` / `enter`) prefers the new
  helper over its raw `list-panes` fallback. This closes a pre-existing hazard
  the docstring already flags: in a renamed window the strict resolver returns
  `None`, the fallback takes "the first non-minimonitor pane in the window", and
  that can be a **shadow** pane.
- `_find_own_agent_snapshot` itself is **unchanged** — all seven action call
  sites (`:850` via the new preference, `:951`, `:992`, `:1153`, `:1275`,
  `:1320`, `:1464`, `:1543`, `:1695`) keep their AGENT-only semantics.

## Tests

No existing test covers `PaneCategory.OTHER` on either side (`grep -rn "OTHER"
tests/` finds nothing for the pane-list partition), so both files are new. Both
are mock-based — **no live tmux**, so implementation is safe from inside a tmux
session. Each case must be shown to fail against the un-fixed code before the
fix lands.

**`tests/test_monitor_companion_filter.py`** (Fix A) — real-dataclass style, as
in `tests/test_monitor_shadow_zone.py:64-93` (`_pane()` / `_make_monitor()`):

- A companion-process pane in a **non-`agent-`** window is filtered out of
  `_parse_list_panes`' first list. *This is the case that fails today.*
- A companion pane in an `agent-*` window is still filtered (no regression).
- A non-companion pane in a non-`agent-` window survives as `OTHER` — the
  negative control proving the filter discriminates on the process, not the
  name.
- **Same-PID exec transition** (the case a cached negative would break). One
  pane, one unchanged `pane_pid`, `_is_companion_process` scripted to flip
  `False → True` (the `bash …/aitask_monitor.sh` →
  `python …/monitor/monitor_app.py` exec). The pane must be filtered out on the
  **very next** `_parse_list_panes` — no tick of exposure, no clock advance.
  *Negative control:* add negative caching (store the `False` verdict) and this
  test must fail, proving it discriminates.
- Memo mechanics: a confirmed-companion pane is probed once and not re-probed on
  the next tick (call-counting spy); a pane whose `pane_pid` changed re-probes;
  advancing the injected `_monotonic` past `_COMPANION_MEMO_TTL` re-probes; a
  pane absent from the next tick is evicted from `_companion_memo`; a
  *different* session's entries survive that sweep; a non-companion pane leaves
  **no** memo entry at all (asserted directly on `_companion_memo`, so the
  no-negative-caching rule is pinned as structure, not only as behaviour).

**`tests/test_minimonitor_other_section.py`** (Fix B + C) — app-stub style, as
in `tests/test_minimonitor_own_task_info.py:93-118`, with the
`FakeContainer` capture-`mount_all` harness from
`tests/test_multi_session_minimonitor.sh:176-190`:

- `_rebuild_pane_list` mounts an `── other (n) ──` header plus one
  `MiniPaneCard` per `OTHER` pane; `TUI` panes are mounted by neither section.
- No `OTHER` panes ⇒ no header mounted (a bare-agents list is byte-identical to
  today).
- The renamed own-window pane is excluded from the OTHER section.
- `_maybe_build_own_agent_panel` builds on the first tick when the own window is
  already renamed (today it never builds) and its header reads
  `── this window ──`; in an `agent-*` window it still reads `── this agent ──`.
  A second call after `_own_panel_built` is set mounts nothing — pinning that
  the panel stays one-shot and is not silently made refreshing.
- `_find_own_agent_snapshot` still returns `None` in a renamed window (pins that
  `k`/`n`/`e`/`E`/`I` stay refused — the deliberate half of the decision).
- Action guards: `action_cycle_compare_mode` and `action_show_task_info` no-op
  with a notice on an `OTHER` card and still act on an AGENT card (paired
  positive control); `action_toggle_mark` likewise, asserted for **both**
  `MiniMonitorApp` and `MonitorApp` since the guard lives in the shared mixin.
- Width: `_other_card_text` for a 40-char window name renders ≤ 38 columns,
  asserted on the composited screen (`_screen_text` / `_flat` helpers in
  `tests/test_minimonitor_pick_by_number.py`), not on `widget.render()` —
  per t1351, `render()` cannot reveal Rich ellipsising.

## Implementation steps

1. `monitor_core.py` — add `_COMPANION_MEMO_TTL`, and `_companion_memo` /
   `_monotonic` / `_is_companion_pane` to `TmuxMonitor` (positives only);
   make the companion filter unconditional and add the session-scoped eviction
   sweep in `_parse_list_panes`. `_is_companion_process` itself is untouched.
2. `monitor_shared.py` — category guard in `AgentMarksMixin.action_toggle_mark`.
3. `minimonitor_app.py` — `_find_own_window_snapshot`; rewire
   `_maybe_build_own_agent_panel`, `_rebuild_pane_list`,
   `_find_sibling_pane_id`; `_other_card_text`; `.mini-section-header` CSS;
   guards in `action_cycle_compare_mode` / `action_show_task_info`.
4. `tests/test_monitor_companion_filter.py` (new).
5. `tests/test_minimonitor_other_section.py` (new).
6. Follow-up task — **created as t1389** (user-requested): *name-independent
   stamped agent and task identity* — a pane-scoped `@aitask_agent` / `@aitask_task_id` stamp at spawn
   time, mirroring `@aitask_shadow_target` (`monitor_core.py:2662-2669`), so a
   renamed window keeps both its agent classification and its task binding.
   Must cover: every launch seam routed through
   `agent_launch_utils.launch_in_tmux`, the unstamped-legacy-pane fallback to
   prefix matching, and the other prefix consumers listed in Context.

## Verification

```bash
python3 tests/test_monitor_companion_filter.py          # new — Fix A
python3 tests/test_minimonitor_other_section.py         # new — Fix B + C
bash   tests/test_multi_session_minimonitor.sh          # divider/list structure
bash   tests/test_monitor_shadow_status.py 2>/dev/null || \
  python3 tests/test_monitor_shadow_status.py           # _pane_cache boundary
bash   tests/run_all_python_tests.sh                    # read the LAST line only
```

Negative control for each new test: revert the single corresponding source
mutation and confirm the suite exits 1 naming the expected test id (one
mutation at a time), then restore forward without `git checkout`.

**Live check (manual, non-destructive — rename + look).** Nothing here kills or
spawns panes, but it does touch the user's real session, so run it deliberately:

1. In a running session, `tmux rename-window -t <agent window> noam_bugs`.
2. `ait monitor` → exactly **one** `OTHER` card for `noam_bugs`; the companion
   minimonitor pane is gone.
3. Another session's minimonitor → the window appears under `── other (n) ──`;
   `s` switches to it; `d` / `i` / `space` report the guard notice.
4. The minimonitor **inside** that window: `k` / `n` / `e` / `I` report "no
   followed agent" (the deliberate behaviour of the chosen direction). Its
   docked panel still reads `── this agent ──` with the **old** name — the
   panel is one-shot and this is the out-of-scope case, not a defect.
5. Verify the new header separately, because it needs a fresh start: kill and
   relaunch the minimonitor in the renamed window (or open a new one), and
   confirm the docked panel now builds at all and reads `── this window ──`
   with the new name. Today it never builds in that situation.
6. Rename back to `agent-*` → the *pane lists* in both TUIs restore the agent
   presentation within one 3 s tick. Already-built docked panels do not change
   (same one-shot rule).

Step 9's `ait gates run` covers `risk_evaluated` (the task's active gate set).

## Risk

### Code-health risk: medium
- Fix A widens `_is_companion_process` from agent-prefixed panes to **every**
  pane on the 3 s refresh path; on macOS that path is a `subprocess.run(["ps"])`
  per pane, on the event loop. Caching only confirmed companions keeps the
  filter exact — the `False → True` exec transition is never hidden — but it
  also means the probe cost is only partially recovered (roughly the companion
  panes, one per agent window). The residual macOS cost is a real increase over
  today's agent-only probing and is not measured here · severity: medium ·
  → mitigation: TBD
- The `action_toggle_mark` guard lives in the shared `AgentMarksMixin`, so it
  changes `ait monitor` behaviour as well as minimonitor (marking a focused
  shell card stops working). Intended, but it is a second surface the task did
  not name · severity: low · → mitigation: TBD
- Splitting `_find_own_agent_snapshot` into an action seam and an
  identity seam adds a resolver that is easy to reach for at the wrong call
  site later; the nine existing call sites must stay on the strict one
  · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The chosen direction fixes the three reported symptoms but leaves the task-id
  binding lost on rename (unrecoverable from the name), so a renamed window
  stays degraded by design. This is the explicit decision, deferred to the
  step-6 follow-up · severity: low · → mitigation: TBD
- `_other_card_text`'s column budget is asserted at width 40 only, and only
  for single-cell characters — the `len()`-based caps under-measure
  double-width names, a flaw inherited from `_agent_card_text`. Confirmed in
  review and deferred to t1351's row-width audit, which owns both rows
  · severity: low · → mitigation: t1351

## Final Implementation Notes

- **Actual work done:** All three fixes landed as planned.
  - *Fix A* — `monitor_core._parse_list_panes` now calls the new
    `TmuxMonitor._is_companion_pane(pane_id, pane_pid, session_name)`
    unconditionally, dropping the `category == PaneCategory.AGENT and` conjunct.
    The memo caches **only confirmed companions** (`_companion_memo`, keyed
    `pane_id → (pane_pid, session, cached_at)`), with a 300 s
    `_COMPANION_MEMO_TTL` backstop, an injectable `_monotonic` clock seam, and a
    session-scoped `_evict_companion_memo` sweep driven by a `seen` set built in
    the parse loop. `_is_companion_process` itself is unchanged, so
    `find_companion_pane` and `kill_agent_pane_smart` keep calling it directly.
  - *Fix B* — `minimonitor_app._rebuild_pane_list` partitions into
    `agents` / `others`, mounts a bold `── other (n) ──`
    (`.mini-section-header`) header when `others` is non-empty, and renders each
    via the new `_other_card_text`. The session-divider block was factored into
    a local `append_group(snaps, text_fn)` shared by both sections.
    Guards added to `action_cycle_compare_mode` and `action_show_task_info`, and
    to the shared `AgentMarksMixin.action_toggle_mark`.
  - *Fix C* — new `_find_own_window_snapshot` (identity seam) backs the docked
    panel, the list exclusion, and `_find_sibling_pane_id`; the header reads
    `── this window ──` when the resolved pane is not an AGENT.
    `_find_own_agent_snapshot` (action seam) is untouched.
- **Deviations from plan:**
  - `_other_card_text` uses **two** leading spaces, not three as sketched in the
    plan; the budget arithmetic in its docstring is the two-space version and
    still totals 36 of ~38 columns.
  - The composited-screen width assertion uses a local 40-column `_RowHost`
    App that mounts one `MiniPaneCard` with minimonitor's own CSS metrics,
    rather than the `_screen_text`/`_flat` helpers named in the plan. Booting a
    full `MiniMonitorApp` would have needed a real `TmuxMonitor`; the host gives
    a genuine compositor pass at the true width without it.
  - The plan listed `action_launch_shadow_pick` (`E`) as needing a guard. It
    does not: it resolves through `_find_own_agent_snapshot`, which is
    AGENT-only. Verified during planning and left unchanged.
- **Issues encountered:**
  - The negative control for the memo caught a bug in the **test**, not the
    source: `test_same_pid_exec_transition_is_seen_on_the_next_pass` asserted
    `"%2" not in _companion_memo` *after* the exec, where a memo entry is
    correct (the pane is by then a confirmed companion). Fixed by snapshotting
    the memo right after the negative pass and asserting against that snapshot,
    and by ordering the behavioural assertion before the structural one so the
    control trips on the user-visible consequence.
  - Two negative controls initially failed with `AttributeError` rather than an
    assertion (unstubbed collaborators on the post-guard happy path, and an
    `IndexError` on an empty header list). Both test helpers were tightened so
    every control now fails as a clean assertion.
- **Key decisions:**
  - **Never cache a negative companion verdict, at any TTL.** The launch chain
    execs in place (`ait` → `aitask_monitor.sh:62` →
    `exec python monitor/monitor_app.py`), so a companion's cmdline flips
    `False → True` under an unchanged pid — the one direction a cached negative
    would hide, and it would hide it for as long as the pane lived. This also
    removed the need for the platform-split (`/proc` vs `ps`) memo an earlier
    revision of the plan proposed.
  - Prefix classification is kept; a renamed window is uncategorized by design,
    so own-agent keys (`k`/`n`/`e`/`E`/`I`) keep refusing there. Only visibility
    and companion-hiding were fixed.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/minimonitor_app.py:_agent_card_text` — the
    pre-existing agent row caps `window_name` with `len()`, which counts code
    points rather than terminal cells, so a double-width (CJK / emoji) window
    name occupies twice its measured width and Rich clips the row. Measured on
    the new OTHER row, which inherits the same convention: 36 code points, **64
    cells**, against a 38-cell budget. Both rows need cell-width-aware
    truncation (`rich.cells.cell_len` / `set_cell_size`). Reviewed during this
    task and dispositioned as a **follow-up**, routed to t1351 (the row-width
    audit), because fixing only the OTHER row would leave the far more common
    agent row wrong. Recorded in both docstrings and in the width test.
  - **→ t1388.** `.aitask-scripts/monitor/minimonitor_app.py:_find_sibling_pane_id` — the raw
    `list-panes` fallback ("first pane in the window that is not me") still has
    no shadow filter, so it can select a shadow pane. This change narrows the
    exposure a lot (the fallback is now reached only when no snapshot resolves
    at all, e.g. `_own_window_index` unset) but does not close it; the fallback
    could filter on `@aitask_shadow_target` the way discovery does.

## Follow-ups created

- **t1388** — `_find_sibling_pane_id` rung-2 fallback has no shadow filter
  (upstream defect surfaced here; exposure narrowed by this task, not closed).
- **t1389** — name-independent stamped agent/task pane identity: the durable
  fix this task deliberately deferred, with the full prefix-consumer survey.
- **t1351** — inherited the cell-width truncation defect (`len()` vs terminal
  cells) for both `_agent_card_text` and `_other_card_text`; see its
  "Incoming scope" section.
