---
priority: medium
effort: medium
depends: [t2211_5]
issue_type: documentation
status: Ready
labels: [sitrep, documentation]
gates: [risk_evaluated]
anchor: 2175
created_at: 2026-11-05 15:37
updated_at: 2026-11-05 15:37
---

## Context

Child 6 of t2211: the docs for the three-pane sitrep window, the new sitrep TUI, the guarded
request delivery, the slimmed skill and `ait board --focus`. Docs are a first-class
deliverable (`aidocs/framework/planning_conventions.md`, "User-facing features"). Parent
plan: `aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`. Read the archived plans of
t2211_1..5 (`aiplans/archived/p2211/`) for what actually landed, and document the landed
behaviour, not this description.

## First step

Re-read the landed docs (t2175_6 edited `aidocs/framework/sitrep.md`, the website workflow
page and the skill page) and confirm they are clean against HEAD.

## Files

- `aidocs/framework/sitrep.md`:
  - "The sitrep window" (~L46): the roles (agent, TUI, minimonitor), the layout, the
    `@aitask_sitrep_tui_root` stamp, the two-predicate table (not an agent for listing / a
    real occupant for retention), the four-way spawn and its statuses, the new wire lines
    `SITREP_ADDED_TUI:` / `SITREP_RESPAWNED_AGENT:`, agent-exit behaviour, races;
  - a new section "The sitrep TUI": views, pointers, actions, reload, the request-delivery
    phases with their refusals / results and the `@aitask_dispatch_ack` ack;
  - "The skill" (~L267): the slim menu and TUI requests;
  - "Tests" (~L322): the new test files.
- `aidocs/framework/tmux_gateway.md`: confirm `@aitask_sitrep_tui_root` and
  `@aitask_dispatch_ack` are in the option inventory (added by t2211_2 / t2211_4).
- `website/content/docs/workflows/sitrep.md`: opening (three panes), what happens at start
  (the TUI harvests + refreshes), the list (in the TUI), triage / asking via TUI keys, the
  shortcodes table (slim), dismissing / restoring (TUI), closing a finished agent.
- `website/content/docs/skills/aitask-sitrep.md`: the capabilities table (slim). "What it
  never does" keeps "type into another agent's pane" and adds that the sitrep TUI types into
  the sitrep agent only at the user's request, refusing when the agent is at a dialog, holds
  a draft, is working or is in copy-mode.
- NEW `website/content/docs/tuis/sitrep/` (`_index.md`, `how-to.md`, `reference.md`),
  modelled on `website/content/docs/tuis/trails/` (front matter: title, linkTitle, weight,
  description, maturity, depth). The reference covers keys (default bindings + the shortcut
  scope `sitrep_tui`), groups, pointer kinds, actions, request keys with their refusals and
  results in user terms.
- `website/content/docs/tuis/_index.md`: add a bullet to "Available TUIs".
- The board reference page: `ait board --focus <id>`.
- Follow `aidocs/framework/documentation_conventions.md`:
  - current state only, no version history;
  - say "autonomous" if auto modes are mentioned;
  - genericize agent names where the passage names the supported coding agents.
- Prefer `{{< relref "/docs/..." >}}` for internal links.

## Verification

- `cd website && hugo build --gc --minify && python3 check_links.py --build` (mandatory).
- Offer `python3 check_link_relevance.py` for the new and retargeted links.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2211_8** id=2026-11-08T08:40:10Z.55f2b54f82b3c8d362ad1494 from=t2211_8 at=2026-11-08T08:40:10Z base=97af1d19ae282df63a283693757f25a30b657244 base_branch=main dirty=yes host=omg16
>
> | Advisory: t2211_8 (before t2211_3) adds a fixed list header, an action-oriented 'What to do' column replacing the internal kind/state, a 'how' line in details, plain-language source labels (KEY receipts hidden), Markdown for task/plan sources, and click-selects/Enter-opens. Document these on the TUI page.

