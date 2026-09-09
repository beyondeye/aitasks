---
Task: t1705_7_monitor_minimonitor_frozen_rows.md
Parent Task: aitasks/t1705_frozen_codeagents_session_store_and_viewer_tui.md
Sibling Tasks: aitasks/t1705/t1705_10_freeze_restore_workflow_docs.md, aitasks/t1705/t1705_11_manual_verification_frozen_codeagents_session_store_and_view.md, aitasks/t1705/t1705_8_frozen_agents_acceptance_test.md, aitasks/t1705/t1705_9_frozenagent_tui_docs.md
Archived Sibling Plans: aiplans/archived/p1705/p1705_1_spike_freeze_standin_and_session_id_capture.md, aiplans/archived/p1705/p1705_2_framework_session_store.md, aiplans/archived/p1705/p1705_3_session_id_capture_hooks.md, aiplans/archived/p1705/p1705_4_freeze_engine.md, aiplans/archived/p1705/p1705_5_restore_and_repick_flows.md, aiplans/archived/p1705/p1705_6_frozenagent_viewer_tui.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-09 11:59
---

# t1705_7 — Frozen rows, counters, unified filter and keys in monitor + minimonitor

## Context

t1705 makes a code agent *freezable*: its process ends, its terminal output is
captured, a stand-in viewer takes its pane, and it can later be restored or
re-picked. Children 1–6 shipped the whole engine — session store, hooks, freeze
coordinator, restore coordinator, and the `ait frozenagent` viewer. What is
missing is that **neither monitor TUI knows the state exists.** A frozen agent
today renders as a normal agent row whose state dot and idle verdict are
arbitrarily stale, and there is no way to freeze or restore one without dropping
to the CLI.

This task closes that: frozen agents get an honest row, their own counter term,
inclusion in the existing hidden-agents filter, and keys to freeze / restore /
re-pick / drop. It is the last implementation child; t1705_8 owns the live tmux
acceptance tests and t1705_9/10 own the docs.

### What re-verification changed (the existing plan is stale in five places)

The plan in `aiplans/p1705/p1705_7_*.md` predates t1705_6. Verified against the
tree:

1. **Key collisions are real.** `monitor_app.py` already binds `z` =
   `cycle_preview_size` ("Zoom") and `R` = `restart_task` ("Restart"). The
   plan's literal `z`/`R` cannot land there. Resolved below.
2. **`monitor_core.py` line numbers are stale by ~130–160 lines** (the plan
   cites `capture_all_classified_async` at :2886, it is at :3048;
   `commit_snapshots` :3019 → :3151; `_parked_snapshot` :1045 → :1177).
   `monitor_shared.py` and the two apps are accurate to ±5.
3. **`TmuxPaneInfo.frozen_record`, `last_discovered_panes()`,
   `FROZEN_OPTION`/`RECORD_OPTION`/`STANDIN_READY_OPTION`/`AGENT_SESSION_OPTION`
   already exist.** `last_discovered_panes()`'s own docstring
   (`monitor_core.py:2046`) says it is unconsumed and waiting for this task.
   **Both observation-protocol readers already handle `PANE` rows** —
   `agent_marks._read_observed` skips them (:625), `agent_sessions` parses them
   (:1236). Only the *writer* is missing.
4. **`kill_agent_pane_smart` is now kill-then-drop** (t1705_6 reversed
   t1705_4) and its `_drop_session_record` is a best-effort, **unleased**
   `aitask_agent_sessions.sh drop`. It must **not** be the TUI's frozen-drop
   path: `aitask_frozen.sh drop` does lease-take → preflight → kill → verify-gone
   → `drop --nonce`, refuses a racing restore (`DROP_REFUSED:<id>|in_flight`),
   **and already implements the same window-collapse rule**
   (`agent_freeze.py:987`). It is a strictly better fit, verified.
5. **`freeze --all` prints no summary line** — one line per pane (`FROZEN:` /
   `FREEZE_FAILED:` / `FREEZE_SKIPPED:<id>|already frozen`). The plan's
   "notify `<ok>/<total>`" must be counted by the caller. (`restore --all` *does*
   emit `RESTORE_ALL:<ok>/<n>`; freeze does not.)

### Decisions taken with the user (supersede the plan text)

- **One filter, one key, one list.** No `F` binding and no
  `action_toggle_frozen_visibility`. The existing `P` filter is **widened** to
  hide parked *and* frozen agents.
- **`f` = freeze this agent, `Z` = freeze all**, identical in both apps (both
  keys free in both), each behind a confirm dialog; `Z`'s dialog names the count.
