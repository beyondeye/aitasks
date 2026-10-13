---
Task: t1957_3_cross_repo_linked_trail_discovery.md
Parent Task: aitasks/t1957_trail_cross_repo_blockers_and_linked_trails.md
Sibling Tasks: aitasks/t1957/t1957_1_*.md, aitasks/t1957/t1957_2_*.md, aitasks/t1957/t1957_4_*.md, aitasks/t1957/t1957_5_*.md
Archived Sibling Plans: aiplans/archived/p1957/p1957_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-13 15:27
---

# t1957_3 — Cross-repo linked-trail discovery helper (`lib/trail_links.py`)

## Context

t1957_4 (the `L` "Linked Trails" jump in By-Trail / `ait trails`) needs, for the
active trail in this repo, the **linked** trails in other registered repos. This
child delivers the discovery helper only:
- an `export` CLI that runs in another repo's root;
- a pure relation function;
- a thread-only scan that never skips a project silently and never reports a
  partial read as a definitive empty result.

Parent plan: `aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`.

**Linked-trail relation** (both directions, `proj#id` members count). Trail B
(repo Y) is linked to trail A (repo X) when any of:
- `fwd-xdeps` — a member of A has `xdeprepo: Y` and an `xdeps` id that is a member of B;
- `fwd-member` — A has a cross-repo member `Y#id` that is a member of B;
- `rev-xdeps` — a member of B has `xdeprepo: X` and an `xdeps` id that is a member of A;
- `rev-member` — B has a cross-repo member `X#id` that is a member of A.

Identity is `(realpath(project root), task_id)`. Project names are always
resolved to roots and never compared as strings. **Ownership is root-based on
both sides.** "Member of B" means a member whose identity root is B's own repo,
whatever name the ref uses: `project.name`, a registry alias, or a tmux name. A
third-repo `Z#3` shared by A and B is not a link.

## Verification findings (plan vs. current code, 2026-10-13)

Anchors hold: `discover_trails()` (`lib/trail_discovery.py:326`) returns
`(infos, unreadable)`, cwd-relative `ARTIFACT_SCRIPT`, per-call `task_dir()`;
`trail_entry_refs` (`:77`); `ProjectRoots` (`lib/trail_gather.py:289`);
`parse_ref` (`lib/cross_repo_notation.py`). Refinements:

1. **`xdep_ref_pairs` lives in `lib/cross_repo_deps.py`** (moved there by
   t1957_1). It is the one xdeps normalization (`lstrip('t')`).
2. **Most registered repos have no `project.name`.** On this host, 5 of the 7
   other registered projects lack it (`aitasks_go`, `timexchange`, `teamim`,
   `animeless`, `aitasks_mobile`). `export` never fails on that; it emits
   `local_project: ""`.
3. **Ownership is decided once, in the scanner, by root (review finding 1).**
   The export does not classify members. It emits the metadata of **every task
   id that appears in any member ref**, keyed by bare id, whatever project name
   the ref uses. The scanner classifies each member by resolved root, and looks
   up the metadata only for the members it classified as own. This prevents two
   losses:
   - a `rev-xdeps` link hidden because the exporting repo has no
     `project.name`;
   - one hidden because its trail names its own members through a registry
     alias.
   The local side uses the same root-based rule: a local-doc member whose name
   resolves to the local root is own, not a candidate project.
4. **Local read failures are reported (review finding 2).** An own local member
   whose task file cannot be read gives a `local_unreadable` error. Links
   established by other members are kept, and `complete=False`.
5. **Archive reads must report their failures (review finding 3).** Today
   `archive_iter` swallows every archive and read failure:
   - `_iter_single_archive` catches `TarError`/`OSError`/`SubprocessError` and
     ignores zstd's exit status;
   - a missing `zstd` binary is silent;
   - `iter_archived_frontmatter` swallows parse exceptions.
   So a corrupt `old0.tar.gz` gives zero discovery records, `unreadable=[]`, and
   member lookup `None`. Add an **opt-in** status channel: a keyword-only
   `errors: list | None = None` parameter through `archive_iter`, and an
   `archive_errors=None` parameter on `discover_trails`. The default path of
   every existing caller (board, stats, codebrowser, trail_gather,
   dep_resolution) stays byte-for-byte unchanged.
6. **`aitasks_mobile` has no `aitask_artifact.sh`** (older framework). The
   frontmatter scan finds no trails there. A trail whose blob does not load
   already fails closed into `load_error`, which the scan reports as `partial`.
