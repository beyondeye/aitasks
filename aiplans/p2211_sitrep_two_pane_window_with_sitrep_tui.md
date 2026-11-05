---
Task: t2211_sitrep_two_pane_window_with_sitrep_tui.md
Base branch: main
Output branch: main
---

# t2211 — Sitrep window: agent + sitrep TUI + minimonitor (decomposed)

## Context

`ait sitrep` currently opens one code-agent pane (`/aitask-sitrep`) in an
`agent-sitrep[-n]` window plus a forced minimonitor companion. The agent also
does purely deterministic work: showing the list, harvest + refresh, dismiss,
restore. Reading the list through an agent is slow and hard to scan. The goal is
a three-pane window: the agent (now focused on agentic work), a new Python/Textual
**sitrep TUI** that shows the store readably and runs the deterministic actions,
and the minimonitor. The scope and decisions are in the task file. Decisions
added during planning (user-confirmed):

- **Split into children** (below). The user approved 5. A review of the plan
  then showed that guarded request delivery needs its own protocol (readiness,
  a delivery result it can observe, submission kept separate from dispatch), so
  it became its own child, making **6**. Skill and docs move to _5 and _6.
- **Layout:** the TUI goes *below* the agent (a vertical split of the agent pane,
  about 40% of its height). The minimonitor stays the narrow right column.
- **Board focus is in scope** (child _3): add `ait board --focus <id>` and a
  focus-or-launch helper.
- **Harvest + refresh at startup belong to the TUI** (on mount, off the event
  loop, plus a key). The skill's Step 0 becomes a root check and a list read.

This is a decomposed parent. Nothing is implemented here: the children carry the
work, and each child is planned and risk-evaluated in detail when it is picked.

## Sequencing: in-flight tasks on the same files (gate)

These tasks are `Implementing` in this checkout and have **uncommitted hunks** in
files the children edit:

- **t2175_6** (harvest fallback + review corpus). It modifies
  `aitask_sitrep.sh` (new `case` verb), `aitask_sitrep_harvest.sh`,
  `aitask_sitrep_todo.sh`, `lib/sitrep_cli.py`, `lib/sitrep_harvest.py`,
  `lib/sitrep_todo.py` (raw/cases store dirs, case-origin pointers),
  `monitor/sitrep_close.py` (`HARVEST_REVIEW:`), `SKILL.md.j2` (new `>c` corpus
  code, triage step 2b for unparsed reviews), the goldens,
  `test_sitrep_skill_contract.sh`, `aidocs/framework/sitrep.md` and both website
  sitrep pages.
- **t2037_2** (monitor status client). It modifies `monitor/monitor_core.py`
  (`seed_pane_cache`) and adds `monitor/status_client.py`, a `TmuxMonitor`
  read-surface client the apps may route through.

Re-checked just before approval: **t2175_6 landed (`6fc7b3972`) and is archived**
during planning. Its work is now the ground truth the children build on, so no
dependency edge on it is needed. Each child's rebase check reads its landed
review-item, case-pointer and `>c` surface. t2037_2's hunks are still
uncommitted.

Rule (memory: shared-file gate before EDIT): children **_2, _3 and _4 depend on
t2037_2**, because they edit `monitor_core.py` and the monitor surfaces it
routes. Each child's first step is a
**rebase check before editing**: re-read the landed versions of the files it
touches, confirm `git diff HEAD -- <files>` is empty for them, and re-derive this
plan's premises from what landed. In particular:
- review items and `case`/raw pointers (t2175_6) must render in the TUI;
- `>c` stays agentic or moves to the TUI (decided in _5);
- every new monitor-side consumer must also work through `status_client`
  (t2037_2).

Children are numbered in dependency order. The sibling auto-dependency chain is
kept: each child depends on the one before it, plus the external gates.

## Children

### Pre-phase (risk mitigations)