- **`R` / `p` / `k` act only on the current agent, and only when it is frozen** —
  minimonitor: the **followed** agent (its docked own-panel, same target as its
  existing `k`); monitor: the **focused card** (same target as its existing `k`).
  Frozen rows that are not the current agent are inert display only.
- **Font manifest is hand-written and flagged** (see Risks).

## Approach

### Pre-phase (risk mitigations)

**`characterize_restore_poll`** — before touching `frozenagent_app.py`, write
`tests/test_frozenagent_restore_poll_characterization.py` pinning the *current*
observable verdicts of `_poll_restore` / `_poll_drop` (:869-928), covering at
minimum: pre-begin (`restore_attempts` unchanged) before and after
`DISPATCH_GRACE`; `live` + `ack=liveness`; `live` without it; `frozen` **with a
cleared `op_nonce` but a preserved `last_error`** (the trap the code documents);
`frozen` with no error; and the post-grace still-transitional timeout. Run it
**green against unmodified code** — that is the control that makes it evidence —
then extract `restore_verdict` (§6) and require it to stay green with no
assertion edited.

### 1. `monitor_core.py` — frozen plumbing, mirroring `parked` exactly

Add `ClassifyResult.frozen: bool = False` (beside `parked`, :219);
`PaneSnapshot.frozen: bool = False` + `frozen_record_id: str = ""` (beside
`parked`, :1221); module-level `_frozen_snapshot(pane, now)` beside
`_parked_snapshot` (:1177) — built directly, **never** through
`_apply_bookkeeping`, for the reason that function's docstring already records;
and `TmuxMonitor._is_frozen_pane(pane)` beside `_is_parked_pane` (:1943):

```python
return pane.category == PaneCategory.AGENT and pane.frozen_record != ""
```

No `set_frozen_agents` publish-down — unlike parked, the truth is already in the
discovery row (`FROZEN_OPTION` at `_LIST_PANES_FORMAT` field 11), which is what
makes it stable between capture and commit.

In `capture_all_classified_async` (:3048), after `_record_discovery_facts`
(:3084), make the two splits **mutually exclusive with frozen first** — not two
independent filters over the same list:

```python
frozen_panes = [p for p in panes if self._is_frozen_pane(p)]
frozen_ids   = {p.pane_id for p in frozen_panes}
parked_panes = [p for p in panes
                if p.pane_id not in frozen_ids and self._is_parked_pane(p)]
```

**Ordering is load-bearing.** `frozen` coexists with the parked *mark* (PINNED),
so a pane can satisfy both predicates. The current code (:3102) splits parked
first over *all* panes; adding a frozen split beside it would hand a
frozen-and-parked pane a `parked=True, frozen=False` snapshot. Checking `frozen`
first in the row renderer cannot recover that — the field is simply not set — so
the row would render `parked`, the session bar would miscount, and the `R`/`p`/`k`
guards would refuse on a genuinely frozen agent. The mark still renders (it comes
from `_mark_kind`, not from the snapshot), which is exactly the coexistence the
task pins. Shadows stay unfiltered, as for parked.

In `commit_snapshots` (:3151) route to `_frozen_snapshot` **before** the parked
branch and before the `result is None` drop (:3225).

**Also guard the single-pane fast path — it is a second, unguarded capture
route.** `monitor_app._fast_preview_refresh` (:1302) does not use the bulk path
at all: it calls `capture_pane_classified_async` (:2967) then `commit_snapshot`
(:2896) and overwrites `self._snapshots[pane_id]`. `commit_snapshot` goes
straight to `_apply_bookkeeping` with no state branch, so focusing a frozen pane
would capture it, run prompt/idle classification over a dead stand-in, and
replace its `frozen=True` snapshot with an ordinary one — losing the row render,
the counter, the preview placeholder and the action guards on the very pane the
user is looking at.

Fix at the **core seam**, not the app, so every caller inherits it:
`capture_pane_classified_async` returns `(gen, pane, "", ClassifyResult(
compare_value="", frozen=True))` **before** its tmux await when
`_is_frozen_pane(pane)`; `commit_snapshot` routes a `result.frozen` to
`_frozen_snapshot`, mirroring `commit_snapshots`.

> **Pre-existing defect found while verifying this (out of scope, follow-up).**
> `parked` has the identical hole at the identical two functions: a focused
> parked pane is captured and classified today, and its `parked=True` snapshot is
> overwritten — so the parked preview placeholder (`monitor_app.py:1961`, which
> reads `snapshots[...].parked`) silently reverts to stale content. That is a
> live t1685 bug, not something this task introduces. I will **file a follow-up
> task** rather than fold a behaviour change to shipped parked code into this
> one; the frozen guard added here is written so the parked case is a two-line
> addition once that task runs.

