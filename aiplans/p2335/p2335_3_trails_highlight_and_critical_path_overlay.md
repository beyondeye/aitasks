---
Task: t2335_3_trails_highlight_and_critical_path_overlay.md
Parent Task: aitasks/t2335_sitrep_work_directions.md
Sibling Tasks: aitasks/t2335/t2335_4_skill_directions_code.md, aitasks/t2335/t2335_5_tui_directions_tab.md, aitasks/t2335/t2335_6_manual_verification_work_directions.md
Archived Sibling Plans: aiplans/archived/p2335/p2335_*_*.md
Base branch: main
Output branch: main
---

# t2335_3 — Trails highlight set and critical-path overlay

## Context

A sitrep work direction (parent t2335) shows its tasks inside the implementation trails that already
exist; it does not generate a trail of its own. That needs three things this child delivers, and that
children 4 (the `>d` skill code) and 5 (the Directions tab) consume:

1. a **pure critical-path function**: given a trail document, a highlight set and resolved task
   states, which tasks must land before the highlighted ones;
2. a **CLI read verb** the sitrep skill can quote (next actionable task, blockers, wave of each
   highlighted task), with its freshness attached;
3. an **`ait trails` overlay**: `--highlight` plus a mailbox form for an already-running app, with
   distinct markers on highlighted and critical-path cards, a banner naming the direction, and a key
   that clears it.

Independent of the store children (t2335_1/2): it reads only trail documents and task files. Related
work check: relations analysis is disabled in this project (no relation data).

### Plan review — concerns addressed

Round 1:

| Concern | Resolution |
|---|---|
| Overlay state parity | ONE state resolver (`lib/trail_task_states.py`) for both callers, off the TUI render path; parity test with an outside prerequisite turning Done |
| Missing prerequisites counted as landed | Only verified landed clears; missing / unreadable / unresolvable / malformed stay unresolved blockers; NEXT needs a verified open node |
| Wave semantics | Only an earlier-wave `hard_prerequisite` blocks through wave order; `preferred_predecessor` / `core` advisory; `coordination_only` / `optional` nothing |
| Stale trail advice | Live dependencies drive the depends edges; the drift verdict qualifies every NEXT |
| 64-id cap | Cap 256; first 256 + total sent above it, trail still opens, partial highlight visible; 65 and 257 pinned |
| (found) `◆` collides with `hard_prerequisite` | Markers `★` / `»` / `›` |

Round 2:

| Concern | Resolution |
|---|---|
| Archive fallback over an unreadable active file | Tri-state `lookup()`; bundles only after ABSENT |
| Removed dependencies | Readable live `depends:` authoritative; dropped saved edges reported `SUPERSEDED` |
| Gate release | `released` satisfies depends edges, not wave-hard edges; never landed, never NEXT |
| Worker redraw vs card focus | Worker updates markers in place (no remount); worker-before/after-focus pilot tests |
| Discovery depth cap | Two passes; outside prerequisites reported and not followed |

Round 3 (2026-11-26):