1. [sitrep_tui_consumer_table_characterization] Carried by **t2211_2** as its
   first implementation step, before any production edit. Write table-driven
   tests (in `tests/test_sitrep_window.py`, plus a row in
   `tests/test_cleanup_rule_parity.sh`). There is one row per helper-rule
   consumer:
   - discovery / monitor card listing;
   - `match_sitrep_pane` fallback;
   - minimonitor `_find_sibling_pane_id`;
   - `_scan_companion_window`;
   - `aitask_companion_cleanup.sh` job 2;
   - `kill_agent_pane_smart` / `_collapse_window_for`;
   - `agent_freeze._other_real_agents`;
   - the `h` harvest gating.

   Each row is fed a pane stamped `@aitask_sitrep_tui_root=<root>` and asserts
   the required classification: "not an agent" for the listing rows, "real
   occupant" for the retention rows, frozen-first everywhere. Run them before
   editing and record which rows are red; those are exactly the rows the change
   must flip. After the change, all rows are green.

### t2211_1 — Sitrep TUI: read views + launcher
- New package `.aitask-scripts/sitrep_tui/sitrep_tui_app.py`, class
  `SitrepTuiApp(TuiSwitcherMixin, ShortcutsMixin, App)`, with
  `_shortcuts_scope="sitrep_tui"`. Template: the frozenagent TUI
  (`frozenagent/frozenagent_app.py`, its launcher `aitask_frozenagent.sh`,
  `ait:220`, `tests/test_frozenagent_app.py`).
- Launcher: a `tui` verb in `aitask_sitrep.sh` that execs a new
  `aitask_sitrep_tui.sh` (`require_ait_python`, dependency check,
  `ait_warn_if_incapable_terminal`), so the command is `ait sitrep tui [--root P]`.
  Add it to the update-check skip list in `ait`. The store is
  `${AITASK_SITREP_DIR:-.aitask-sitrep}` relative to the cwd, so the TUI runs with
  cwd = `canonical_root` (via `sitrep_cli.root_arg`).
- Main screen: grouped lists Pick now / Next / Waiting, plus Recently done and
  Dismissed behind a toggle. Groups come from `sitrep_todo.SLOTS` and `_slot_of`.
  Each row shows the cid, kind, state, title, outcome and `checked_at` age. The
  situation text per theme sits in a header panel.
- Data: `sitrep_todo.load_todo_for_read(store_dir)` for todo and `parse_qa` for
  `qa.md`. A `FormatError` shows an "store unusable" banner; restore is wired in
  _3.
- Details screen (`GuardedModalScreen`, or a pushed Screen): item fields, outcome
  with its age, and the context map (background, origin, theme, sources,
  related). **Read-only pointer following** in a viewer pane:
  - `task:`, `plan:`, `file:`: read the repo-relative file (re-validated with the
    same rules as `_check_pointer`: no `..`, no absolute paths);
  - `capture:`: the retained `sources/<hex>.txt` lines `#La-Lb`;
  - `commit:`: `git show --stat`;
  - `trail:` / `artifact:`: `aitask_artifact.sh get` +
    `aitask_trail_gather.sh drift`;
  - `url:`: shown, not opened;
  - t2175_6 case / raw pointers.

  All subprocesses run off the event loop with timeouts.
- Q&A browser screen: `QaLog.entries` newest first. Each entry links to the items
  it names, and the items link back.
- Auto-reload: a sha256-keyed `todo.md`/`qa.md` watcher on an interval, using
  `asyncio.to_thread` (the `SitrepNowCounter` pattern in
  `monitor/sitrep_close.py:286`). It re-renders only when a digest changes and
  keeps the selection by cid.
- Markup safety: store strings through `Content(text)` / `markup_literal`, and
  `notify(..., markup=False)`.
- Registration:
  - add the module to `KNOWN_BINDING_SOURCES` (`lib/shortcut_scopes.py`);
  - add a `TUI_REGISTRY` row in `lib/tui_registry.py` with `in_switcher=False`.
    The window is `agent-sitrep`, the switcher's `S` keeps opening the sitrep
    window, and the registry row exists so `TUI_NAMES` and the docs know the TUI.
    Check that adding the name does not make `maybe_spawn_minimonitor` refuse the
    `agent-sitrep` window: it is keyed by window name, and the TUI's pane is not a
    window.
