---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [tui, minimonitor]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1326
created_at: 2026-08-03 11:44
updated_at: 2026-08-03 22:46
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

## Key choice — do NOT use `shift+space` (measured)

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

**Established convention in this TUI is a dedicated uppercase key** resolving
via `_find_own_agent_snapshot()`: `i` → `I` (t1282), `e` → `E`. `space` has no
uppercase form, so decide during planning between:

- an uppercase letter (free today: `S`, `O`, `F`, `P` is taken by pick, …), or
- `*` — mirrors the `★` mark glyph and is unambiguous through tmux (verified:
  Textual reports `asterisk`).

Optionally add `shift+space` as an *extra* alias for terminals that do deliver
it — acceptable only if the primary key stands alone and the alias cannot
degrade into the list-agent toggle.

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
2. Add the new action in `minimonitor_app.py` resolving via
   `_find_own_agent_snapshot()`, warning `"No followed agent in this window"`
   when unresolvable (mirrors `action_show_own_task_info`).
3. Render `★`/`☆` in the docked panel and update it when the bit flips.
4. Update the hard-coded `#mini-key-hints` panel in `compose()`
   (`minimonitor_app.py:266-277`).
5. Update `website/content/docs/tuis/minimonitor/how-to.md` — the key list and
   the reversed note at line 176.

## Acceptance criteria

- Pressing the new key in minimonitor toggles the prioritized mark on the
  followed agent; the docked panel shows `★` when marked and `☆` when not.
- A mark set on the followed agent is visible from `ait monitor` and from
  another repo's minimonitor within one refresh cycle, keyed by
  *(project root, tmux window name)*.
- A mark set (or expired / swept) **elsewhere** is reflected in the docked
  panel within one refresh cycle — not only on local toggle.
- The list-agent `space` behaviour is unchanged; the new key never toggles a
  list agent, and `space` never toggles the followed agent.
- With no followed agent resolvable, the new key warns and does not write.
- The docked panel still shows no live status (no state dot, no compare-mode
  or shadow glyph, no COMPLETED badge).
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
- Negative control: revert the action to focus resolution and confirm the new
  tests fail.
- Live acceptance (manual, in a real tmux pane with a real keypress — not
  `send-keys`): confirm the chosen key reaches the app and that `space` still
  targets the list.

## Related

- **t1309** — `d` (detect) has the identical reachability gap; kept separate
  by explicit user decision during exploration. Whatever key convention this
  task settles on should be the one t1309 follows.
- **t1326** — added the prioritized-mark feature and the `space` binding.
- **t1282** — established the `_find_own_agent_snapshot()` pattern for `I`.
- **t1350** — pins that App-level bindings do not dispatch inside a
  `ModalScreen`; the new binding inherits that protection.
