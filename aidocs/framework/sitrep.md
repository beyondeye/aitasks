# Sitrep: the per-repo todo steward

Sitrep keeps **one persisted todo list per repository** so finished or frozen
agent windows can be closed without losing their follow-up information (follow-up
tasks, "push main", a trail's next wave). It is advisory-only: the sitrep agent
never picks a task, pushes, commits, edits code, or types into another pane. The
one pane anything types into is the sitrep agent's own, and only from the sitrep
TUI when the user presses a request key (`t` `a` `w` `T` `n`). That delivery is
guarded: it refuses a busy or moded agent, uses an identity-checked, acked paste,
and proves the composer before every Enter
(`.aitask-scripts/monitor/agent_request_delivery.py`).

User-facing pages: `website/content/docs/workflows/sitrep.md`,
`website/content/docs/skills/aitask-sitrep.md` and the TUI's
`website/content/docs/tuis/sitrep/` (`_index`, `how-to`, `reference`).

## Components

| Piece | Entry point | Core | Role |
|---|---|---|---|
| store + writer | `.aitask-scripts/aitask_sitrep_todo.sh` | `lib/sitrep_todo.py` | the ONLY writer of `.aitask-sitrep/` (mutex, atomic writes, rolling backup, CAS by store-wide rev) |
| harvest | `.aitask-scripts/aitask_sitrep_harvest.sh` | `lib/sitrep_harvest.py` | finished agents' wrap-ups → triage, task and trail items + retained passages; the confidence check; receipts gate `drop` / `purge` |
| review corpus | `aitask_sitrep_harvest.sh case` (= `ait sitrep case`) | `lib/sitrep_corpus.py` | uncertain output kept verbatim with diagnostics and one review item; list / show / read / review / replay / export |
| refresh | `.aitask-scripts/aitask_sitrep_refresh.sh` | `lib/sitrep_refresh.py` | deterministic re-check of task, push and trail items (Part 1 only) |
| window + facts | `ait sitrep` → `.aitask-scripts/aitask_sitrep.sh` | `open`: `monitor/sitrep_open.py` → `monitor/monitor_core.py` `spawn_sitrep`; `root` / `triage`: `lib/sitrep_cli.py` (stdlib; lib/ never imports the monitor package) | opens the sitrep agent in its own window; read-only facts for the skill |
| TUI | `ait sitrep tui` → `.aitask-scripts/aitask_sitrep_tui.sh` | `sitrep_tui/` (`sitrep_tui_app.py`, `_model`, `_widgets`, `_actions`, `_requests`, `_trails`); delivery in `monitor/agent_request_delivery.py` | the list's read views, the deterministic actions (harvest + refresh, dismiss, restore, pick, board / trails jumps, push command), the guarded requests into the agent |
| agent | `/aitask-sitrep` | `.claude/skills/aitask-sitrep/SKILL.md.j2` | triage, situation text, trail reports, pick advice, answers from the sources, Q&A log; handles the requests the TUI types |
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
pointer survives the frozen capture being dropped. `raw/<hex>.txt` are whole
raw inputs of review cases (below), kept byte for byte; `cases/<hex>.txt` are
the trusted review-case records.

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
It returns `SitrepSpawn(status, pane, window, detail, tui)` with status
`spawned`, `added_tui`, `respawned_agent`, `focused`, `focus_failed` (a sitrep
exists but switching to it failed — reported, never claimed as focused;
`--no-select` / `select_window=False` reuses it without switching) or `refused`.
`pane` is always the agent's pane; `detail` is a comma-joined warning list
(`companion_not_spawned`, `tui_not_spawned:<why>`, `tui_moved`, `tui_not_moved`,
`focus_failed`, `focus_not_restored`), one `SITREP_WARN:` line each. `--root` is
validated once, inside the Python parsers (`sitrep_cli.root_arg`: empty or a `..`
segment → exit 2, every spelling, abbreviations disabled).

- **Placement.** Its own window `agent-sitrep` (`-<n>` when the session already
  holds that name; `SITREP_WINDOW_RE` in `lib/sitrep_harvest.py`), cwd = the
  canonical root, holding two **roles** and a companion:

  ```
  +----------------+------+
  | sitrep agent   | mini |
  +----------------+ mon  |
  | sitrep TUI 40% |      |
  +----------------+------+
  ```

  The TUI (`ait sitrep tui --root <root>`, `monitor_core.sitrep_tui_command`) is
  a detached `split-window -v -l 40%` under the agent; the minimonitor is
  `maybe_spawn_minimonitor(..., agent_pane=, explicit=True,
  force_companion=True, full_height=True)` — tmux `-f`, so it is a full-height
  right column rather than a split of the agent's cell. The sitrep window always
  gets one, whatever `tmux.minimonitor.auto_spawn` or
  `companion_window_prefixes` say (the occupancy, pane-count and lock gates
  still apply). The `agent-` prefix keeps the agent a normal agent for the
  monitor.
- **Four-way spawn** (`find_sitrep_roles` → `(ok, agent, tui)`, one
  `list-panes -a` read; a TUI stamped for the root counts in ANY window):

  | agent | TUI | action | status |
  |---|---|---|---|
  | live | live | focus the agent | `focused` / `focus_failed` |
  | — | — | new window: agent, then the TUI (a TUI failure is a warning) | `spawned` |
  | live | — | split the TUI under the agent | `added_tui` |
  | — | live, agent slot empty | `split-window -v -b -l 60%` above the TUI | `respawned_agent` |
  | — | live, slot occupied | new window with the agent; `join-pane -d` moves the TUI under it | `spawned` + `tui_moved` |

  The CLI prints one line per status (`aitask_sitrep.sh` header):
  `SITREP_SPAWNED:<pane>|<session>:<window>`, `SITREP_ADDED_TUI:…`,
  `SITREP_RESPAWNED_AGENT:…`, `SITREP_FOCUSED:<pane>` (exit 0, followed by 0+
  `SITREP_WARN:<item>` lines), `SITREP_FOCUS_FAILED:<pane>` and
  `SITREP_REFUSED:<reason>` (exit 1). `<pane>` is always the agent's.

  The agent slot is empty when the TUI's window holds nothing but the TUI and
  helpers (`classify_window_panes`). A **frozen** sitrep agent is an occupant
  (frozen first), and so are a dead pane or a user's shell: the replacement is
  never split over them. The frozen session stays untouched in its window with
  its companion, the one TUI moves to the new agent, and each window then lists
  exactly one agent pane — so each window's minimonitor follows the right one.
  A respawned agent gets the companion cleanup hook (`window_companion_pane`).
- **Focus.** Every role split is detached (`TmuxLaunchConfig.split_detached`,
  tmux `-d`). On `added_tui` / `respawned_agent` the window's active pane is
  read first; with `select_window` the client then switches to the agent,
  without it the original active pane is reselected if the companion spawn moved
  it (`focus_not_restored` when that fails).
- **Agent exit.** The TUI is a real sibling for the cleanup hook, so a dead
  agent pane is removed and the TUI and minimonitor stay (the minimonitor is
  not alone, so it does not auto-close). The next `ait sitrep` respawns the agent
  above the TUI.
- **Identity.** The agent pane is stamped `@aitask_sitrep_root=<canonical root>`
  (`lib/helper_panes.py` `SITREP_ROOT_OPTION`). It is **not** a helper marker and
  never joins `BOUND_HELPER_TARGET_OPTIONS`: the pane must stay in agent lists. A
  pane that cannot be stamped is removed (`_stamp_or_remove`).
- **The TUI's two predicates.** The TUI pane is stamped
  `@aitask_sitrep_tui_root=<canonical root>` (`SITREP_TUI_ROOT_OPTION`). It is
  **not an agent** for anything that lists agents — discovery drops it (like a
  scratchpad), the agent matcher skips it in both passes, the minimonitor never
  follows it (`WindowPane.is_sitrep_tui`), and `h` refuses it at the identity
  read (`RunIdentity.sitrep_tui_root` → `not_an_agent`, which also covers a
  status server older than this rule). It is **a real occupant** for retention —
  `is_helper` is unchanged, so the cleanup hook, smart kill / collapse, the freeze
  coordinator, the companion occupancy scan and auto-close all count it. Frozen
  first on every read (`is_sitrep_tui_pane`).
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
- **Races.** Lookup, launches, the TUI move and both stamps run under a
  per-server `flock` beside the tmux socket (`_sitrep_spawn_lock`, the
  `_companion_spawn_lock` shape), so concurrent `ait sitrep` calls leave one
  agent and one TUI per root, whatever the starting state. Not held → `lock_busy`. The
  test seam `AITASK_SITREP_SPAWN_PAUSE_FIFO` (`sitrep_harvest.spawn_test_pause`,
  point `spawn:after_lookup`) holds a spawn inside the lock, so the live test
  proves a second spawn waits rather than racing it.
- **The TUI itself** — views, actions and requests: see *The sitrep TUI*
  below.
- **Known gaps, by design.** A frozen sitrep does not block a new spawn (frozen
  panes are never live identity), and `/aitask-sitrep` typed into an arbitrary
  agent pane is unstamped. At worst two stewards share one locked, CAS-guarded
  store.

All tmux goes through the gateways (`aidocs/framework/tmux_gateway.md`).

## The sitrep TUI

`ait sitrep tui [--root <path>]` (`aitask_sitrep_tui.sh` checks `textual` /
`pyyaml`, then runs `sitrep_tui/sitrep_tui_app.py`). `--root` goes through
`sitrep_cli.root_arg` (empty or a `..` segment → exit 2); an unresolvable root
prints `ROOT_FAILED:<why>` and exits 1. The store is
`<canonical root>/.aitask-sitrep`, the one every read-side consumer uses. The
TUI does the deterministic work itself; the agent keeps the agentic work.

### Reads

One small synchronous read at mount, so the first frame shows the store; then a
poll every `RELOAD_INTERVAL` (2.0 s), off the event loop. Each tick hashes
`todo.md` and `qa.md` (sha256; the digest is `(state, sha)` per file). An
unchanged digest re-renders only the age labels. A changed one parses the same
bytes it hashed, so a write between the hash and the parse cannot be missed.
The **last good parse** of each file is kept when a later read fails. The
banner then says `Store unusable: <err>` / `Q&A log unusable: <err>`, plus
`Showing the last good view.` and the `R` hint. With no good parse at all, the
header reads `store unusable`. The agent's state (`find_sitrep_roles`) is
polled every `AGENT_POLL_INTERVAL` (3.0 s).

### Views

- **Main list.** The groups come from `sitrep_todo`'s GROUPS, shown with the
  TUI labels (`now` → **Now**). Now / Next / Waiting are always shown; Recently
  done / Dismissed only behind `d`, whose footer label follows the state
  (`_set_binding_label`). A fixed column header (Item / Checked / Pri/Eff /
  Created / What to do) sits outside the list, so it never scrolls. Rows are
  one line, cut with an ellipsis.
- **"What to do" / "How".** `classify` + `NEXT_STEPS` in `sitrep_tui_model.py`
  are the single source. The `{k_*}` placeholders resolve to the **effective**
  keys (user overrides included), so a remap is what the text names.
- **Task fields** (priority, effort, status, labels, `created_at`) are read
  from the task files, never copied into the store. The **list** uses a cache
  built once per store generation (`model.task_metas` in `_apply`), so its
  Pri/Eff and Created cells and the label filter show a task-file edit at the
  next store change. **Opening details** reads the task file afresh
  (`model.task_meta` in `open_item`), so the details always show its current
  values.
  `created_at` is local wall-clock time with no zone; "today" compares calendar
  dates in the local zone (clock seam `AITASK_SITREP_NOW`).
- **Item details, source viewer, Q&A log and entry** are separate screens with
  their own shortcut scopes (`sitrep_tui.detail`, `.viewer`, `.qa`,
  `.qa_entry`; `lib/shortcut_scopes.py`). Details are snapshots. Every action
  re-resolves its item against the current store (see the actions below).
- **Mouse.** A click only selects, on every list (`SelectOnClickList`,
  `sitrep_tui_widgets.py`); Enter opens.

### Pointers

The links list renders each context source with a plain label
(`sitrep_tui_model.py`, `source_label`). Capture passages get labels by kind:
`Closing message`, `Workflow result`, `Excerpt of the unparsed output`, the
three `Review case:` records. **KEY receipts are hidden**: they stay in the
store, and the identity index still uses them. A trusted review case adds a
`Raw input (review case)` row, and its bytes are re-hashed against the case
record before they are shown.

The viewer renders task, plan and `.md` file pointers as Markdown (front matter
becomes a fenced yaml block) with `open_links=False`. A `#L` pointer or an
error starts raw, with line numbers; `m` toggles. A capture shows only its line
range. A commit is `git show --stat --format=fuller`. A URL is shown, never
opened. The size cap is 256 KiB. A refused pointer reads `Not followed: <why>`.

### Actions

- Writes go only through the writer, run with `cwd=<root>` and without
  `AITASK_SITREP_DIR`, which is the store the TUI reads.
- **Dismiss** passes `--expect-rev <the rev the user saw>`. `STALE:` re-reads
  and asks again; it never retries blind.
- **Restore** is `restore <kind> --if-damaged`. The writer re-checks the live
  file under its lock, so a repair that landed while the confirm dialog was
  open is never rolled back. Plain `restore` stays unconditional for the CLI.
- **Harvest + refresh** (`harvest all`, then refresh with budget 60 / timeout
  75) runs once at startup and on `r`, one run at a time.
- **The agent's state** comes from `find_sitrep_roles`, polled off the event
  loop. A failed query reads as "unknown", never as "not running".
  **Respawn** is `aitask_sitrep.sh open --session <the TUI's own session>`,
  the one spawn path above.
- **Item launches** re-resolve the item against the current store. Details
  are snapshots, so a moved rev refreshes them and launches nothing:
  - **pick** is for pick items only (never triage) and works like the
    minimonitor's (tmux window only);
  - **open in board** is `launch_or_focus_board` plus `switch-client` when
    the board lives in another session of the project;
  - **show in trails** (`z`, and Enter on a details trail row) is
    `launch_or_focus_trails(…, task_id)` with the same session rule: the
    trail opens in `ait trails` with the task's card focused (a running
    trails too old for the task form still opens the trail and says so);
  - **push** shows the command and never runs it.