### 2. `monitor_shared.py` — glyph, unified filter, sessions purge, command seam

- `FROZEN_GLYPH = "F"` beside `PARK_GLYPH` (:251) with the same measurement
  comment shape. `format_frozen_prefix(kind)` returning
  `format_mark_glyph(kind) + f"[bold cyan]{FROZEN_GLYPH}[/]"`. Do **not** add a
  frozen kind to `agent_marks` — `format_mark_glyph` raises on unknown kinds by
  design (:293) and frozen composes *with* a mark, it is not one.
- **Widen the filter. Rename the state, NOT the action id.**
  - Rename the internal state only: `_hide_parked` → `_hide_inactive` (class
    floor :443, init :516) plus a shared
    `_is_inactive(snap) = snap.parked or snap.frozen`. A flag named
    `_hide_parked` that also hides frozen agents is exactly the "two names
    disagreeing" trap p1685's notes record. ~9 source + ~16 test references,
    mechanical. `_hand_off_focus_before_hiding`'s guard
    (`monitor_app.py:2689`) widens too.
  - **`toggle_parked_visibility` stays the action id, and
    `action_toggle_parked_visibility` stays the method name.** The action string
    in `BINDINGS` is a **persisted public identifier**, not an internal name:
    `keybinding_registry.register_app_bindings` resolves overrides with
    `overrides.get(str(binding.action))` (:136) against the `shortcuts:` section
    of `userconfig.yaml`, scoped `monitor` / `minimonitor`
    (`monitor_app.py:383`, `minimonitor_app.py:858`). Renaming it would orphan
    every existing user override in **both** scopes — a customized `ctrl+p`
    would silently revert to the default `P`, with no error anywhere. A Python
    method alias does not help: the registry keys off the string in `BINDINGS`,
    and Textual dispatches `action_<that string>`.

    Only the **description** widens ("Parked/frozen") — labels are recorded as a
    *value* in `_DEFAULTS[(scope, action)]`, never as a key, so changing one is
    safe. Carry a comment at the binding saying why the action id deliberately no
    longer matches the field name, so nobody "tidies" it later.
- `_run_marks_cmd` (:631) gains keyword-only `script=_MARKS_SH` **and
  `timeout=_MARKS_CMD_TIMEOUT`** parameters (its error strings already
  interpolate `_MARKS_SH.name` → `script.name`); `_run_frozen_cmd(argv, timeout)`
  calls it with `_FROZEN_SH`. One timeout / zombie-reap implementation, two
  scripts, **two budgets**.

  **The marks budget must not be reused for freeze.** `_MARKS_CMD_TIMEOUT` is
  20.0s and the helper *kills* the child on expiry, but one freeze spends up to
  30s in `capture-pane` alone (`agent_freeze.py:197`) plus two 20s store calls
  (`freeze-begin`, `freeze-commit`) plus a respawn — a single legitimate freeze
  can exceed 20s, and `freeze --all` is **sequential over every eligible pane on
  every session**, so it exceeds it routinely. Worse, `agent_freeze.main()`
  buffers the whole batch and prints the per-pane lines only after `freeze_all()`
  returns, so a killed batch reports **nothing** — including the agents it had
  already frozen — and the remaining agents are never processed.

  Budgets, bounded but honest:
  - `_FREEZE_ONE_TIMEOUT = 90.0` for `freeze <pane>` (30 capture + 20 + 20 + slack).
  - `freeze --all`: `_FREEZE_ONE_TIMEOUT * max(1, eligible)`, using the same
    eligible count the confirm dialog shows (§4). Scaling with the real batch
    size is what keeps it bounded without being arbitrary.

  On expiry the notify must read as **partial, not failed** — "freeze timed out;
  some agents may be frozen — run `aitask_frozen.sh reconcile`". A killed freeze
  leaves a `freezing` record that reconcile settles once the lease goes stale, so
  the damage is a stranded record, never lost capture; saying "failed" would send
  the user looking for a problem that repairs itself.
- `_write_observation_file` (:873) gains `panes=None` and emits
  `PANE\t<root>\t<window>\t<pane_id>\t<pane_pid>\t<pane_dead>` rows after the
  `WINDOW` rows. Both readers already handle this — no reader change.
- `_maybe_purge_sessions()` as a twin of `_maybe_purge_marks` (:887) with its own
  inflight flag and the same `_MARKS_PURGE_STARTUP_GRACE` / `_MARKS_PURGE_INTERVAL`,
  awaited **inside** the `_maintenance()` coroutine in
  `_dispatch_refresh_maintenance` (:476-479) — never by the render path. It writes
  the observation file with `panes=self._monitor.last_discovered_panes()`, then
  runs `aitask_agent_sessions.sh purge --observed <f>` and
  `aitask_frozen.sh reconcile`.

