# Sitrep: the per-repo todo steward

Sitrep keeps **one persisted todo list per repository** so finished or frozen
agent windows can be closed without losing their follow-up information (follow-up
tasks, "push main", a trail's next wave). It is advisory-only: nothing in it ever
picks a task, pushes, commits, edits code, or types into another pane.

User-facing pages: `website/content/docs/workflows/sitrep.md` and
`website/content/docs/skills/aitask-sitrep.md`.

## Components

| Piece | Entry point | Core | Role |
|---|---|---|---|
| store + writer | `.aitask-scripts/aitask_sitrep_todo.sh` | `lib/sitrep_todo.py` | the ONLY writer of `.aitask-sitrep/` (mutex, atomic writes, rolling backup, CAS by store-wide rev) |
| harvest | `.aitask-scripts/aitask_sitrep_harvest.sh` | `lib/sitrep_harvest.py` | finished agents' wrap-ups → triage, task and trail items + retained passages; receipts gate `drop` / `purge` |
| refresh | `.aitask-scripts/aitask_sitrep_refresh.sh` | `lib/sitrep_refresh.py` | deterministic re-check of task, push and trail items (Part 1 only) |
| window + facts | `ait sitrep` → `.aitask-scripts/aitask_sitrep.sh` | `open`: `monitor/sitrep_open.py` → `monitor/monitor_core.py` `spawn_sitrep`; `root` / `triage`: `lib/sitrep_cli.py` (stdlib; lib/ never imports the monitor package) | opens the sitrep agent in its own window; read-only facts for the skill |
| agent | `/aitask-sitrep` | `.claude/skills/aitask-sitrep/SKILL.md.j2` | triage, situation text, answers from the sources, dismissals, Q&A log |
| monitor surface | `h` / `S` in `ait monitor` and `ait minimonitor`, `S` in the TUI switcher | `monitor/sitrep_close.py` (`SitrepCloseMixin`) | harvest-and-close, open the sitrep window, the `sitrep N now` count; the maintenance `harvest all` pass |

Each helper's header is its wire contract (verbs, result lines, exit codes); the
store's consumer contract is the fixture `tests/fixtures/sitrep/`. The monitor's
maintenance tick runs `harvest all` and then refresh (`monitor/monitor_shared.py`
`_maybe_harvest_sitrep`, `_maybe_refresh_sitrep`).

## The store

`<main worktree>/.aitask-sitrep/`, gitignored, never committed. `todo.md` holds
Part 1 (situation text per theme; items grouped Pick now / Next / Waiting /
Recently done / Dismissed) and Part 2 (one context entry per item: a **map, not a
summary** — background, origin, source pointers, related items). `qa.md` is the
dated Q&A log. `sources/<hex>.txt` are retained, content-addressed passages, so a
pointer survives the frozen capture being dropped.

One store per repository: every helper maps its root to the main worktree
(`sitrep_harvest.canonical_root`; a linked or removed `aiwork/<task>` worktree
maps to the repository that owns it). Harvest and refresh always write
`<canonical root>/.aitask-sitrep` and ignore an outer `AITASK_SITREP_DIR`; only
the writer honours that variable (relative to its cwd), so the skill runs from
the main worktree root (`ait sitrep root` checks it).

## The sitrep window

`ait sitrep` (default verb `open`) focuses the repository's sitrep agent or
launches it. `monitor_core.spawn_sitrep(monitor, target_root=, session=,
select_window=, agent_string=)` is the one implementation. The TUIs' `S` key
runs it through the CLI, `ait sitrep open --root <r> --session <s>`, naming the
selected agent's (or switcher session's) session; `--session` must name an
existing session (exact `has-session -t =<s>`), else `SITREP_REFUSED:no_session`.
It returns `SitrepSpawn(status, pane, window, detail)` with status
`spawned`, `focused`, `focus_failed` (a sitrep exists but switching to it failed
— reported, never claimed as focused; `--no-select` / `select_window=False`
reuses it without switching) or `refused`. `--root` is validated once, inside the
Python parsers (`sitrep_cli.root_arg`: empty or a `..` segment → exit 2, every
spelling, abbreviations disabled).