> **✉ note:t2211_8** id=2026-11-08T10:24:57Z.94b6f7ba84c4a8bf39d87cf8 from=t2211_8 from_verified=yes at=2026-11-08T10:24:57Z base=593be5e9cfd800d74cdb26367179df2df6a2bca9 base_branch=main dirty=yes host=omg16
>
> | t2211_8 (committed in 593be5e9c on main) changed what the sitrep TUI shows. No docs were written there: the user said the `ait sitrep` feature is still in flux, so documentation stays with this task. When it is written, the user-visible behaviour to cover is:
> | - the main list has a fixed header (Item / Checked / What to do). The "What to do" column replaces the internal kind/state words, e.g. "Triage t2175_2's wrap-up: ...", "Pick t2182 (status: Ready): ...", "Waiting on: ... — nothing to do now". "Checked" shows "—" for never.
> | - the details show labelled Item / Context sections: What to do, How, About (the item's ref), Checked, Outcome, Background, Origin sub-fields, Theme.
> | - sources use plain labels ("Closing message", "Workflow result", "Task t<N> (archived)", "Plan of t<N>", "Commit <sha>", "Excerpt of the unparsed output", "Raw input (review case)"), with "Related: item c<N>" and "Mentioned by item c<N>" links. KEY receipts are hidden (they stay in the store).
> | - a click only selects a row on every list; Enter opens.
> | - task / plan / .md file sources render as Markdown (links never opened); `m` toggles the raw text with line numbers; a `#L` pointer opens raw.
> | The How texts will change as t2211_3/t2211_4 add keys; the single source is `sitrep_tui_model.NEXT_STEPS`. Advisory context only.

> **✉ note:t2211_3** id=2026-11-09T07:38:12Z.48acd9cecf094c958028ea28 from=t2211_3 from_verified=yes at=2026-11-09T07:38:12Z base=706bf2f6d8f8138a01cacd722201196cbfbf1aba base_branch=main dirty=yes host=omg16
>
> | t2211_3 (committed in 706bf2f6d on main) added the sitrep TUI's actions. What your docs need:
> | - Keys: r harvest+refresh (main list AND item details; also once at startup, toast only), x dismiss with a reason, R restore (only when the store is unusable), A respawn agent (only when the agent is not running), p pick (pick items only, never triage), b open in board, P push command (shown and copyable, never run). The "How" lines name the effective (remapped) keys.
> | - The mixed group is labelled "Now" in the TUI (the store heading stays "### Pick now").
> | - New list column Pri/Eff (hi/lo, med/med; "—" = task file not found; blank for non-task items). Details of a task item show Priority / Effort / Task status ("(archived)") and a first link "Task description: t<N> (<path>)".
> | - Header: "agent: running | not running — press A | unknown" and "refreshed HH:MM ok|with errors".
> | - New `ait board --focus <id>` (12, t12, 12_3); a running board takes the request through its pane mailbox (@aitask_board_app / @aitask_board_focus); from another session the client is switched.
> | - Writer: `aitask_sitrep_todo.sh restore todo|qa --if-damaged` -> RESTORE_NOT_NEEDED:<file> when the live file parses (plain restore stays unconditional).
> | Framework text already landed in aidocs/framework/sitrep.md ("The TUI's actions") and tmux_gateway.md. Advisory context only.

> **✉ note:t2211_9** id=2026-11-09T08:07:04Z.8e235305d623d3a798d68daa from=t2211_9 at=2026-11-09T08:07:04Z base=706bf2f6d8f8138a01cacd722201196cbfbf1aba base_branch=main dirty=yes host=omg16
>
> | New sibling t2211_9 (created 2026-11-09, not implemented yet) will change sitrep TUI surfaces your docs cover. Planned, not landed:
> | - item details: Priority and Effort on ONE line ("Priority    high · effort low") instead of two;
> | - the `d` toggle becomes visibly a toggle: footer "Show done" / "Hide done", hidden counts in the header, and showing the closed groups jumps to the first closed item;
> | - task items show when the follow-up task was created (from the task file's created_at): time if today, else date, in the list row and the details;
> | - a new key filters the main list by task labels (labels from the task files' frontmatter); behaviour for non-task items while a filter is active is still to be decided there.
> | If you document the TUI before t2211_9 lands, describe the current behaviour and expect these changes; the final key and column names come from t2211_9's implementation. Advisory context only.