7. **A status-aware resolver in `trail_links`, not `ProjectRoots`.** `ProjectRoots`
   collapses `STALE` and `NOT_FOUND` into `None`. `trail_gather.py` also carries
   another session's uncommitted edit, so it is not touched. The resolver calls
   the same `aitask_project_resolve.sh <name>` (absolute path in this checkout)
   and parses `RESOLVED:` / `STALE:` / `NOT_FOUND:`.
8. **Registry enumeration fails closed.** `aitask_project_resolve.sh list`
   prints nothing on an unreadable registry, which looks like an empty one. Use
   `agent_launch_utils._parse_registry_records_strict()` instead: a missing file
   gives `[]`, an unreadable one raises. It is imported lazily so the export
   subprocess does not load tmux modules. A path without the
   `aitasks/metadata/project_config.yaml` marker is `stale`, the same rule as
   `_read_registry_index`.
9. **`__file__` must be absolute.** The export re-execs `trail_links.py` with
   `cwd=<other root>`, so the module captures `_THIS_FILE =
   os.path.abspath(__file__)` at import.
10. **No whitelist entries.** The module is called only from Python TUIs and its
    own subprocess, never from a skill (`aidocs/framework/aitasks_extension_points.md`
    "Adding a new helper script").

## Implementation

### 1. `.aitask-scripts/lib/archive_iter.py` — opt-in failure reporting

Add a keyword-only `errors: list | None = None` parameter to
`_iter_single_archive`, `iter_numbered_archives`, `iter_legacy_archive`,
`iter_all_archived_markdown`, `iter_archived_frontmatter` and
`find_archived_markdown_by_id`, and pass it down. When it is `None`, nothing
changes. When it is a list, append `"<path>: <reason>"` for each of these:
- a loose file whose read raises `OSError`;
- an archive whose open or iteration raises `TarError` / `OSError` /
  `SubprocessError`. This includes a missing `zstd` binary (`FileNotFoundError`
  from `Popen`) and a corrupt `.tar.gz`;
- **zstd exit status ≠ 0, checked only when the tar loop ran to completion.**
  On normal completion, drain the rest of `proc.stdout` (tar padding) before
  closing, so zstd never dies of EPIPE on a clean read. On an early generator
  close (`find_archived_markdown_by_id` stops at the first match), `GeneratorExit`
  skips both the check and the drain. A SIGPIPE from a deliberate early stop is
  therefore never reported. Use a local `completed` flag that is set after the
  loop.
- `iter_archived_frontmatter`: for a task-named file (`^t\d+(_\d+)?_`),
  `parse_fn` raising or returning a non-dict → `"<name>: unparseable frontmatter"`.

Module docstring: one paragraph on the opt-in contract. Unset means best-effort,
as before. A list means every failure that could hide a record is reported.

### 2. `.aitask-scripts/lib/trail_discovery.py` — thread `archive_errors`

`discover_trails(archive_errors=None)` passes the list to
`_iter_trail_frontmatter_records(unreadable, archive_errors=None)`. That
function passes it to `iter_archived_frontmatter(..., errors=archive_errors)`.
An archived record whose metadata is not a dict is also reported there. Docstring
update. The board calls it without the argument, so its behaviour is unchanged.

### 3. New `.aitask-scripts/lib/trail_links.py`

Module docstring:
- purpose and the relation;
- root-based ownership;
- invocation contract: cwd = project root, `TASK_DIR` read per call;
- `scan_linked_trails` is for thread use only.

Data types (frozen dataclasses):
```python
LinkedTrail(project: str, root: str, handle: str, name: str, reasons: tuple[str, ...])
ProjectScanError(project: str, kind: str, detail: str)
# kind ∈ stale | not_found | export_failed | timeout | partial
#        | registry_unreadable | local_unreadable
LinkScan(links: list, errors: list, complete: bool)
ProjectExport(project: str, root: str, data: dict)   # data = parsed export JSON
```

**Shared readers (cwd-relative):**
- `_local_project_name() -> str`: `project.name` from
  `task_dir()/metadata/project_config.yaml`, read with `yaml.safe_load`. Returns
  `""` when absent or unreadable.