- Tests: `tests/test_sitrep_tui_app.py` (`App.run_test`, a fixture store built
  through the real writer verbs; groups, details, each pointer kind, the Q&A
  links, the reload on a digest change, a hostile-markup title).

### t2211_2 — Window identity + four-way spawn roles
- Stamp: `@aitask_sitrep_tui_root=<canonical root>` (constant in
  `lib/helper_panes.py`, beside `SITREP_ROOT_OPTION`). `spawn_sitrep` sets it
  through `_stamp_or_remove`.
- **Two predicates, not one** (this is the core design point). The sitrep TUI
  pane is
  - **not an agent** for discovery and listing: monitor cards (`_parse_list_panes`
    / `classify_pane`), the `match_sitrep_pane` name+cwd fallback, the
    minimonitor's `_find_sibling_pane_id` (which agent it follows), the `h`
    harvest target, `kill_agent_run_guarded`;
  - **a real occupant** for retention: `aitask_companion_cleanup.sh` job 2 (the
    companion stays while the TUI lives), `kill_agent_pane_smart` /
    `count_other_real_agents` / `_collapse_window_for` (killing the agent never
    collapses the window under the TUI), and `agent_freeze._other_real_agents`.
  - The child's first deliverable is a **consumer table**: every reader of
    `FROZEN_AWARE_PANE_FORMAT`, `pane_is_helper`, `classify_window_panes`,
    `_scan_companion_window` and `_check_auto_close`, plus the cleanup script and
    `test_cleanup_rule_parity.sh`. Each row records the TUI pane's required
    classification and how it reads the stamp. The frozen-first rule is kept in
    every row.
- Agent exit: the agent's pane-died hook runs the cleanup. The TUI is a real
  sibling, so the dead agent pane is killed and the minimonitor stays. The TUI
  then shows "agent not running" (_3). `_check_auto_close` already sees the TUI
  as company, so the companion does not close. Pin that with a test.
- `spawn_sitrep`, under the existing `_sitrep_spawn_lock`, does one lookup that
  returns both roles (`find_sitrep_roles` → agent pane, TUI pane), then:
  - **nothing alive**: new window with the agent, `split-window -v -l 40%` of the
    agent pane running `ait sitrep tui --root R`, stamp both, then (outside the
    lock, as today) the forced minimonitor companion;
  - **agent alive, TUI missing**: split the TUI under the agent and stamp it.
    Status `added_tui`;
  - **TUI alive, agent missing**: split the agent *above* the TUI
    (`split-window -v -b`, via `launch_split_pane`), stamp it, and arm the
    companion cleanup hook. Status `respawned_agent`;
  - **both alive**: `focused` (or `focus_failed`), as today.
  - Never a second TUI or agent per root, including the cross-window case (a TUI
    stamped for R in another window counts).
- **Geometry (the agreed layout).** The companion split must produce a
  **full-height right column** beside both the agent and the TUI. Today
  `_companion_check_and_split` (`lib/agent_launch_utils.py` ~L2725) runs
  `split-window -h -l <w> -t <agent_pane>`. After the TUI split that halves only
  the agent's cell, so the minimonitor would sit top-right and the TUI would span
  the whole bottom.
  - Fix: add a keyword-only `full_height: bool = False` to
    `maybe_spawn_minimonitor` → `_companion_check_and_split`. When true it adds
    tmux's `-f` (`split-window -h -f`: the new pane spans the full window height
    on the right). Only `spawn_sitrep` passes it. Every other companion caller
    keeps today's geometry; pin that with the existing companion tests and one new
    argv assertion.
  - Role splits target the left column only: the TUI is `split-window -v -l 40%
    -t <agent>` and the respawned agent is `split-window -v -b -t <tui>`. Both
    stay in the left column whatever order the companion was created in.
  - On the repair paths (`added_tui`, `respawned_agent`), call
    `maybe_spawn_minimonitor(..., full_height=True)` as well (outside the lock).
    Its existing "companion present" gate makes it a no-op when the minimonitor
    survived, and it restores the column when the minimonitor did not.