| Concern | Resolution |
|---|---|
| Lookup precedence: a higher-precedence location that cannot be stat'ed / listed still let an older copy win; `_dir_identity` folds every stat error into absence | `lookup()` walks the precedence chain (active → loose archived → bundles) and continues past a location **only on confirmed absence** (ENOENT / ENOTDIR, or a clean listing with no hit); any other stat or listing error is UNREADABLE and stops the walk. New private `_dir_state()` separates absence from error; `_dir_identity`, `facts()`, `classify()` unchanged. Tests: active stat failure and active listing failure, each with a loose and with a bundled Done copy → unreadable |
| Cross-repo blockers (xdeps) ignored by readiness | A node's `xdeprepo`/`xdeps` pairs are strong readiness blockers decided by the existing rule: `cross_repo_deps.classify_xdep_status` over `probe_xdep_status` results (only `Done` unblocks; unprobed = unresolved). The TUI feeds the overlay from `session.xdep` / `session.xdep_inflight` — the same results its cards render — and the CLI runs the same probe. Foreign trail members use the same probe too (no second foreign resolver). Test: one task with its remote prerequisite open, then Done, in both callers |
| Overlay refresh lifecycle | Every input refresh or replacement (`r`, trail reload / watch reload, a new highlight, clear, tab close) **invalidates the advice** (`overlay_states = None`: highlight markers only, no path/NEXT markers, banner `resolving task states…`) and draws a fresh unique `overlay_gen`; a worker callback applies only when its `(session object, gen)` is still current, so clear, replacement and close retire it. Tests: `r` with a delayed worker; clear and close+reopen while a result is pending |
| Direction display title | Identity and display are separate: `direction=<slug>` (identity, `DIRECTION_RE` grammar) and `title=<base64url UTF-8>` (display: one line, ≤ 120 characters — the store's `MAX_DIRECTION_TITLE` rule); cold launch passes `--highlight-direction <slug> --highlight-title "<title>"` in argv form. The banner reads `direction: <title>`. Test: `Stabilize CI` (and a non-ASCII title with `|`) through the cold launch and the running-app mailbox |

Round 4 (2026-11-26):

| Concern | Resolution |
|---|---|
| Cross-repo refresh parity: `r` reloads local xdeps but the xdep worker never runs on `r` (its docstring: "`r` and a tab switch stay zero-subprocess"), so a newly added xdep stays unchecked in the TUI while the CLI probes it | For a session **with an overlay**, `r` computes the probe key set from the reloaded tasks (`remote_keys`, the shared definition); when a key has neither a completed result nor an in-flight probe, it starts the existing full xdep worker over the latest key set (the mechanism is the round-5 row below — the additive probe first proposed here was withdrawn). While it runs, the affected cards show `(checking…)`, the overlay reads the new key as unresolved (never NEXT), and the banner says `checking <n> cross-repo prerequisite(s)…`. Sessions without an overlay keep today's zero-subprocess `r`. Test: add an xdep on an already-Done remote task, press `r` → checking, then NEXT; the CLI on the same tree says NEXT |
| Foreign member readiness: a foreign member is never NEXT, so a Ready foreign member with no known blocker read as "blocked" with zero blockers | Readiness is an explicit enum for every highlighted and path node: `next`, `blocked` (≥ 1 known blocker), `unverified` (open with no known blocker, but its prerequisites cannot be examined — a foreign member: its probe returns a status only), `unresolved` (its own state is unresolved), `released`. `blocked` always comes with ≥ 1 blocker (asserted). CLI `HIGHLIGHT:` / `PATH:` carry it; the card reads `★ direction · readiness unverified (cross-repo)`. Test: a highlighted foreign `Ready` member with no known blocker → `unverified`, 0 blockers, no NEXT, in both callers |
| Valid direction names: a title such as `--follow-up` breaks `--highlight-title <value>`; a store slug longer than 64 characters was refused | Every value-carrying launch option is passed in the single-token `--opt=value` form (`--highlight-title=--follow-up` parses); the docs show that form. The slug grammar is the store's own (`DIRECTION_RE`, unbounded there); the transport bound is 512 characters, and a longer slug is **left out** of the request with a warning ("direction id too long to send — the trail opens with the title only") while the trail and the highlight still open. Tests: titles `--follow-up` and `-x` through the cold argv and the mailbox; a 65-character slug sent whole; a 600-character slug left out with the warning and the trail opened |

Round 5 (2026-11-26):

| Concern | Resolution |
|---|---|
| Overlapping remote checks: a second additive probe retired the first one's completion and left its keys in `xdep_inflight` for good; an older full probe landing late could overwrite an additive result | **No additive probe.** When `r` discovers a key with neither a completed result nor an in-flight probe, it starts the **existing full worker** (`_start_session_xdep`) over the latest key set. One path, one generation (`xdep_gen`), newest wins, and the accepted completion replaces the map and clears the **whole** in-flight set — so no rejected completion can strand a key and no older probe can overwrite a newer result. The overlay counts a key as pending only when it has no completed result, so re-probing known keys does not blank valid advice. Cost: the session's other keys are re-probed too. Tests: two consecutive edits each adding a key (probes overlap, both orders of completion); a `d` full refresh overlapping an `r`-started probe (both orders) |
| Completed readiness: no readiness value for a verified-Done highlighted task; `released (gates pending)` said the opposite of the state | Readiness gains `landed` (a Done highlighted task: `HIGHLIGHT:…|done|landed|0|-`, card `★ direction · landed`) and is total over every state, with a stated precedence. A released task reads "cleared for dependents, awaiting landing" in the CLI comment, the card note and the docs. Tests: a Done highlighted task and a released highlighted task, each in the CLI output and on its card |

Round 6 (2026-11-26):

| Concern | Resolution |
|---|---|
| Next task eligibility: any readable non-terminal task with clear dependencies was NEXT, including `Postponed` and `Implementing`, while t2335_4's `>p` reads NEXT as pick advice | **NEXT is pick eligibility**: clear of every trail-known blocker **and** status `Ready`. A clear `Implementing` task is `in_progress`, any other clear non-terminal status is `on_hold` (status named); both have their own CLI lines (`IN_PROGRESS:` / `ON_HOLD:`) and card notes, and the consumer rule is written into the advice contract. Pinned: `Ready` / `Postponed` / `Implementing` with zero blockers, in the pure tests, the CLI and on cards |
| Cached remote advice: subtracting cached keys from the pending set let a cached `Done` yield a plain `next` while its re-read was in flight | The pending set is passed whole. A key with a previous result that is in flight is **rechecking**: the previous evidence stays visible and decides blocked / clear, but every `next` that relies on it is qualified `next? (rechecking cross-repo)` and the banner counts the rechecked keys. Test: a delayed probe that turns a cached `Done` into `Implementing` (and into unreachable) |

## Semantics (traced from `implementation_trail.schema.json`, `trail_schema.py`, `aidocs/implementation_trail_design.md`, `website/content/docs/workflows/implementation-trails.md`, the board reference's classification table, `lib/dep_resolution.py`, `lib/cross_repo_deps.py`)

**Edges** (`from` must land before `to`):

- **Depends (strong)**, into node X:
  - when X's live `depends:` is readable (X resolved `open` or `released`): exactly X's live depends;
  - otherwise (X unresolved, or a foreign member): the saved evidence — `relations[type=hard_depends]`
    with `to == X` and X's entry `snapshot.depends`;
  - saved edges into a node with readable live depends that the live list lacks are reported as
    **superseded** (historical evidence, not blockers).
- **Cross-repo (strong, readiness)**: each `xdeprepo`/`xdeps` pair of a local node with a readable
  file (`cross_repo_deps.xdep_ref_pairs`). Satisfied only when a completed probe says `Done`
  (`classify_xdep_status`); a completed probe with any other status or `NOT_FOUND` / unreachable
  blocks; a ref not probed yet (or still being probed) is **unresolved** and blocks. Cross-repo
  prerequisites are reported, never followed.
- **Wave-hard (strong)**: an entry classified `hard_prerequisite` in a wave with a lower ordinal than
  X's earliest wave.
- **Weak (advisory)**: `relations[type=advisory_precedes]`; **wave-soft** — earlier-wave entries
  classified `preferred_predecessor` or `core`.
- **None**: earlier-wave `coordination_only` and `optional` entries; same-wave peers; `coordinates_with`,
  `verifies`, `informs` relations.
- A ref listed in several waves takes its **earliest** ordinal; all ordinals are reported.

**States** (never from the trail snapshot):

| State | Meaning | Depends edge from it | Wave-hard edge from it | NEXT-eligible |
|---|---|---|---|---|
| `done` | verified landed: status Done (active, loose archive, or bundle after confirmed absence everywhere above); a foreign task whose probe says `Done` | satisfied | satisfied | no |
| `released` | local, active, not Done, required gates pass (the t635_3 rule `ait ls` uses) | satisfied | **blocks** | no |
| `open` | local readable file, non-terminal status (carried verbatim in `TaskState.status`), readable `depends:`; a foreign task whose probe returned another status | blocks | blocks | local only, with status `Ready`, when all its strong edges are satisfied |
| `unresolved:<reason>` | missing, unreadable, stat/listing failed, bundle copy not Done, folded, malformed `depends:`, bad dep token, foreign unreachable / `NOT_FOUND`, not probed or resolved yet | blocks | blocks | no |

**Sets**, for highlight set H. Traverse backwards from H over strong depends + wave-hard edges; an
edge whose predecessor satisfies it is not traversed and the predecessor is recorded — `done` in
**landed**, `released` in **released**. A predecessor reached by at least one unsatisfied edge is on
the **path** (`via`: `depends` when reachable from H by depends edges only, else `wave`).

- **advisory** = backward closure from H ∪ path over strong + weak edges, minus H ∪ path ∪ landed.
- A local prerequisite with no trail entry → **outside**; a cross-repo prerequisite → **cross_repo**.
  Both block unless satisfied, have no card, and are **not followed** (both surfaces say so).
- A highlighted id that is not a member → **not_in_trail**, never dropped. Empty H → empty result.
- **Clear**: a local node of H ∪ path in state `open` whose every direct strong edge — depends,
  wave-hard and cross-repo — is satisfied. Clearance says only that nothing the trail knows blocks it.
- **Next actionable = pick eligibility**: a clear node whose status is exactly `Ready` — the status
  `ait ls` lists and `/aitask-pick` claims from. This is the one meaning of NEXT on both surfaces,
  because t2335_4's `>p` reads it as pick advice. A clear node with any other status is **not** NEXT:
  `Implementing` → `in_progress` (already claimed: the work to finish, not to pick); `Postponed`,
  `Editing`, an empty or unrecognized status → `on_hold` (status named). Outside, cross-repo and
  foreign nodes are never NEXT. What NEXT does **not** establish, stated in the CLI docstring and the
  docs: it reads no locks and no gates of the task itself — the pick's own claim does; a `Ready`
  parent with pending children is NEXT (picking it leads to its children).
- **Readiness** of every highlighted node (H can hold a task in any state) and every path node,
  exactly one of — the function is total over (state, edges), asserted:
  - `landed` — state `done` (highlighted nodes only; a `done` node is never on the path). It has no
    blockers, is not expanded, and is not NEXT;
  - `released` — its required gates have passed: **cleared for its dependents, awaiting landing**
    (not Done yet, so later waves still wait for it); never NEXT;
  - `next` — next actionable: clear **and** status `Ready` (above);
  - `in_progress` — clear, status `Implementing`;
  - `on_hold` — clear, any other non-terminal status (`Postponed`, `Editing`, empty, unrecognized);
    the status is the reason;
  - `blocked` — at least one known blocker (a direct strong edge unsatisfied), always listed, whatever
    the status;
  - `unverified` — state `open`, no known blocker, but its prerequisites cannot be examined: a foreign
    member (its probe returns a status only, not its dependencies);
  - `unresolved` — its own state is unresolved (reason given).
  Precedence when several could apply: `landed` > `released` > `unresolved` > `blocked` > `unverified`
  > `in_progress` > `on_hold` > `next`. `blocked` with zero blockers cannot occur (asserted in the
  function and in tests).
- **Blockers** of a highlighted task: its transitive strong predecessors reached by unsatisfied edges,
  plus the unsatisfied cross-repo prerequisites of itself and of those predecessors.
- Cycles are safe (visited sets). Order is deterministic: (earliest wave, ref).

### Advice contract (freshness and lifecycle)

Edges come partly from the saved trail, so the advice inherits its freshness. Both callers take the
verdict from the **same drift helper** (`trail_gather drift`: the CLI runs it in-process on the same
loaded document; the TUI already holds it in `session.drift` from `run_trail_drift`):

| Drift verdict | NEXT claims | CLI | TUI |
|---|---|---|---|
| CURRENT | unqualified | `NEXT:<ref>|<waves>|current` | `» next` / `★ … · next` |
| STALE | qualified | `NEXT:…|stale` + `FRESHNESS:stale|<codes>` | `» next? (trail stale)`; banner `next t12 (trail stale — R refreshes)` |
| unavailable / not checked yet | qualified | `NEXT:…|unknown` + `FRESHNESS:unknown|<reason>` | `» next? (freshness unknown)` / `(checking…)` |

A second, independent qualifier exists only in the TUI (the CLI probes synchronously and never holds a
cached remote result): a `next` whose clearance relies on a cross-repo key that is **being rechecked**
reads `next? (rechecking cross-repo)` whatever the drift verdict; with a stale trail as well:
`next? (trail stale; rechecking cross-repo)`. A plain `next` therefore means: trail current **and** no
relied-on remote evidence in flight.

**What NEXT means for a consumer** (the contract t2335_4 quotes): NEXT is pick eligibility — clear of
everything the trail knows **and** status `Ready`. `IN_PROGRESS` and `ON_HOLD` are clear but are not
pick advice; `>p` may say "the direction's next step, t12, is already in progress" from `IN_PROGRESS`,
and must not offer an `ON_HOLD` task as a pick.

In the TUI, advice exists only while its inputs are the ones it was computed from: any refresh or
replacement of the task states, the document or the highlight drops it until the states worker for
the new inputs lands (see §7).

## Implementation

### Pre-phase (risk mitigations)

1. [baseline_trails_suites] Before editing any file, run
   `~/.aitask/venv/bin/python -m pytest tests/test_trails_app.py tests/test_board_bytrail_view.py tests/test_board_trail_view.py tests/test_trail_screen_host_protocol.py tests/test_trails_focus_writer.py tests/test_trail_gather.py tests/test_sitrep_tui_trails_actions.py tests/test_local_dep_parity.py tests/test_minimonitor_pick_by_number.py -q -p no:cacheprovider`
   (and `tests/test_trails_focus_mailbox_live.py` separately) and record the pass/fail counts and the
   names of any failing tests in the plan's Final Implementation Notes. A test that fails here is
   pre-existing and is reported, not fixed, by this task. Do not stash or reset anything to get the
   baseline; record it as the tree stands.

### 1. `lib/dep_resolution.py` — a precedence-strict public lookup (existing APIs unchanged)

- New private `_dir_state(path) -> ("absent" | "present" | "error", detail)`: `os.stat` →
  `FileNotFoundError` / `NotADirectoryError` (ENOENT / ENOTDIR) is `absent`; a non-directory or any
  other `OSError` (EACCES, EIO, ELOOP, …) is `error`. `_dir_identity` stays as it is (the existing
  caches keep their semantics).
- New `Lookup(kind, facts, path, detail)` with `kind` ∈ `FOUND | UNREADABLE | ABSENT`, and
  `LocalDepResolver.lookup(canonical) -> Lookup`, which walks the **same candidate order as
  `_path_for`** (active, then loose archived; child ids in `t<parent>/` dirs) and for each location:
  - `_dir_state` `error` → `UNREADABLE(detail=…)` — **stop** (a higher-precedence copy cannot be ruled out);
  - `absent` → continue to the next location;
  - `present` → list it directly (`os.listdir`, its own index build — the cached `_index_for` swallows
    listing errors and is left alone); a listing `OSError` → `UNREADABLE`, stop; a hit → read + parse
    → `FOUND(facts)` or `UNREADABLE(path, detail)` (unreadable file, unparseable frontmatter), stop;
    no hit → continue.
  - Every location confirmed absent → `ABSENT`.
- `facts()` / `classify*()` / `scan` keep their exact behaviour; a test pins that.

### 2. `lib/trail_task_states.py` (new, I/O — the ONE local resolver both callers use)

`resolve_local_states(refs, *, local_project, tasks_dir, archived_dir, registry_file) -> {ref: TaskState}`
and `resolve_for_trail(doc, highlight, ...)`.

- **Two passes, no loop**: pass 1 resolves every local trail ref (`trail_critical_path.trail_refs`:
  entry tasks, `snapshot.depends` refs, relation endpoints, the highlight); pass 2 resolves the local
  live `depends:` refs of pass-1 nodes not resolved yet (the outside prerequisites); their own depends
  are read for their state but never resolved further.
- **Local refs** (`LocalDepResolver(tasks_dir, registry_file).lookup`):
  - `FOUND`: status Done → `done`; status Folded / `folded_into` → `unresolved:folded`;
    `classify_facts` SATISFIED by the gate rule → `released`; otherwise `open`. Then, from the file's
    frontmatter (`task_yaml.parse_frontmatter`): live depends via `dep_resolution.read_depends`
    (malformed → `unresolved:malformed_depends`; each token through `canonical_dep_id` + the local
    project, a non-canonical token → an unresolved prerequisite `unresolved:bad_dep_token`), and the
    cross-repo pairs via `cross_repo_deps.xdep_ref_pairs(meta.get("xdeprepo"), meta.get("xdeps"))`.
  - `UNREADABLE` → `unresolved:unreadable` (no archive fallback).
  - `ABSENT` → only now `archive_iter.find_archived_markdown_by_id(id, archived_dir, errors=…)` for
    the numbered bundles: any recorded error → `unresolved:unreadable`; a parsed copy with status Done
    → `done` (`reason=bundle`); another status → `unresolved:bundle_not_done`; nothing →
    `unresolved:missing`.
- **Foreign refs and xdep keys are not resolved here.** They are remote statuses, supplied by the
  caller from `cross_repo_deps.probe_xdep_status` (§4 CLI, §7 TUI — the existing xdep probe).
- `TaskState(state, reason, depends: tuple | None, xdeps: tuple | None)`.

### 3. `lib/trail_critical_path.py` (new, pure: no I/O, no TUI imports)

```python
@dataclass(frozen=True)
class TaskState:
    state: str                     # "done" | "released" | "open" | "unresolved"
    reason: str = ""
    status: str = ""               # the task file's status, verbatim ("" = none / unknown)
    depends: tuple | None = None   # live canonical refs; None = unavailable
    xdeps: tuple | None = None     # "repo#id" keys; None = unavailable

@dataclass(frozen=True)
class PathNode:
    ref: str; waves: tuple; state: str; reason: str = ""; via: str = ""
    readiness: str = ""            # released|unresolved|blocked|unverified|in_progress|on_hold|next
    status: str = ""               # task status, verbatim
    rechecking: bool = False       # its clearance relies on a remote key being re-read

@dataclass(frozen=True)
class HighlightNode:
    ref: str; waves: tuple; state: str; reason: str; blockers: tuple
    readiness: str                 # landed|released|unresolved|blocked|unverified|in_progress|on_hold|next
    status: str = ""
    rechecking: bool = False

@dataclass(frozen=True)
class CriticalPath:
    highlighted: tuple; path: tuple; advisory: tuple; landed: tuple; released: tuple
    outside: tuple                 # local non-member prerequisites (not followed)
    cross_repo: tuple              # (node ref, xdep key, status | "unchecked", blocked)
    not_in_trail: tuple; next_actionable: tuple
    unresolved: tuple; superseded: tuple

def canonical_ref(ref, local_project="") -> str | None
def trail_refs(doc, highlight, *, local_project="") -> set        # local refs to resolve
def remote_keys(doc, states, *, local_project="") -> set          # foreign members + xdep keys to probe
def critical_path(doc, highlight, *, states, remote, remote_pending=frozenset(),
                  local_project="") -> CriticalPath
```

- `remote_keys` is the **same key set** the TUI's existing probe covers (`board_trail_view.trail_xdep_refs`:
  each active local member's xdep pairs plus each foreign member ref) — moved into this lib module
  and re-exported from `board_trail_view` so there is one definition — so the CLI and the TUI probe
  exactly the same keys. Outside prerequisites' xdeps are not probed: outside nodes are never NEXT.
- `states`: local refs → `TaskState`; a local ref missing from it is `unresolved:not_resolved`.
- `remote`: completed probe results `{"repo#id": status}`; a foreign member's state and every xdep
  verdict come from `cross_repo_deps.classify_xdep_status(key, status)` (only Done unblocks). A key in
  `remote_pending` **without** a completed result is `unresolved:checking`, a key in neither is
  `unresolved:unchecked`.
- A key in `remote_pending` **with** a completed result is being **rechecked**: its last result still
  decides the verdict (previous evidence stays visible), but it is recorded in
  `CriticalPath.rechecking`, and every node whose clearance relies on it — the key is one of its own
  xdeps, or a foreign member that satisfies one of its strong edges — gets `rechecking=True`
  (`PathNode` / `HighlightNode` field). A `next` claim on such a node is qualified, never plain.
- Canonicalization uses `cross_repo_notation.parse_ref` (the parser `board_trail_view` uses); bare ids
  need `local_project`. Type-guarded traversal so a hand-edited document never crashes the TUI.

### 4. CLI verb — `critical-path` in `lib/trail_gather.py` (+ wrapper)

`aitask_trail_gather.sh critical-path --trail <path|art:handle> --highlight <ids,…>`

- `.aitask-scripts/aitask_trail_gather.sh`: rewrite `--trail art:` to a temp file for `critical-path`
  as well as `drift` (`case "${1:-}" in drift|critical-path)`).
- `lib/trail_gather.py`: subparser + `cmd_critical_path(args, out)`. Shares the load/validate block
  with `cmd_drift` (factor `_load_stored_trail(path, out) -> doc | None`); local states from
  `trail_task_states.resolve_for_trail`; remote statuses by `probe_xdep_status` for every key of
  `remote_keys(...)` (sequential, the probe's own 10 s timeout; a failed probe returns `""`, which
  the rule reads as unreachable → blocks); freshness by running `cmd_drift` on the same path into a
  buffer and reading its `CURRENT` / `STALE` / `DRIFT:` / `ERROR:` lines. A highlight value that is
  neither a bare id nor a `proj#id` → `ERROR:bad_highlight:<value>` alone, exit 0.
- Line protocol (module docstring; free field last; sorted by (wave, ref)):

```
TRAIL:<trail_id>
FRESHNESS:<current|stale|unknown>|<drift codes csv or reason or ->
HIGHLIGHT:<ref>|<waves csv>|<state>|<landed|released|unresolved|blocked|unverified|in_progress|on_hold|next>|<n blockers>|<status or ->|<reason or ->
NOT_IN_TRAIL:<ref>
NEXT:<ref>|<waves csv>|<current|stale|unknown>          (pick-eligible: clear AND status Ready)
IN_PROGRESS:<ref>|<waves csv>|<status>                  (clear, already Implementing — not a pick)
ON_HOLD:<ref>|<waves csv>|<status or ->                 (clear, status not Ready — not a pick)
BLOCKER:<highlighted ref>|<blocker ref>|<waves csv or ->|<via>|<state>|<reason or ->
PATH:<ref>|<waves csv>|<via>|<state>|<released|unresolved|blocked|unverified|in_progress|on_hold|next>|<status or ->|<reason or ->
ADVISORY:<ref>|<waves csv>|<state>|<reason or ->
LANDED:<ref>|<waves csv or ->|<reason or ->      (a Done PREDECESSOR; a Done highlighted task is HIGHLIGHT:…|done|landed|0|-)
RELEASED:<ref>|<waves csv or ->|<reason or ->    (gates passed: cleared for dependents, awaiting landing)
OUTSIDE:<ref>|<state>|<reason or ->              (its own prerequisites are not followed)
XDEP:<node ref>|<repo#id>|<status or unchecked>|<blocked|clear>   (not followed)
SUPERSEDED:<from ref>|<to ref>                   (saved edge, absent from the live depends)
SUMMARY:highlighted=<n>|path=<n>|advisory=<n>|landed=<n>|released=<n>|not_in_trail=<n>|outside=<n>|xdep_blocked=<n>|unresolved=<n>|next=<n>|in_progress=<n>|on_hold=<n>
```

No new whitelist entry: the script is already a whitelisted internal helper; only a verb is added.

### 5. Mailbox + launcher — `lib/agent_launch_utils.py`

- Capability `TRAILS_HIGHLIGHT_OPTION = "@aitask_trails_highlight"` with `mark_/unmark_trails_highlight`;
  generalize `_trails_receiver_takes_task(pane)` into `_trails_receiver_has(pane, option)` (same
  one-read, same-pid rule); the old name stays as a thin wrapper.
- Grammar (untrusted, whole-or-nothing):
  - `HIGHLIGHT_ID_RE = (?:[a-z0-9_-]+#)?[0-9]+(?:_[0-9]+)?`, `HIGHLIGHT_MAX = 256`;
  - `direction=<slug>` — identity, the store's own grammar `[a-z0-9][a-z0-9_-]*` (the
    `sitrep_todo.DIRECTION_RE` rule, unbounded in the store) with a transport bound of 512 characters
    (`HIGHLIGHT_DIRECTION_MAX`); the parser refuses a longer one, so the writer never sends it;
  - `title=<b64>` — display: `[A-Za-z0-9_-]{1,640}` (base64url, no padding) that decodes to UTF-8,
    contains no CR / LF and is at most 120 characters after `strip()` (the store's
    `MAX_DIRECTION_TITLE` single-line rule). Any other control character is kept in the value and
    replaced by `�` only at display time.
  - Payload: `<handle>[ <task>][ hl=<id>(,<id>)*[ of=<total>]][ direction=<slug>][ title=<b64>]` —
    `of=` only when truncated.