- `lookup_task_meta(task_id) -> dict` returns one of:
  - `{"state": "ok", "xdeprepo": str, "xdeps": [ids]}`, with xdeps normalized by
    `xdep_ref_pairs` (empty unless both fields are set);
  - `{"state": "missing"}`;
  - `{"state": "unreadable", "detail": str}`.

  Lookup order:
  - Active first: a parent id globs `task_dir()/t<id>_*.md` (child filenames
    excluded); a child id globs `task_dir()/t<parent>/t<id>_*.md`. A read or parse
    failure, or a non-dict result, is `unreadable`.
  - Otherwise archived: `find_archived_markdown_by_id(id, task_dir()/"archived",
    errors=errs)`. A hit that does not parse is `unreadable`. No hit with `errs`
    non-empty is `unreadable` with the errors as detail. No hit with no errors is
    `missing`.

**Export side:**
- `build_export() -> dict`:
  - `archive_errors = []`;
    `infos, unreadable = discover_trails(archive_errors=archive_errors)`.
  - For each info: `members = sorted(trail_entry_refs(info.doc))` (`[]` when
    `doc` is None).
  - `ids` = every id that `parse_ref` returns from any member of any trail,
    whatever its project name.
  - `tasks = {id: lookup_task_meta(id) for id in ids}`.
  - Returns:
  ```json
  {"format": 1, "local_project": "", "unreadable": [], "archive_errors": [],
   "trails": [{"handle", "name", "title", "owner_id", "load_error", "members": []}],
   "tasks": {"7": {"state": "ok", "xdeprepo": "x", "xdeps": ["42"]}}}
  ```
  `name` is `info.name`, or the doc title, or the handle.
- `main(argv)`: argparse with a single `export` subcommand. It prints
  `json.dumps(build_export())` and returns 0. Unexpected exceptions propagate,
  so the scanner sees a non-zero exit.

**Pure relation:**
- `find_linked_trails(local_doc, local_tasks, local_project, local_root, exports,
  resolve) -> tuple[list[LinkedTrail], list[ProjectScanError]]`.
  - `resolve(name)` returns the realpath of a root, or None. In tests it is a
    dict lookup.
  - `local_tasks` is `{id: meta}` in the same shape as the export's `tasks`.

  - **Identity of a ref** on a side with own project `P` and own root `R`:
    - unparseable → ignored;
    - `P` non-empty and the project equals `P` → `(R, id)`;
    - otherwise `resolve(project)` gives `(root, id)`, and an unresolvable name
      is ignored.

    The ref is **own** when its root is `R`, whether it got there by `P` or by an
    alias; otherwise it is foreign.
  - **Per side:**
    - `own` = own member identities;
    - `foreign` = foreign identities, each with its raw ref;
    - `xdep_targets` = for each own member, its task's meta (`tasks[id]`):
      - `ok` → `(resolve(xdeprepo), xid)` per xdep;
      - `unreadable`, or an id missing from `tasks` (the export omitted it) →
        a `partial` error for an export side, `local_unreadable` for the local
        side;
      - `missing` → nothing.
  - **Links:** for each export trail B (skipped when `load_error` is set), the
    four relations are set intersections: `xdep_targets(A) ∩ own(B)`,
    `foreign(A) ∩ own(B)`, `xdep_targets(B) ∩ own(A)`, `foreign(B) ∩ own(A)`.
  - **Reason strings:**
    - `fwd-xdeps: <A ref> xdeps <xdeprepo>#<id>`
    - `fwd-member: <A foreign ref>`
    - `rev-xdeps: <B ref> xdeps <xdeprepo>#<id>`
    - `rev-member: <B foreign ref>`

    They are sorted and deduplicated.
  - **Output:** one `LinkedTrail` per (root, handle), sorted by (project,
    handle). Errors are deduplicated by (project, kind, detail).