### 3. Both apps — row, filter, partition, session bar

Treat `frozen` exactly as `parked` at every partition site, with `frozen`
**winning** the row render (checked first):

| site | minimonitor | monitor |
|---|---|---|
| row render | `_agent_card_text` :2261 | `_format_agent_card_text` :1721 |
| filter | `_rebuild_pane_list` :2652 | :1830 (+ :1086 focus honouring, :2704) |
| completed skip | `_compute_completed_panes` :2241 | :1431 |
| session bar | `_rebuild_session_bar` :2166 | :1637 |
| auto-switch ×3 | — | `_maybe_auto_switch` :1474 / :1487 / :1498 |
| concern offer | — | `_offer_concerns` :1182 |
| signature scan | — | `_scan_concern_signatures` :2293 |

Row becomes `f"{format_frozen_prefix(self._mark_kind(snap))} {name}  [dim]frozen[/]"`
(monitor keeps its `window_index:window_name (pane_index)` shape). The mark glyph
is display-only on a frozen row; `space` still cycles it.

Session bar keeps **separate** terms so parked and frozen stay distinguishable —
minimonitor `[dim]{n}f[/]` after `{n}p` (:2179), monitor `"  N frozen"` after
`"  N parked"` (:1649) — and both leave every live bucket:
`live = [a for a in agents if not a.parked and not a.frozen]`. Terms render
independently of the filter, as the parked term already does.

### 4. Keys

New in both apps: `Binding("f", "freeze_current", …)`,
`Binding("Z", "freeze_all", …)`, and `Binding("p", …)` in monitor only (minimonitor
already has `p`). `P` keeps its key, gains the widened action and a
"Parked/frozen" label.

