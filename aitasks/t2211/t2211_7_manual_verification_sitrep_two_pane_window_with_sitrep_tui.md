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

> **✉ note:t2211_8** id=2026-11-08T10:25:00Z.71f19ee8077a629cc6135d8c from=t2211_8 from_verified=yes at=2026-11-08T10:25:00Z base=593be5e9cfd800d74cdb26367179df2df6a2bca9 base_branch=main dirty=yes host=omg16
>
> | t2211_8 (committed in 593be5e9c on main) made the sitrep TUI readable. Candidate checklist items for this manual verification:
> | - `ait sitrep tui` on the real store: the list has a fixed Item / Checked / What to do header that stays put while scrolling, and its columns line up over the rows.
> | - rows say what to do (no internal kind/state words), and pick rows show the task's real status.
> | - a left click only highlights a row on the main list, the details links, the Q&A log and the Q&A entry links; Enter (footer "Details" / "Open") opens.
> | - details show bold labels with plain values in Item / Context sections; How names the way to act.
> | - c1's sources show "Closing message", "Workflow result", "Task t2175_2 (archived)", "Plan of t2175_2 (archived)" and "Commit d0c48e88d", with no KEY lines and no hex handles.
> | - a task/plan source renders as Markdown; `m` switches to the raw text and back.
> | As of 593be5e9c the How texts name agent codes (`>t`, `>q`, `>r`, `>x`); t2211_3/t2211_4 may replace them with keys before this task runs. Advisory context only.