- **Label filter** (`f` / `F`): task items whose task has any checked label;
  every non-task item, cross-repo item and missing task file is hidden while it
  is on. Per-session UI state, never written to the store.

**Trail membership** (`sitrep_tui/sitrep_tui_trails.py`) is one
`trail_links.export_project(root)` subprocess per scan, in a thread worker:
after a store change, when a task item's details open, and every 60 s. A
task is `in` some trails, in `none`, or `unknown` (the export failed,
`project.name` is unset, or a partial scan found nothing for it — never
shown as "in no trail"). A partial scan keeps the trails it did read.
The details show a `Trails` line and one links row per trail, keyed by
the trail's handle, so a rescan never re-points a selected row; `z` is
shown only for a task known to be in a trail.

### Requests into the agent

`AGENT_REQUESTS` (`sitrep_tui_requests.py`) is the one table: the bindings, the
How-text keys and the re-export the skill-parity test imports all come from it.

| Key | Typed | Fits |
|---|---|---|
| `t` | `>t c<N>` | `classify` → `triage` / `review` |
| `a` | `>q c<N> <text>` | any item (ask dialog: one line, ≤ 300 chars, no control characters, no trailing `@mention`) |
| `w` | `>w <theme>` | the item's context names a theme |
| `T` | `>tr c<N>` | `classify` → `watch` (a trail-checked watch) |
| `n` | `>p` | store-wide |

