---
Task: t1912_5_stats_migration_and_registry_split.md
Parent Task: aitasks/t1912_move_codeagent_stats_to_plumbing_branch.md
Sibling Tasks: aitasks/t1912/t1912_*_*.md
Archived Sibling Plans: aiplans/archived/p1912/p1912_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-16 17:09
---

# t1912_5 — Stats migration + registry split (plan, verified 2026-11-16)

## Context

t1912_1–4 moved every stats **write** onto the `aitask-stats` orphan branch.
The legacy counters (`usagestats` / `verifiedstats`) in
`aitasks/metadata/models_<agent>.json` are now frozen, and the readers add
them to the branch counters until a per-agent marker
(`migrations/<agent>.json`) exists. This task moves those counters into the
branch exactly once. It strips them from the registry, and makes sure nothing
re-adds them. The protocol in the task file (steps 1-6, uniqueness, no-remote
mode, the transient window) is **normative**: it was hardened over three
review rounds. This plan implements it as written.

## Verification findings (what changed since the plan was written)

- **`current_task_branch` does not exist.** The data-branch rule is
  `_ait_detect_data_worktree` in `lib/task_utils.sh`: a `.aitask-data`
  worktree at the toplevel ⇒ branch mode (its checked-out branch, normally
  `aitask-data`); otherwise legacy (the root's checked-out branch). The
  migrate module restates the rule in Python:
  - detached HEAD ⇒ `MIGRATE_DEFERRED:detached_head`;
  - a linked worktree with no `.aitask-data` of its own ⇒
    `MIGRATE_DEFERRED:linked_worktree`. Treating it as legacy would push a
    strip to the crew branch.
- **Store API (t1912_1/_4, read in tree):**
  - `mss.update(root, agent, fn, return_commit=True)` handles one path only.
    The absorb must write `<agent>.json` and the marker in one commit, so the
    write loop is generalised (Step 1).
  - Every store commit must keep the `Stats-Write-Id` nonce.
  - The loader only tests that a marker exists. `effective_total` reads the
    marker from the written commit, so once the marker lands the writers
    print branch-only totals with no change on their side.
- **`orphan_ref_store`** provides `fetch_pinned` (private temp ref),
  `build_commit` (private index), `cas_push` (leased; OK / CONFLICT / ERROR),
  `cas_local`, `read_file` and `is_ancestor`.
  - The remote strip pushes `aitask-data` and **never moves the local
    `refs/heads/aitask-data`** (it is checked out in `.aitask-data`), its
    worktree or its index.
  - `fetch_pinned` may update `refs/remotes/origin/aitask-data` along the
    way, as t1912_1 observed. That is harmless, and the untouched-worktree
    test asserts HEAD, index, status and the local branch ref, not the
    tracking ref.
- **jq byte stability:** all six `models_*.json` files (3 live, 3 seed) are
  byte-identical under `jq .` (jq 1.8.2). One jq filter therefore strips
  byte-stably on every path.
- **The trailer scan must not be path-limited.** Default history
  simplification can hide S1 behind a merge that is TREESAME on the path.
  Worse, an empty baseline is TREESAME to its parent and is dropped by any
  pathspec, `--full-history` included. The scan walks the whole tip history,
  narrowed by `--grep` and decided by the parsed trailers.
- **OpenCode merge must keep carrying stats keys.** Dropping them before a
  marker exists would delete counters that were never absorbed. The new-row
  default (L165) is the only change there. The comment at L170-180 still
  describes the old counter writers; correct it to current state.
- **Refresh-code-models wrappers** (`.agents/`, `.opencode/`) only point at
  the `.claude` source and carry no stats text, so no port tasks are needed.
- **The settings TUI never writes `models_*.json`.** Only `import_all_configs`
  can re-add keys, so the import strips them.
- **New helpers are internal** (invoked by the migrate CLI and setup, never by
  a skill), so no permission-whitelist touchpoints apply, per
  `aitasks_extension_points.md`.

### Pre-phase (risk mitigations)

1. [store_write_regression_baseline] Before editing
   `lib/model_stats_store.py`, run and record per-file results (pass/fail
   counts):
   - `python3 -m pytest tests/test_model_stats_store.py -q`
   - `bash tests/test_model_stats_parity.sh`
   - `bash tests/test_model_stats_refresh_routes.sh`
   - `bash tests/test_usage_update.sh`
   - `bash tests/test_verified_update.sh`
   - `bash tests/test_verified_update_flags.sh`
   - `bash tests/test_stats_writers_leave_task_data.sh`

   Record the table in the plan's implementation notes. After Step 1, rerun
   the same set. Every file must keep its result, and a changed result is
   fixed, not waived.
2. [setup_install_suite_baseline] Before Step 6, run every test file that
   runs setup `main` or `install.sh` on a fixture. The list is built from
   `grep -l 'install.sh\|aitask_setup.sh' tests/*.sh` and filtered to those
   that execute the flow; record the list in the plan. Record per-file
   results. After Step 6, rerun the same list. Any new failure is
   investigated and fixed (for example, a fixture that must now expect the
   migration, or set `AIT_STATS_MIGRATE=0` where the suite tests something
   unrelated, with the reason stated).

## Steps

### 1. Generalise the store write loop (`lib/model_stats_store.py`)

- Add `write(project_root, render, *, message, timeout=None, remote="origin")
  -> UpdateResult`. `render(read)` receives `read(path) -> bytes|None` at the
  base the commit is built on. It returns `(changes, value)`, where `changes`
  is `{path: bytes|None}`, or `None` for "nothing to write".
  - On `None` the loop builds no commit and pushes nothing. It does
    **fast-forward the local read ref to the base it rendered against**
    (`advance_ref(L_REF, base)`, ff-only, so it never rewinds concurrent
    local progress), then returns
    `UpdateResult(value, None, "UNCHANGED:<advance outcome>")`.
  - This matters because readers read only `refs/heads/aitask-stats`. A
    no-op that validated a marker on origin's tip must leave the local
    readers seeing that tip (round 2, concern 2).
- Move the current `update` loop body into `write`, unchanged:
  - probe → ABSENT / pinned base;
  - the divergence rules;
  - `_test_hook` points `after_render`, `after_pin`, `after_push`;
  - `cas_push` / `cas_local`;
  - the post-OK never-raise rule.
- `_render` becomes `_commit(root, base, changes, message)`, which adds the
  `Stats-Write-Id` nonce.
- `update(...)` keeps its exact signature and behaviour as a thin adapter:
  `render = lambda read: ({path: render_blob(new)}, value)`, with
  `fn(parse_blob(read(path)))`.
- Add `marker_blob(...)` / `parse_marker(data)` helpers: JSON
  `{"schema":1, "agent", "migration_id", "strip_commit", "source_commit",
  "source_blob", "absorbed_runs", "absorbed_at"}`, rendered sorted with
  indent 2.
  - **There is no `source: none` form.** Every marker names a baseline S1,
    which may be an empty commit (review concern 1).
  - `source_blob` is `null` only when `S1^` had no registry file.
  - `parse_marker` raises `StatsError("malformed_marker")` on any other shape.
- **Publication gate for local-only migration markers (round 3).** Every
  stats push carries the whole local history. So the shared boundary in
  `write` decides what may be published, not the migrate command:
  - Before a remote push, compute `unpublished_markers(commit, remote_tip)`:
    every `migrations/<agent>.json` in the commit's tree that is absent from
    `remote_tip`'s tree or has a different blob there. With `remote_tip`
    None (origin ABSENT), that is every marker in the commit. Every agent
    counts, not only the one being written.
  - `write(..., marker_gate=None)`: when that set is non-empty, it goes to
    `marker_gate(markers: {agent: marker})`. The gate returns normally
    (publish) or raises.
  - **The default gate, used by every ordinary writer, holds the write
    locally.** Nothing is pushed; the write lands with
    `cas_local(L_REF, commit, local)` on top of the local history (in this
    situation `base` is always local, because only local-ahead or
    origin-ABSENT bases carry local-only commits).
  - The result is `UpdateResult(value, commit, "HELD_LOCAL:<agents>")`. The
    CLI's `_write` prints a stderr note: "stats recorded locally; an offline
    migration of <agents> is not published until `./ait setup` validates it".
    The `UPDATED:` line and exit 0 are unchanged, because the write is
    recorded.
  - Ordinary writers therefore never fetch the data branch, which keeps
    their task-data isolation (the t1912_4 acceptance test stays green).
    They only compare stats trees they already hold.
  - No-remote mode publishes nothing and is unaffected.
- `MarkerGate(root, tip)` is the migrate route's gate, a callable object.
  `tip` is the **validation tip V**: the newest data-branch commit known to
  be on origin. It is kept **separate from the absorb source** `S1^`, which
  never changes (round 4):
  - after a pin or re-pin, V = the pinned O;
  - after **our own** baseline (or residue) push returns OK, V = that
    pushed commit. The lease succeeded, so origin's data branch held exactly
    that commit at that moment, and a leased history is never rewound by
    this framework. A fresh S1 is O's child, so validating against the
    pre-push O would reject every first-run absorb;
  - in no-remote mode, V = the post-strip local HEAD, resolved by trailer
    and id rather than sampled.

  Each local-only marker, of every agent, is checked against V:
  - its `strip_commit` is a `Kind: baseline` commit for **that marker's
    agent** (trailer check);
  - it is an ancestor of, or equal to, V;
  - `source_commit` equals its first parent.

  Any failure raises `MarkerUnpublishable(agent, reason)`. The reason is
  `strip_unpublished` when the strip is reachable from the local data branch
  but not from O; otherwise `marker_not_in_source`.

  Validation is by sha, never by migration id: a rebased copy of an offline
  strip has another parent, so its absorbed counters came from a different
  source.
- Add `publish(project_root, gate, timeout=None, remote="origin") -> sha`. It
  makes origin hold the local stats history before anything relies on it
  (concern 2), runs `gate` on the local-only markers before any push, and
  uses the store's existing upgrade rules:
  - probe ERROR ⇒ `StatsError("unreachable:…")`;
  - ABSENT and a local ref ⇒ `cas_push(local, base=None)`;
  - present ⇒ `fetch_pinned` then:
    - local absent or an ancestor of R ⇒ `advance_ref` to R;
    - R strictly an ancestor of local ⇒ `cas_push(local, base=R)`;
    - otherwise `StatsDiverged`;
  - CONFLICT ⇒ retry (bounded, jittered);
  - no remote ⇒ return the local sha.
  - It returns the tip that local and origin now share. It never builds a
    commit.

### 2. Shared strip filter (`.aitask-scripts/lib/model_stats_strip.jq`)

```jq
if (.models | type) == "array"
then .models |= map(if type == "object" then del(.usagestats, .verifiedstats) else . end)
else . end
```

This is the one strip definition. It is used by the remote strip (Python
pipes the blob through `jq -f`), the no-remote helper, `--sync-seed` and the
seed strip (Step 7).

### 3. Migration module (`.aitask-scripts/lib/model_stats_migrate.py`, new, stdlib only)

**Context resolution.** `resolve_data_context(root)` returns
`(toplevel, data_worktree|None, data_branch, mode)` using the rule in the
findings above. The registry path inside the branch is
`<TASK_DIR or aitasks>/metadata/models_<agent>.json`, with the same
absolute-TASK_DIR fallback as `mss.metadata_dir`.

**Pure helpers:**
- `has_stats(blob)`: any row (an object) carries `usagestats` or
  `verifiedstats` under any value.
- `legacy_counters(blob)`: `{model: {key: map}}`, keeping only dict values,
  the same as `_read_legacy`.
- `count_runs(counters)`: the sum of normalised `all_time.runs` over both keys,
  every skill and every model.
- `strip_blob(bytes)`: runs `jq -f lib/model_stats_strip.jq`. A jq failure
  raises `StatsError("strip_failed:…")`.

**Trailer scan.** `find_baseline(root, tip, agent)` runs:

```
git log --reverse --grep=Stats-Migration-Agent: --fixed-strings
  --format=%H%x00%(trailers:key=Stats-Migration-Agent,valueonly,separator=%x2C)%x00%(trailers:key=Stats-Migration-Kind,valueonly,separator=%x2C)%x00%(trailers:key=Stats-Migration-Id,valueonly,separator=%x2C)%x1e
  <tip>
```

- **No pathspec (review round 2).** An empty baseline has the same tree as
  its parent, and any path-limited log omits it as TREESAME, even with
  `--full-history`.
- `--grep` only narrows the walk cheaply (legacy mode walks the code
  branch). The decision is made on the parsed trailers alone: exact agent
  match, kind `baseline` / `residue`, non-empty id. A commit that mentions the
  string in its body without being a trailer is ignored.
- `find_by_id` uses the same scan.

It returns the oldest `(sha, id)` whose agent == `agent` and kind ==
`baseline`, or `None`. A companion `find_by_id(root, tip, path, id)` returns
the commit carrying a given `Stats-Migration-Id`. S1 must have exactly one
parent (`rev-list --parents -n1`); otherwise `MIGRATE_ERROR:bad_baseline`.

**Strip identity is never sampled from a mutable ref (concern 3).** After any
strip lands, S1 is re-derived by `find_baseline` from the post-strip tip. The
same scan must also find our own `Stats-Migration-Id`
(`find_by_id`). Otherwise the result is
`MIGRATE_ERROR:<agent>|strip_not_found`.
- In remote mode the pushed commit sha is known exactly, and is checked
  against the scan.
- In no-remote mode an unrelated commit U landing right after the strip
  cannot be mistaken for S1, because U carries no trailer.

**Strip message.** One line plus trailers:

```
ait: Strip <agent> stats keys from the model registry (<kind>)

Stats-Migration-Agent: <agent>
Stats-Migration-Kind: baseline|residue
Stats-Migration-Id: <uuid4 hex>
```

**The cutover point is the baseline commit on the data branch, on every path
(concern 1).** When B carries no counters, the baseline is an **empty commit**
(same tree as O) with the same trailers, pushed with the same lease. The
empty-source case therefore goes through the one leased data-branch push, the
same as the counters case:
- A migrator that pinned an empty O loses its lease if an old-framework write
  lands first. It then re-pins and strips those counters as the baseline.
- If its empty baseline lands first, any later old-framework write is
  post-cutover residue.
- The uniqueness argument (at most one baseline per agent) now covers both
  cases. The marker always names that one S1, and the
  `marker_mismatch`-after-strip outcome becomes unreachable for compatible
  histories.

**Global pre-check, once per `migrate` run, before any agent cuts a
baseline (round 3).**
- Pin the data tip O. Classify the stats ref (read-only, as in step 2).
- Run `MarkerGate(root, tip=O)` over **every** local-only marker in
  the candidate stats tip.
- If any marker fails, every agent reports
  `MIGRATE_ERROR:<agent>|blocked:<bad agent>:marker_not_in_source`, or
  `MIGRATE_DEFERRED:<agent>|blocked:<bad agent>:strip_unpublished`. Nothing is
  stripped, published or absorbed.
- Otherwise a later agent's absorb would push an unpublishable marker of
  another agent. Its baseline would already be on origin, so the transient
  under-report would become indefinite.
- The `marker_not_in_source` diagnostic on stderr explains the fail-closed
  state: the offline migration absorbed a source that origin's registry
  history does not contain. It needs manual repair: discard the local
  `aitask-stats` marker history and re-run `migrate` against origin.
  Automatic repair is out of scope (recorded as an upstream follow-up
  candidate in the Final Notes).

**Per-agent protocol `migrate_agent(root, agent)`.** It returns a list of
result lines. Each agent run creates one `gate = MarkerGate(root, tip=O)`,
and every `mss.write` / `mss.publish` call below passes `marker_gate=gate`.
- `gate.tip` is moved to O' on every re-pin, and to the pushed commit right
  after a successful baseline or residue push.
- The absorb's source stays `S1^` throughout. The remote case is shown first; no-remote differs only in the
pin and strip primitives (below).

1. **Pin the source first.** Loop bounded by `MAX_ATTEMPTS` (8) with
   `mss._jitter`:
   - `probe_remote_branch(data_branch)`:
     - ERROR ⇒ `MIGRATE_DEFERRED:<agent>|unreachable`;
     - ABSENT ⇒ `MIGRATE_DEFERRED:<agent>|data_branch_absent`.
   - Otherwise `fetch_pinned(data_branch, tmp_prefix="refs/aitask-stats/migrate-tmp/")`
     ⇒ **O**. A failure ⇒ `MIGRATE_DEFERRED:<agent>|unreachable`.
   - Read **B** = `read_file(O, path)`. A missing file ⇒ no keys.
   - `_hook("after_pin", agent, O)`.
2. **Reconcile the stats ref before trusting a marker (concern 2).**
   - Fetch and classify the stats branch exactly as `publish` does, but write
     nothing yet. The candidate tip T is:
     - origin's tip when local is absent or behind it;
     - local when origin is ABSENT or strictly behind;
     - diverged ⇒ `MIGRATE_ERROR:<agent>|stats_diverged`;
     - unreachable ⇒ `MIGRATE_DEFERRED:<agent>|unreachable`.
   - Read the agent's marker M at T.
   - **M present** ⇒ validate it against the pinned source:
     - `M.strip_commit` must be a baseline commit for the agent (trailer
       check) **and** an ancestor of, or equal to, O. Then the marker belongs
       to this source history.
       - **Converge both refs to the validated state:** call
         `mss.publish(root, gate=gate)` (`gate.tip` = O). When T is
         local-only (origin ABSENT or behind)
         it pushes local, so the absorbed totals and the marker reach origin
         before anything acts on them. When T is origin's tip (local absent
         or behind) it fast-forwards `refs/heads/aitask-stats` to it, so this
         clone's readers show the migrated totals at once (round 2,
         concern 2). It never rewinds: `advance_ref` is ff-only, and local
         progress made meanwhile reads `ALREADY_NEWER`.
       - A publish failure ⇒ `MIGRATE_DEFERRED` (unreachable / contended)
         or `MIGRATE_ERROR` (diverged).
       - `publish` returns the shared tip T'. If T' ≠ T, re-read the marker
         at T'. If it now fails validation, restart at step 1: a concurrent
         migrator's newer S1 means O must be re-pinned.
       - Then go to 5 (residue).
     - `M.strip_commit` is reachable from the **local** data branch but not
       from O (an offline migration whose strip was never pushed) ⇒
       `MIGRATE_DEFERRED:<agent>|strip_unpublished`. Nothing is published,
       nothing is stripped, and `ait sync` publishes the data branch. The
       marker must not reach origin while origin's registry still holds
       counters that S1 did not cut.
     - Otherwise (an incompatible source history) ⇒
       `MIGRATE_ERROR:<agent>|marker_not_in_source`, failing closed.
   - **M absent** ⇒ continue. Any local-only stats history is published by
     the absorb write in step 4 (the store's existing ABSENT / local-ahead
     base rules).