- Helpers `encode_highlight_title(title) -> str` / `decode_highlight_title(token) -> str | None`
  (single-sourced: the writer, the parser and `trails_app.main()` share the 120-character rule).
- `parse_trails_request(value) -> (id, TrailsRequest | None) | None`,
  `TrailsRequest(handle, task, highlight: tuple | None, total: int, direction: str, title: str)`.
  `parse_trails_focus_target` stays (older grammar); a test pins that it refuses the highlight form —
  the reason the capability gate exists.
- `launch_or_focus_trails(session, root, handle, task_id=None, highlight=None, direction=None,
  title=None)`: validates before tmux (empty list → error; a slug outside `DIRECTION_RE` or a title
  breaking the single-line / 120-character rule → error); a valid slug longer than 512 characters is
  **left out** with the warning "direction id too long to send — the trail opens with the title only"
  (the highlight and the trail still go out); de-duplicates preserving caller order; more than
  `HIGHLIGHT_MAX` → first 256, `of=<total>`, warning "highlighting the first 256 of <total> tasks".
  Warnings accumulate (one string, `; `-joined), so a truncation and a dropped slug are both
  reported. Warm path: receiver advertises the highlight capability → full form;
  otherwise today's task/bare fallback plus "the running ait trails cannot highlight a direction —
  restart it to see the overlay" (the trail still opens). Cold path: `trails_supports_highlight(root)`
  probes `'"--highlight"'` in `trails_app.py`; supported → argv `--highlight=<csv>
  [--highlight-total=<n>] [--highlight-direction=<slug>] [--highlight-title=<title>]` — the
  single-token `--opt=value` form for every value (argparse keeps a value that starts with `-`, e.g.
  `--highlight-title=--follow-up`), argv form, no shell, the raw title — else the trail opens and the
  warning says so. (`--trail` / `--task` keep their current two-token form: their grammars cannot
  start with `-`.) Without `highlight` every
  tmux call is byte-identical to today.