- **Placement.** Its own window `agent-sitrep` (`-<n>` when the session already
  holds that name; `SITREP_WINDOW_RE` in `lib/sitrep_harvest.py`), cwd = the
  canonical root, plus a minimonitor companion
  (`maybe_spawn_minimonitor(..., agent_pane=, explicit=True,
  force_companion=True)`): the sitrep window always gets one, whatever
  `tmux.minimonitor.auto_spawn` or `companion_window_prefixes` say (the
  occupancy, pane-count and lock gates still apply). The `agent-` prefix keeps
  it a normal agent for the monitor.
- **Identity.** The agent pane is stamped `@aitask_sitrep_root=<canonical root>`
  (`lib/helper_panes.py` `SITREP_ROOT_OPTION`). It is **not** a helper marker and
  never joins `BOUND_HELPER_TARGET_OPTIONS`: the pane must stay in agent lists. A
  pane that cannot be stamped is removed (`_stamp_or_remove`).
- **One per root — the live lookup** (`find_sitrep_pane_status` /
  `match_sitrep_pane`):
  - a query that cannot be answered **refuses** (`lookup_failed`), never reads
    as "none";
  - frozen and dead panes never match;
  - helper panes never match, by the shared `pane_is_helper` rule (the one
    `classify_window_panes` applies): the sitrep window's own minimonitor
    companion has the same window and cwd and no stamp, and must not pass for
    the agent — also when the agent beside it is frozen;
  - a pane stamped for the root wins over the **name+cwd fallback** (an unstamped
    pane in a sitrep-named window whose cwd maps to the root), in two passes so
    row order never decides. The fallback exists because a restore into a NEW
    window recreates the pane without custom options; a same-pane restore keeps
    the stamp.
- **Races.** Lookup, launch and stamp run under a per-server `flock` beside the
  tmux socket (`_sitrep_spawn_lock`, the `_companion_spawn_lock` shape), so two
  concurrent `ait sitrep` calls leave one window. Not held → `lock_busy`. The
  test seam `AITASK_SITREP_SPAWN_PAUSE_FIFO` (`sitrep_harvest.spawn_test_pause`,
  point `spawn:after_lookup`) holds a spawn inside the lock, so the live test
  proves a second spawn waits rather than racing it.
- **Known gaps, by design.** A frozen sitrep does not block a new spawn (frozen
  panes are never live identity), and `/aitask-sitrep` typed into an arbitrary
  agent pane is unstamped. At worst two stewards share one locked, CAS-guarded
  store.

All tmux goes through the gateways (`aidocs/framework/tmux_gateway.md`).

## The agent never harvests itself

Harvest skips any session record whose window matches `SITREP_WINDOW_RE`:
`HARVEST_NONE:<id>|sitrep_agent`, with a receipt so `drop` and `purge` stay
unblocked. The sitrep screen only echoes the store (banners it is triaging, trail
handles it reports), so harvesting it would feed the store back into itself. The
match is the window name, so a hand-renamed sitrep window is harvested normally —
at worst duplicate, linked triage items, never lost ones.

## The monitor surface

`monitor/sitrep_close.py` (`SitrepCloseMixin`, mixed into both apps) owns `h`
and `S`; the TUI switcher's `S` lives in `lib/tui_switcher.py` and shares only
the result wording (`sitrep_cli.sitrep_open_message` — lib/ never imports the
monitor package).

**`h` — harvest-and-close.** The order is the contract: capture first, show what
was captured, then offer the close.

- **Target.** The full monitor's focused card or the minimonitor's followed
  agent — AGENT cards only (`_current_agent_snapshot` can return a TUI or shell
  card, which `_kill_target_state` would call `live`). `unverified` state or an
  unknown project root (`_strict_root_for_snap`) stops before anything runs.
- **Harvest.** A frozen agent: `harvest record <id> --force` (`--force`
  because the detached post-freeze harvest has usually written the receipt
  already, and a short-circuit prints no item lines). A live agent: one gateway
  `capture-pane -p -J -S -50000` (the freeze default depth), piped into
  `harvest capture --root --agent --task --operation`. A live
  `agent-sitrep[-n]` window is never captured or harvested (`capture` does not
  consult the window name); its report is `skipped`, which is ok.