They apply only when `request_available()` holds (the TUI runs in a pane of the
gateway server and the agent state is `running`). One request is in flight at
a time: the keys are disabled meanwhile, and a second press is refused, never
queued. Every action re-checks the item: a moved rev sends nothing.

Delivery (`monitor/agent_request_delivery.py`, `deliver_sitrep_request`) runs in
three observed phases:

1. **Readiness.** Two captures `COMPOSER_DRAIN_SECONDS` (0.5 s) apart must both
   show an empty, idle composer (`readiness_verdict` over `shadow_state`), and
   the pane must not be in a tmux mode. Otherwise the request is refused and
   nothing is typed.
2. **Guarded paste.** The text goes to tmux on stdin (`load-buffer -`; argv
   mangles a trailing `;`, `TmuxClient.run_with_input`), then ONE
   `if-shell -F` on the run identity and `#{pane_in_mode}` = 0
   (`monitor_core.guarded_paste_text`). The `@aitask_dispatch_ack` nonce
   (`<nonce>:sent` / `<nonce>:skipped`, read back by `dispatch_ack_state`)
   reports which branch ran, since `if-shell` answers 0 either way.
3. **Submission.** Before every Enter, the first one and every retry, the
   current composer's **complete payload** must equal the request
   (`review_loop.composer_payload`, `payload_matches`; only justified display
   wraps are allowed), and the pane mode is the last read. The Enter itself is
   guarded and acked (`guarded_send_key`). After it, `READY` / `WORKING` →
   submitted. A composer that still holds exactly the request → a swallowed
   Enter (retry). Anything else → `unknown`, because the request may have gone
   and "not submitted" would invite a duplicate.