3. **Find or cut the baseline.**
   - Run `find_baseline(O)` **before looking at B** ⇒ S1. Found ⇒ go to 4.
   - Not found ⇒ build the baseline:
     - `changes = {path: strip_blob(B)}` when `has_stats(B)`, else `{}`
       (the empty baseline);
     - `ors.build_commit(root, O, changes, msg(kind=baseline, id=new))`;
     - `_hook("before_strip_push")`;
     - `cas_push(root, commit, data_branch, O)`:
       - OK ⇒ re-derive S1 by trailer scan from `commit` (it must equal
         `commit` and carry our id), **set `gate.tip = S1`** (the published
         validation tip; the absorb still reads `S1^`), then
         `_hook("after_strip", agent, S1)`;
       - CONFLICT ⇒ restart at 1 (re-pin, re-reconcile, re-scan);
       - ERROR ⇒ `MIGRATE_DEFERRED:<agent>|push:<reason>`.
   - Exhausted attempts ⇒ `MIGRATE_DEFERRED:<agent>|contended`.
4. **Absorb + marker.** First `_hook("before_absorb", agent, S1)`, then
   `mss.write(root, render)`, where `render(read)` runs on every attempt
   against the re-read tip:
   - Marker present:
     - names S1 ⇒ `None` (no-op);
     - names anything else ⇒ raise `MarkerMismatch`.
   - Otherwise:
     - `legacy = legacy_counters(read_file(S1^, path))`;
     - `models = parse_blob(read(<agent>.json))["models"]`;
     - `new = mss.merge_stats(legacy, models)`;
     - changes = `{<agent>.json: render_blob({schema, models: new}),
       migrations/<agent>.json: marker}`.
     - The marker `migration_id` is S1's trailer id. `source_blob` is the
       blob id of `S1^:path`. `absorbed_runs` is `count_runs(legacy)`.
       `absorbed_at` is UTC ISO.
   - Output:
     - write landed ⇒ `MIGRATED:<agent>|<S1>|<runs absorbed>` (the local ref
       is advanced by the existing post-push rule);
     - no-op (a marker naming S1 found, possibly only on a retry) ⇒
       `MIGRATE_NOOP:<agent>|marked`, with the local ref fast-forwarded to
       that tip by `write`'s `None` rule;
     - `MarkerMismatch` ⇒ `MIGRATE_ERROR:<agent>|marker_mismatch`;
     - `StatsDiverged` ⇒ `MIGRATE_ERROR:<agent>|stats_diverged`;
     - other `StatsError` ⇒ `MIGRATE_DEFERRED:<agent>|stats:<reason>`. S1
       stays and is recovered by trailer next run.