- **`f`** — resolve the current agent (minimonitor `_find_own_agent_snapshot`,
  monitor focused card), confirm via a `KillConfirmDialog`-shaped dialog ("Freeze
  <window>? The process ends; its output is kept and it can be restored."), then
  `_run_frozen_cmd(["freeze", pane_id])`. Safe as a subprocess: it respawns the
  *agent's* pane, not the TUI's.
- **`Z`** — `_run_frozen_cmd(["freeze", "--all"])`, but the confirmation must
  first tell the truth about **scope**, which is much wider than the view.
  `freeze_all()` (`agent_freeze.py:450`) iterates `discover_aitasks_sessions()`
  — *every* aitasks session on the machine — and its only filters are
  `category == AGENT` and "not already frozen". So it also stops **parked**
  agents (parking is an App-published concept; the fresh `TmuxMonitor` it builds
  has no parked set) and agents belonging to **other projects**. Neither app's
  display can see that population: both support single-session mode, and §3
  defines the displayed live set as *excluding* parked. Counting `self._snapshots`
  — or reusing that live set — would understate a destructive operation, which is
  precisely the number a user leans on when confirming.

  So **derive the count from the operation itself**: add
  `freeze --all --dry-run`, returning `freeze_all()`'s own eligible enumeration
  without freezing (`WOULD_FREEZE:<pane_id>|<session>|<window>` per pane,
  `FREEZE_ELIGIBLE:<n>` last). The TUI calls it to build the dialog, so the count
  cannot drift from what the button does. The dialog states the scope in words
  too — "every aitasks session on this machine, including parked agents and other
  projects" — because a bare number still reads as "the agents I can see". The
  same count sizes the timeout above.

  **This needs the shell wrapper as well as the engine.** `aitask_frozen.sh`'s
  `freeze` case is `[ $# -eq 2 ] || usage` (:81-83), so `freeze --all --dry-run`
  is three arguments and exits 2 on usage **before Python ever runs** — the TUI's
  real entry point is the wrapper, so a Python-only change would leave the
  confirmation path dead while engine-level tests passed. Relax it to
  `[ $# -ge 2 ] || usage`, matching the convention the adjacent `restore` case
  already states (:85-88), and update `usage()` and the header verb list.

  **Relaxing the wrapper is only safe if the engine validates the full grammar
  first — today it does not.** `agent_freeze.main()` dispatches on `rest[0]`
  alone and **silently ignores every trailing argument** (:1119-1124):

  ```python
  if rest and rest[0] == "--all":   results = freeze_all()      # REAL freeze
  elif rest:                        results = [freeze_pane(rest[0])]  # REAL freeze
  ```

  So `freeze --all --dry-rnu` (one typo) performs a **real freeze of every agent
  on the machine**, and `freeze <pane> --dry-run` really freezes that pane. The
  shell's `-eq 2` is the only thing rejecting those forms today; relaxing it
  while teaching Python to recognise just the one new spelling would open exactly
  that hole. Merely *adding* `--dry-run` recognition is not enough.

  So validate the **complete supported grammar, before any enumeration or
  mutation**, and reject everything else:

  ```
  freeze --all
  freeze --all --dry-run
  freeze <pane_id>            # <pane_id> must not begin with "-"
  ```

  Every other form — extra arguments, unknown flags, `--dry-run` on a single
  pane, a flag-shaped pane id — returns usage/exit 2 having called neither
  `freeze_all` nor `freeze_pane`. That restores every rejection the old `-eq 2`
  gave, and adds one form rather than a wildcard.

  For the result notify, **count the result lines** (`FROZEN:` = ok,
  `FREEZE_SKIPPED:` = already frozen, `FREEZE_FAILED:` = error); `freeze --all`
  emits no summary line (unlike `restore --all`, which does emit `RESTORE_ALL:`).
- **`R` / `p` / `k`** — guarded **in the action**, not the binding: no-op with a
  notify unless the current agent is frozen, so monitor's `R`=Restart and
  minimonitor's `p`=Pick keep their live-row meaning. All three dispatch through
  `TmuxClient.run(["run-shell", "-b", shlex.join([FROZEN_SH, …])])` — never
  `subprocess` — because each replaces or kills the pane (and possibly the window)
  the TUI is in. `k` uses `aitask_frozen.sh drop <id>`, **not**
  `kill_agent_pane_smart`.
- **Hints** (minimonitor): `KEY_HINTS_TEXT` (:782-798) must surface `f`, `Z`, `R`
  and the widened `P` while staying at **ten rows** and ≤38 cells per line —
  `_KEY_HINTS_ROWS` is derived (:848) and `test_minimonitor_top_chrome_render`
  pins the height; `test_key_hints_surface_every_binding` pins the parity. Fold,
  do not add a row (an 11th costs the pane list a row at every pane height).

### 5. Own panel (minimonitor)

In `_refresh_own_live_state` (:2501), when the followed snapshot is frozen render
`F frozen <frozen_at>` (from `SessionsView().by_id(snap.frozen_record_id)`) and no
phase line. `n` stays enabled; the companion does not auto-despawn — a stand-in
counts as a real agent.

### 6. Restore feedback — extract, do not copy

`frozenagent_app.py:869-928` already implements exactly the poll this task needs,
including two hard-won correctness rules: gate on `restore_attempts` (not `state`)
to tell pre-begin from failure, and **never** match `last_error` against a freshly
read `op_nonce` (recovery clears the lease while preserving the error).
Re-implementing it in `monitor_shared` would be a fourth copy of subtle logic —
the exact failure t1705_6's own note flags for the pane-classification rule.

Extract the verdict into a **pure, Textual-free** function in
`lib/agent_frozen_ops.py`:

```python
def restore_verdict(rec, prev_attempts: int, elapsed: float) -> tuple[bool, str, bool]
```

returning `(done, message, warn)`. The viewer keeps its `set_interval` and calls
it; the two TUIs get their own timer and call the same function. Per repo
convention a new shared API is pinned by its **own** contract test, not
incidentally by the viewer's suite.

## Files

- **Edit** `.aitask-scripts/monitor/monitor_core.py`, `monitor_shared.py`,
  `minimonitor_app.py`, `monitor_app.py`
- **Edit** `.aitask-scripts/lib/agent_frozen_ops.py` (+ `frozenagent/frozenagent_app.py`
  to call the extracted verdict)
- **Edit** `.aitask-scripts/lib/agent_freeze.py` — `freeze --all --dry-run`, plus
  explicit `freeze` argument-grammar validation in `main()` (today it dispatches
  on `rest[0]` and ignores trailing args, so extra-argument forms reach a real
  freeze). No existing *supported* form changes behaviour or wire lines; what
  changes is that unsupported forms are now rejected in Python rather than only
  by the wrapper's arity gate.
- **Edit** `.aitask-scripts/aitask_frozen.sh` — relax the `freeze` arity gate so
  the dry-run reaches the engine, plus `usage()` and the header verb list
- **Edit** `tests/tools/regen_font_coverage.py` (add `0x0046` to candidates),
  `tests/data/font_coverage.json`, `tests/test_mark_glyphs_single_source.py`,
  `tests/test_monitor_agent_marks.py`
- **Edit** the `_hide_parked` → `_hide_inactive` references in
  `tests/test_monitor_parked_filter.py`, `test_monitor_parked_capture.py`,
  `test_monitor_agent_marks_action.py`
- **Edit** the six `SimpleNamespace` snapshot doubles (add `frozen=False`,
  `frozen_record_id=""`): `test_minimonitor_gate_phase_row.py`,
  `test_minimonitor_other_section.py`, `test_minimonitor_scroll_preservation.py`,
  `test_minimonitor_top_chrome_render.py`, `test_monitor_pane_sort_order.py`,
  `test_monitor_session_divider.py` — complete the doubles, never make the
  renderers defensive with `getattr`
- **New** `tests/test_monitor_frozen_capture.py`,
  `tests/test_monitor_frozen_filter.py`,
  `tests/test_frozen_restore_verdict.py` (contract test for the extracted API),
  `tests/test_frozenagent_restore_poll_characterization.py` (the pre-phase control),
  `tests/test_shortcut_overrides_survive.py`,
  `tests/test_freeze_argument_grammar.py`,
  `tests/test_frozen_dry_run_wrapper.sh` (opt into the file-backed assert
  counters if its bodies run in `( … )` subshells)

## Tests for the four verified concerns

Each gets a test that fails against the naive implementation, not just against
broken code:

1. **Capture partition precedence** — drive a pane that is **both** frozen and
   parked through `capture_all_classified_async` → `commit_snapshots` and assert
   the committed snapshot has `frozen=True`, plus that its mark still renders.
   Constructing a frozen snapshot directly in a renderer test would pass while
   the real partition is broken — so this must go through the real capture path.
   Negative control: parked-only still commits `parked=True`.
2. **Fast-preview route** — call `capture_pane_classified_async` on a frozen pane
   with a recording `capture_pane_content_async` seam and assert **no capture and
   no classify call**; then `commit_snapshot` and assert the result is a
   `frozen=True, content=""` snapshot. Then drive `_fast_preview_refresh` on a
   focused frozen pane and assert `self._snapshots[pane_id].frozen` survives and
   the preview shows the frozen placeholder. Positive control: a live focused
   pane *is* captured.
3. **Freeze-all scope and count** — with a fake enumeration of **two sessions**
   containing a parked agent, an already-frozen stand-in and a plain agent,
   assert `--dry-run` reports every eligible pane across both sessions (parked
   included, frozen excluded), that the dialog's count equals it **in
   single-session display mode**, and that the dispatched argv is
   `["freeze", "--all"]`.
4. **Freeze command lifetime** — assert the seam receives `_FREEZE_ONE_TIMEOUT`
   for a single freeze and a count-scaled budget for `--all` (never
   `_MARKS_CMD_TIMEOUT`); a slow-but-successful freeze that outlives 20s
   completes rather than being killed; and a genuine timeout surfaces the
   partial-completion wording, not "failed".
5. **Dry-run path — two isolated layers, neither touching a live tmux server.**

   > **Correcting an unsafe test design in this plan's previous draft.** It
   > proposed running the real wrapper *and* real engine with
   > `AITASKS_AGENT_SESSIONS_FILE` pointed at a temp store, calling that safe
   > "because dry-run freezes nothing". That reasoning is wrong twice over. The
   > store override isolates only the JSON store — `discover_aitasks_sessions`
   > (`agent_launch_utils.py:881`) enumerates *"aitasks-like tmux sessions on the
   > current tmux server"* and re-queries tmux on every call, so the test would
   > have enumerated the live `-L ait` server holding the user's real agents. And
   > "dry-run freezes nothing" assumes the code under test is correct — which is
   > precisely what the test exists to establish. Combined with the `rest[0]`
   > defect above, a single typo would have frozen every real agent on the
   > machine while filing their records into a temp store. **Safety must hold
   > even when dry-run dispatch is broken**, so no test here invokes the real
   > engine against a real server.

   - **(a) Wrapper forwarding — fake engine, shell test.** Build a temp
     `SCRIPT_DIR` with `aitask_frozen.sh` copied in, `lib/terminal_compat.sh` and
     `lib/python_resolve.sh` symlinked from the repo, and a **fake
     `lib/agent_freeze.py`** that only echoes its argv. Assert
     `freeze --all --dry-run` forwards verbatim; assert the ordinary
     `freeze <pane>` control forwards verbatim **within the same isolation**;
     assert bare `freeze` still exits 2 without reaching the engine. Real
     freezing is impossible here by construction, not by argument.
   - **(b) Engine grammar and dry-run — fake enumeration + mutation spies,
     python test.** Patch `discover_aitasks_sessions` / `_agent_panes_for` with a
     fake two-session enumeration, and spy on `freeze_pane` and `freeze_all`.
     Assert `--dry-run` reports the eligible set and calls **neither**; assert
     each rejected form (`--all --dry-rnu`, `<pane> --dry-run`, extra args,
     unknown flags, a `-`-prefixed pane id) exits 2 and calls **neither**. The
     spies are the assertion that matters — a grammar test that only checks exit
     codes would pass while a mutator ran.
6. **Keybinding override survival** — with a `shortcuts:` override for
   `toggle_parked_visibility` seeded in **both** the `monitor` and `minimonitor`
   scopes, assert `register_app_bindings` still returns the overridden key after
   the widening — i.e. the action id did not move. This test fails against the
   rename I originally proposed, which is what makes it worth having.

## Verification

```bash
# pre-phase control FIRST: green against unmodified code, then still green after §6
python3 tests/test_frozenagent_restore_poll_characterization.py

# new + mirrored suites, then the modules the rename and the new field touch
python3 tests/test_monitor_frozen_capture.py
python3 tests/test_monitor_frozen_filter.py
python3 tests/test_frozen_restore_verdict.py
python3 tests/test_monitor_parked_capture.py && python3 tests/test_monitor_parked_filter.py
python3 tests/test_mark_glyphs_single_source.py && python3 tests/test_monitor_agent_marks.py
python3 tests/test_minimonitor_top_chrome_render.py    # ten-row hint budget
python3 tests/test_minimonitor_concern_action.py       # hints/bindings parity
python3 tests/test_frozenagent_app.py                  # viewer still green after the extraction
python3 tests/test_shortcut_overrides_survive.py       # action-id stability, both scopes
bash    tests/test_frozen_dry_run_wrapper.sh           # wrapper forwarding, FAKE engine
python3 tests/test_freeze_argument_grammar.py          # grammar + mutation spies, no tmux

bash tests/run_all_python_tests.sh                     # read ONLY the last line
bash tests/test_no_raw_tmux.sh
shellcheck .aitask-scripts/aitask_*.sh
```

Every new test gets its **pre-fix control**: run it against the unmodified code
first and watch it fail, so a green result is evidence rather than a tautology.

Baseline confirmed green before starting: `test_monitor_parked_filter` (29),
`test_monitor_parked_capture` (14), `test_mark_glyphs_single_source` (28, 1 skip).

**Not runnable from this session, by design:** this agent runs *inside* the `ait`
tmux server (`$TMUX` is set), so the live tmux suites
(`tests/test_multi_session_*.sh`, `tests/test_cleanup_rule_parity.sh`, and any
hands-on `./ait minimonitor` freeze) refuse or would be destructive. Those are
**t1705_8**'s scope (it opens with a blocking tmux preflight for exactly this
reason) and t1705_11's checklist. This task ships unit- and render-level
coverage only, and I will say so plainly rather than implying live verification.