**Scan (thread-only):**
- `scan_linked_trails(local_doc, *, local_root=".", local_project=None,
  local_tasks=None, max_workers=4) -> LinkScan`.
  1. `local_root = realpath(local_root)`. `local_project` defaults to
     `_local_project_name()`. `local_tasks` defaults to `lookup_task_meta` for
     every id in the local doc's member refs, which the relation then filters to
     own members by root.
  2. **Candidates:** an ordered map `realpath → name`, filled in this order:
     - (a) The registry, read strictly. An unreadable registry gives
       `registry_unreadable` (project = the registry path). A record without the
       marker gives `stale` (detail = path). The local root itself (same
       realpath) is skipped.
     - (b) Direct names: the `xdeprepo` of each own local member with `ok` meta,
       plus the project of each local-doc member that is not `local_project`.
       Each goes to `_resolve_name`:
       - `RESOLVED` adds a candidate, unless it is the local root (an alias for
         own) or already present;
       - `STALE` gives `stale`;
       - `NOT_FOUND` gives `not_found`.
  3. **Exports:** run with `ThreadPoolExecutor(max_workers)`. `_run_export(root)`
     runs `subprocess.run([sys.executable, _THIS_FILE, "export"], cwd=root,
     env={**os.environ, "TASK_DIR": "aitasks"}, capture_output=True, text=True,
     timeout=30)`.
     - `TimeoutExpired` gives `timeout`.
     - Non-zero exit, `OSError`, invalid JSON, a non-dict result, or a `format`
       other than 1 give `export_failed` (detail = last stderr line).
     - A non-empty `unreadable` or `archive_errors`, or any trail with
       `load_error`, gives `partial` (the detail names them). The data is still
       used.
     - Results are gathered in candidate order, so the output is deterministic.
  4. `links, rel_errors = find_linked_trails(..., resolve=<cached _resolve_name
     → realpath or None>)`.
  5. Return `LinkScan(links, errors + rel_errors, complete=not all_errors)`.
- `_resolve_name(name) -> tuple[status, path]` runs
  `[<scripts>/aitask_project_resolve.sh, name]` with a 30s timeout. Its results
  are cached in a per-scan dict. Any failure is `NOT_FOUND` with the error text
  as detail.
- Test seams patched on the module: `_read_registry`, `_resolve_name`,
  `_run_export`.

### 4. Tests

**`tests/test_archive_iter_consolidated.py` (new cases):**
- with `errors=[]`:
  - a corrupt `.tar.gz` gives an error;
  - a corrupt `.tar.zst` gives an error;
  - `PATH` without `zstd` gives an error for a `.tar.zst`;
  - an unparseable archived frontmatter gives an error in
    `iter_archived_frontmatter`;
  - `find_archived_markdown_by_id` against a corrupt bundle for that id gives
    `None` plus an error.
- An **early-stopping lookup** in a valid multi-member `.tar.zst` reports
  **no** error (the SIGPIPE guard), and a full valid scan reports none.
- Default calls (no list) on the same corrupt fixtures still yield silently.
  This pins the default path as unchanged.

**`tests/test_trail_discovery.py` (new cases):**
- `discover_trails(archive_errors=lst)` with a corrupt `old0.tar.gz` → `lst`
  is non-empty.
- A malformed archived owner → it is reported.
- The default call returns the same `(infos, unreadable)` as before.

**`tests/test_trail_links.py` (new), pure relation:** synthetic exports and a
dict resolver.
- Each of the four directions on its own produces one link with the right
  reason code.
- Name ≠ `project.name`: A's `xdeprepo: mob_reg` → B's `mobile#7`.
- String-equal names on different roots → no link.
- **Alias-named own member:** B lists `mob_alias#7`, where `mob_alias` resolves
  to B's root, and `tasks["7"]` has xdeps back to A → `rev-xdeps` found.
- **`local_project: ""`:** B's members are owned through the resolver, and
  `rev-xdeps` is found.
- An own B member with `tasks` state `unreadable`, or one omitted from `tasks`
  → a `partial` error, and other links are kept.
- A `t` prefix is tolerated. Unparseable refs are ignored.
- A shared third-repo member gives no link. A B with `load_error` gives no link.
- Several relations on one B give one `LinkedTrail` with merged, sorted reasons.

**`tests/test_trail_links.py`, scan (patched seams):**
- Self is excluded by realpath (a registry path through a symlink to the local
  root), and a local alias name is not a candidate.
- An **xdeprepo naming a STALE registered project** gives `complete=False`,
  exactly one `stale` error, and no links. The same holds for `not_found`.
- A successful empty scan gives `complete=True` and `errors == []`.
- Export results map to errors as follows:
  - timeout → `timeout`;
  - rc≠0, invalid JSON, or a wrong `format` → `export_failed`;
  - `archive_errors` / `unreadable` / `load_error` → `partial`, with the links
    kept.
- A registry read that raises gives `registry_unreadable`, and direct names are
  still searched.
- Dedupe: a registry name and a direct name on the same root run one export.
- **Malformed local member:** its xdeps would link to B, while a second member
  links to C via `fwd-member`. Result: only C is linked, there is one
  `local_unreadable` error naming the id, and `complete=False`.

