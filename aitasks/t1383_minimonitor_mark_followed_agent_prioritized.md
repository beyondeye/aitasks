---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [tui, minimonitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1326
implemented_with: claudecode/opus5
created_at: 2026-08-03 11:44
updated_at: 2026-08-03 23:18
boardidx: 11264
---

## Origin

User request during `/aitask-explore`: minimonitor's `space` marks the
*selected* agent in the scrollable list, but the agent this minimonitor
**follows** — pinned in the docked `── this agent ──` panel — cannot be
marked, because its pane is outside the list. The user asked for the same
capability for the followed agent (initially suggesting `shift+space`).

## Reachability gap

`AgentMarksMixin.action_toggle_mark`
(`.aitask-scripts/monitor/monitor_shared.py:321`) resolves its target through
`self._get_focused_pane_id()`. The followed agent is:

- excluded from the card list — `_rebuild_pane_list` drops `own_pane_id`
  (`.aitask-scripts/monitor/minimonitor_app.py:764-770`), and
- rendered as plain, **non-focusable** `Static`s by
  `_maybe_build_own_agent_panel` (`minimonitor_app.py:731-751`).

So no focus-resolved action can ever target it. This is the same shape as
t1282 (`i` → `I`, Task Info) and t1309 (`d`, still open). Handlers scoped to
the followed agent resolve instead via `_find_own_agent_snapshot()` —
`action_kill_own_agent` (`k`), `action_pick_next_for_own` (`n`),
`action_show_own_task_info` (`I`).

## Key choice — SETTLED during planning: no new key

**Decision (confirmed with the user at planning time): do not add a second key.
`space` in the minimonitor is *retargeted* to the followed agent, independent of
list focus.** One key, one target. The minimonitor is a companion pane bound to
exactly one agent, so "mark" there can only sensibly mean "the agent I am
watching".

Consequences, all confirmed:

- Minimonitor list cards are **no longer togglable**. They keep rendering
  `★`/`☆` read-only, so marks set elsewhere stay visible (the name budget stays
  at 20 — t1326's width trade is unchanged).
- `ait monitor` is **unchanged**: it follows nothing, so focus is its only
  sensible target, and it remains the place to mark any *other* agent.
- The uppercase-sibling convention (`i`→`I`, `e`→`E`) is deliberately **not**
  applied here — it exists to add a followed-agent action *beside* a focus-scoped
  one, and this task removes the focus-scoped one instead.

The `shift+space` measurement below is retained as evidence (it is also the
reason no alias was added, and it stays relevant to **t1309**).

### Original evidence — do NOT use `shift+space` (measured)

Probed on this machine (tmux 3.7 with `extended-keys on` /
`extended-keys-format csi-u`, outer terminal ghostty, Textual 8.2.7, agent
running in the ghostty-attached session):

| sent | Textual `event.key` |
|---|---|
| `S-Space` | `space` |
| `Space` | `space` |
| `S-Tab` | `tab` |
| `C-i` | `tab` |
| `S-Enter` | `enter` |

No modifier disambiguation survived the trip in that pane, so `shift+space`
is not dependable. Worse, the failure is **silent and wrong**: if the binding
collapses to `space`, the keypress toggles the mark on the *selected list*
agent instead of the followed one.

Caveat on the evidence: `tmux send-keys` is not a real keypress from the
terminal, and the same probe failed to distinguish `S-Tab`/`C-i` — keys the
repo binds successfully elsewhere (`shift+tab` in stats / brainstorm /
settings). So the probe proves "not dependable", not "impossible". Any
`shift+space` binding must be validated by a **real keypress in a real tmux
pane**, never by `send-keys`.

The candidates weighed at planning time — an uppercase letter (`S`, `O`, `F`)
or `*` (unambiguous through tmux: Textual reports `asterisk`) — are recorded
here for **t1309**, which still needs a key. No `shift+space` alias was added:
where the modifier collapses, the keypress would silently hit the wrong target,
and an alias cannot prevent that.

## Rendering the mark in the docked panel

`_own_agent_identity_text` (`minimonitor_app.py:702-729`) renders no `★`/`☆`
today, and `_maybe_build_own_agent_panel` builds the panel **once**
(`_own_panel_built`). A toggle-only refresh is not enough: marks live in
`~/.config/aitasks/agent_marks.json` (user-global), can be set from the full
monitor or another repo's TUI, and **expire after ~2 days**, so a once-built
panel would show a stale `★`.

Cheapest correct approach: re-render the own-card text on the tick where the
mark bit flips. `_refresh_marks()` already runs every tick and
`MarksView.is_marked` is a set lookup, so this costs nothing measurable — but
the panel widget must be updated in place (keep the identity text static;
only the mark glyph changes).

This does not violate the panel's static contract: t1133/t1322 excluded live
**agent status** (state dot, compare-mode glyph, shadow glyph, COMPLETED
badge). A mark is a durable *user annotation* — `format_mark_glyph`'s
docstring already places it "outside the live state cluster". State that
reasoning in the code so the exception reads as deliberate.

## Documented decision to reverse

`website/content/docs/tuis/minimonitor/how-to.md:176` currently says:

> the followed agent pinned at the top of the pane is not markable; marks
> apply to the agents in the scrollable list. Prioritizing the agent you are
> already watching would not tell you anything.

That note must be rewritten, not merely appended to. The counter-argument to
record: a mark is *user-global and cross-repo* — marking the followed agent
tells every **other** view (`ait monitor`, another project's minimonitor)
that this agent is the one that matters.

## Suggested implementation

1. Extract the write path in `AgentMarksMixin` — `_toggle_mark_for(snap)`
   holding the root resolution, `aitask_agent_marks.sh toggle` call,
   notification branches and post-write invalidate/refresh — and make
   `action_toggle_mark` a thin focus-resolving caller. Keep the existing
   `MARKED:`/`UNMARKED:`/`LOCK_BUSY` handling and the focus-vs-cached-pane-id
   comment intact.
2. **Override** `action_toggle_mark` in `minimonitor_app.py` resolving via
   `_find_own_agent_snapshot()`, warning `"No followed agent in this window"`
   when unresolvable (mirrors `action_show_own_task_info`). No new binding —
   the existing `space` row is relabelled.
3. Render `★`/`☆` in the docked panel and update it when the bit flips.
4. Update the hard-coded `#mini-key-hints` panel in `compose()`
   (`minimonitor_app.py:266-277`).
5. Update `website/content/docs/tuis/minimonitor/how-to.md` — the key list and
   the reversed note at line 176.

## Acceptance criteria

- Pressing `space` in minimonitor toggles the prioritized mark on the followed
  agent **regardless of which list card is focused**; the docked panel shows
  `★` when marked and `☆` when not.
- A mark set on the followed agent is visible from `ait monitor` and from
  another repo's minimonitor within one refresh cycle, keyed by
  *(project root, tmux window name)*.
- A mark set (or expired / swept) **elsewhere** is reflected in the docked
  panel within one refresh cycle — not only on local toggle.
- Minimonitor list cards are no longer togglable and render marks read-only;
  `ait monitor`'s focus-scoped `space` is unchanged and remains the way to mark
  any *other* agent.
- With no followed agent resolvable — including a window renamed off the
  `agent-` prefix — `space` warns and does not write, and the docked panel
  shows **no** mark glyph at all (not a read-only `☆`).
- The docked panel still shows no live status (no state dot, no compare-mode
  or shadow glyph, no COMPLETED badge), and its identity text stays frozen
  across a mark flip.
- The `how-to.md:176` note is rewritten, not contradicted by neighbouring
  prose.

## Testing

- Unit: mirror `tests/test_monitor_agent_marks_action.py` — drive the new
  action with `_run_marks_cmd` overridden, assert the wrapper is called with
  the **followed** agent's `(root, window)` while a *different* list card
  holds focus. That focus arrangement is the discriminating case: a test with
  nothing else focused would pass even against the old focus-resolved code.
- Render-level: assert the docked card's `render().plain` contains `★` after a
  toggle and `☆` before it, and that it flips when the marks file changes
  without a local keypress.
- Wiring: the repaint must be proven through a **real refresh cycle** on a
  mounted app — a direct `_refresh_own_mark()` call cannot catch a production
  call that is missing from `_refresh_data` or ordered before the mark/root
  refreshes.
- Negative control: revert the action to focus resolution and confirm the new
  tests fail. Two more, one per remaining failure direction (stale glyph after
  a rename; missing `_refresh_data` wiring).
- Live acceptance (manual, in a real tmux pane with a real keypress — not
  `send-keys`): confirm `space` reaches the app and targets the followed agent
  while a different list card is highlighted.

## Related

- **t1309** — `d` (detect) has the identical reachability gap; kept separate
  by explicit user decision during exploration. This task settled on
  *retargeting* rather than adding a key, which does **not** transfer to
  `d`: `d` must keep its focused-card meaning for the list, so t1309 still
  needs a dedicated key. The candidates weighed here (`D`, `*`) and the
  `shift+space` measurement above are the inputs for that choice.
- **t1326** — added the prioritized-mark feature and the `space` binding.
- **t1282** — established the `_find_own_agent_snapshot()` pattern for `I`.
- **t1350** — pins that App-level bindings do not dispatch inside a
  `ModalScreen`; the new binding inherits that protection.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-03T20:18:11Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-04T06:29:04Z status=pass attempt=1 type=human