- Wire lines (`monitor/sitrep_open.py` and `sitrep_cli.sitrep_open_message`):
  keep `SITREP_SPAWNED:` / `SITREP_FOCUSED:` / `SITREP_FOCUS_FAILED:` /
  `SITREP_REFUSED:` / `SITREP_WARN:`, and add `SITREP_ADDED_TUI:<pane>|<window>`
  and `SITREP_RESPAWNED_AGENT:<pane>|<window>`. The switcher and monitor toasts
  decode them.
- `sitrep_close.py` / `sitrep_harvest.is_sitrep_window` keep skipping the window.
  Check that the `h` gating refuses the TUI pane even though it is in an
  `agent-` window (category AGENT by window name).
- Tests:
  - `tests/test_sitrep_window.py`: matcher rows with a TUI-stamped pane, the
    four-way spawn table with FakeMon, consumer-table parity cases;
  - `tests/test_cleanup_rule_parity.sh`: add the TUI row;
  - `tests/test_sitrep_window_live.sh`: new scenarios for cold start, agent-only
    (adds the TUI), TUI-only (respawns the agent), TUI-only with the companion
    also gone (column restored), both alive (focus), and **race proofs** for the
    new roles, extending the `AITASK_SITREP_SPAWN_PAUSE_FIFO` scenario C so that
    concurrent calls in each starting state leave exactly one of each role.
  - **Assert coordinates, not pane counts**, in every live layout scenario. Read
    `#{pane_id} #{pane_left} #{pane_top} #{pane_width} #{pane_height}
    #{window_width} #{window_height}` and check:
    - agent `left=0, top=0`;
    - TUI `left=0`, `top = agent.top + agent.height + 1`,
      `width = agent.width`;
    - minimonitor `left = agent.width + 1`, `top=0`,
      `height = window_height`;
    - agent height + TUI height + 1 = window height.

    A mutant that drops `-f` must turn the cold-start scenario red.

### t2211_3 — TUI deterministic actions, respawn, launches, board focus
- Harvest + refresh: on mount, and on a key. Run `aitask_sitrep_harvest.sh all
  --root .` then `aitask_sitrep_refresh.sh --root .` in a worker, with a timeout
  ≥ budget + 15 s. Show the result lines in a result panel, reusing the
  `HarvestReport` line parsing in `sitrep_close.py`. While one run is in flight,
  refuse a second. Reload afterwards.
- Dismiss: a confirm dialog with a reason (`--outcome`) runs
  `aitask_sitrep_todo.sh dismiss c<N> --outcome … --expect-rev <rev>`. On
  `STALE:` the TUI reloads, shows that the item changed, and asks again; it never
  retries blind. Exit 3 `LOCK_BUSY` shows a toast and the user may retry.
- Restore: on an unusable store (exit 4 / `FormatError`), a confirm dialog runs
  `restore todo|qa` and shows `RESTORED:` / `no-damaged-copy`.
- Respawn agent: when the role lookup finds no agent, the header shows "agent not
  running" and a key runs `aitask_sitrep.sh open --root R --session S` (the same
  `spawn_sitrep` path), then shows the decoded wire line.
- User-driven launches (allowed for the user acting through the TUI; the sitrep
  agent stays advisory-only):
  - task item → `/aitask-pick <id>`, following `trails_app.action_pick_task`
    (`focus_existing_agent_window`, `build_pick_screen`, `launch_in_tmux`,
    `maybe_spawn_minimonitor`);
  - open in the board → **new** `ait board --focus <id>` (board argv parsing,
    selecting and scrolling the card after load) plus
    `launch_or_focus_board(session, root, task_id)` in `agent_launch_utils.py`,
    modelled on `launch_or_focus_trails` (a pane-option handoff to a running board
    pane, else a new window);
  - push item → show the push command (copyable via `tui_clipboard`), never run
    it.
- Dynamic bindings: `check_action` returns False unless the selected item's kind
  and state fit, and `refresh_bindings()` runs on selection and reload. Every
  action re-checks its precondition (a binding gate is not a guard).
- Tests:
  - `tests/test_sitrep_tui_actions.py` (run_test; STALE re-read, confirm cancel,
    restore, bindings per kind and state, respawn-key wire-line decoding);
  - board `--focus` test (argv parsing, card selected after load, handoff to a
    running board pane).