**`tests/test_trail_links.py`, end-to-end** (real export subprocess, real
artifact CLI, real resolver):
- **Fixture Y setup:** temp aitasks layout, a `.aitask-scripts` symlink to this
  checkout's scripts, git init with a commit, and `XDG_CACHE_HOME` /
  `AITASKS_PROJECTS_INDEX` kept inside the temp dir (`TrailGatherCase`
  env-isolation pattern). Build a schema-valid trail document (version from
  `trail_schema.load_schema()`, shape as in `test_trail_gather.make_trail`), and
  check it with `trail_schema.validate_trail` in setUp so a bad fixture is a setup error.
  Store it with the real `aitask_artifact.sh create <owner> <blob> --kind
  implementation_trail --handle <h>`.
- **Export JSON:** members `fixy#5`, `fixy#7`, `fixy#9`, `other#3`; t7 is active
  with xdeps, t9 is archived with xdeps. Assert `tasks` for 7 (active) and 9
  (archived) are `ok` with their xdeps, and that `unreadable` and
  `archive_errors` are `[]`.
- **Reverse discovery, missing `project.name`:** Y has no `project.name` and is
  registered as `fixy`. Its trail lists `fixy#7`, and t7 has `xdeprepo: localx,
  xdeps: [42]`. The registry maps `localx` → X. Scanning from X with a local doc
  holding X's member 42 finds Y's trail with `rev-xdeps`, and `complete=True`.
- **Reverse discovery, alias:** Y has `project.name: fixy` and is also
  registered as `fixy_alias`. Its trail lists `fixy_alias#7`, and t7 has xdeps
  back to X. The scan finds it with `rev-xdeps`.
- **Forward discovery:** the local member has `xdeprepo: fixy, xdeps: [7]`,
  which gives `fwd-xdeps`.
- **Corrupt archive in Y:** writing a corrupt `aitasks/archived/_b0/old0.tar.gz`
  makes the scan report `partial` with `complete=False`, never a definitive
  empty. A malformed archived owner gives the same.
- **Negative controls during implementation:** confirm that the alias and
  missing-name tests fail when the export filters by `project.name`, that the
  corrupt-archive tests fail without the `errors` plumbing, and that the
  local-unreadable test fails without its propagation.

### Post-phase (risk mitigations)