5. **Residue,** reached after 4 or from step 2 with a validated, published
   marker:
   - re-pin O (step 1);
   - if `has_stats(B)`: `runs = count_runs(legacy_counters(B))`, strip with
     `Kind: residue` using the same leased loop (CONFLICT ⇒ re-pin; never
     absorb);
   - print `STRIPPED_RESIDUE:<agent>|<runs>`.
   - When the marker pre-existed and nothing was stripped, the agent's single
     line is `MIGRATE_NOOP:<agent>|marked`.
   - An agent with no registry file at O and no marker ⇒
     `MIGRATE_SKIPPED:<agent>|no_registry`, and no baseline is cut.

**No-remote mode** (`ors.remote_url(root) is None`):

**Source.** The committed data-branch HEAD (the data worktree's HEAD, or the
root's in legacy mode): O = `rev-parse HEAD`, B = `O:path`. Step 2's
reconciliation is local only. A marker is valid when its `strip_commit` is a
baseline for the agent and an ancestor of O; otherwise
`MIGRATE_ERROR:<agent>|marker_not_in_source`.

**Worktree state.** The worktree file must be one of:
- byte-equal to B (clean);
- byte-equal to `strip_blob(B)`: **the migration's own interrupted
  intermediate state** (concern 4). A run killed after the CAS rewrite and
  before the commit leaves exactly these bytes, and the retry resumes it by
  committing them as the baseline. A hand edit that happens to produce the
  same bytes is indistinguishable, and harmless: it is the stripped content
  the baseline commits anyway, and the absorb reads `S1^`, the unstripped
  committed blob.

Anything else ⇒ `MIGRATE_DEFERRED:<agent>|dirty`, and the file is never
touched.

**Strip with counters** (baseline or residue): a subprocess

```
bash .aitask-scripts/aitask_model_stats_strip.sh --path <path> \
  --expect-blob <B sha> --expect-stripped-blob <sha of strip(B)> \
  --message-file <tmp>
```

with `cwd=toplevel` (Step 4 below). Its outcome lines:
- `STRIPPED` ⇒ the commit landed;
- `STRIP_DEFERRED:<reason>` ⇒ `MIGRATE_DEFERRED`;
- `STRIP_ERROR:…` ⇒ `MIGRATE_ERROR`.

The helper prints **no sha**. Python re-reads HEAD and re-derives S1 (or
finds the residue commit) by trailer scan plus `find_by_id` (concern 3). An
unrelated commit that lands just after the strip carries no trailer and is
never taken for it.

**Empty baseline** (B has no counters): plumbing only, with no worktree or
index involvement:
- `commit-tree O^{tree} -p O` with the trailer message;
- then `update-ref refs/heads/<data_branch> <new> O`, a CAS against the
  pinned head. A miss ⇒ re-pin and re-scan.
- The tree is identical to O's, so the checked-out worktree and index stay
  consistent with the new HEAD by construction.

**Absorb** goes through the same `mss.write`, which already uses `cas_local`
when there is no remote. **Trailer recovery** scans local HEAD the same way.

**Seams.** `_hook(point, **ctx)` is a module-level no-op that tests replace
in-process. The points are `after_pin`, `before_strip_push`, `after_strip`
and `before_absorb`. A test can raise from `after_strip` to simulate a crash,
or run a second migrator inside `before_absorb` to stage a race
deterministically.

**`migrate(root, agent=None)`:**
- Agents = `--agent`, or every `models_<a>.json` (`a` matching `AGENT_RE`) in
  the first pinned O's metadata tree. A source that cannot be pinned ⇒ one
  `MIGRATE_DEFERRED:all|<reason>` line.
- Each agent runs independently. A failure in one never stops the rest.

### 4. No-remote strip helper (`.aitask-scripts/aitask_model_stats_strip.sh`, new)

Usage:

```
--path <repo-rel> --expect-blob <sha> --expect-stripped-blob <sha> --message-file <f>
```

It is built from the shell conventions: `set -euo pipefail` and sources of
`task_utils.sh` and `lib/registry_cas.sh`.
- `dest = $_AIT_DATA_WORKTREE/<path>` (via `_ait_detect_data_worktree`).
- Render function:
  - `git hash-object <snapshot>` must equal `--expect-blob` **or**
    `--expect-stripped-blob` (the resume case). Otherwise set
    `STRIP_REASON=dirty` and `return 1`.
  - Then `jq -f "$SCRIPT_DIR/lib/model_stats_strip.jq" <snapshot>`. This is
    idempotent: stripping already-stripped bytes reproduces them, as the jq
    byte-stability measurement shows.
  - Per the `registry_cas.sh` contract it returns and never exits.
- `ait_cas_rewrite "$dest" 3 render`:
  - rc 1 ⇒ `STRIP_DEFERRED:${STRIP_REASON:-render_failed}`;
  - rc 2 ⇒ `STRIP_DEFERRED:contended`.
- Test seam `AIT_STATS_STRIP_AFTER_REWRITE_HOOK` (same shape as
  `AIT_CAS_BEFORE_SWAP_HOOK`) runs here, between the rewrite and the commit,
  with `AIT_STATS_STRIP_PID=$$` exported. The termination test uses it to
  SIGKILL the helper.
- Then `aitask_task_commit.sh -m "$(cat msgfile)" "$path"`.
  - `COMMITTED:` ⇒ print `STRIPPED`. **No sha is sampled from HEAD**
    (concern 3).
  - Any other result ⇒ **roll back**: CAS-rewrite the file back to the
    saved pre-rewrite snapshot, but only while it still holds the stripped
    bytes. Print `STRIP_DEFERRED:commit_failed:<detail>`.
  - The rollback covers a *reported* commit failure. A *killed* helper is
    covered by the resume rule above, which the next run applies from a
    fresh process.
- Exit 0 on `STRIPPED`, 2 on deferred, 1 on error. shellcheck must be clean.

### 5. CLI verb (`aitask_model_stats.py migrate [--agent X] [--root R]`)

- Prints the result lines from Step 3 (one or more per agent). Diagnostics
  go to stderr.
- Exit 0 unless a `MIGRATE_ERROR:` line was printed (then 1) or there was a
  usage error (2).
- Update the module docstring's verb table.

### 6. Setup / upgrade hooks

`aitask_setup.sh` gets a new `setup_model_stats_migration` function:
- Returns 0 unless inside a git work tree. `AIT_STATS_MIGRATE=0` opts out
  (same shape as `AIT_HOME_MIGRATE`).
- `py=$(resolve_python)`. If none ⇒ `warn` with
  `MIGRATE_DEFERRED:all|no_python` and return 0.
- `info "Moving code-agent stats to the aitask-stats branch..."`, then
  `out=$(cd "$project_dir" && "$py" "$SCRIPT_DIR/aitask_model_stats.py" migrate --root "$project_dir" 2>&1) || true`.
- Per line:
  - `MIGRATED` / `MIGRATE_NOOP` ⇒ `success` / `info`;
  - `STRIPPED_RESIDUE` ⇒ `warn` ("discarded N runs an older framework wrote
    after the cutover");
  - `MIGRATE_DEFERRED` ⇒ `warn` "… retried on the next ait setup / ait
    upgrade";
  - `MIGRATE_ERROR` ⇒ `warn`.
- **Never fatal.**

Call sites:
- `main` calls it right after `setup_lock_branch`.
- `install.sh` calls it in the existing-install block **after
  `commit_installed_data_files`**, guarded by
  `[[ "$EXISTING_INSTALL" == true ]] && declare -F setup_model_stats_migration`.
  This placement matters: the install's own seed merge of `models_*.json`
  must be committed first, or the no-remote path reads "dirty" and defers.

### 7. Registry split: stop re-adding keys

- `aitask_add_model.sh` L161 / L182: drop `"verifiedstats": {}` and keep
  `"verified": {}`.
- `aitask_opencode_models.sh`:
  - L165 new-row default: drop `verifiedstats`;
  - correct the merge comment;
  - `--sync-seed` (L368-375): replace the `cp` with
    `jq -f "$SCRIPT_DIR/lib/model_stats_strip.jq" "$METADATA_FILE"` into a
    temp file, then `mv` to `$SEED_FILE`.
- `seed/models_{claudecode,codex,opencode}.json`: run the jq filter in place
  (byte-stable, as measured). This also removes the stale flat entry on
  `openai_gpt_5_4`. `verified` is kept.
- `aitask_install_merge.py` `merge_json_models`: appended seed-only rows lose
  `usagestats` / `verifiedstats` (`{k: v … if k not in STATS_KEYS}`). Existing
  destination rows are untouched, because they are the legacy counters the
  migration owns.
- `lib/config_utils.py` `import_all_configs`: a `models_*.json` or
  `models_*.local.json` payload has stats keys removed from its `models` rows
  before planning the write. This is a small helper
  `_strip_registry_stats(name, data)`. Replace mode no longer brings the
  bundle's counters in. Before, it replaced the destination's counters with
  the bundle's; now neither set is imported, and the destination's legacy
  counters are replaced as before. Note this in the t1912_6 note.
- `.claude/skills/aitask-refresh-code-models/SKILL.md`:
  - Step 4 NEW rows: `verified` only;
  - Step 6 item 3: preserve `verified`, never add, edit or remove
    `usagestats` / `verifiedstats` (the migration owns them);
  - field-ordering text;
  - "initialize `verified`" only;
  - seed sync: copy through `jq -f .aitask-scripts/lib/model_stats_strip.jq`;
  - Notes L228 bullet.
  - It has no `.md.j2` template and no golden. The wrappers need no port.
- `tests/test_metadata_writer_inventory.py`: pin
  `aitask_model_stats_strip.sh::<render/commit fn>` with its commit seam
  (`aitask_task_commit.sh`). Classify `model_stats_migrate.py` if discovery
  sees it (plumbing only, no file write expected).

### 8. Tests

New `tests/test_model_stats_migrate.py` uses the `IsolatedGit` pattern from
`test_model_stats_store.py`: a bare origin, a seed clone that publishes
`aitask-data`, and a local clone with a `.aitask-data` worktree. It contains:

1. **Parity:** the `tests/golden/stats_readers` fixture is committed in a
   legacy no-remote project and migrated. `stats_reader_capture.py` then
   equals `expected.txt` byte for byte, and all three markers exist.
2. **Stale local vs newer remote:** local data branch 100 runs, origin 110 ⇒
   110 absorbed, `source_commit` = origin's commit, and the local worktree
   file is never read.
3. **Origin moves between pin and strip** (`after_pin` hook), run twice:
   once with an unrelated commit and once with an old-framework stats write
   (+1 run). The first lease fails, nothing is stripped and the restart
   absorbs the newer content.
4. **Two clones concurrently:** clone B runs to completion inside A's
   `after_pin`. Result: one baseline, one absorb (A ends
   `MIGRATE_NOOP|marked`), and totals equal the source.
5. **Crash after strip, before absorb:** `after_strip` raises. Then the store
   holds no marker and the loader under-reports. A rerun recovers S1 by
   trailer and absorbs exactly once.
6. **Baseline-recovery race:**
   - A strips 110 runs; inside `before_absorb`, an old-framework write adds
     1 run and B runs to completion. B absorbs 110 from `S1^`, the marker
     names S1, and B prints `STRIPPED_RESIDUE:…|1`. A resumes and prints
     `MIGRATE_NOOP`. Totals are 110.
   - Same with A resuming before B. Then the residue appears after the
     marker, and the next run strips it.
7. **Baseline uniqueness:** after every race test, the origin data branch
   holds exactly one `Kind: baseline` commit per agent.
8. **Unreachable remote** (origin URL pointing at a missing path) ⇒
   `MIGRATE_DEFERRED`, no marker, no strip, and the loader still shows file +
   branch.
9. **Idempotent second run** ⇒ `MIGRATE_NOOP`, and no new commits on either
   branch.
10. **No-remote:**
    - clean ⇒ migrated, with a strip commit carrying the trailers;
    - a dirty worktree file ⇒ `MIGRATE_DEFERRED|dirty`, nothing written;
    - rollback: a fixture pre-commit hook fails the strip commit, and the
      file is restored byte for byte;
    - an empty no-remote baseline leaves `git status --porcelain` and
      `ls-files -s` byte-identical.
11. **Remote mode leaves `.aitask-data` untouched:** HEAD, `ls-files -s`
    hash, `status --porcelain` and `refs/heads/aitask-data` are the same
    before and after, with the worktree dirty.
12. **No-stats source** ⇒ `MIGRATED:<agent>|<S1>|0`, where S1 is an
    **empty** baseline commit (same tree as its parent, with trailers) and
    the marker names it. Plus the `write` adapter keeping `update`
    behaviour: the existing `test_model_stats_store.py` stays green
    unmodified.
13. **Empty-source cutover race (concern 1), both orderings with two
    migrators:**
    - (a) A pins an empty registry. Inside A's `after_pin`, an old-framework
      write adds counters, and B runs to completion: B pins them, pushes a
      counters baseline S1 and absorbs. A resumes, its empty-baseline lease
      fails, it re-pins, finds S1 and ends `MIGRATE_NOOP`. Totals equal the
      counters, and there is one baseline.
    - (b) A's empty baseline lands. Inside A's `before_absorb`, an
      old-framework write adds counters, and B runs: B finds A's S1, absorbs
      0, and strips the counters as residue (`STRIPPED_RESIDUE:…|n`). A
      resumes and ends `MIGRATE_NOOP`. There is one baseline, and the marker
      names A's S1.
    - In neither ordering does any run print `marker_mismatch`.
14. **Offline migrate, then attach origin (concern 2):**
    - A no-remote clone migrates, so it holds a local strip, a local marker
      and absorbed totals.
    - Attach an origin that holds the old registry (counters, no S1 in its
      history) and no `aitask-stats`. `migrate` ⇒
      `MIGRATE_ERROR:…|marker_not_in_source`; origin's data and stats
      branches are unchanged, and nothing is stripped or published.
    - Variant: origin is an ancestor of the local data branch, so the strip
      is merely unpushed ⇒ `MIGRATE_DEFERRED:…|strip_unpublished`. After
      `git push` of the data branch, `migrate` publishes the stats history
      (the marker lands on origin) **before** any residue strip. A second
      clone then reads the absorbed totals.
    - Variant: local and origin stats diverged ⇒
      `MIGRATE_ERROR:…|stats_diverged` with nothing written.
15. **Local strip identity (concern 3):** a fixture git `post-commit` hook in
    the no-remote repo creates an unrelated commit U right after the strip
    commit, so HEAD = U. `migrate` absorbs the full counters (not 0), and the
    marker's `strip_commit` is the trailer-carrying commit, not U.
16. **Empty-baseline discovery (round 2, concern 1):**
    - after an empty baseline is pushed, `find_baseline` /`find_by_id` return
      it at once, so no `strip_not_found` appears;
    - kill the run in `after_strip` (a crash), then a fresh-process `migrate`
      recovers the empty S1 by trailer, publishes the marker and absorbs 0;
    - ordering: empty baseline lands, an old-framework write adds counters,
      `migrate` runs ⇒ the counters are residue (`STRIPPED_RESIDUE`), never a
      second baseline. Uniqueness holds.
    - A regression control asserts that a path-limited `git log -- <path>`
      really omits the empty commit in that fixture, so the test proves why
      the pathspec was dropped.
17. **Second clone converges its read ref (round 2, concern 2):**
    - clone A migrates (published);
    - clone B, with its local `aitask-stats` (a) absent and (b) stale at a
      pre-migration commit, runs `migrate` ⇒ `MIGRATE_NOOP`;
    - **without any separate refresh**, `mss.load_agent_stats(B)` shows the
      absorbed totals and `refs/heads/aitask-stats` equals origin's tip.
    - Variant for a marker discovered on an absorb retry: B's absorb render
      first finds no marker; A's marker lands in a hook before B's push, B
      retries and sees it, and the result is `MIGRATE_NOOP` with B's local
      ref at that tip.
    - Variant for local progress made meanwhile: a local stats write ahead
      of the validated tip is never rewound (`ALREADY_NEWER`).
20. **First run delivers in one invocation (round 4), for both a counters
    baseline and an empty baseline, in remote mode:**
    - a **single** `migrate` call prints `MIGRATED:<agent>|<S1>|<n>`;
    - origin's `aitask-stats` holds `migrations/<agent>.json` naming S1,
      whose parent is the pre-run tip;
    - a second clone reads totals equal to the source (n or 0) with no
      re-run.
    - A unit test of `MarkerGate` shows that a marker naming a child of the
      pinned O is rejected with `tip=O` and accepted with `tip=S1`, so the
      ordering is pinned. Each fixture must run exactly one invocation; a
      test that passes only on a second run fails.
18. **Reconnect through ordinary writers (round 3):**
    - Fixture: a no-remote clone migrates `claudecode` offline (absorbs
      100). Origin's data branch holds a registry history that advanced to
      110 and does not contain the local strip S1. Attach origin with
      `aitask-stats` ABSENT.
    - (a) `aitask_model_stats.py bump-usage --agent claudecode` ⇒
      `UPDATED:…`, exit 0, and a stderr note "recorded locally … not
      published". Origin `aitask-stats` stays ABSENT, and the local ref holds
      the write.
    - (b) **Cross-agent:** `bump-usage --agent codex` and `record-verified
      --agent codex` are likewise held. Origin is still ABSENT, so no marker
      of any agent leaked.
    - (c) A second fixture where origin `aitask-stats` exists and is behind
      local: the same holding applies (the local-ahead base).
    - (d) `migrate` ⇒ every agent
      `MIGRATE_ERROR:…|blocked:claudecode:marker_not_in_source`. Origin's
      data and stats tips are unchanged, and no baseline is cut for `codex`
      / `opencode`.
    - (e) Positive control: origin's data branch is an ancestor of the local
      one, and the data branch is then pushed, so S1 is in origin's history.
      Ordinary writers still hold. Then `migrate` validates every local-only
      marker, publishes, and a second clone reads the absorbed totals plus
      the held writes, with nothing lost.
    - (f) Unit test of the gate: an ordinary `write` whose base carries an
      already-published marker (same blob on `remote_tip`) pushes normally,
      so the gate fires only for local-only markers.
19. **Killed between rewrite and commit (concern 4):**
    - `AIT_STATS_STRIP_AFTER_REWRITE_HOOK` SIGKILLs the helper. The worktree
      is now stripped, HEAD is unstripped, there is no trailer, and the loader
      under-reports.
    - A **fresh-process** `aitask_model_stats.py migrate` resumes: it commits
      the baseline, absorbs the full counters, and the loader totals are
      exact.
    - Control: the same interrupted state plus an unrelated edit to the file
      ⇒ `MIGRATE_DEFERRED:…|dirty`, and the file bytes are untouched.

Updated suites:
- `tests/test_add_model.sh`: new rows have no `verifiedstats`.
- `tests/test_opencode_models_merge.sh`: L189 / L248 seed assertions become
  "seed carries no `usagestats`"; L212 `verifiedstats` defaulted ⇒ absent;
  the registry still carries existing counters.
- `tests/test_opencode_models_reserved.sh`: re-check only, since its
  existing-row counters are carried, not added.
- `tests/test_install_merge.sh`: a seed-only row carrying stats keys is
  appended without them.
- A config-import case in the `config_utils` tests: the stats keys are
  stripped.
- Must stay green: `test_codeagent_trail.sh` and
  `test_codeagent_work_report.sh` (seed `verified` priors),
  `test_stats_readers_golden.py`, `test_model_stats_parity.sh`,
  `test_model_stats_refresh_routes.sh`, the writer tests and
  `test_stats_writers_leave_task_data.sh`.

New `tests/test_setup_model_stats_migration.sh` sources
`aitask_setup.sh --source-only`:
- the no-remote fixture prints `MIGRATED` lines and exits 0;
- `AIT_STATS_MIGRATE=0` does nothing;
- a broken interpreter stub ⇒ a deferral warning with exit 0 (never fatal).

### Post-phase (risk mitigations)

1. [migrate_dry_run_preview] Add `migrate --dry-run` (CLI flag →
   `migrate(root, agent, dry_run=True)`). It does protocol steps 1-2 and
   the step-3 trailer scan (pin, read-only reconcile, scan) and computes
   what the rest would do. It never builds,
   pushes or CAS-writes anything. Per agent it prints:

   ```
   MIGRATE_PLAN:<agent>|marker=<yes|no>|baseline=<S1|none>|absorb_runs=<n>|residue_runs=<n>
   ```

   plus `MIGRATE_DEFERRED` when the pin fails. Add a test proving the dry
   run leaves the origin `aitask-data` / `aitask-stats` tips and the local
   refs unchanged, and that its `absorb_runs` equals the real run's absorbed
   runs. Run `--dry-run` on this repo and show the output to the user
   **before** asking to run the real migration.

## Verification

- All the tests above pass. Run each bash file directly, and run
  `test_model_stats_migrate.py` / `test_model_stats_store.py` /
  `test_stats_readers_golden.py` with pytest.
- `shellcheck` is clean on the touched scripts (setup, install,
  opencode_models, add_model, the new strip helper).
- `bash tests/run_all_python_tests.sh`: report the last-line verdict
  (`PYTHON SUITE: …`). Pre-existing failures are classified against HEAD.
- Full flow under a scratch `HOME` (`AITASKS_HOME` unset or scratch):
  - an existing-install scratch project with legacy stats (no remote, plus a
    bare-origin variant): `bash install.sh --dir <scratch>` (upgrade path),
    then `./ait setup`;
  - expected: per-agent `MIGRATED` lines on the first route and
    `MIGRATE_NOOP` on the second;
  - `jq` shows no stats keys in the registry, and `aitask_model_stats.py
    show` shows the absorbed totals.
- **Real run on this repo (pushes to origin):** ask the user first. Then run
  `aitask_model_stats.py migrate`, record each agent's output, and check
  `show` against the pre-run `export` totals.
- Send a note to t1912_6:
  - config export no longer carries stats once migrated;
  - import strips stats keys;
  - `--sync-seed` strips;
  - the setup / upgrade hook and `AIT_STATS_MIGRATE=0`.

## Step 9

Post-Implementation per task-workflow (child task: archive, plan notes for
t1912_6 / t1912_7).

## Risk

### Code-health risk: medium
- Turning `mss.update` into a generic multi-path `write` changes the one write
  loop both live writers go through, so a mistake regresses every stats
  write · severity: low (residual — addressed by inline pre-phase
  store_write_regression_baseline) · → mitigation: inline pre-phase
  store_write_regression_baseline
- The setup / upgrade hook now runs a migration (commits locally, pushes with
  a remote) inside every existing test that runs setup `main` or `install.sh`
  on a fixture. That can break unrelated suites or leave commits in fixtures
  · severity: low (residual — addressed by inline pre-phase
  setup_install_suite_baseline) · → mitigation: inline pre-phase
  setup_install_suite_baseline
- The remote-mode strip leaves the local `.aitask-data` file with stats keys
  until the next sync. A local commit to the same file in that window
  (add-model, opencode refresh) can hit an adjacent-hunk rebase conflict
  against the stripped origin · severity: low · → mitigation: none (rare:
  setup/upgrade time only; the syncer reconciles; any surviving keys become
  residue)

### Goal-achievement risk: medium
- The core protocol (pin, leased strip, trailer recovery, absorb + marker,
  residue) must be exactly right under races, or counters are lost or double
  counted · severity: medium · → mitigation: none (designed in the task;
  the deterministic seam-hook race matrix in Step 8 is in scope)
- Review round 1 found four reachable loss paths in the first design:
  - the unserialised `source: none` marker;
  - trusting an unreconciled local marker;
  - sampling the strip sha from HEAD;
  - no recovery for a strip killed before its commit.

  Each is now designed out (the empty baseline commit, marker validation
  against O plus publish-before-residue, identity by trailer and id, the
  resume rule) and pinned by Tests 13-15 and 19 · severity: low (residual) ·
  → mitigation: none (in scope)
- Review round 2 found two more: an empty baseline invisible to a
  path-limited trailer scan, and an already-migrated clone whose local read
  ref never advanced. Both are designed out (scan with no pathspec; publish
  / ff-only advance on every validated path, including a no-op `write`) and
  pinned by Tests 16-17 · severity: low (residual) · → mitigation: none
  (in scope)
- Review round 3: the store's shared publication path (any writer, any
  agent) could publish an offline, unvalidated marker. It is now gated at
  `write` / `publish`: ordinary writers hold such history locally, and only
  the migrate route validates **every** local-only marker against a pinned
  data tip. Round 4: the gate's validation tip is separate from the absorb
  source and advances to our own published S1, so a fresh migration
  publishes its marker on the first run. Pinned by Tests 18 and 20 ·
  severity: low (residual) · → mitigation:
  none (in scope)
- An offline migration whose source origin's history lacks is failed closed
  (`marker_not_in_source`). Writers on that clone keep holding locally until
  someone repairs it by hand · severity: low (rare: offline migrate followed
  by attaching a divergent origin) · → mitigation: none (diagnostic names
  the repair; automatic repair noted as an upstream follow-up candidate)
- Every agent with no counters now gets one empty baseline commit on the
  data branch: three one-time empty commits per project on its first
  setup/upgrade · severity: low · → mitigation: none (the price of a single
  serialization point)
- The real-repo run pushes strip commits to origin's `aitask-data` and is
  effectively one-way. A surprise there (wrong agent set, unexpected residue,
  wrong totals) can only be repaired by hand afterwards · severity: low
  (residual — addressed by inline post-phase migrate_dry_run_preview) ·
  → mitigation: inline post-phase migrate_dry_run_preview
- Legacy mode with a remote pushes the strip to the code branch. A protected
  branch keeps it deferred on every run · severity: low · → mitigation: none
  (reported as `MIGRATE_DEFERRED:…|push:<reason>`, never fatal)

### Planned mitigations
- timing: pre-phase | name: store_write_regression_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: write-loop generalisation regressing the live writers | desc: per-file results of the store/parity/refresh/writer suites before and after the mss.write refactor
- timing: pre-phase | name: setup_install_suite_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: setup/upgrade hook breaking unrelated setup/install suites | desc: per-file results of every setup-main / install.sh test before and after the hook lands
- timing: post-phase | name: migrate_dry_run_preview | type: feature | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: one-way real-repo migration push | desc: migrate --dry-run reporting per-agent baseline/absorb/residue without writing; previewed on this repo before the real run
