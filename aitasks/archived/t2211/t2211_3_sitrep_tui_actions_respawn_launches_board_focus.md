---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: [t2211_2, t2211_8, t2037_2]
issue_type: feature
status: Done
labels: [sitrep, tui, board]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
implemented_with: claudecode/opus5_5
created_at: 2026-11-05 15:36
updated_at: 2026-11-09 09:38
completed_at: 2026-11-09 09:38
---

## Context

Child 3 of t2211. It adds the deterministic actions to the sitrep TUI (built read-only in
t2211_1), the respawn-agent key (using t2211_2's spawn roles), and user-driven launches from
item details, including a NEW `ait board --focus <id>` (user-confirmed in scope). Agentic
requests typed into the agent are t2211_4, not this child. Parent plan:
`aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`.

The advisory-only rule binds the sitrep **agent**. The user acting through the TUI may
launch picks and open the board. The TUI never pushes or commits, and never runs a push
command.

## Gate and first step

- Depends on t2211_2 (sibling) and **t2037_2** (uncommitted `monitor_core.py` /
  `status_client.py`). Re-read the landed `monitor/monitor_core.py`, `monitor/sitrep_close.py`,
  `lib/agent_launch_utils.py` and `board/aitask_board.py`, and confirm `git diff HEAD --
  <files>` is empty before the first edit.
- Harvest/refresh at startup is owned by the TUI (user-confirmed). t2211_5 removes it from
  the skill.

## Key files

- `.aitask-scripts/sitrep_tui/sitrep_tui_app.py` (from t2211_1): actions, dialogs, dynamic
  bindings.
- `.aitask-scripts/board/aitask_board.py` (+ its launcher `aitask_board.sh` / the `ait board`
  route): a `--focus <id>` argv. It selects and scrolls to the card after the board loads,
  and accepts a handoff to an already-running board pane.
- `.aitask-scripts/lib/agent_launch_utils.py`: `launch_or_focus_board(session, root,
  task_id)`, modelled on `launch_or_focus_trails` (~L3022). That one passes a handle to a
  running trails pane via a tmux pane option, else starts a new window. Compare
  `launch_or_focus_codebrowser` (~L2882, env + `--focus`).

## Reference patterns

- Harvest/refresh output (parse; do not invent):
  - `aitask_sitrep_harvest.sh all --root .` emits, per record, `HARVEST_ITEM:` /
    `HARVEST_WARN:` / `HARVEST_REVIEW:` then one of `HARVESTED:` / `HARVEST_NONE:` /
    `HARVEST_FAILED:`. Exit 1 if any record failed. Reuse the line parsing in
    `monitor/sitrep_close.py` (~L230-256 `HarvestReport`).
  - `aitask_sitrep_refresh.sh --root .` emits `REFRESH_ITEM:` lines and a final
    `REFRESHED:` / `REFRESH_NONE:` / `REFRESH_FAILED:`. The default budget is 60 s, and the
    caller's timeout must be ≥ budget + 15 s (as in `monitor_shared.py` ~L512).
- Writer (`aitask_sitrep_todo.sh`, header ~L84-134; cwd = root or an absolute
  `AITASK_SITREP_DIR`):
  - `dismiss c<N> --outcome <reason> --expect-rev <rev>` → `STATE:c<N>|dismissed|<rev>` or
    `STALE:c<N>|<rev>` (exit 0!);
  - `restore todo|qa` → `RESTORED:<kind>.md|recovered/<name>` or `|no-damaged-copy`;
  - exits: 2 bad request, 3 `LOCK_BUSY`, 4 store unusable.
- Pick launch: `trails_app.action_pick_task` (~L571):
  - `focus_existing_agent_window(id, root)` (`agent_launch_utils` ~L621);
  - `lib/agent_command_screen.build_pick_screen(root, id)` (~L1320);
  - the callback runs `run_dialog_command` / `launch_in_tmux(cmd, cfg)` (~L2086), then
    `maybe_spawn_minimonitor`;
  - the fallback is `aitask_codeagent.sh invoke pick <id>`.
- Dynamic bindings: `check_action` + `refresh_bindings()` (board `aitask_board.py` ~L2429 /
  ~L3782, trails `trails_app.py` ~L775, frozenagent ~L957 / ~L1153). False hides a binding,
  None disables it. A binding gate is not a guard: every action re-checks.
- Confirm dialog shape: `frozenagent_app.ConfirmDialog` (~L127), but base it on
  `lib/guarded_dismiss.GuardedModalScreen`. Clipboard via `tui_clipboard`.
- Respawn path: `aitask_sitrep.sh open --root R --session S` (45 s timeout, like
  `tui_switcher._open_sitrep_async` ~L1717), decoded via `sitrep_cli.sitrep_open_message`,
  which includes the new `SITREP_ADDED_TUI:` / `SITREP_RESPAWNED_AGENT:` lines from
  t2211_2. **Never** a second spawn implementation.

## Implementation plan

1. Rebase check.
2. Harvest + refresh:
   - one worker runs harvest then refresh, on mount and on a key, with the timeouts above;
   - a second request while one is in flight is refused with a toast;
   - a result panel shows the counts and the failed/review lines (markup-safe);
   - reload afterwards.
3. Dismiss:
   - a confirm dialog with a reason input, then `dismiss --outcome --expect-rev <rev from the
     loaded store>`;
   - `STALE:` → reload, show "item changed (rev X→Y)", re-open the dialog. Never retry blind;
   - exit 3 → toast and retry offered; exit 2/4 → error panel.
4. Restore: on an unusable store (`FormatError` from the reader, or exit 4), a confirm dialog
   offers `restore todo` / `restore qa`, then shows the result line and reloads.
5. Agent status:
   - poll `monitor_core.find_sitrep_roles` (t2211_2) off-loop;
   - the header shows "agent running" / "agent not running";
   - the respawn key is shown only when no agent role resolves, and the action re-checks;
   - it runs `aitask_sitrep.sh open`, then toasts the decoded line.
6. Launches from details (key shown only for a matching kind/state; re-checked in the action):
   - task item (`ref` `t<N>[_M]`) → pick launch as in trails, and "open in board" →
     `launch_or_focus_board`;
   - push item (`push:<branch>@<sha>`) → show the exact push command (`./ait git push` for
     task data, or `git push origin <branch>` per the ref's meaning; check
     `sitrep_todo.parse_push_ref`), copyable, **never executed**.
7. Board `--focus <id>`:
   - argv parsing in the board main;
   - after the first load, select the card (parent or child id; archived → toast "not on the
     board");
   - for a running board pane, use a pane-option handoff read on its refresh (as trails
     does) so a second board is not started.
8. Tests:
   - `tests/test_sitrep_tui_actions.py` (run_test, a fixture store built through the real
     writer verbs): STALE re-read, confirm cancel = no write, LOCK_BUSY, restore,
     harvest/refresh panel parsing, bindings per kind/state, respawn-key wire decoding,
     push command shown not run;
   - a board `--focus` test (argv, card selection, handoff).

## Verification

- The tests above + `bash tests/run_all_python_tests.sh --test-dir tests` (last-line
  verdict).
- `bash tests/test_no_raw_tmux.sh`; `shellcheck` on changed scripts.
- Manual: in the sitrep window press harvest, dismiss an item, kill the agent and respawn it
  from the TUI, open a task in the board.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2211_8** id=2026-11-08T08:40:05Z.bf7f1f261860e09bc32389c1 from=t2211_8 at=2026-11-08T08:40:05Z base=97af1d19ae282df63a283693757f25a30b657244 base_branch=main dirty=yes host=omg16
>
> | Advisory (decided with the user 2026-11-08): t2211_8 (sitrep TUI readability) now runs before t2211_3. It replaces the user-facing `kind`/`state` columns with an action-oriented "What to do" column plus a "how" line in item details, from ONE mapping table in sitrep_tui/sitrep_tui_model.py. Its "how" names today's means (`>t c<N>` / `>q c<N>` typed to the sitrep agent, `/aitask-pick <N>`, the push command). When you add your keys, change that table's "how" entries rather than adding a parallel list. Also from t2211_8: click only SELECTS in the main list, the details links list and the Q&A list (Enter opens), so any new list or action should follow that rule. KEY receipt sources are hidden from the TUI.

> **✉ note:t2211_8** id=2026-11-08T10:24:37Z.783ccefcc77d0a6520bd18cd from=t2211_8 from_verified=yes at=2026-11-08T10:24:37Z base=593be5e9cfd800d74cdb26367179df2df6a2bca9 base_branch=main dirty=yes host=omg16
>
> | t2211_8 (committed in 593be5e9c on main) changed how the sitrep TUI presents the store. Points that touch your plan:
> | - `sitrep_tui_model.NEXT_STEPS` is now the ONE kind/state -> "What to do" + "How" table. When your keys land (pick `p`, board `b`, push `P`, dismiss `x`, refresh `r`), edit the `how` texts of the matching rows there: pick, pick_xref, push, do, unknown, unknown_manual. Do not add a parallel mapping.
> | - `classify(item, refresh_check)` keys are stable; your `check_action` gating can key on `model.classify(...)` instead of raw kind/state. `model.refresh_checks(store)` (built from `sitrep_refresh.select_targets`) says which items refresh re-checks; the app caches it as `app._checks` in `_apply`, and `ItemDetailScreen(..., refresh_check)` takes the cached value.
> | - All four lists are `SelectOnClickList` (a click only highlights; Enter opens via the footer binding). New lists should use it too.
> | - Detail bodies are `Content` built by `body_content(now)` (styled labels, plain values); `body_text` is `.plain`. Details are still snapshots.
> | - The main list header is `#st-columns`; row text is `model.row_text(item, now, cid_w, refresh_check)`.
> | Advisory context only; see aiplans/archived/p2211/p2211_8_* Final Implementation Notes once archived.

> **👁 note:read** id=2026-11-08T15:43:05Z.4087e0e370e39d6d6d472b6b by=t2211_3 at=2026-11-08T15:43:05Z mode=explicit ids=2026-11-08T08:40:05Z.bf7f1f261860e09bc32389c1,2026-11-08T10:24:37Z.783ccefcc77d0a6520bd18cd

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-08T16:53:11Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-09T07:36:28Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-09T07:38:35Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:bbad37ff1bf427d3

> **✅ gate:risk_evaluated** run=2026-11-09T07:38:35Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2211_3/risk_evaluated_2026-11-09T07:38:35Z-risk_evaluated-a1.log`