### t2211_4 — Guarded request delivery into the sitrep agent
The TUI's agentic keys type a request into the sitrep agent pane and submit it.
A live, unfrozen pane is **not** proof it is safe to type into. The agent may be
parked at a confirmation dialog, where Enter answers it. It may be holding the
user's unfinished draft, where Enter submits the draft mixed with our text. Or it
may be working. Delivery therefore has three separately observed phases:
readiness, dispatch, submission.

- **Request table.** `AGENT_REQUESTS` lives in the TUI module and is the single
  source the parity test (post-phase, _5) reads:
  - triage this → `>t c<N>`;
  - ask about → `>q c<N> <text>`, from an input dialog; the text is one line,
    with control characters and newlines refused;
  - write situation → `>w <theme>`;
  - refresh trail → `>tr c<N>`;
  - pick advice → `>p`.
- **Phase 1 — readiness (positive detection; refusal otherwise).** Reuse the
  per-agent detectors in `monitor/review_loop.py`: `shadow_state(raw_text,
  agent)` (L1003), `SHADOW_STATE_DETECTORS`, and the order rationale at ~L469
  (dialog first, `working` outranks `ready`). Do **not** write a second detector.
  - Resolve the agent key (`claude` / `codex` / `opencode`) from the sitrep pane's
    launch agent string.
  - Take two raw tails with `capture_raw_tail` (monitor_core L738, `-e` ANSI
    kept) `COMPOSER_DRAIN_SECONDS`-ish apart. Require `shadow_state ==
    SHADOW_READY` on both and byte-identical tails, which is the
    `shadow_prompt_ready(..., hash_stable)` contract.
  - Also check `query_pane_mode` (L783) shows no copy-mode, and an unreadable mode
    counts as not ready.
  - Refusal mapping, shown to the user and never retried automatically:

    | verdict | refusal |
    |---|---|
    | `SHADOW_DIALOG` | `not_ready:dialog` ("the agent is waiting for an answer") |
    | `SHADOW_BUSY` | `not_ready:draft` ("the agent has unsent input — submit or clear it first") |
    | `SHADOW_WORKING` or an unstable hash | `not_ready:working` |
    | `SHADOW_UNKNOWN`, a failed capture, an agent with no detector | `not_ready:unknown` |
    | pane in a mode | `not_ready:in_mode` |
    | mode unreadable | `not_ready:mode_unreadable` |
- **Phase 2 — dispatch with an observable result** (new
  `TmuxMonitor.dispatch_text_guarded(identity, text, nonce)` in `monitor_core.py`,
  beside `kill_agent_run_guarded`; shares `run_identity_condition` / `all_of`).
  `readback_state` cannot classify a send: it was built for kills
  (`helper_panes.py:247`) and only reports pane present / gone / unknown, and a
  pane that received the text and a pane the guard skipped both remain present.
  `if-shell` success also does not show which branch ran. So:
  - The text **never enters the tmux command parser**. Load it first with
    argv-only `set-buffer -b aitask-sitrep-<nonce> -- <text>`. The guarded branch
    contains only controlled tokens: a validated pane id, a hex nonce, a fixed
    option name.
  - Run `if-shell -F -t <pane> <cond> "paste-buffer -d -b aitask-sitrep-<nonce>
    -t <pane> ; set-option -p -t <pane> @aitask_dispatch_ack <nonce>:sent"
    "delete-buffer -b aitask-sitrep-<nonce> ; set-option -p -t <pane>
    @aitask_dispatch_ack <nonce>:skipped"`.
  - Read back `#{pane_id}\t#{pid}\t#{@aitask_dispatch_ack}` and classify with a
    new pure `dispatch_ack_state(rc, out, pane_id, server_pid, nonce)`:
    - `sent` only for the same server pid, the same pane, and ack ==
      `<nonce>:sent`;
    - `skipped` for `<nonce>:skipped`;
    - anything else, including a different nonce, a failed read or a gone pane,
      is `unknown`, never `sent`.
  - Then unset the ack (`set-option -pu`). On `unknown` / `skipped`, also try
    `delete-buffer` so no named buffer leaks.
  - Add `@aitask_dispatch_ack` to the `@aitask_*` option inventory in
    `aidocs/framework/tmux_gateway.md`.
  - **Measure first:** confirm live that `paste-buffer` of a short single line
    lands as typed composer text for each supported agent. Claude collapses large
    pastes into `[Pasted text …]`. If it does not land as typed text for an
    agent, **stop and report the measurement**. Never fall back to inlining the
    text into the `if-shell` command string, which would hand it to tmux's command
    parser. The replacement design is then decided with the user. Record the
    measurement in the plan either way.
