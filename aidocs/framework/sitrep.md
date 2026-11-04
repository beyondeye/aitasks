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

Each helper's header is its wire contract (verbs, result lines, exit codes); the
store's consumer contract is the fixture `tests/fixtures/sitrep/`. The monitor's
maintenance tick runs refresh (`monitor/monitor_shared.py`
`_maybe_refresh_sitrep`).

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
select_window=, agent_string=)` is the one implementation; t2175_5's TUI key
calls it too. It returns `SitrepSpawn(status, pane, window, detail)` with status
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