### 6. Overlay state + rendering (shared renderer; the board stays without an entry point)

- `board_trail_screen.TrailSession`: `highlight: tuple = ()`, `highlight_total: int = 0`,
  `highlight_direction: str = ""`, `highlight_title: str = ""`, `overlay_states: dict | None = None`
  (None = advice not available for the current inputs), `overlay_gen: int = 0`, `overlay: object = None`
  (the last `CriticalPath`). View state only — nothing writes the trail artifact.
- `board_trail_view.py`:
  - `overlay_for_entry(ref, result, freshness) -> (kind, note)` — `kind` ∈ `highlight|path|advisory|""`.
  - Markers (`markup=False`), glyph **plus** a text attribute, distinct from `◆ ▲ ● ⇄ ○` and
    `✔ ⚠ 🌐 ↗ 👻`: highlighted, one note per readiness value — `★ direction · landed` /
    `· cleared for dependents, awaiting landing` (released) / `· unresolved (<reason>)` /
    `· blocked by <n>` / `· readiness unverified (cross-repo)` / `· in progress` /
    `· on hold (<status>)` / `· next` — (bold) with a `heavy` idle
    border (a landed highlighted card keeps its existing `✔` strike-through title as well); critical
    path, likewise per value — `» critical path · awaiting landing` (released) /
    `· unresolved (<reason>)` / `· blocked` / `· readiness unverified (cross-repo)` / `· in progress` /
    `· on hold (<status>)` / `· next` (bold); advisory `› advisory predecessor` (italic); `next` qualified per
    the advice contract. A card whose own xdeps block is never `next` — consistent with its existing
    `🌐 blocked (cross-repo)` line, because both read `session.xdep`.
  - `TrailTaskCard` / `TrailGhostCard`: `compose` yields the marker Label (class `trail-overlay`, right
    after the title) only when the view carries an overlay — a view without one composes exactly as
    today. `apply_overlay(kind, note)` updates the card **in place** (mount / update / remove that one
    Label; reset the idle border, a focused card keeping its focus border until blur). No remount.