1. [measure_linked_scan_latency] Time `scan_linked_trails` against the real
   registry on this host: 7 other projects, with `thinking_app` and
   `thinking_backend` holding trails and `aitasks_mobile` on an older framework.
   Use a scratchpad script that loads a real local trail through
   `discover_trails()` and wraps `_run_export` / `_resolve_name` to record
   timings per project and per name. Record the total and per-project timings in
   the plan's Final Implementation Notes.
   - If one scan exceeds about 2s, add a `progress(project, done, total)`
     callback parameter and a session-lifetime export cache before closing this
     child. The cache is a module-level dict keyed by realpath, bypassed with
     `rescan=True`. Add tests for both.

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_trail_links.py tests/test_trail_discovery.py tests/test_archive_iter_consolidated.py tests/test_lib_shadow_guard.py -q`
- Regression check for `archive_iter` consumers:
  `tests/test_local_dep_parity.py` and the board / stats / trail_gather suites
  through `bash tests/run_all_python_tests.sh` (read the last line for the
  verdict).
- Manual: run `TASK_DIR=aitasks ~/.aitask/venv/bin/python
  /home/ddt/Work/aitasks/.aitask-scripts/lib/trail_links.py export` in
  `aitasks_mobile` and in `thinking_app`, and check that the output is valid JSON
  (`python -m json.tool`).

## Step 9 reference

After review: Step 9 — commit on main, archive this child (the parent archives
with its last child).

## Notes for t1957_4 (to record in Final Implementation Notes and send as a note)

- API: `scan_linked_trails(session.doc)` → `LinkScan`. It runs in a thread
  worker, and cwd must be the project root.
- Error kinds: `stale`, `not_found`, `export_failed`, `timeout`, plus:
  - `partial` — the project was searched, but some of its tasks, archives or
    trails could not be read;
  - `registry_unreadable` — `project` is the registry path;
  - `local_unreadable` — a member of this trail could not be read.
- Reasons use the `fwd-xdeps:` / `fwd-member:` / `rev-xdeps:` / `rev-member:`
  prefixes.

## Risk

### Code-health risk: medium
- `lib/archive_iter.py` is shared by the board, stats, codebrowser, trail_gather and dep_resolution; the new `errors` parameter touches every iterator · severity: medium · → mitigation: none (addressed in-plan: keyword-only and opt-in, the default path stays byte-identical and is pinned by "default call still silent" tests, the existing archive_iter and parity suites run, and the zstd drain and rc check run only on the opt-in path)
- New cross-process JSON contract between this checkout's scanner and `export` running in another repo (framework-version skew) · severity: low · → mitigation: none (a `format` field, fail-closed parsing into `export_failed`, and end-to-end subprocess tests)
- Bounded concurrent export subprocesses launched from inside a Textual thread worker · severity: low · → mitigation: none (each export has its own timeout, the pool is limited to 4 workers, and the resolver cache is filled only by the calling thread)

### Goal-achievement risk: low
- Scanning every registered project on each `L` press (one export subprocess per project, artifact reads per trail) may be slow enough to feel broken · severity: low (residual — addressed by inline post-phase measure_linked_scan_latency, which adds progress + cache if >2s) · → mitigation: inline post-phase measure_linked_scan_latency
- A stale registry entry, a corrupt archive, or an older repo whose trails fail to load keeps every scan `complete=False` · severity: low · → mitigation: none (accepted by design: an incomplete scan never shows the definitive "no linked trails" message, and error rows name the project and cause)

### Planned mitigations
- timing: post-phase | name: measure_linked_scan_latency | type: performance | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — linked-trail scan latency | desc: measure scan_linked_trails on the real registry; add progress callback + session export cache if >2s

## Final Implementation Notes

- **Actual work done:**
  - `lib/archive_iter.py` gained an opt-in, keyword-only `errors` list on
    `_iter_single_archive`, `iter_numbered_archives`, `iter_legacy_archive`,
    `iter_all_archived_markdown`, `iter_archived_frontmatter` and
    `find_archived_markdown_by_id`.
  - `lib/archive_iter.py` also gained a public `checked_glob` (`Path.glob`
    when `errors` is None; otherwise an explicit listing that reports a
    directory it cannot list).
  - `lib/trail_discovery.py`: `discover_trails(scan_errors=None)` passes
    that list through, to both the archived half and the active directory
    listings.
  - New `lib/trail_links.py` provides `lookup_task_meta`, `build_export` /
    `export` CLI, the pure `find_linked_trails`, and the thread-only
    `scan_linked_trails`.
  - Tests:
    - 42 in the new `tests/test_trail_links.py`: relation, scan, end-to-end
      with the real artifact CLI and resolver, and a live PyPy case;
    - 17 new cases in `tests/test_archive_iter_consolidated.py`;
    - 5 new cases in `tests/test_trail_discovery.py`.
- **Deviations from plan:**
  - **Framed export record.** The export prints one `TRAIL_LINKS_EXPORT:<json>`
    line and the scanner reads only that line. Under PyPy (the board's fast
    path, whose `sys.executable` the scan re-uses), `import yaml` loads PyYAML's
    C extension through cpyext and prints `(_common_types_metatype, …)` lines to
    **stdout**. Parsing the whole stdout as JSON made every export
    `export_failed` from a PyPy-hosted board. This is pinned by a live PyPy test
    (skipped when `~/.aitask/pypy_venv` is absent) and by a noise unit test.
    Both fail under the pre-fix parsing.
  - **An extra zstd test.** A fixture that is only half truncated is caught by
    a tar error, so it never exercised the exit-status check. The mutant that
    removed the check survived until a fixture was added: whole tar members
    with no end marker, followed by a garbage zstd frame. That is the case only
    the exit status catches.
- **Issues encountered:**
  - Synthetic export fixtures first omitted their own members' `tasks` entries.
    The scan correctly reported `partial` ("not exported"), so the helper now
    auto-fills `tasks` the way the real export does.
  - A scan test lacked a resolver entry for a local foreign ref. The scan
    correctly reported `not_found` and found no link.
  - `tests/test_trail_discovery_sequencing.py` stubbed
    `_iter_trail_frontmatter_records` with a one-argument lambda. It now
    accepts the new optional `scan_errors` (same precedent as t1957_2's stub
    update).
  - The first review round's suite: `PYTHON SUITE: PASSED (runner=pytest,
    exit=0)`, 8827 passed, 2 skipped. An earlier run failed only because the framing edit landed while
    it was in progress: workers held the old scanner while the on-disk export
    printed the framed record.
- **Key decisions:**
  - **Ownership is decided once, in the scanner, by root.** The export emits
    the metadata of every member id regardless of project name (review
    finding 1). Mutants confirm the alias and missing-name end-to-end tests fail
    when the export filters by `project.name` or the scanner classifies by name.
  - **The default `archive_iter` path is unchanged.** It is pinned by "default
    stays best-effort" tests. The zstd drain and exit-status check run only on
    the opt-in path.
  - Mutants confirmed each guard is test-pinned:
    - the `completed` guard on the zstd exit status (early-stop SIGPIPE);
    - exception recording;
    - frontmatter reporting;
    - `scan_errors` plumbing;
    - the checked directory listing and existence probes;
    - the checked active lookup in `lookup_task_meta`;
    - local-unreadable propagation;
    - stale registry rows.
- **measure_linked_scan_latency (post-phase) — results on this host
  (2026-10-13):**
  - Setup: 7 other registered projects, local aitasks trail
    `art:trail-artifacts-and-attachments`, 4 workers.
  - **Total scan: 1.53s.** A second run with a doc holding `aitasks#1595` took
    1.64s and then 1.63s.
  - Per-project export times:

    | project | export |
    |---|---|
    | thinking_app (7 trails) | 1.26s |
    | thinking_backend | 0.54s |
    | aitasks_mobile | 0.11s |
    | aitasks_go | 0.09s |
    | timexchange | 0.08s |
    | teamim | 0.06s |
    | animeless | 0.06s |

    Resolver calls took 0.07–0.10s each (`aitasks`, `thinking_app`,
    `thinking_backend`).
  - The scan stays under the ~2s threshold, so no progress callback or export
    cache was added. The slowest single export, `thinking_app`, sets the
    makespan.
  - Real detection works: the `aitasks#1595` doc finds `rev-member: aitasks#1595`
    in thinking_app's `art:trail-parallel-throughput`.
  - Real scans on this host are `complete=False` today. thinking_app
    (`art:trail-build-test-speed`, `art:trail-localization-programme`) and
    thinking_backend (`art:trail-new-prod-and-dev-servers`) hold stored trails
    with `schema_version 1.0.0`, which their own 1.1.0 schema rejects as well.
    `partial` is the honest answer.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/archive_iter.py:_iter_single_archive (gz branch) — a truncated .tar.gz raises EOFError, which the except clause (TarError/OSError/SubprocessError) does not catch, so every best-effort caller (board, stats, codebrowser, trail_gather, dep_resolution) crashes instead of skipping the bundle; t1957_3 catches it only on the opt-in errors path to keep the default path unchanged`
  - `thinking_app#art:trail-build-test-speed / art:trail-localization-programme and thinking_backend#art:trail-new-prod-and-dev-servers — stored trails at schema_version 1.0.0 are rejected by the 1.1.0 schema in both repos, so they render as error cards and keep every cross-repo scan from this host partial (data in other repos; needs a refresh there)`