Results (`DeliveryResult`; user wording from `.message()`):

| Code | Returned when | Typed / submitted |
|---|---|---|
| `submitted` | the post-Enter capture is idle or working | yes / yes |
| `typed_not_submitted` | detail `composer_changed` (the first pre-Enter proof failed) or `submit_unconfirmed` (retries exhausted with the request still in the composer) | yes / no |
| `typed_not_submitted:in_mode` / `:mode_unreadable` | the last pre-Enter read found a mode / could not read it, or the guarded Enter skipped on `pane_in_mode` | yes / no |
| `refused:not_ready:<dialog\|draft\|working\|unknown\|in_mode\|mode_unreadable>` | readiness failed (an agent without a measured grammar is `not_ready:unknown`, detail `agent:<key>`) | no / no |
| `refused:identity_changed` | the guarded Enter skipped on run identity | **yes** (into the replaced run) / no |
| `refused:<no_agent\|frozen\|dispatch_failed\|invalid_request>` | before the paste | no / no |
| `skipped` | the guarded paste's condition failed | no / no |
| `unknown` | the paste or Enter ack was unreadable, the pre-Enter composer was unprovable, or the post-Enter state proves nothing | **unknown** — never read as sent, never as not sent |

Every result is toasted; anything but `submitted` also opens the result panel
(red only for `unknown`). Supported agents are
`review_loop.PAYLOAD_GRAMMAR_AGENTS` (claude, codex, opencode), whose composer
grammars were measured from real captures (`tests/sitrep_request_fixtures.py`).

