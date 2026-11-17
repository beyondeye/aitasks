# Code-agent stats store (`aitask-stats`)

Maintainer reference for where the code-agent usage and verified-score counters
live, how they are read and written, and how a project's legacy counters move
there. The module docstrings are authoritative and this page points at them:
`.aitask-scripts/lib/model_stats_store.py` (layout, refs, write and read rules),
`.aitask-scripts/lib/model_stats_migrate.py` (migration protocol) and
`.aitask-scripts/aitask_model_stats.py` (CLI verbs and output lines).

## What lives where

| Data | Location |
|---|---|
| Model registry rows: `name`, `cli_id`, `notes`, `status`, `verified` | `aitasks/metadata/models_<agent>.json` on the task-data branch |
| Counters: `usagestats`, `verifiedstats` | `<agent>.json` on the orphan branch `aitask-stats` |
| Per-agent cutover marker | `migrations/<agent>.json` on `aitask-stats` |

`<agent>.json` is `{"schema": 1, "models": {"<model name>": {"usagestats": {…},
"verifiedstats": {…}}}}`. The per-skill entries keep the writers' bucket shape
(`all_time`, `prev_month`, `month`, `week`; periods `%Y-%m` and ISO `%G-W%V`).
The user-facing description of the buckets is on the website settings
reference ("Model Entry Schema").

`verified` in the registry is a **static prior**. No writer touches it. Readers
show the `all_time` average for a skill that has runs, and the prior for a skill
that has none (`aitask_codeagent.sh list-models`, `agent_model_picker`, the
settings app). `aitask_add_model.sh add-json` creates new rows with
`"verified": {}` only.

The store is agent-agnostic: an agent name is anything matching
`AGENT_RE = [a-z][a-z0-9]*`. Adding a code agent needs no store change and no
counter keys in its registry. See `adding_a_new_codeagent.md` §3.

## Refs and writes

- `refs/heads/aitask-stats` is the only ref readers read. Only
  `model_stats_store` moves it, and only by fast-forward.
  `refs/remotes/origin/aitask-stats` is never consulted; fetches go through
  `orphan_ref_store.fetch_pinned` into a private temp ref.
- Every write is plumbing only: trees are built through a private
  `GIT_INDEX_FILE`, so a write never touches any worktree, index or HEAD,
  including `.aitask-data` (pinned by `TestDataWorktreeUntouched` and
  `tests/test_stats_writers_leave_task_data.sh`).
- `write()` / `update()` do a leased read-modify-write. When a remote is
  configured, every attempt probes and fetches origin, renders on the newer of
  local and origin (diverged → `StatsDiverged`), and pushes with a lease,
  retrying a lost race up to `MAX_ATTEMPTS`. An unreachable origin raises
  `StatsError("unreachable:…")`. Without a remote the commit lands on the local
  ref only. Each commit carries a `Stats-Write-Id: <uuid4>` trailer, so two
  identical writes never build the same commit.
- **Publication gate.** A push that would newly publish a migration marker goes
  through `marker_gate`. Ordinary writers pass none, so such a write is held on
  the local ref and reported as `HELD_LOCAL:<agents>`. The CLI turns that into
  the stderr warning "stats recorded locally only …"; the write still counts as
  recorded. Only the validated migration route publishes the marker.

The counter writers are `aitask_usage_update.sh` and
`aitask_verified_update.sh`. Their CLI, validation and registry check (they
only read the registry) are unchanged shell. They write through
`model_stats_write` in `lib/verified_update_lib.sh`, which calls
`aitask_model_stats.py bump-usage` / `record-verified`. Output:
`UPDATED:<agent>/<model>:<skill>:<value>` always means recorded. `<value>` is
the total readers now show, or the literal `unknown`. A failed write prints
`STATS_ERROR:<reason>` and exits non-zero. Each writer's `--help` states this
contract.

## Reads

- Library readers call `model_stats_store.overlay_rows(<dir the rows came from,
  or an explicit project root>, agent, rows)`, or `load_agent_stats` /
  `load_all_stats`. Shell and jq consumers use `aitask_model_stats.py overlay` /
  `export`. Never read `usagestats` / `verifiedstats` from the registry file
  directly, and never pass the cwd as the repository.
- **Marker rule.** When `migrations/<agent>.json` exists, readers use the branch
  counters only, and drop a key the branch lacks for that model. Without it,
  readers add the registry's legacy counters to the branch counters.
- Readers never fetch. A git failure reads as legacy-only and is reported once
  per project on stderr, because readers are display paths.
- `tests/test_stats_readers_golden.py` pins every reader's output; capture with
  `tests/lib/stats_reader_capture.py <root>`.

## Refresh routes

`refresh()` fast-forwards the local ref from origin, never raises, and leaves a
diverged ref where it is. It runs:

