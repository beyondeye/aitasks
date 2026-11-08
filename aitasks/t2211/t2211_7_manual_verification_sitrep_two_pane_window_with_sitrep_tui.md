---
priority: medium
effort: medium
depends: [t2211_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [2211_1, 2211_2, 2211_3, 2211_4, 2211_5, 2211_6]
anchor: 2175
followup_kind: manual_verification
created_at: 2026-11-05 15:40
updated_at: 2026-11-05 15:40
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t2211_1] `./ait sitrep tui` on the real store shows Pick now / Next / Waiting groups, toggles Recently done + Dismissed, and renders situation text per theme
- [ ] [t2211_1] Item details show fields, outcome with checked_at age, the context map; each pointer kind (task/plan/file/capture/commit/trail/artifact/case) opens read-only in the viewer
- [ ] [t2211_1] Q&A browser lists entries newest first and links to/from the items they name; editing todo.md via a writer verb reloads the view within a few seconds, selection kept
- [ ] [t2211_2] `ait sitrep` cold start: agent top-left, sitrep TUI below it, minimonitor full-height right column; a second `ait sitrep` only focuses
- [ ] [t2211_2] Close the agent: TUI and minimonitor stay; `ait sitrep` respawns the agent above the TUI and the layout is restored
- [ ] [t2211_2] Kill the TUI pane: `ait sitrep` adds it back under the agent; the monitor and minimonitor never list the TUI pane as an agent
- [ ] [t2211_3] In the TUI: harvest+refresh key shows results; dismiss with a reason asks for confirmation and the item moves to Dismissed; cancel writes nothing
- [ ] [t2211_3] With the agent closed the TUI shows "agent not running" and the respawn key brings it back
- [ ] [t2211_3] On a task item: pick launches /aitask-pick <id> in a new agent window; open-in-board opens or focuses the board on that card; on a push item the push command is shown, not run
- [ ] [t2211_4] Triage key on an item submits `>t c<N>` to an idle sitrep agent and the agent starts triage
- [ ] [t2211_4] With a permission dialog open in the agent, or a half-typed draft in its composer, the request key is refused and the dialog/draft is untouched
- [ ] [t2211_4] Entering tmux copy-mode in the agent pane during delivery leaves the request typed and unsubmitted; clipboard not clobbered
- [ ] [t2211_5] Fresh `ait sitrep`: the agent greets without running harvest/refresh; its menu no longer lists >s, >r, >x; a TUI-typed `>q c<N> ...` is answered and logged
- [ ] [t2211_6] Website: the new Sitrep TUI page is reachable from the TUIs index, and the sitrep workflow / skill pages describe the three-pane window accurately

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2211_8** id=2026-11-08T08:40:12Z.25b2cdeb75a68d6750ca811e from=t2211_8 at=2026-11-08T08:40:12Z base=97af1d19ae282df63a283693757f25a30b657244 base_branch=main dirty=yes host=omg16
>
> | Advisory: new child t2211_8 (sitrep TUI readability) needs checklist items: the list header is readable without docs, every 'What to do' row says how to act, click only selects (Enter opens) on all three lists, labels are distinct from values in details, task/plan sources render as Markdown, KEY receipts are hidden.