- `TrailScreenMixin._build_active_trail_lanes`: with a non-empty `highlight`, compute the overlay when
  `session.overlay_states` is available — `critical_path(..., states=session.overlay_states,
  remote=session.xdep, remote_pending=session.xdep_inflight)` with the session's drift verdict (the
  function separates "checking" from "rechecking" by whether a completed result exists) — store
  it on `session.overlay` and attach `(kind, note)` to the views; with `overlay_states is None`:
  highlight markers only (state-free) and `session.overlay = None`. No highlight → no-op — the board's
  case: it has no flag, no mailbox and no key that sets one, so it is left out, and the docs say so.
- `TrailScreenMixin._refresh_trail_overlay()`: recompute for the active session and `apply_overlay` on
  every attached trail card + refresh the banner — the in-place path for the states worker, a drift
  result and a clear.

### 7. `ait trails` — `board/trails_app.py`

- `main()`: `--highlight IDS` (needs `--trail`; csv; `t` prefix dropped; each `HIGHLIGHT_ID_RE`;
  1–256 ids), `--highlight-total N` (needs `--highlight`; ≥ the id count), `--highlight-direction SLUG`
  (`DIRECTION_RE`, ≤ 512 characters) and `--highlight-title TITLE` (need `--highlight`; validated by
  the shared helpers). The help text and docs show the `--highlight-title=<title>` form, which is
  what keeps a title starting with `-` a value. Refused before
  the TUI starts. Passed as `initial_highlight` / `initial_highlight_total` /
  `initial_highlight_direction` / `initial_highlight_title`.
- **Overlay lifecycle** — one method owns invalidation, `_invalidate_overlay(session)`:
  `session.overlay_states = None`, `session.overlay = None`,
  `session.overlay_gen = self._bump_trail_gen()` (unique, monotonic). Called on every input refresh or
  replacement: `_load_trail_tasks` (`r`, for every session), trail reload and watch reload (that
  session), a new highlight on that session, clear (`h`), and tab close. After invalidation, a session
  that still has a highlight starts the worker with the new gen.
- **States worker, off the render path**: `@work(thread=True, group="trails_overlay")
  _trail_overlay_states_worker(session, gen)` runs `trail_task_states.resolve_for_trail`;
  `_on_trail_overlay_states(session, gen, states)` applies only when `self._trail_sessions.get(
  session.handle) is session and session.overlay_gen == gen` — so a clear, a replacement or a close
  (and a close + reopen, which creates a new session object) retires the result. Applying stores the
  states and, for the active session only, calls `_refresh_trail_overlay()` (in place: focus and
  `_pending_card` untouched). The existing xdep and drift callbacks already re-render the active tab
  and therefore recompute the overlay with the new remote statuses / verdict; they do not invalidate
  the local states.