## Unparsed output: the review corpus

The harvest certifies a capture for deletion only after a **confidence check**
(`sitrep_harvest.assess`). Each expected occurrence must be claimed by its own
success, never by "any success in scope":

| Reason | Fires for |
|---|---|
| `banner_incomplete` | a recognised banner first line whose fields are missing or invalid |
| `bad_followup` | a follow-ups token outside the grammar (an *unresolved* cross-repo token is valid) |
| `passage_truncated` | a closing passage clipped to the retain cap |
| `banner_unparsed` | a banner first line no parsed banner starts on (also one quoted inside a field) |
| `created_unparsed` | a `Created: aitasks/…` reference with no grammar match at its offset (drafts under `aitasks/new/` excepted) |
| `marker_without_banner` | a `⎿ HARVEST_RUN:<id>` tool line no banner claims, by the same `pair_markers` the run identity uses |
| `pipe_without_banner` | a non-blank `banner` pipe with no banner |

No banner at all (an agent frozen mid-work) is **not** a reason. With a reason,
`apply` still writes every item it found, then `sitrep_corpus.record_case`
preserves the case **before the receipt**:

- `raw/<hex>.txt`: the input byte for byte (`retain-raw`, any non-NUL bytes up
  to 64 MiB). Above the cap, or when the writer's sha differs, the harvest fails
  and the capture stays protected. Nothing is truncated.
