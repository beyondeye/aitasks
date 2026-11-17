---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [tui_switcher, documentation]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2278
created_at: 2026-11-16 19:53
updated_at: 2026-11-17 12:55
---

## Context

The docs screenshot generator (t2278) captures the real TUI switcher for two
documentation markers:

- `tui_switcher_from_monitor` (`website/content/docs/tuis/monitor/_index.md`,
  `tuis/monitor/how-to.md`)
- `tui_switcher_from_minimonitor` (`website/content/docs/tuis/minimonitor/how-to.md`)

The real switcher lists **"Diff Viewer"**: `.aitask-scripts/lib/tui_registry.py`
registers `("diffviewer", "Diff Viewer", "ait diffviewer", True)` with
`in_switcher=True`, and `lib/tui_switcher.py` builds `KNOWN_TUIS =
switcher_tuis()` from it. CLAUDE.md ("Project-Specific Notes") says diffviewer
is transitional and must be omitted from user-facing docs and lists of TUIs.
So any screenshot of the switcher puts it on the website.

t2278_4 found this while recording the monitor-family scenes and, by the
user's decision, did NOT capture the two switcher scenes and did not patch the
switcher. This task decides how the switcher stops showing Diff Viewer.

## The constraint to reconcile

CLAUDE.md also says: "Keep `diffviewer` in `KNOWN_TUIS` inside
`.aitask-scripts/lib/tui_switcher.py` — it must remain switchable via `j`
until the brainstorm integration lands." Hiding it from the switcher list and
keeping it switchable via `j` pull in opposite directions. Options to put to
the user during planning (do not pick silently):

1. Keep it in `KNOWN_TUIS` but hide its row from the switcher LIST (still
   reachable by a direct key or by its running window, if one exists) —
   check whether "switchable via `j`" means "listed" or only "reachable".
2. Hide it only when a docs-screenshot session asks (an environment switch the
   screenshot tool pins) — keeps users' switcher unchanged; the docs then
   show a list that differs from the real one, which needs its own judgement.
3. Drop it from the switcher now and update the CLAUDE.md rule, if the
   brainstorm integration plan no longer needs `j` access.

Whatever is chosen, update the CLAUDE.md note in the same change so the rule
and the code agree, and check `website/content/docs/tuis/_index.md`
("Navigating between TUIs") for the switcher's documented list.

## After this lands

The two switcher scenes can be recorded with the t2278_4 tooling
(`website/screenshots.sh`, datasets `agents`, pane/window verbs). t2278_5
(the skill and the pass over the remaining markers) was notified that these
two scenes wait for this task.

## Verification

- The switcher opened from monitor and from minimonitor no longer lists Diff
  Viewer (in the way the chosen option defines), and the diff viewer is still
  reachable as the chosen option promises.
- `tests/test_tui_switcher*.py` and any test pinning `KNOWN_TUIS` updated and
  passing.