- **Notes for sibling tasks (t1957_4):**
  - **API:** `trail_links.scan_linked_trails(session.doc)` returns
    `LinkScan(links, errors, complete)`. Call it from a thread worker; cwd must
    be the project root. Each `LinkedTrail` has
    `(project, root, handle, name, reasons)`, where `project` is the name the
    project was searched under (registry name preferred) and `root` is a
    realpath. Hand `root` + `handle` to `launch_or_focus_trails`.
  - **Error kinds** for the modal's disabled rows:
    - `stale` — registered path moved, missing, or never recorded
      (name-only registry row: detail "no path registered");
    - `not_found` — not registered;
    - `export_failed`;
    - `timeout` — 30s per project;
    - `partial` — searched, but some tasks, directories, archives or trails
      were unreadable. Its links are still returned, and paths in the detail
      are relative to that project's root;
    - `registry_unreadable` — `project` is the registry path;
    - `local_unreadable` — a member of the current trail could not be read.

    Never show the definitive "No linked trails" when `complete` is False.
  - **Reasons** carry the `fwd-xdeps:` / `fwd-member:` / `rev-xdeps:` /
    `rev-member:` prefixes, followed by the refs involved.
  - **Latency** is about 1.6s on this host with 7 projects, so a
    "Searching linked trails in N projects…" notice is enough; no progress UI
    is needed.
  - **Interpreter:** the export subprocess uses `sys.executable`, so a scan
    started from the PyPy board runs the export under PyPy. The framed record
    makes that safe.


## Post-Review Changes

