---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [tui, minimonitor, monitor, agent_marks]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-02 12:34
updated_at: 2026-09-02 12:44
---

## Problem

`ait monitor` and `ait minimonitor` list every agent window across every
session. The prioritized mark (`★`/`☆`, t1326/t1383) lets a user flag what
matters, but it only *annotates* a long list — it never shortens it, and every
listed agent is captured and classified on every refresh tick whether or not the
user still cares about it.

What is missing is a way to **park** an agent: declare "I am done watching this
one", have it drop out of the list, and stop paying for its status entirely.

## Design (settled with the user during exploration)

### 1. Tristate mark, one store entry

`space` becomes a three-state cycle: **unmarked → ★ prioritized → P parked →
unmarked**. An agent is starred *or* parked, never both — which is what makes
the cycle clean and keeps the mark column one cell wide.

Store: `.aitask-scripts/lib/agent_marks.py`, identity unchanged
(`(realpath(project_root), window_name)`). Add a `kind` field to each record:
`"priority"` (absent ⇒ priority) or `"parked"`.

**`SCHEMA_VERSION` goes to 2, and a v1→v2 read migration must be written.**
`_parse` rejects any version != `SCHEMA_VERSION` outright and the module's
docstring is explicit that this is deliberate because *no migration exists*. The
consequence of the bump is total and cross-repo: an older `ait` reading the
store renders **no marks at all**, in every project. That is fail-safe, and it
is the accepted cost — but the migration is not optional, and the version
contract's comment in `_parse` must be updated rather than worked around.

### 2. Target resolution — unchanged from t1383

- `ait monitor`: `space` acts on the **focused card** (inherited
  `AgentMarksMixin.action_toggle_mark`).
- `ait minimonitor`: `space` acts on the **followed agent** — the one in the
  docked `── this agent ──` panel. `MiniMonitorApp.action_toggle_mark` already
  overrides the mixin for exactly this reason; that decision stands. List rows
  in minimonitor stay read-only.

So parking is always an action on the one agent the user is explicitly pointing
at. This is load-bearing for the visibility rule in §4.

### 3. `P` toggles parked visibility, in both TUIs

New binding `P` in `MonitorApp.BINDINGS` and `MiniMonitorApp.BINDINGS` (both
keys are currently unbound in both apps): hide/show parked agents in the pane
list. Same key, same meaning in both, matching the existing `M` / `d` / `c` /
`e` / `s` / `k` / `n` parity.

Minimonitor also needs a `KEY_HINTS_TEXT` row — hints/BINDINGS parity is
test-pinned (the audit added in t1159_2 fails a binding with no hint line), and
the top-chrome height budget (`_TOP_CHROME`, `_SHORT_HINT_ROWS`) must be
re-checked against the extra row.

### 4. Visibility is live, not frozen