## Risk

*Reassessed after the inline pre-phase was confirmed and again after review
surfaced four defects in the first draft (partition precedence, the unguarded
fast-preview route, the marks timeout, freeze-all scope). All four are now
addressed in the approach with their own tests. The pre-phase gives the
highest-severity code-health item a real pre-extraction control, but the blast
radius (5 source modules, ~12 test modules) and the two load-bearing capture
paths sustain **medium** on that axis; goal-achievement is untouched by these
fixes and stays **medium**, dominated by the no-live-tmux gap.*

### Code-health risk: medium

- The frozen split lands in `capture_all_classified_async` / `commit_snapshots` — the load-bearing capture path for **both** TUIs. A misordered branch (frozen checked after the `result is None` drop) silently drops frozen panes from the snapshot map. · severity: medium · → mitigation: TBD
- Extracting `restore_verdict` refactors **shipped t1705_6 code** whose correctness rests on two non-obvious rules (gate on `restore_attempts`, never match `last_error` against a fresh `op_nonce`). A faithful-looking extraction that loses either one turns a failed restore into a reported success. · severity: high · → mitigation: inline pre-phase characterize_restore_poll
- The `_hide_parked` → `_hide_inactive` rename touches ~9 source and ~16 test sites across 3 test modules outside this task's nominal scope; a missed site leaves a filter that silently stops filtering. · severity: low · → mitigation: none — the alternative (a flag whose name lies about what it hides) is worse
- **Binding action ids are persisted user config, not internal names.** `register_app_bindings` resolves overrides by `str(binding.action)` against `userconfig.yaml`'s `shortcuts:` section, so renaming one silently orphans a user's customized key — no error, it just reverts to default. This plan's first draft renamed `toggle_parked_visibility` and would have done that in both the `monitor` and `minimonitor` scopes. · severity: medium · → mitigation: none — the id is now preserved, pinned by concern-test 6, and carries a comment saying why it no longer matches its field name
- There are **two** capture routes (`capture_all_classified_async` +
  `commit_snapshots`, and `capture_pane_classified_async` + `commit_snapshot`) and
  guarding only the bulk one leaves the fast-preview path capturing frozen panes
  and overwriting their snapshots. Now addressed at the core seam so every caller
  inherits it — but any *future* single-pane capture entry point would reopen it. · severity: medium · → mitigation: none — the guard sits in `monitor_core`, not in an app, which is what makes new callers inherit it