- One **origin** record per source identity (record / run / source mode /
  agent / task / capture path / capture time; no harvest timestamp, so a retry
  is a no-op), one **analysis** per origin and parser revision (class, reasons
  with raw line ranges, warnings, the partial items) and the case **key**.
  They live in the **trusted namespace `cases/`**, written only by the writer's
  `retain-case` (which accepts nothing but case-record headers). Their
  byte-identical `sources/` copies exist only because context pointers must be
  `sources/`. An **excerpt** around the first reason (its own header line, so
  it can never equal a record) is a plain `sources/` passage.
- **Trust.** `sources/` also holds harvested passages whose text an agent
  controls, so nothing reads a case from there by header. `scan_cases` reads
  `cases/` only. `triage` labels a pointer `CASE` / `ANALYSIS` / `REVIEW`, and
  emits `REVIEW_CASE`, only when its `cases/` twin exists. `check-sources`
  follows only a trusted origin, and identity counts only review items.
- ONE review item, `Analyze unparsed agent output …` (`kind=question
  derived=script group=now`), added last and only when no item owns the key yet.
  An existing item, in any state, is reported `exists` and never reopened, but
  a new origin's files are still written.

**Receipt contract.** Deletion is allowed after reliable extraction, or after
raw evidence plus a durable review item. Any failure before that is
`HARVEST_FAILED` with no receipt (fault seam `AITASK_SITREP_HARVEST_FAULT`).
Receipts carry `cert=2` (`HARVEST_CERT` = `agent_sessions.HARVEST_RECEIPT_CERT`).
A legacy receipt without it fails both `receipt_valid` (so `record`
re-harvests) and `capture_harvested` (so `drop` refuses and `purge` keeps), and
the re-harvest's identity keys make the old items `exists`.
`HARVEST_REVIEW:<src>|c<N>|added|exists|case=<hex>|<codes>` and
`HARVESTED:…|review=c<N>` report it; a cached `already_harvested` result
prints the same `HARVEST_REVIEW:…|exists|` line (a lock-free read), because the
automatic post-freeze or maintenance harvest usually runs first. `h` shows
"kept for sitrep review", which is still ok (`HarvestReport.reviews`).