- **Report.** `parse_harvest_output` reads the helper's lines; ok only when the
  exit is 0 AND the last final line is `HARVESTED` / `HARVEST_NONE`. Titles come
  from a lock-free store read (`item_titles`, display only).
- **Dialog.** `HarvestResultDialog` (a `GuardedModalScreen`, its own CSS, plain
  Content for every harvested string). A failed report renders only **Close** —
  no affirmative button — and the confirm callback re-checks `report.ok`.
- **Run identity.** A pane id is a container: a freeze or restore respawns
  another process into it. `RunIdentity(pane_id, pane_pid, server #{pid},
  @aitask_frozen)` is read before and after the harvest (a change fails the
  report). At confirm: a frozen close requires the snapshot's record AND the
  live `@aitask_frozen` option to still name the harvested record, then
  `_drop_frozen` (the leased `aitask_frozen.sh drop`, via `run-shell -b`, which
  harvests again under its lease); a live close re-reads `_kill_target_state`,
  then `TmuxMonitor.kill_agent_run_guarded` — ONE `if-shell -F` gated on
  unfrozen + the bound `pane_pid` + the bound server pid, then a read-back:
  `killed` / `changed` (pane still there: refused, "press h again") /
  `unknown` (never read as gone). **Pane only, never the window:** the
  condition is evaluated in the target pane's context, so nothing at dispatch
  can prove the window's other occupants — a single `swap-pane` (or a pane
  moved in) would hand a `kill-window` an unrelated, unharvested agent under an
  unchanged window id and pane count. The killed agent's bound helpers go with
  the guarded sweep, and a companion minimonitor closes itself once it is
  verifiably alone (`_check_auto_close`) — the "kill the companion only, never
  the window" rule. The condition grammar is `helper_panes.all_of`, shared with
  the helper sweep.
- **Runner.** `run_owned_group` (`AgentMarksMixin._run_sitrep_harvest`): its own
  process group, killed as a group on timeout AND on cancellation (Textual
  cancels workers at app exit; `wait_for` does not touch the child), the
  cancellation then re-raised. `_run_marks_cmd` would kill only the wrapper,
  leaving the Python child holding the store mutex.

**Maintenance.** `_maybe_harvest_sitrep` runs one global `harvest all` per pass
(`_MARKS_PURGE_INTERVAL`, startup grace) BEFORE `_maybe_refresh_sitrep`, so a
pass refreshes what it harvested, and kept records (`KEPT:…|unharvested_text`)
become droppable and purgeable. Failures are swallowed; the next pass retries.

**Indicator.** The full monitor's session bar shows `sitrep N now` — open items
in the Pick-now group of its own repository's store (`SitrepNowCounter`, read
off the pump with `asyncio.to_thread`, recounted only when the sha256 of
`todo.md` changed). No store, an unreadable one, or zero → no term. The
minimonitor has none (its session bar is hidden by default).

**`S`.** The selected agent's root and session, else the app's own; the switcher
uses its selected session. Result lines map to a toast; nothing is claimed for
`SITREP_FOCUS_FAILED` or a refusal.

## The skill

`/aitask-sitrep` (profile-aware stub + `SKILL.md.j2`, resolver key `sitrep`).
On start: `ait sitrep root`, `harvest all --root .`, `refresh --root .`, then
`list` / `read todo`, then a greeting built from its Capabilities section.