> **✉ note:t2211_3** id=2026-11-09T07:38:14Z.0defac6c660699c72dd71dbd from=t2211_3 from_verified=yes at=2026-11-09T07:38:14Z base=706bf2f6d8f8138a01cacd722201196cbfbf1aba base_branch=main dirty=yes host=omg16
>
> | t2211_3 (committed in 706bf2f6d) is ready for manual checks in a real sitrep window. Suggested checklist items:
> | - r opens the harvest+refresh panel (also from an item's details); at startup only a toast.
> | - x on an open item dismisses it with the typed reason; change the item from the agent meanwhile -> the dialog asks again (rev a->b).
> | - Kill the sitrep agent -> header says "agent: not running — press A" -> A + Confirm respawns it beside the TUI.
> | - b on a task item: (1) with a board running -> that board focuses the card (no second board); (2) with no board -> a "board" window opens on the card; (3) with the board in another session of the project -> the client switches there.
> | - p on a pick item opens the pick dialog (narrow) and launches in a tmux window; p is absent on triage items.
> | - P on a push reminder shows a quoted command with Copy/Close only.
> | - Damage todo.md (edit a kind= value) -> banner says press R -> R restores; repair it by hand while the dialog is open -> "healthy again — nothing restored".
> | - The Pri/Eff column and, in task details, Priority/Effort/Task status and the "Task description" link (opens the rendered task file).
> | Advisory context only.

> **✉ note:t2211_9** id=2026-11-09T08:07:06Z.74f44aa5b70630bde411191d from=t2211_9 at=2026-11-09T08:07:06Z base=706bf2f6d8f8138a01cacd722201196cbfbf1aba base_branch=main dirty=yes host=omg16
>
> | New sibling t2211_9 (created 2026-11-09, not implemented yet) adds sitrep TUI behaviour your manual checklist should cover once it lands:
> | - details of a task item show Priority and Effort on one line;
> | - `d` shows/hides "Recently done" + "Dismissed" visibly: the footer label and header counts change, and showing jumps to the first closed item, also in a short pane; check that it works with no item selected (the user reported it seemed to need a selection; a pilot test could not reproduce that);
> | - task rows and details show the follow-up task's creation time (today) or date (earlier);
> | - the label filter: apply, check the header says what is filtered/hidden, clear it.
> | Exact keys and labels come from t2211_9's implementation. Advisory context only.

> **✉ note:t2211_9** id=2026-11-09T15:27:00Z.6a2b45505c0933ab80f6160f from=t2211_9 from_verified=yes at=2026-11-09T15:27:00Z base=6d44bd275b3df9d0dea78d4137a12f305584d5c1 base_branch=main dirty=yes host=omg16
>
> | Advisory (claim, from t2211_9; code commit 6d44bd275). Checklist items for the real sitrep window, if you want them:
> | 
> | - In a SHORT sitrep pane (about 14-16 rows): press `d`. The highlight jumps to the first "Recently done" item and it is visible. The footer flips between "Show done" and "Hide done". While hidden, the header shows "· N done, M dismissed hidden". Repeat with focus on the situation pane (tab) and after opening and closing an item's details.
> | - Task rows show a "Created" cell: HH:MM for tasks created today, MM-DD for this year.
> | - Item details show "Priority    <p> · effort <e>" on one line and a "Created" line.
> | - `f` opens the label picker. Check one label and apply. Only matching task items remain, and the header says "filtered by: <label> · N hidden (F clears)". `F` restores the full list.
> | - With the picker open at about 16 rows: Apply / Clear / Cancel are clickable with the mouse. Resize the pane smaller while a lower label is highlighted: the highlight stays visible.
> | 
> | Automated coverage exists for all of these (pilot tests in tests/test_sitrep_tui_actions.py). These items are the human-eye check.

> **✉ note:t2211_10** id=2026-11-10T07:03:23Z.fc3d2e1102da1708448c3e9e from=t2211_10 from_verified=yes at=2026-11-10T07:03:23Z base=0e17732b1e5f4d2b3849a80cf3000e2ddf2b22d2 base_branch=main dirty=no host=omg16
>
> | Advisory (claim, from t2211_10; code commit 0e17732b1, tree-relative). Manual checks to add for "show a task in ait trails", in a real sitrep window:
> | 
> | 1. A task item whose task is in a trail (e.g. one of art:trail-sitrep-followups' members). Its details show a `Trails` line and one "In trail: … — wave N" row per trail. A task in no trail shows "Trails  none" and no rows.
> | 2. Enter on a trail row opens `ait trails` on that trail with that task's card focused. A click on the row only selects it.
> | 3. `z` on the main list with `ait trails` already running in the session (handoff: the running trails switches to the trail and focuses the card).
> | 4. `z` with no `ait trails` running: a new `trails` window opens with `--trail <h> --task <id>`, and the card is focused.
> | 5. `z` from a sitrep TUI whose own session is not the project's session: the client switches to the project session.
> | 6. A task in 2+ trails: `z` opens the picker; Enter opens the chosen trail.
> | 7. A long wave: the focused card is scrolled into view, both on the first request and again after scrolling the column away and pressing `z` once more.
> | 8. `ait trails` started before this change and still running: `z` opens the trail, and the sitrep TUI warns "cannot focus a card".
> | 9. `z` is not shown for triage / question / push items, or while the trail lookup is still "looking…".

> **✉ note:t2211_4** id=2026-11-10T10:45:18Z.8ded83624c430b4f50c5b866 from=t2211_4 from_verified=yes at=2026-11-10T10:45:18Z base=e16e440e4036bf3929b3d0a60a54f81be2f11003 base_branch=main dirty=yes host=omg16
>
> | Advisory (a claim from t2211_4, code commit e16e440e4, tree-relative), for your t2211_4 checklist rows:
> | 
> | - The request keys are `t` (triage), `a` (ask), `w` (situation text), `T` (trail refresh) and `n` (pick advice — NOT `p`, which is Pick).
> | - Expected outcomes, shown as a toast and, unless submitted, a result panel:
> |   - with a permission dialog open → "Not sent: the agent is waiting for an answer to a dialog";
> |   - with a half-typed draft → "Not sent: the agent's composer holds unsent text (left untouched)";
> |   - copy-mode entered after the text was typed → "Typed into the sitrep agent but NOT submitted: its pane is in a tmux mode …", with the request left in the composer.
> | - A sitrep agent pane frozen before you press a key reads as "no running sitrep agent pane".
> | - The ask dialog refuses a question ending in an @mention: it opens the agent's file picker, which would take the Enter.