- **Newly discovered cross-repo keys on `r`** — no second probe path. For a session with a highlight,
  after `_load_trail_tasks`, compute `keys = remote_keys(...)` from the reloaded tasks. If any key has
  neither a completed result in `session.xdep` nor a place in `session.xdep_inflight`, call the
  **existing** `_start_session_xdep(session)`: the one full worker, over the latest key set. Its
  contract is unchanged and already safe under overlap: it draws a new `xdep_gen`, sets
  `xdep_inflight` to the **whole** new key set, and `_on_trail_xdep` accepts only the newest gen and
  then **replaces** `session.xdep` and clears `xdep_inflight`. So:
  - a second `r` that discovers another key starts another full probe; the older one's completion is
    discarded by gen, and the newest one covers every key — no key is left in `xdep_inflight` by a
    rejected completion, because the accepted (newest) completion clears the whole set;
  - a full probe started earlier by `d` / a reload that lands later is likewise discarded by gen and
    cannot overwrite the newer result;
  - cached results stay shown while the new probe runs (existing behaviour), and the overlay treats a
    new key (no completed result) as `checking` and a known key under the new probe as **rechecking**:
    its previous result stays visible and still decides blocked / clear, but a `next` that relies on
    it is shown qualified — `next? (rechecking cross-repo)` — until the probe lands, and the banner
    says `rechecking <n> cross-repo prerequisite(s)…`. A cached `Done` can therefore never produce a
    plain `next` while it is being re-read.
  When no key is new, `r` starts nothing — and a session **without** a highlight never takes this
  branch, so its `r` stays zero-subprocess as today. While a new key is pending, the banner shows
  `checking <n> cross-repo prerequisite(s)…` and the cards their existing `(checking…)` suffix.
  Cost, stated: a newly found key re-probes the session's other keys too (one status subprocess each).
- Request state: `_deliver_trail_focus(handle, task=None, highlight=None, total=0, direction="",
  title="")`; the held-back `_pending_trail_focus` tuple carries the new fields; a resumable
  `_pending_overlay = (seq, handle, highlight, total, direction, title)` is cancelled by the
  `_trail_active` setter when the active handle moves elsewhere (the `_pending_card` rule) and by a
  newer request. Consumed at render time (a `_build_active_trail_lanes` override: matching handle +
  current seq → write it into the session, `_invalidate_overlay`, kick the worker, render), so a fresh
  trail shows the highlight markers on its first render. For the trail that is **already active**,
  `_activate_trail` consumes it and applies it with `_refresh_trail_overlay()` (in place). A request
  **without** `hl=` leaves an existing overlay on that tab alone; one with `hl=` replaces it.
- Mailbox: poll parses with `parse_trails_request`; registration stamps `mark_trails_highlight(pane)`
  after `mark_trails_card_focus` and before `mark_trails_receiver`; `on_unmount` unstamps the receiver
  first, then both capabilities.
- Overlay banner: a one-row `TrailOverlayBar(Static)` under the tab strip (hidden without an overlay),
  `markup=False`, refreshed from `_refresh_subtitle` and `_refresh_trail_overlay`; shed right-to-left:
  `★ direction: <title> · 3 highlighted · » 4 on the critical path · › 1 advisory · 2 outside the trail (not followed) · 1 cross-repo blocker · 1 not in trail · 2 unresolved · next t12 · h clears`
  — `direction: <slug>` when there is no title, `highlight:` when neither; the title elided with `…`
  before any count is shed; zero-count segments omitted; `(showing 256 of 300)` right after the
  highlighted count when truncated (never shed); `resolving task states…` while `overlay_states` is
  None; the `next` segment qualified per the advice contract. Kept off the header banner so its
  freshness shedding ladder stays byte-identical.
- Tab label: `trail_tab_label` appends ` ★` for a session with a highlight (unchanged otherwise).
- Clear key: `Binding("h", "trail_overlay_clear", "Clear Highlight")`, a trails-only row like
  `TRAIL_TAB_BINDINGS` (`h` is bound nowhere in the board scope); `check_action` shows it only when the
  active session has a highlight; it clears that tab's highlight, `_invalidate_overlay`, applies in
  place and notifies "Highlight cleared".

### 8. Docs

- `aidocs/framework/tui_conventions.md` (the trails part of "The board package"): the overlay
  contract — per-tab view state in `TrailSession`, never written; the local resolver off the render
  path, remote statuses from the session's xdep probe; the invalidation + generation rule; in-place
  marker updates; the capability stamp and fallback; the truncation rule; slug vs title; the marker
  vocabulary; board out of scope.
- `website/content/docs/tuis/trails/reference.md`: launch rows for `--highlight` /
  `--highlight-total` / `--highlight-direction` / `--highlight-title`, key `h`, a markers table
  (★ » ›, heavy border, `next?`); `how-to.md`: "Show a direction's tasks in a trail" — what blocks and
  what does not (classification rule, gate-released tasks, cross-repo prerequisites, outside
  prerequisites not followed), why a `next` can be qualified, why markers disappear briefly after `r`.
  Current-state prose only. Then `cd website && python3 check_links.py --build`.
- `lib/trail_gather.py` docstring: the `critical-path` verb, its line protocol and the advice contract.
- `lib/dep_resolution.py` docstring: `lookup()`'s precedence-strict tri-state and why `facts()` stays
  two-state.

### 9. Notes to the consuming siblings (after the code commit)

Both siblings already exist and name this child's output, so the contract goes to them as notes
(`/aitask-note`, `./ait note <id> --from 2335_3 --file -`), written against the commit that lands it:

- **t2335_4** (skill): the `critical-path` verb and its line protocol; NEXT = pick eligibility
  (`IN_PROGRESS` / `ON_HOLD` are not picks); the freshness qualifier on every NEXT; `released` =
  cleared for dependents, awaiting landing; outside and cross-repo prerequisites reported and not
  followed; `unverified` for foreign members.
- **t2335_5** (TUI tab): the `launch_or_focus_trails(…, highlight=, direction=, title=)` signature; the
  256-id cap with `of=` and its warning; the slug bound and its warning; warnings are `; `-joined;
  the older-receiver fallback warning.

### Post-phase (risk mitigations)

1. [request_flow_order_tests] In `tests/test_trails_app.py`, add `OverlayRequestOrderTests`
   (pilot, with the `_PaneStore` / `_Modal` helpers of `TrailFocusTests` / `TrailCardFocusTests`). One
   test per arrival order, each asserting **both** the overlay (which cards carry ★/», the banner text)
   and the focused card: (a) overlay request while a modal is open → applied on resume; (b) request for
   an unknown handle → applied after the one rescan finds it; (c) request A superseded by request B
   before A's rescan lands → only B's overlay exists; (d) pending overlay for trail X, user switches to
   tab Y → cancelled, X opens later without it; (e) request for the **already active** trail → applied
   in place, focus kept; (f) `hl=` + task together → overlay and card focus both land; (g) a plain
   request (no `hl=`) for a tab with an overlay → the overlay stays; (h) the states worker lands after
   the user switched tabs → stored on its session, the active tab untouched; (i) **worker before
   focus** — the requested card ends focused, markers correct, no "card is not visible" notice;
   (j) **worker after focus** — focus stays, the card widget is the same object (no remount);
   (k) **`r` with a delayed worker** — between `r` and the worker landing no card carries a path / next
   marker and the banner says `resolving task states…`; after it lands the markers match the new
   states; (l) **clear while a result is pending** — the late result is discarded, no marker
   reappears; (m) **close + reopen while a result is pending** — the old session's result is discarded
   and the reopened tab's own worker decides.