### Change Request 1 (2026-10-13)
- **Requested by user:** three review findings.
  1. `Path.glob` swallows `PermissionError`, so an inaccessible
     `aitasks/archived` holding a trail owner gave
     `LinkScan(links=[], errors=[], complete=True)`. The fix must cover child
     and bundle directories and keep the default callers' behaviour.
  2. A name-only registry row (`('broken', '')`) was skipped silently.
  3. Invalid UTF-8 in the local `project_config.yaml` raised
     `UnicodeDecodeError` out of `scan_linked_trails`.
- **Changes made:**
  1. **Directory listings:**
     - `archive_iter.checked_glob` lists each directory a pattern enters with
       `os.scandir` and reports one it cannot list, while an absent directory
       is still empty. It equals `Path.glob` when `errors` is None.
     - `_checked_exists` stats bundle and legacy paths, so an unsearchable
       `_b0/` is reported instead of reading as absent.
     - `_note` now records each entry once, because several globs list the
       same directory.
     - The same blind spot existed on the active side
       (`_iter_active_task_frontmatter` and `lookup_task_meta`'s globs); both
       now use `checked_glob`. The opt-in list was therefore renamed
       `archive_errors` → `scan_errors` (`discover_trails(scan_errors=)`, and
       the export field `scan_errors`).
  2. A name-only registry row becomes `stale` with detail
     "no path registered".
  3. `_local_project_name` also catches `ValueError`. The same class of decode
     failure was fixed in the export and resolver subprocess calls
     (`errors="replace"`), so undecodable output becomes an `export_failed` row
     instead of an exception in the worker.
  - **Tests (regression tests were red before the fix, except the
    archive_iter ones, which could not import before `checked_glob` existed):**
    - archive_iter: unlistable archive dir, unlistable child dir, unsearchable
      bundle dir, and `checked_glob` ≡ `Path.glob` on a normal tree including
      an absent directory;
    - trail_discovery: unlistable archive dir and active child dir;
    - trail_links: name-only registry row, invalid-UTF-8 local config, a member
      in an unlistable child dir (`unreadable`, not `missing`), undecodable
      export output, and the reviewer's end-to-end case (an archived owner in
      a mode-000 `aitasks/archived` gives `partial`, `complete=False`).
  - **Mutants** (an isolated copy):
    - `checked_glob` → plain `Path.glob` fails 7 tests;
    - `_checked_exists` → plain `exists()` fails the bundle-dir test;
    - an unchecked active child glob in `lookup_task_meta` fails its test.
- **Verification:** full suite `PYTHON SUITE: PASSED (runner=pytest,
  exit=0)`, 8846 passed, 2 skipped. A real-registry rescan still finds
  `rev-member: aitasks#1595` (1.91s while the suite was loading the machine).
- **Files affected:** `.aitask-scripts/lib/archive_iter.py`,
  `.aitask-scripts/lib/trail_discovery.py`, `.aitask-scripts/lib/trail_links.py`,
  `tests/test_archive_iter_consolidated.py`, `tests/test_trail_discovery.py`,
  `tests/test_trail_discovery_sequencing.py`, `tests/test_trail_links.py`

### Change Request 2 (2026-10-13)
- **Requested by user:** `lookup_task_meta` checked its active-directory
  listing errors only when the archive lookup returned None. When an
  inaccessible active `t42/` hid a `t42_3` carrying xdeps, an archived copy
  without dependencies came back as `ok`, and the scan reported
  `complete=True` with no links. Active files take precedence, so an archived
  copy cannot be authoritative when the active location could not be checked.
- **Changes made:**
  - An active-listing failure now returns `unreadable` before the archive is
    consulted at all.
  - The same flaw existed one level down. `find_archived_markdown_by_id`
    searches loose files before bundles, so a bundle hit after an unlistable
    loose `archived/t42/` was also returned as `ok`. Any error the archive
    lookup records now makes the result `unreadable`, whether or not it hit.
    The lookup stops at its first hit, and an early-stopped bundle read
    records nothing, so every recorded failure lies at a location that
    precedes the hit.
  - Trail-owner discovery has no equivalent per-item gap: its directory
    failures already land in `scan_errors`, which makes the export `partial`.
  - Regressions, both red before the fix:
    - an unlistable active `t42/` plus an archived copy → `unreadable`, plus a
      scan-level `local_unreadable` with `complete=False`;
    - an unlistable loose `archived/t42/` plus a bundle copy → `unreadable`.
- **Files affected:** `.aitask-scripts/lib/trail_links.py`,
  `tests/test_trail_links.py`
- **Verification:** full suite `PYTHON SUITE: PASSED (runner=pytest,
  exit=0)`, 8848 passed, 2 skipped.