- **Writes only through writer verbs** (`add`, `set-state`, `dismiss`,
  `situation`, `upsert-context`, `qa`; `restore` on the user's yes), with
  `--expect-rev` on every write to an existing item; `STALE:` means re-read,
  never retry blind.
- **Triage** turns each open triage question (one per harvested wrap-up run) into
  agent-derived action/watch items after ONE confirmation for the whole batch,
  then closes the question (`set-state … done --outcome "triaged: …"`). The
  mechanical facts come from `ait sitrep triage c<N>` (helpers report evidence;
  the agent judges): the passage pointer, the identity-key files, the copied
  task/plan/commit pointers, which trail handles a **watch** already covers
  (`TRAIL_WATCHED` / `TRAIL_UNWATCHED` — the question itself and non-watch items
  never count), and items an earlier triage of the same question already wrote.
  The skill reads the whole batch with `ait sitrep triage --open`, which ends
  with one `BATCH_TRAIL_UNWATCHED:<handle>|c<a>,c<b>` line per uncovered trail:
  every item is read before anything is written, so two pending wrap-ups naming
  one trail must be coalesced there into ONE watch related to both (empty-ref
  items have no writer-side dedup).
- **Trail watches** carry exactly one `trail:` source in their own context:
  harvest records in-passage handles only on the triage question, and refresh
  follows only a watch with exactly one `trail:` source.
- **Push reminders** use `--ref push:<branch>@<sha>` so refresh can mark them
  done when the commit reaches the push destination.
- **Answers come from the sources** through the context pointers, never from a
  remembered summary; a `checked_at` older than an hour is called out. Every Q&A
  goes to `qa.md`.
- **Trails and picks** are reported and offered, never acted on: a stale trail
  is refreshed only by running `/aitask-trail --refresh` on the user's yes;
  suggestions come from `/aitask-backlog-roadmap --show`, never a ranking of its
  own; it never picks a task.

## Code agents

The skill renders for every agent (the stubs exist in `.agents/` and
`.opencode/`; the template has no agent gate), but the `sitrep` codeagent
operation is **Claude Code only**: `aitask_codeagent.sh` refuses it for other
agents before composing anything (the `explore-relay` precedent), and
`tests/test_codeagent_op_wiring.sh` exempts it. The codex and opencode ports lift
that gate after verifying the skill's tool use and nested skill calls there.
Default model: `defaults.sitrep` in `codeagent_config.json`.

## Permissions

Every helper the skill calls is on the five code-agent allow-lists
(`aidocs/framework/aitasks_extension_points.md`, "Adding a new helper script"):
`aitask_sitrep_todo.sh`, `aitask_sitrep_harvest.sh`, `aitask_sitrep_refresh.sh`,
`aitask_sitrep.sh`, plus the trail readers `aitask_artifact.sh` and
`aitask_trail_gather.sh`. `tests/test_sitrep_skill_contract.sh` checks that set
against the rendered skill.

## Tests

| Test | Covers |
|---|---|
| `tests/test_sitrep_todo.sh`, `tests/test_sitrep_todo_format.py` | writer, format, recovery |
| `tests/test_sitrep_harvest.sh`, `tests/test_sitrep_harvest.py` | harvest, receipts, the drop/purge gates, the self-harvest skip |
| `tests/test_sitrep_refresh.sh`, `tests/test_sitrep_refresh.py`, `tests/test_monitor_sitrep_refresh.py` | refresh and its monitor tick |
| `tests/test_sitrep_window.py` | lookup matcher, spawn decisions, the CLI (mocks) |
| `tests/test_sitrep_window_live.sh` | the spawn against a private tmux server |
| `tests/test_skill_render_aitask_sitrep.sh` | the skill's render, goldens, stubs |
| `tests/test_sitrep_skill_contract.sh` | the skill's documented commands against the real helpers |
| `tests/test_monitor_sitrep_harvest_close.py` | `h` / `S`: report parsing, the owned-group runner (timeout and cancel), target and sitrep-window guards, run identity, confirm callback, maintenance order, the count, the dialog, the real key presses, the switcher `S` |
| `tests/test_kill_agent_run_guarded.sh` | the guarded run kill against a private tmux server (respawned / frozen pane refused, always pane-only: the last agent's window and companion stay, a pane moved into another agent's window and a helper swapped for an unrelated agent leave that agent alive) |
| `tests/test_monitor_harvest_close_live.sh` | `h` end to end against a private tmux server: real gateway capture → real `harvest capture` → store items → guarded close of the pane only (window and companion stay), on both tmux routes; a failed harvest keeps the pane; `agent-sitrep` is never captured; a respawn after the harvest is refused. Opt-in: refuses inside tmux or with `-L ait` alive |
