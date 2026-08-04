---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, agentcrew]
anchor: 1046
created_at: 2026-08-04 17:28
updated_at: 2026-08-04 17:28
---

## Problem

`AgentCrewDashboard._refresh_data` (`.aitask-scripts/agentcrew/agentcrew_dashboard.py:984-999`)
tears down and rebuilds the whole crew list on every tick:

```python
crew_list = self.query_one("#crew-list", VerticalScroll)
await crew_list.remove_children()
...
for crew in self.crews:
    card = CrewCard(crew, ri, id=f"crew-{crew['id']}")
    await crew_list.mount(card)
```

It is wired to a 5-second interval (`on_mount`: `self.set_interval(5.0, self._refresh_data)`).
Removing the focused widget drops focus, so ~5 s after the user last pressed
`Tab` there is no focused `CrewCard`.

Every crew-scoped action resolves its target through `_get_focused_crew_id()`
(dashboard.py:1005-1010), which returns `None` when nothing is focused:

- `enter` → `action_open_detail` → `notify("No crew selected", severity="warning")`
- `r` → `action_start_runner`, `k` → `action_stop_runner`, `d` → `action_cleanup` — same

So the keybindings advertised in the footer silently stop working a few seconds
after arriving on the screen, and the only way to use them is to press `Tab` and
the action key within the same 5 s window.

Reproduced during t1046 verification: `Tab`, wait, `Enter` → nothing happens;
`Tab Tab Tab Enter` sent back-to-back → detail screen opens.

## Suggested fix

Preserve selection across refresh. Options, roughly in order of preference:

1. **Update in place** — reuse the mounted `CrewCard` widgets when the crew set is
   unchanged (assign `crew_data` / `runner_info` and `refresh()`), mounting and
   removing only cards for crews that actually appeared or disappeared. This also
   removes a full remount of every widget every 5 s.
2. **Restore focus** — capture `self.focused` crew id before `remove_children()`
   and re-focus that card after remounting (fallback if 1 is too invasive).
3. Track selection in an app-level `_selected_crew_id` (the attribute already
   exists but is unused for this) instead of deriving it from widget focus.

Note the crew list is a `VerticalScroll`; scroll position is likely reset by the
same remount and should be checked alongside focus.

## Acceptance criteria

- With the dashboard idle for >5 s (at least one refresh tick), `Tab` to a crew,
  wait through another tick, then press `Enter` — the detail screen opens for
  that crew.
- Same for `r` / `k` / `d`: the action targets the previously focused crew and
  does not fall back to "No crew selected".
- Focus (and ideally scroll position) survives a refresh in which the crew list is
  unchanged.
- A crew disappearing from the list (e.g. cleaned up) does not leave focus
  dangling or crash the refresh.

## Provenance

Found during t1046 (manual verification of t1041). Pre-existing and unrelated to
the status-rollup change. See `aiplans/archived/p1046_manual_verification_auto.md`
("Upstream defects identified").