**Lifecycle.** The sitrep agent finds the reviews in `triage --open`
(`REVIEW_CASE:<hex>|<codes>`, `CASE:` / `ANALYSIS:` labels), reads them with
`case show` / `case read`, writes the missed items through the writer, then runs
`case review --item`. That adds an append-only review record, then closes the
item. Status (`case list`) comes from the review ITEM: pending (open, also
when a record exists but the close was stale or failed:
`REVIEW_NOT_CLOSED:c<N>|<why>`, exit 1), dismissed (the user's dismissal always
wins), resolved or reviewed. Those last two come from the item's **accepted**
outcome (`reviewed: <outcome>`, which only a successful close writes). Review
records are history, so a failed `resolved` attempt never shows as resolved.
`case review` on a done item re-closes it with a new accepted outcome; on a
dismissed one it only adds the record. A case without an item is incomplete.
Cases are found by scanning the trusted `cases/` namespace, never `sources/`
and never through item contexts. The review item is recognised by
**provenance**, never by its (editable) title: a script-derived question whose
context points at the case key and at a trusted origin or analysis of the same
case. Nothing prunes `raw/`, `cases/` or `sources/`.

**Improving the parser.** `case replay <hex>` re-runs the current grammar over
the kept input through a write-nothing `DryStore` (it mirrors the real store's
identity index as it simulates adds, so a repeated commit, run or passage key
matches exactly as it would for real): `REPLAY_ITEM:…|new` lines
show what it would recover, and `REPLAY_RESOLVED:` lines show the reasons a
change fixed. `--apply` (under the harvest mutex) writes the items and a new
`origin=replay` analysis and leaves the review item alone. `case export <hex>
--out <dir>` refuses a case the parser still classifies `review`, and writes
`input.txt` plus `case.json` (expected class, refs and kind counts). Redact the
input, then commit it under `tests/fixtures/sitrep_harvest/corpus/`.
`tests/test_sitrep_corpus_fixtures.py` runs `check-fixture` over every committed
fixture. The first one is the **joined banner** (displayed without its fence,
fields inline; `ACCEPT_JOINED_BANNER`, `PARSER_REV` 2). It is synthetic, built
from workflow-end.md's fence rule. `tests/test_sitrep_corpus.sh` case 8 proves
the fixture fails against a copy with the flag off.

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
  exit is 0 AND the last final line is `HARVESTED` / `HARVEST_NONE`.
  `HARVEST_REVIEW:` lines become `reviews` (verdict "output kept for sitrep
  review"; still ok, since the case was saved before the receipt). Titles come
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
On start: `ait sitrep root`, then `list` + `read todo`, then a greeting built
from its Capabilities section. It does **not** harvest or refresh: the TUI does
both at its start and on `r`. `list` exit 4 (store unusable) → it names the
TUI's `R` and writes nothing until `list` reads again.

- **Codes:** `>t [c<N>]`, `>w [<theme>]`, `>q [c<N>]`, `>tr [c<N>]`, `>p`, `>c`,
  `>?`. A bare `>t` triages every open triage item as one batch; `>t c<N>` only
  that item (it never reads, proposes for or closes another one). A bare `>w` /
  `>tr` covers every theme / trail watch.
- **Writes only through writer verbs** (`add`, `set-state`, `situation`,
  `upsert-context`, `qa`, plus `aitask_sitrep.sh case review`), with
  `--expect-rev` on every write to an existing item; `STALE:` means re-read,
  never retry blind. `dismiss` and `restore` are not the agent's: they are the
  TUI's `x` and `R`.
- **Requests from the sitrep TUI** ("Requests from the sitrep TUI" in the
  skill): the five request lines of `AGENT_REQUESTS`. A request carries the
  authority of typed input and no more, so every write is still confirmed. Before
  each one the agent re-reads `list` (plus `context c<N>` for an item request,
  `read context` + `read todo` for `>w`) and checks the request on that fresh
  read: an open triage item for `>t`, any listed item for `>q`, a watch with a
  `trail:` source for `>tr`, a known theme for `>w`. A failed check is reported
  and writes nothing.
- **Done in the TUI, not here:** show, harvest + refresh, dismiss and restore
  are TUI keys; asked for one, the agent names the key (`r` / `x` / `R`).
- **Guardrail:** the TUI may type into the agent at the user's request; the agent
  never types into the TUI or any other pane.
- **Triage** turns each selected open triage question (one per harvested wrap-up run; all of them for a bare `>t`, one for `>t c<N>`) into
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
| `tests/test_sitrep_corpus.sh`, `tests/test_sitrep_corpus.py`, `tests/test_sitrep_corpus_fixtures.py` | the confidence check (every reason, per-occurrence pairing, negatives), legacy receipts, case files and provenance, faults, the replay / export loop, committed fixtures |
| `tests/test_sitrep_refresh.sh`, `tests/test_sitrep_refresh.py`, `tests/test_monitor_sitrep_refresh.py` | refresh and its monitor tick |
| `tests/test_sitrep_window.py` | lookup matcher, spawn decisions, the CLI (mocks) |
| `tests/test_sitrep_window_live.sh` | the spawn against a private tmux server (cleanup hook stubbed) |
| `tests/test_sitrep_window_hook_live.sh` | the window under the REAL companion cleanup hook: the agent exits → its pane goes, the TUI and companion stay; `ait sitrep` respawns the agent above the TUI |
| `tests/test_sitrep_tui_app.py` | the TUI's read views over a fixture store built through the real writer: snapshots and last-good-parse, the What-to-do / How texts, columns, pointers and the Markdown viewer, details, the Q&A screens, reload, header, click-selects |
| `tests/test_sitrep_tui_actions.py` | the actions (`r`, `x`, `R`, `A`, `p`, `b`, `P`) through the real writer: re-resolution against the current store, `STALE` handling, restore `--if-damaged`, the agent state; task metadata, the Created column, the `d` toggle and the label filter |
| `tests/test_sitrep_tui_requests.py` | the request keys, app side: `AGENT_REQUESTS` as the one table, availability, one in flight, re-checks, the ask dialog, the result panel |
| `tests/test_sitrep_request_delivery.py`, `tests/sitrep_request_fixtures.py` | delivery without tmux: the readiness table per `shadow_state`, the dispatch ack, the composer-payload proof over real captured composers of claude / codex / opencode, every result code |
| `tests/test_sitrep_request_delivery_live.sh` | delivery against a real tmux server and a scripted Claude-shaped agent: respawns, freezes, copy-mode and user typing interleaved between the phases |
| `tests/test_sitrep_tui_trails.py`, `tests/test_sitrep_tui_trails_actions.py` | trail membership (fail-closed `unknown`, partial scans), the trail picker, `z` and the details' trail rows |
| `tests/test_board_focus.py`, `tests/test_board_focus_writer.py`, `tests/test_board_focus_mailbox_live.py` | `ait board --focus` and the board's pane mailbox (`launch_or_focus_board`) |
| `tests/test_trails_focus_writer.py`, `tests/test_trails_focus_mailbox_live.py` | `ait trails --trail --task` and the trails mailbox's task form |
| `tests/test_skill_render_aitask_sitrep.sh` | the skill's render, goldens, stubs |
| `tests/test_sitrep_skill_contract.sh` | the skill's documented commands against the real helpers |
| `tests/test_monitor_sitrep_harvest_close.py` | `h` / `S`: report parsing, the owned-group runner (timeout and cancel), target and sitrep-window guards, run identity, confirm callback, maintenance order, the count, the dialog, the real key presses, the switcher `S` |
| `tests/test_kill_agent_run_guarded.sh` | the guarded run kill against a private tmux server (respawned / frozen pane refused, always pane-only: the last agent's window and companion stay, a pane moved into another agent's window and a helper swapped for an unrelated agent leave that agent alive) |
| `tests/test_monitor_harvest_close_live.sh` | `h` end to end against a private tmux server: real gateway capture → real `harvest capture` → store items → guarded close of the pane only (window and companion stay), on both tmux routes; a failed harvest keeps the pane; `agent-sitrep` is never captured; a respawn after the harvest is refused. Opt-in: refuses inside tmux or with `-L ait` alive |