The original request asked for a frozen hidden set ("keep the agent visible
until the next time we trigger to hide"). The user withdrew that after the
exploration established §2: because parking only ever acts on the currently
selected / followed agent, no *unrelated* row can vanish under the cursor. The
filter is therefore applied live at rebuild time — a parked agent disappears
from the list on the next tick.

Three consequences were identified and accepted; the first is a required part of
this change:

- **Focus handoff is mandatory (confirmed defect otherwise).**
  `MonitorApp._restore_focus` (`monitor_app.py:1450`) restores focus via
  `self._pane_cards.get(pane_id)`, and its earlier guard tests
  `focused.pane_id in self._snapshots`. A card filtered out of the list is
  absent from `_pane_cards`, and a parked agent has no snapshot at all (§5), so
  **both** paths miss and focus silently leaves the pane list;
  `_update_content_preview` then renders against a `_focused_pane_id` with no
  snapshot. Parking the focused card with the filter on must hand focus to the
  next visible card *before* the rebuild.
- **A row can still vanish with no local keypress.** Marks are a cross-repo
  store and `_refresh_marks()` picks up another repo's write within one tick, so
  someone parking an agent from another project's monitor removes a row here.
  Accepted: that is the same propagation the mark feature already ships.
- **With the filter on, a parked agent cannot be unparked from the list** — it
  is not rendered. The path is `P` to reveal, then `space`. Document it, and say
  so in the toast shown when an agent is parked while the filter is on.

Minimonitor has no jump at all: the followed agent lives in the docked panel and
was never in the list, so parking it removes nothing.

### 5. Parked agents are not checked

The saving is in `TmuxMonitor.capture_all_classified_async`
(`monitor_core.py:2634`): parked agent panes are excluded from the
`capture_pane_content_async` gather and from the `_classify_batch` payload.

Two things this must not break:

- **They must still render when the filter is off.** `commit_snapshots` drops
  any entry whose result is `None` (`if result is None: continue`), so a parked
  pane cannot simply be routed down the "failed capture" path or it vanishes
  even with parked agents shown. It needs an explicit parked branch producing a
  minimal snapshot (no content, `is_idle=False`, `awaiting_input=False`, a
  `parked` flag) so the row can render the placeholder from §6.
- **Discovery must still see them.** `_record_discovery_facts` /
  `last_discovered_agents()` are populated from *discovery*, not from capture,
  and `sweep_liveness` keys on those. Because parking skips only capture, a
  parked agent stays in discovery and its mark survives the liveness sweep.
  **This is the load-bearing correctness fact of the whole feature** — if a
  parked agent ever drops out of discovery, the next purge deletes the very mark
  that parked it.

`monitor_core` currently knows nothing about marks (they live on the App-side
`AgentMarksMixin`), so the parked key set has to be published down once per tick
— the same shape as the existing `_set_session_root_map`, and for the same
reason: `_strict_root_for_snap` must not do a blocking tmux round-trip from the
render path (`tests/test_monitor_refresh_no_sync_tmux.py` guards that).

### 6. Parked rows render an explicit placeholder

No state dot and no status text: a frozen `●` would read as a live idle/active
verdict that is in fact arbitrarily stale. Render the `P` glyph, the window
name, and a dim `parked` marker.

### 7. The followed agent keeps being monitored

Parking the agent a minimonitor follows is a signal **to other monitors'
lists**, not an instruction to that minimonitor to stop working. Its own docked
panel keeps being captured, and `L` (auto-recheck loop), `c` (concerns) and
shadow readiness keep functioning — all of them are bound to that agent and all
of them need live capture. The panel shows the `P` glyph.

### 8. Glyph: `P` (U+0050)

Measured against both families in `mark_glyphs.SUPPORTED_FONTS` by reading their
`cmap` tables via `tests/tools/regen_font_coverage.py` (never `fc-list` — see
that tool's docstring):

| candidate | JetBrainsMono NF | CaskaydiaMono NF | verdict |
|---|---|---|---|
| `P` U+0050 | yes | yes | **chosen** — no emoji font claims it, single cell |
| `⏸` U+23F8 | no | no | rejected: emoji-capable, i.e. the exact t1638 invisible-glyph defect |
| `■` U+25A0 | yes | yes | rejected: collides visually with the state dot `●` |
|  U+F04C (nf-fa-pause) | yes | yes | rejected for now: PUA renders as tofu without a Nerd Font, and the declared tier that would make it safe (t1639) does not exist yet |
| `★`/`☆` (today) | no | no | for reference — already resolve by fallback; non-emoji, so not broken |

`P` is therefore strictly more reliable than the star pair currently shipping.

**No coupling to t1639 was requested.** That task may revisit the glyph when it
introduces the declared `nerd` tier; this task does not reserve a PUA codepoint
for it and does not depend on it.

Add the three codepoints to `tests/data/font_coverage.json` via the generator so
the rejections above stay machine-checked and the manifest keeps discriminating.

### 9. Expiry policy

Parked marks are **exempt from `expire()`** — parking is a long-lived "ignore
this" intent, and a 2-day `DEFAULT_TTL_DAYS` silently un-parking a background
agent defeats the feature. They remain subject to `sweep_liveness()`, so a
parked agent whose tmux window is gone is still reaped. Star marks keep the
existing TTL unchanged.

## Consumers that must exclude parked agents

Roughly eight `PaneCategory.AGENT` sites per app. The precedent to follow is
`_completed_pane_ids` (t1322), which is exactly this shape: a per-tick excluded
set threaded through the same consumers.

- `MonitorApp._maybe_auto_switch` (`:1398`) — both the `awaiting` and the
  `idle_agents` branches. Auto-switch must never move focus to a hidden card.
- The session-bar counters (`monitor_app.py:1550`). Their docstring states an
  explicit contract: "the three counters partition the agents exactly as the
  badges do … so every agent lands in at most one bucket and the bar can never
  disagree with the rows above it". Parked agents have no meaningful
  `is_idle` / `awaiting_input`, so they must leave that partition entirely.
  Decide and document whether the bar gains an `N parked` term.
- `_compute_completed_panes`, the concern offering, and the review loop.
- `MonitorApp._rebuild_pane_list` (`:1723`) — note its in-place fast path keyed
  on pane-id order; the filter must be applied *before* the `desired_ids`
  comparison or a park will not trigger a rebuild.
- `MiniMonitorApp._rebuild_pane_list` (`:2455`).

## Acceptance criteria

1. `space` cycles unmarked → ★ → P → unmarked, on the focused card in
   `ait monitor` and on the followed agent in `ait minimonitor`.
2. A parked agent renders `P` plus a `parked` placeholder, with no state dot,
   in both TUIs and in minimonitor's docked own-agent panel.
3. `P` hides parked agents from the pane list in both TUIs and shows them again;
   the state is per-app-instance and in-memory.
4. Parking the focused card in `ait monitor` while the filter is on leaves focus
   on a *visible* card — asserted directly, since the current `_restore_focus`
   demonstrably drops it.
5. A parked agent is not passed to `capture_pane_content_async` or to
   `_classify_batch` — asserted on the call arguments, not inferred from timing.
6. A parked agent still appears in `last_discovered_agents()`, and a purge run
   while it is parked does **not** drop its mark. This needs a negative control:
   the same purge with the agent's window actually gone *must* drop it, or the
   assertion proves nothing.
7. A v1 store loads under v2 with every existing mark preserved as
   `kind: priority`, and round-trips to a v2 file.
8. `expire()` drops an over-TTL star mark and leaves an over-TTL parked mark;
   `sweep_liveness()` drops a parked mark whose window is gone.
9. The session-bar counters still partition the visible agents exactly, with
   parked agents excluded from all three buckets.
10. Auto-switch (`A`) never focuses a parked agent.
11. `tests/data/font_coverage.json` records `P`, `⏸` and `■` with the measured
    per-font results above.

## Documentation

- `website/content/docs/tuis/monitor/how-to.md` — the mark bullet in the card
  anatomy list (:64) and the "How to Mark an Agent as Prioritized" section
  (:226); add the parked state and the `P` filter.
- `website/content/docs/tuis/monitor/reference.md` — the `Space` row (:38) and a
  new `P` row.
- `website/content/docs/tuis/minimonitor/how-to.md` — the mark bullet (:43), the
  "note you left yourself" passage (:150), the marking section (:284) and the
  keybinding table (:380).
- Explain in all three that with the filter on, unparking requires revealing
  parked agents first.
- `KEY_HINTS_TEXT` in `minimonitor_app.py`.
