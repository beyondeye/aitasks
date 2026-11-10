---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t2211_5]
issue_type: documentation
status: Done
labels: [sitrep, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
implemented_with: claudecode/opus5_5
created_at: 2026-11-05 15:37
updated_at: 2026-11-10 18:29
completed_at: 2026-11-10 18:29
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

> **✉ note:t2211_9** id=2026-11-09T15:26:43Z.b9e1fe4227966b3ce1d3f784 from=t2211_9 from_verified=yes at=2026-11-09T15:26:43Z base=6d44bd275b3df9d0dea78d4137a12f305584d5c1 base_branch=main dirty=yes host=omg16
>
> | Advisory (claim, from t2211_9; code commit 6d44bd275). What changed in the sitrep TUI that the window docs may want to cover:
> | 
> | - `d`: the footer label now follows the state, "Show done" / "Hide done". While the closed groups are hidden, the header adds "· N done, M dismissed hidden". Showing them moves the highlight to the first done (else dismissed) item and scrolls to it. Cause of the original "d only works when an item is selected" report: in a short pane the list is about one row tall and the groups were added off-screen. There was no focus dependency.
> | - `f` opens a label picker: the labels on the store's task items, with counts. Space toggles, Enter or Apply applies, Clear empties the filter, Esc cancels. The filter shows task items whose task has ANY checked label. Non-task items (triage, decisions, watches, pushes, cross-repo refs) and task items whose file is missing are hidden while it is on. The header reads "filtered by: <labels> · N hidden (F clears)". `F` clears. Both keys work on the main list only. The filter is per-session and never written to the store.
> | - New list column "Created" (task items naming a local task): HH:MM when created today, MM-DD in the current year, YYYY-MM-DD in other years; "—" when the file is missing or has no created_at, "?" when it cannot be parsed. Rule: created_at is local wall-clock time with no zone; "today" compares calendar dates in the machine's local zone (the clock seam AITASK_SITREP_NOW applies).
> | - Item details: Priority and effort are now one line ("Priority    high · effort low"), plus a "Created" line with the full stored value.
> | 
> | See aiplans/p2211/p2211_9_* (archived under aiplans/archived/p2211/ once t2211_9 archives), "Notes for sibling tasks".

> **✉ note:t2211_10** id=2026-11-10T07:03:06Z.ad44f6bda58f2101fe296e47 from=t2211_10 from_verified=yes at=2026-11-10T07:03:06Z base=0e17732b1e5f4d2b3849a80cf3000e2ddf2b22d2 base_branch=main dirty=no host=omg16
>
> | Advisory (claim, from t2211_10; code commit 0e17732b1, tree-relative). New sitrep TUI behaviour to document:
> | 
> | - Key `z` "Trails" on the main list and on item details. It is shown only for a task item whose task is known to be in at least one implementation trail. It opens `ait trails` on that trail with the task's card focused. With 2+ trails a picker opens (a click selects, Enter opens, Esc cancels). On the details screen, `z` acts on the highlighted trail row, else 1 trail → open, 2+ → the picker.
> | - Task item details:
> |   - a `Trails` line, e.g. "Sitrep follow-ups (w1)", or "none" / "looking…" / "unknown (<reason>)";
> |   - one links row per trail, e.g. "In trail: Sitrep follow-ups (art:trail-sitrep-followups) — wave 1". Enter on the row does the same jump.
> | - States:
> |   - "looking…" until the first scan lands (it runs in the background after a store change, when details open, and every 60 s);
> |   - "unknown (<reason>)" when the scan failed, `project.name` is unset, or a partial scan found nothing for the task. It is never shown as "in no trail".
> |   - A partial scan keeps the trails it did read, plus a disabled "some trails could not be read" row.
> | - Session handling is as for `b`: the TUI's own session, else the project's live session, with a client switch when needed.
> | - New CLI: `ait trails --trail <handle> --task <id>` (`--task` needs `--trail`; 12, t12 and 12_3 are accepted).
> | - A running `ait trails` started before this change still opens the trail; the sitrep TUI then warns that it cannot focus a card (restart trails).
> | Framework-side docs already updated in that commit: aidocs/framework/sitrep.md and tmux_gateway.md (`@aitask_trails_card_focus`).

> **✉ note:t2211_4** id=2026-11-10T10:45:15Z.b932f8c8b6b59cc64a1dd074 from=t2211_4 from_verified=yes at=2026-11-10T10:45:15Z base=e16e440e4036bf3929b3d0a60a54f81be2f11003 base_branch=main dirty=yes host=omg16
>
> | Advisory (a claim from t2211_4, code commit e16e440e4, tree-relative). Facts for the sitrep TUI docs:
> | 
> | - Request keys, all remappable: `t` triage (triage/review items) → `>t c<N>`; `a` ask (any item, one-line dialog) → `>q c<N> <text>`; `w` situation text (items whose context has a theme) → `>w <theme>`; `T` trail refresh (trail-checked watches) → `>tr c<N>`; `n` pick advice (main list + details) → `>p`. They are shown only while the sitrep agent runs, and only one request at a time.
> | - Delivery (`.aitask-scripts/monitor/agent_request_delivery.py`) has three phases:
> |   1. Readiness: two captures 0.5 s apart must both show an empty, idle composer, and the pane must not be in a tmux mode. Otherwise the key is refused and nothing is typed.
> |   2. Guarded paste: the text goes to tmux on stdin (`load-buffer -`; argv mangles a trailing `;`), then one `if-shell -F` checks the run identity and `pane_in_mode`. The `@aitask_dispatch_ack` nonce reports which branch ran.
> |   3. Submission: before every Enter the composer's complete payload must equal the request (only justified display wraps allowed), and the mode is read last. The Enter is itself guarded and acked.
> | - Results: `submitted`, `typed_not_submitted[:in_mode|:mode_unreadable]`, `refused:<not_ready:dialog|draft|working|unknown|in_mode|mode_unreadable | identity_changed | no_agent | frozen | dispatch_failed | invalid_request>`, `skipped`, `unknown`. `unknown` never reads as sent. User-facing wording comes from `DeliveryResult.message()`; every result is toasted, and anything but `submitted` also opens the result panel.
> | - Already done by t2211_4: the `@aitask_dispatch_ack` row and `TmuxClient.run_with_input` in `aidocs/framework/tmux_gateway.md`. In `aidocs/framework/sitrep.md` only the intro sentence ("never types into another pane") was corrected; the full TUI section is still yours.
> | - Agent support: claude, codex and opencode have measured composer grammars (`review_loop.PAYLOAD_GRAMMAR_AGENTS`). Any other agent is refused before typing.

> **✉ note:t2211_5** id=2026-11-10T13:59:35Z.eac5833fe42c37f81f42b81d from=t2211_5 from_verified=yes at=2026-11-10T13:59:35Z base=82f5351bc2f8459ec865315fcc4801818a47bc8d base_branch=main dirty=yes host=omg16
>
> | Advisory (a claim from t2211_5, code commit 82f5351bc, tree-relative) for the docs in your scope:
> | 
> | - The skill's codes are now `>t [c<N>]`, `>w [<theme>]`, `>q [c<N>]`, `>tr [c<N>]`, `>p`, `>c`, `>?`. `>s`, `>r` and `>x` no longer exist; a shortcodes table or capabilities table that lists them is stale.
> | - The skill no longer harvests/refreshes at start. `aidocs/framework/sitrep.md` L364 ("On start: `ait sitrep root`, `harvest all --root .`, `refresh --root .`, then …") still describes the old start; the skill now runs root, then `list` + `read todo`, then greets.
> | - Two new skill sections to describe: "Requests from the sitrep TUI" (the five request lines; same authority as typed input, still confirmed before writing; a fresh `list` / `context` / `read context` + `read todo` before each request; per-code checks) and "Done in the sitrep TUI, not here" (show, refresh, dismiss, restore are TUI keys `r` / `x` / `R` by default; the agent names the key instead of acting).
> | - `>t c<N>` triages only that item; a bare `>t` triages every open triage item as one batch.
> | - The guardrail now says the TUI may type into the agent at the user's request, never the reverse ("What it never does").

> **👁 note:read** id=2026-11-10T14:10:43Z.4285e607c6aad24e7788685d by=t2211_6 at=2026-11-10T14:10:43Z mode=explicit ids=2026-11-08T08:40:10Z.55f2b54f82b3c8d362ad1494,2026-11-08T10:24:57Z.94b6f7ba84c4a8bf39d87cf8,2026-11-09T07:38:12Z.48acd9cecf094c958028ea28,2026-11-09T08:07:04Z.8e235305d623d3a798d68daa,2026-11-09T15:26:43Z.b9e1fe4227966b3ce1d3f784,2026-11-10T07:03:06Z.ad44f6bda58f2101fe296e47,2026-11-10T10:45:15Z.b932f8c8b6b59cc64a1dd074,2026-11-10T13:59:35Z.eac5833fe42c37f81f42b81d

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-10T15:41:46Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-10T16:24:31Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-10T16:28:53Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:c56a25f7a918f1dc

> **✅ gate:risk_evaluated** run=2026-11-10T16:28:53Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2211_6/risk_evaluated_2026-11-10T16:28:53Z-risk_evaluated-a1.log`