- **`agent_freeze.main()` ignores trailing arguments today** (`rest[0]` only), so the wrapper's `[ $# -eq 2 ]` gate is the *sole* thing rejecting `freeze --all --dry-rnu` and `freeze <pane> --dry-run` — both of which currently reach a **real** freeze. Relaxing that gate without adding full grammar validation in Python would open a path where a single typo freezes every agent on the machine. · severity: high · → mitigation: none — the grammar is now validated before any enumeration or mutation, pinned by concern-test 5(b)'s mutation spies
- Tests that exercise the freeze engine can reach the **live tmux server**: `AITASKS_AGENT_SESSIONS_FILE` isolates only the JSON store, while `discover_aitasks_sessions` re-queries the current server on every call. Any test that runs the real engine — however "safe" its verb looks — can act on the user's real agents, and this session runs on that very server. · severity: high · → mitigation: none — no test invokes the real engine against a real server; forwarding is proven with a fake engine and dry-run with fake enumeration (concern-test 5)
- Six `SimpleNamespace` snapshot doubles must be completed for the two new `PaneSnapshot` fields. An incomplete double **raises** rather than degrading, so the failure is loud — but the temptation to "fix" it with a `getattr` default would also mask a real snapshot missing the field. · severity: low · → mitigation: TBD