- **Phase 3 — submission, separate from dispatch.**
  - Re-capture and require the request text visible in the composer, and no
    dialog (the `HOLD_PRE_ENTER_DIALOG` / `DISARM_TEXT_NOT_IN_COMPOSER` analogues
    in `review_loop.py` L116-L132).
  - **Pane-mode gate before EVERY Enter, retries included** (t2001, the rule
    `MiniMonitorApp._submit_shadow_prompt` documents at
    `minimonitor_app.py` ~L5475). The user can enter copy-mode after readiness
    or after the paste. `capture-pane` still shows the composer underneath, but
    Enter goes to the mode, where vi copy-mode's copy-pipe-and-cancel clobbers
    the clipboard and exits the mode.
    - Read `query_pane_mode` as the **last await before each Enter**. Active or
      unreadable → no Enter; the result is
      `typed_not_submitted:in_mode` / `typed_not_submitted:mode_unreadable`, and
      the request stays typed in the composer for the user.
    - Belt-and-braces: both guarded dispatches (paste and Enter) also carry
      `#{==:#{pane_in_mode},0}` as an extra conjunct of their `if-shell -F`
      condition. The server then re-checks the mode atomically at dispatch time,
      closing the gap between the Python read and the key. On a `skipped` ack,
      one read of `#{pane_in_mode}` plus the run identity labels the reason
      (`in_mode` vs `identity_changed`).
  - Then a second guarded dispatch of `send-keys -t <pane> Enter` with its own
    nonce ack.
  - Then verify by re-capture that the composer is empty or the agent began
    working. Retries are bounded by `SHADOW_SUBMIT_RETRIES`, and each retry
    passes the mode gate again.
  - Model the sequence on `MiniMonitorApp._submit_shadow_prompt`
    (`monitor/minimonitor_app.py` ~L5433). Do **not** refactor the minimonitor
    path in this child. If extracting a shared helper looks worthwhile, note it in
    the parent's `## Notes for sibling tasks` / a follow-up with file + line
    ranges.
- **Result vocabulary**, shown in a markup-safe toast and the TUI's result panel:

  | result | meaning |
  |---|---|
  | `submitted` | dispatched, Enter acked, submit verified |
  | `typed_not_submitted[:in_mode\|:mode_unreadable]` | text is in the composer, but Enter was withheld (pane in a mode or mode unreadable), skipped or unconfirmed; the user is told the text is waiting there |
  | `refused:<reason>` | phase-1 reasons, or `identity_changed` / `no_agent` / `frozen` |
  | `skipped` | the identity guard declined at dispatch |
  | `unknown` | the outcome could not be verified; the user is told to look at the agent pane, never "sent" |

- Identity: the agent is re-resolved through `find_sitrep_roles` (from _2) and
  `RunIdentity` is re-read on **every** request. It is never cached across user
  actions. Only the pane stamped for this root, live, unfrozen and not dead is a
  target.
- Contextual bindings: the request keys appear only when the selected item fits
  (e.g. `>tr` only on trail-watch items) **and** an agent role is resolved. The
  action re-checks both.