2. [board_render_parity_test] In `tests/test_board_bytrail_view.py`, render the board's By-Trail view
   for a fixture trail and assert every card's label texts and idle border style equal the no-overlay
   values (no ★/»/› label, no `heavy` border); assert also that `KanbanApp` declares no
   `trail_overlay_clear` binding and that its sessions never carry a highlight.

## Tests

- `tests/test_local_dep_parity.py` (extend; the existing `dep_resolution` suite): `lookup()` — FOUND;
  UNREADABLE for an unreadable file and for unparseable frontmatter; **active-directory stat failure
  and active-directory listing failure, each with a loose archived Done copy present → UNREADABLE,
  never the archived copy**; the same for a child id's `t<parent>/` directory; ABSENT only when every
  location is confirmed absent; `facts()` / `classify()` outputs unchanged on the same fixtures.
  (Stat and listing failures are injected by patching `os.stat` / `os.listdir` for one path, so the
  tests do not depend on running as non-root.)
- `tests/test_trail_task_states.py` (new, fixture trees): active Done / Ready / Folded; loose archived
  Done; ABSENT + bundled Done (`done`, `reason=bundle`) and bundled non-Done; **malformed active file
  with a Done copy loose and bundled → `unresolved:unreadable`**; **active-dir stat failure with a
  bundled Done copy → `unresolved:unreadable`**; missing; malformed `depends:`; bad dep token;
  gate-released upstream → `released`; xdep pairs read; pass 2 stops at outside refs.
- `tests/test_trail_critical_path.py` (new, pure, states and remote given as dicts): chain; diamond;
  advisory-only edges; later-wave highlight with no explicit edge (earlier-wave `hard_prerequisite` on
  the path, `core` / `preferred_predecessor` advisory, `optional` / `coordination_only` absent,
  same-wave peers absent); earlier-wave `optional` entry with an explicit hard dependency → on the
  path; done predecessors; live dependency removed (`superseded`, dependent NEXT) and added (new
  blocker); unavailable live depends fall back to saved edges; gate-released A with direct dependent B
  and later-wave successor C (A `released`, B NEXT, C blocked, A neither NEXT nor landed); missing and
  unreadable hard prerequisites; a ref absent from `states`; **a task whose xdep is open (blocked, not
  NEXT), Done (NEXT), unchecked / pending (unresolved, not NEXT), NOT_FOUND (blocked)**; a foreign
  member resolved from `remote`; **a highlighted foreign `Ready` member with no known blocker →
  readiness `unverified`, 0 blockers**; **a highlighted Done task → `landed`, no blockers, not
  expanded, not NEXT; a highlighted released task → `released`**; **three otherwise identical tasks
  with zero blockers and status `Ready` / `Postponed` / `Implementing` → `next` / `on_hold` /
  `in_progress`, and only the `Ready` one in `next_actionable`** (plus `Editing` and an empty status →
  `on_hold`; a `Postponed` task **with** a blocker → `blocked`); **a cached-`Done` xdep key listed in
  `remote_pending` → the node keeps `next` with `rechecking=True`; without the pending flag
  `rechecking=False`**; a property check over every fixture
  that `blocked` always has ≥ 1 blocker and every highlighted / path node has exactly one readiness
  from its allowed set (the function raises on a state it cannot classify); an outside chain longer than four (only the first reported); a
  non-member highlight; empty highlight set; lite trail; two highlighted tasks blocking each other; a
  cycle; canonicalization; deterministic order.
- `tests/test_trail_gather.py`: `CriticalPathVerbTests` over `SyntheticRepo` — protocol lines,
  `bad_highlight`, `invalid_trail`, `FRESHNESS:current` with unqualified NEXT; dependency added after
  trail creation (new blocker, dependent not NEXT, `FRESHNESS:stale|…dependency_changed…`, remaining
  NEXT `|stale`); dependency removed (`SUPERSEDED:`, dependent NEXT `|stale`); **an xdep with
  `probe_xdep_status` stubbed to `Implementing` then `Done`** (`XDEP:…|blocked` and no NEXT, then
  `XDEP:…|clear` and NEXT); a wrapper test that `critical-path --trail art:…` is resolved like `drift`.