### Goal-achievement risk: medium

- **Nothing here can be verified against a real tmux server.** This session runs inside the `ait` server, so the freeze / restore / drop keys ship proven only at the argv level (fake seams) — the call *shape*, never the outcome. Live proof is structurally t1705_8's scope, but until it runs, "the keys work" is unevidenced. · severity: high · → mitigation: none — already owned by sibling t1705_8 (`depends: [t1705_7]`); spawning one would duplicate it
- The `F` glyph's font coverage is **asserted, not measured** — the generator cannot run on this machine (no fontconfig, neither Nerd Font). Certain for an ASCII capital, and it fails loudly on a font-equipped box, but it is not the machine-checked evidence the repo's discipline expects. · severity: low · → mitigation: none — accepted, fails loudly in the right direction
- The minimonitor hint band must surface three new keys plus a widened `P` label within **ten rows and 38 cells** — a budget that has already forced one design change (t1685). If it cannot be met, either a hint goes unsurfaced (failing the parity test) or the pane list loses a row at every height. · severity: medium · → mitigation: none — `test_minimonitor_top_chrome_render` + `test_key_hints_surface_every_binding` already enforce both halves

### Planned mitigations
- timing: pre-phase | name: characterize_restore_poll | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — restore_verdict extraction may silently lose a correctness rule | desc: characterization test pinning the viewer's current restore/drop poll verdicts, run green pre-extraction as the control

## Follow-ups to file (Step 8d)

- **Parked panes are captured and overwritten on the fast-preview route.** A live
  t1685 defect found while verifying this plan, at the same two functions this
  task guards for frozen: focusing a parked pane captures it, classifies it, and
  replaces its `parked=True` snapshot, so the parked preview placeholder
  (`monitor_app.py:1961`) reverts to stale content and the session-bar term
  drops it. Not folded in here — it is a behaviour change to shipped parked code
  with its own test expectations — but the frozen guard is written so the parked
  case is a two-line addition.

## Risks (implementation notes)

- **Font manifest is hand-written, not measured.** `tests/tools/regen_font_coverage.py`
  cannot run here — no fontconfig (`fc-match`/`fc-list` absent) and neither Nerd
  Font installed. `0x0046` goes into the generator's candidate list and the
  manifest entry is written as covered-by-both. For an ASCII capital in these
  monospace families this is certain (U+0050 `P` is already measured `true`), and
  if it were wrong `test_the_manifest_matches_the_installed_fonts` fails loudly on
  a font-equipped machine — the correct fail direction. It **skips** here. Recorded
  in the Final Implementation Notes as un-regenerated.
- **The `_hide_parked` rename touches three test modules** outside this task's
  nominal scope. Mechanical, and the alternative (a flag whose name lies about
  what it hides) is worse.
- **`_LIST_PANES_FORMAT` is a closed-arity format** (`_LIST_PANES_ARITIES =
  (9, 10, 11, 15)`) and `classify_window_panes` **silently skips** wrong-arity rows
  — a miscount vanishes panes rather than erroring (it already bit
  `test_monitor_companion_filter.py`). This task adds no field to either format,
  which is what keeps that risk at zero; do not widen them.