- after the fetch in `ait sync` (`aitask_sync.sh`) and in `aitask_pick_own.sh`'s
  `sync_remote`, through `ait_model_stats_refresh` (`lib/task_utils.sh`). The
  helper is silent for `REFRESHED`, `no_remote` and `absent`. It prints anything
  else to stderr as `model-stats refresh: …` and always returns 0. The timeout
  is `AIT_STATS_REFRESH_TIMEOUT`, 5s by default;
- as part of every write, which reads origin before it commits;
- by hand: `aitask_model_stats.py refresh`.

TUIs and the other readers never refresh. `tests/test_model_stats_refresh_routes.sh`
pins the routes.

## Migration (legacy registry counters → `aitask-stats`)

`aitask_model_stats.py migrate [--agent A] [--dry-run]` moves an agent's legacy
counters exactly once. The protocol is in the `model_stats_migrate.py`
docstring:

- One leased **baseline** commit per agent on the task-data branch, identified by
  `Stats-Migration-*` trailers, is the cutover. It strips the counters, or is an
  empty commit when the registry has none. It is found by a trailer scan with no
  pathspec, because an empty commit is TREESAME to its parent.
- The **absorb** reads the registry at `S1^` (the baseline's parent, immutable),
  merges it into the branch counters and writes the marker in one leased
  `aitask-stats` commit.
- Counters an older framework writes after the baseline are **residue**. They
  are stripped (`STRIPPED_RESIDUE:`) and never absorbed.
- In remote mode the strip is pushed to origin directly. The local
  `.aitask-data` worktree, index and branch ref are not touched, so the local
  registry keeps its keys until `./ait sync` brings the strip in. Readers ignore
  those keys once the marker exists.
- In no-remote mode the strip goes through `aitask_model_stats_strip.sh` (a CAS
  rewrite with `lib/model_stats_strip.jq`, then a path-scoped commit).
- `MarkerGate` validates every local-only marker against the task-data history
  it claims to cut before anything is published.
- `marker_not_in_source` (a local marker whose strip origin does not contain)
  fails closed and is not repaired automatically. The local `aitask-stats`
  history may hold held-local writes that exist nowhere else, so a manual repair
  must keep that history. A plain reset followed by a re-run is not lossless.

Result lines: `MIGRATED`, `MIGRATE_NOOP`, `MIGRATE_SKIPPED`,
`MIGRATE_DEFERRED` (retried on the next run), `MIGRATE_ERROR` (exit 1),
`MIGRATE_PLAN` (`--dry-run`, writes nothing) and `STRIPPED_RESIDUE`.

`setup_model_stats_migration` (`aitask_setup.sh`) runs the migration from
`ait setup` after the Python venv step, and from `install.sh`'s existing-install
block (the `ait upgrade` route). It is never fatal: it reports each line and
returns 0, so a deferral is retried on the next setup or upgrade.
`AIT_STATS_MIGRATE=0` skips it.

Other registry writers keep counters out:

- `aitask_opencode_models.sh --sync-seed` strips them from the seed copy, and
  the seeds carry none.
- The install-time registry merge (`aitask_install_merge.py json-models`)
  strips them from seed rows it appends and from a registry it creates from a
  seed, and leaves the destination's existing rows as they are.
- Config import (`config_utils._registry_without_bundle_stats`) drops a
  bundle's counters and keeps the destination's own unmigrated counters.

## Files and tests

| File | Role |
|---|---|
| `.aitask-scripts/lib/model_stats_store.py` | Store: pure bucket ports, write, refresh, loader, overlay |
| `.aitask-scripts/lib/model_stats_windows.py` | Current week/month periods |
| `.aitask-scripts/lib/orphan_ref_store.py` | Plumbing primitives shared with other orphan-branch stores |
| `.aitask-scripts/lib/model_stats_migrate.py` | Migration protocol |
| `.aitask-scripts/aitask_model_stats_strip.sh`, `.aitask-scripts/lib/model_stats_strip.jq` | No-remote strip |
| `.aitask-scripts/aitask_model_stats.py` | CLI |
| `.aitask-scripts/lib/verified_update_lib.sh` | Writers' bridge (`model_stats_write`) |

Tests: `tests/test_model_stats_store.py`, `test_model_stats_windows.py`,
`test_model_stats_parity.sh` (with `tests/golden/model_stats_parity/`),
`test_model_stats_refresh_routes.sh`, `test_model_stats_migrate.py`,
`test_setup_model_stats_migration.sh`, `test_stats_writers_leave_task_data.sh`,
`test_usage_update.sh`, `test_verified_update.sh`,
`test_verified_update_flags.sh` and `test_stats_readers_golden.py` (with
`tests/golden/stats_readers/`).