- **CLI/TUI parity** (`tests/test_trails_app.py`, `OverlayParityTests`), one fixture tree + trail,
  sets compared from the CLI lines and `session.overlay` (highlight / path / advisory / outside /
  released / cross-repo / next): (1) highlighted B depends on outside task A — both say B blocked by
  A; mark A Done, rerun the CLI and press `r` — both say B is NEXT; (2) highlighted C carries an xdep
  with the probe stubbed to `Implementing` (the TUI through its xdep worker, the CLI through the same
  function) — both say C blocked and the card also shows `🌐 blocked (cross-repo)` with no `next`
  marker; switch the stub to `Done`, press `d` in the TUI and rerun the CLI — both say C is NEXT;
  (3) **edit-and-refresh**: D has no xdep and is NEXT; add an xdep naming an already-`Done` remote task
  to D's file, rerun the CLI (NEXT, `XDEP:…|clear`) and press `r` in the TUI — the new key appears in
  `xdep_inflight`, D's card shows `(checking…)`, the overlay is not NEXT and the banner says `checking 1
  cross-repo prerequisite…`; once the (full) probe lands, D is NEXT and the sets match the CLI. A
  variant with the remote task `Implementing` ends `blocked` in both. A control: the same edit without a
  highlight leaves `r` zero-subprocess (no probe call recorded); (4) a highlighted **foreign member**
  whose probe returns `Ready`, with no known blocker → `unverified`, 0 blockers, not NEXT, in both;
  (6) three highlighted tasks with zero blockers and status `Ready` / `Postponed` / `Implementing` →
  the CLI emits `NEXT:` for the first only, `ON_HOLD:…|Postponed` and `IN_PROGRESS:…|Implementing` for
  the others, and the cards read `★ direction · next`, `· on hold (Postponed)` and `· in progress`;
  (5) a highlighted **Done** task → `HIGHLIGHT:…|done|landed|0|-` in the CLI and `★ direction · landed`
  on its card, never NEXT and never a blocker; a highlighted **released** task →
  `HIGHLIGHT:…|released|released|…` and `★ direction · cleared for dependents, awaiting landing`.
- **Overlapping remote checks** (`tests/test_trails_app.py`, `OverlayXdepOverlapTests`, pilot with a
  controllable `probe_xdep_status` stub that blocks until released): (a) edit 1 adds key K1, `r`; edit 2
  adds key K2, `r` while the first probe is still running; release the **first** probe, then the second
  → both keys end with completed results, `xdep_inflight` is empty, the overlay matches the CLI;
  (b) the same, releasing the **second** probe first, then the first → the late first result is
  discarded, both keys still resolved, `xdep_inflight` empty; (c) a later `r` after either order starts
  no probe (nothing new) and a further edit adding K3 does start one — proving no key is stuck in
  flight; (d) `d` (full refresh) pressed while an `r`-started probe runs, completing in both orders →
  the newest probe's results stand and are never overwritten by the older one; (e) while a re-probe of
  already-resolved keys runs, their cards keep their previous verdict but a `next` reads
  `next? (rechecking cross-repo)`, never plain `next`; (f) **a delayed probe that turns a cached `Done`
  into `Implementing`**: before it lands the card shows `next? (rechecking cross-repo)` and the banner
  `rechecking 1 cross-repo prerequisite…`; after it lands the card is `blocked` with the `🌐 blocked
  (cross-repo)` line and no `next`; the same with the new result `NOT_FOUND` / unreachable.
- `tests/test_trails_focus_writer.py`: grammar (bounds, `of=`, `direction=`, `title=` encoding and
  its 120-character / no-line-break rule, whole-or-nothing); `parse_trails_focus_target` refuses the
  highlight form; capability read; writer: capable receiver → full form, older receiver → task/bare
  form + warning, cold path with/without `--highlight` support, invalid input refused before tmux,
  no-highlight argv unchanged; 65 ids delivered whole; 257 ids → first 256 in caller order, `of=257`,
  the warning, the trail still opens; duplicates collapse before counting; **the titles `Stabilize CI`,
  `Ünïcode | pipes ★`, `--follow-up` and `-x` survive the cold-path argv (parsed back through
  `trails_app.main`'s real parser) and the mailbox payload** (decoded back exactly); **a 65-character
  slug** is sent whole; **a 600-character slug** is left out with the warning while the highlight and
  the trail still go out; a truncation and a dropped slug together produce both warnings.
- `tests/test_trails_focus_mailbox_live.py`: a highlight request with `of=`, `direction=` and a
  `title=` holding spaces round-trips through a real pane option; the capability stamp is read back.
- `tests/test_trails_app.py` (pilot): `--highlight` boot marks the right cards (text, heavy border),
  banner `direction: Stabilize CI · …`, `resolving task states…` before the worker lands; a mailbox
  request with a spaced title shows the same banner; a title with a control character renders it as
  `�`; `h` clears in place and is hidden afterwards; overlay per tab; a drift result updates the `next`
  qualifier; a truncated request shows `(showing 256 of 300)`; the banner names outside and cross-repo
  prerequisites as not followed; `main()` flag validation.
- Regression suites that must stay green: those in the pre-phase list, plus
  `tests/test_no_lib_to_tui_import.sh` (the new lib modules import nothing from a TUI directory);
  `shellcheck` on the wrapper.

## Verification

```bash
~/.aitask/venv/bin/python -m pytest tests/test_local_dep_parity.py tests/test_minimonitor_pick_by_number.py \
  tests/test_trail_task_states.py tests/test_trail_critical_path.py tests/test_trail_gather.py \
  tests/test_trails_focus_writer.py tests/test_trails_focus_mailbox_live.py tests/test_trails_app.py \
  tests/test_board_bytrail_view.py tests/test_board_trail_view.py tests/test_trail_screen_host_protocol.py \
  tests/test_sitrep_tui_trails_actions.py -q
bash tests/test_no_lib_to_tui_import.sh
shellcheck .aitask-scripts/aitask_trail_gather.sh
./.aitask-scripts/aitask_trail_gather.sh critical-path --trail <a real art: handle> --highlight <member ids>
(cd website && python3 check_links.py --build)
```

Manual: `ait trails --trail <handle> --highlight <ids> --highlight-direction demo --highlight-title "Stabilize CI"`
— markers, banner, `h`, tab switching, `r` after changing a prerequisite's status (end-to-end coverage
belongs to t2335_6).

## Risk

### Code-health risk: medium
- The trails request state machine (`_pending_trail_focus` / `_pending_card`, modal hold-back, rescan, the `_trail_active` setter — t2211_10) is intricate; widening its tuples, render-time overlay consumption, invalidation and an async states worker can regress card focus or a held-back request · severity: medium · → mitigation: inline pre-phase baseline_trails_suites, inline post-phase request_flow_order_tests
- The overlay lives in the renderer and cards the board's By-Trail view shares; a defect could change the board's cards even with no highlight · severity: low · → mitigation: inline post-phase board_render_parity_test
- `dep_resolution` is the parity core of `ait ls`, the board and the minimonitor; the new `lookup()` and `_dir_state()` must not change `facts()` / `classify()` / `_dir_identity` · severity: medium · → mitigation: inline pre-phase baseline_trails_suites (includes the dep_resolution suites) plus the unchanged-output tests in §Tests
- Mailbox grammar grows (ids, `of=`, `direction=`, encoded `title=`); an older running receiver must never be sent a form it refuses (capability gate + fallback planned) · severity: low · → mitigation: none needed beyond the planned writer and live-mailbox tests

### Goal-achievement risk: medium
- The critical-path rule is an interpretation of the schema and the documented classifications (classification-aware wave edges, live depends authoritative, `released` satisfying depends but not waves, cross-repo prerequisites blocking readiness, outside prerequisites not followed, only verified-Done clears); child t2335_4's skill quotes it, so a wrong shape means rework there · severity: medium · → mitigation: critical_path_rule_review
- "The banner names the overlay" is delivered as a dedicated overlay row under the tab strip, not inside the header banner, to keep the header's freshness-shedding ladder unchanged · severity: low · → mitigation: none (stated in the plan for approval)

### Planned mitigations
- timing: pre-phase | name: baseline_trails_suites | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: request-state-machine and dep_resolution regressions (code-health) | desc: record the trails/board-trail/gather/focus-writer/dep-resolution suite results before any edit
- timing: post-phase | name: request_flow_order_tests | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: request-state-machine regression (code-health) | desc: pilot tests for every overlay-request, states-worker and invalidation order, asserting overlay and card focus together
- timing: post-phase | name: board_render_parity_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: shared-renderer risk to the board (code-health) | desc: board By-Trail cards unchanged without a highlight, and the board has no highlight entry point
- timing: before | name: critical_path_rule_review | type: chore | priority: medium | effort: low | inline_risk: medium | added_complexity: low | addresses: critical-path interpretation (goal-achievement) | desc: review the critical-path rule and advice contract in the t2335_3 plan (classification-aware wave edges, live depends authoritative with superseded saved edges, the released state, cross-repo readiness via the xdep rule, NEXT as pick eligibility (status Ready) with `in_progress` / `on_hold` beside it, the readiness enum including `unverified` for foreign members, outside prerequisites not followed, verified-Done-only clearance, freshness qualifiers, slug vs title) against how t2335_4's skill will quote it, and record the confirmed rule or the corrections in the t2335_3 plan before implementation | created: t2367

## Step 9 (Post-Implementation)

Commit code and plan separately per the workflow, then Step 9: archival of t2335_3 via the standard
post-implementation procedure (current-branch mode, no merge).