- Tests:
  - `tests/test_sitrep_request_delivery.py`, pure / FakeMon: the refusal table per
    verdict, using the review_loop fixture captures for dialog, draft, working
    and unknown; `dispatch_ack_state` for each field mismatch; the phase order;
    the identity re-read per request.
  - `tests/test_sitrep_request_delivery_live.sh`, isolated tmux modelled on
    `tests/test_kill_agent_run_guarded.sh`, with a scripted fake agent pane that
    renders a Claude-shaped composer, dialog and draft from fixtures. Cases:
    - (a) a ready pane gives `submitted`, and the pane received exactly the
      request text + Enter;
    - (b) a dialog shown gives `refused:not_ready:dialog` and the pane received
      nothing;
    - (c) a draft present gives `refused:not_ready:draft`, nothing sent, the draft
      intact;
    - (d) a `respawn-pane -k` between readiness and dispatch gives `skipped` while
      the pane stays alive, and the buffer is deleted;
    - (e) a frozen stamp gives refused/skipped;
    - (f) a text with `;`, quotes, `#{…}` and `$(…)` arrives literally, with no
      tmux command executed;
    - (g) a pane that answers the dispatch but never empties the composer gives
      `typed_not_submitted`;
    - (h) copy-mode entered **after** the text arrives (driven from the test via
      the delivery's pause seam) gives `typed_not_submitted:in_mode`. No Enter
      reaches the pane: the composer still holds the request, the pane is still
      in copy-mode, and a sentinel buffer/clipboard is unchanged;
    - (i) copy-mode entered between a first unconfirmed Enter and its retry
      gives no retry Enter.
  - **A mutant per guard:**
    - drop the identity condition, and (d) goes red;
    - drop the readiness check, and (b)/(c) go red;
    - classify ack-less as `sent`, and (d) goes red;
    - put the text inline in the if-shell, and (f) goes red;
    - drop the Python pre-Enter mode read **and** the `#{pane_in_mode}` conjunct,
      and (h)/(i) go red;
    - with only the conjunct removed, (h) stays green through the Python gate.
      The test records that both layers exist, and the pure test asserts the
      conjunct is in the built condition.

### t2211_5 — Slim the sitrep skill
- `.claude/skills/aitask-sitrep/SKILL.md.j2`:
  - Step 0 becomes the root check, then `list` + `read todo`, then the greeting.
    The startup harvest/refresh is removed (the TUI owns it).
  - On exit 4, point to the TUI's restore.
  - Drop `>s`, `>r` and `>x`, or reduce each to one line that says "use the sitrep
    TUI".
  - Keep `>t`, `>w`, `>q`, `>tr`, `>p`, `>?`, and `>c` (as t2175_6 landed it),
    the writer rules and the advisory guardrail.
  - Add "Requests from the sitrep TUI": the same `>` codes carrying item ids
    (`>t c12`, `>q c12 <text>`, `>w <theme>`, `>tr c12`). These requests carry no
    more authority than typed input, and the agent still confirms before writing.
  - The guardrail states that the TUI may type into the agent, never the reverse.
- Regenerate the three goldens (the command is in
  `aidocs/framework/skill_authoring_conventions.md` "Regenerate goldens").
- Update `tests/test_skill_render_aitask_sitrep.sh` Test 2s `SHORTCODES` and
  `tests/test_sitrep_skill_contract.sh`:
  - L190 refresh assertion;
  - the `dismiss` example run moves to a TUI-side writer test or stays as a
    documented example;
  - the `'Only when the user asks for it'` string.
- Run `./.aitask-scripts/aitask_skill_verify.sh`.
- Allow-lists: unchanged for the TUI's helpers, which are Python-only callers
  (extension_points L394-403). Check contract test (a) against the slimmed skill.
- Send a note to t2199 (`./ait note 2199 --from 2211_5`) describing the slimmed
  skill surface. Suggest the codex/opencode port pick up the new menu.

### t2211_6 — Docs
- `aidocs/framework/sitrep.md`:
  - "The sitrep window": the roles, the TUI stamp, the two-predicate table, the
    four-way spawn, the new wire lines, agent-exit behaviour;
  - a new "The sitrep TUI" section;
  - "The skill" (slim menu, TUI requests).
- Website:
  - `website/content/docs/workflows/sitrep.md` (opening, what starts, list,
    shortcodes table, dismissing, restore);
  - `website/content/docs/skills/aitask-sitrep.md` (capabilities table; "What it
    never does" keeps "types into another agent's pane" and adds that the TUI
    types into the sitrep agent at the user's request);
  - new `website/content/docs/tuis/sitrep/` (`_index.md`, `how-to.md`,
    `reference.md` — keys, groups, pointers, the request-delivery refusals and
    results from _4 in user terms), modelled on `tuis/trails/`;
  - a bullet in `tuis/_index.md`;
  - the board `--focus` mention in the board reference.
- Follow `aidocs/framework/documentation_conventions.md` (current state only).
- Run `cd website && hugo build --gc --minify && python3 check_links.py --build`,
  and offer `check_link_relevance.py`.

### Post-phase (risk mitigations)

1. [sitrep_tui_skill_request_parity] Carried by **t2211_5**. Add a test (in
   `tests/test_sitrep_skill_contract.sh`, or a small Python test it calls) that
   imports the TUI's `AGENT_REQUESTS` table. It asserts that every request
   template starts with a `>` code documented in the rendered skill's "Requests
   from the sitrep TUI" section, and that the code's own `### \`>x\`` capability
   heading exists. Add a mutant (an unknown code in a copy of the table) that must
   turn the test red.

## Verification (parent level)

Every child carries its own tests. The parent-level end-to-end check, which is
offered as an aggregate manual-verification sibling, covers the following:
- `ait sitrep` cold start gives agent + TUI below + minimonitor; a second call
  focuses;
- close the agent: the TUI shows "agent not running", the minimonitor stays, and
  the respawn key or `ait sitrep` restores the agent;
- kill the TUI, then `ait sitrep` adds it back;
- the monitor never lists the TUI pane;
- the TUI lists, details, follows pointers, browses Q&A, harvests/refreshes, and
  dismisses with confirm;
- `>t c<N>` is submitted to an idle agent. With a permission dialog open, or a
  half-typed draft in the agent's composer, the TUI refuses and the dialog or
  draft is untouched;
- the minimonitor is a full-height right column beside both the agent and the
  TUI, after cold start and after each repair;
- `ait board --focus <id>` focuses the card.

Step 9 (Post-Implementation): each child archives itself. The parent archives
when the last child completes.

## Risk

### Code-health risk: medium
- Teaching one pane to be "not an agent" for listing and "a real occupant" for
  retention touches every consumer of the helper rule (discovery, matcher,
  minimonitor sibling-follow, companion cleanup script, smart kill, freeze). A
  missed consumer silently misclassifies the TUI (listed as an agent, followed by
  the minimonitor, or collapsing the window on agent exit) · severity: medium ·
  → mitigation: inline pre-phase sitrep_tui_consumer_table_characterization
- New `dispatch_text_guarded` is a second guarded-dispatch primitive beside
  `kill_agent_run_guarded`. It must share `run_identity_condition` / `all_of`
  rather than fork them, and it needs its own nonce-ack classifier, because
  `readback_state` only reports presence · severity: low · → mitigation: none
  (design requirement in t2211_4, with a mutant per guard)
- Typing into a live agent that is at a dialog, holding a draft or working would
  answer the dialog or submit mixed text. Positive readiness detection
  (`review_loop.shadow_state`) is reused and every non-ready verdict refuses ·
  severity: medium · → mitigation: none (design requirement in t2211_4,
  live cases b/c/g with mutants)

### Goal-achievement risk: medium
- The TUI's request strings (_4) and the skill's documented `>` codes (_5) are
  written in different children and can drift. The TUI would then type requests
  the agent does not recognise · severity: medium · → mitigation: inline
  post-phase sitrep_tui_skill_request_parity
- The in-flight t2175_6 / t2037_2 may land a different store and skill surface
  than the one this plan was written against (review items, case pointers, `>c`,
  status_client routing). The children gate on them and re-derive premises ·
  severity: low · → mitigation: none (depends edges + rebase-check first step)

### Planned mitigations
- timing: pre-phase | name: sitrep_tui_consumer_table_characterization | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — helper-rule consumer misclassification | desc: table-driven tests of every helper-rule consumer against a TUI-stamped pane, written red-first as t2211_2's first step
- timing: post-phase | name: sitrep_tui_skill_request_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — TUI request strings vs skill codes drift | desc: test that every AGENT_REQUESTS template uses a > code the rendered skill documents, with a mutant
