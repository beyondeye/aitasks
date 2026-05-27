---
Task: t838_codebrowser_show_tasks_without_code_commits.md
Base branch: main
plan_verified: []
---

# Plan: Surface tasks without (tNN) code commits in codebrowser history

## Context

`ait codebrowser` history pane silently omits any archived task that lacks
a `(tNN)`-tagged source-code commit. Concretely t787 (a
`manual_verification` task that produced follow-up tasks but no code) is
missing. This is a class problem, not a one-off: `manual_verification`
and `brainstorm` tasks legitimately complete without source commits, and
their activity lives on the `aitask-data` branch as framework `ait:` /
`brainstorm:` commits without `(tNN)` parens (by design — the documented
recipe is `ait: Record verification state for t<id>`).

The `(tNN)` convention is correct and must stay. The fix is to give
codebrowser a deliberate fallback path for tasks anchored only by
framework commits.

## Approach

**Same task source, additional anchor.** The archived `.md` files
remain the single source of rows — we are *not* introducing a second
listing pipeline. What changes is how each row's `(commit_date,
commit_hash)` anchor is resolved: instead of dropping the row when no
`(tNN)` commit exists, fall through to one of two fallbacks.

Anchor each archived task by the best available signal, in priority
order:

1. **Code commit** — latest `(tNN)`-tagged commit (existing behavior).
2. **Archive commit** — latest framework commit matching
   `ait: Archive completed t<N>` on any branch (this is the canonical
   archival commit, present for all tasks archived under the current
   recipe — including t787).
3. **File mtime** — for loose archived `.md` files only; fall back to
   the disk mtime when neither commit signal is available. Tar-bundled
   legacy tasks (very old) without commit signals continue to be
   dropped, since their on-disk location isn't queryable here.

Tag each `CompletedTask` with `has_code_commits: bool` so the list and
detail panes can visibly distinguish "framework only" rows.

### Pagination, sort, and "Load more" semantics

`HistoryTaskList._load_chunk` paginates over a single
`self._index: list[CompletedTask]` that is already sorted at
index-build time by `commit_date` descending
(`history_data.py:147,153`). The change preserves this exactly:

- Both git-log calls (`_build_commit_map` for `(tNN)`-tagged commits
  and the new `_build_archive_commit_map` for `ait: Archive completed`
  commits) run once upfront, before any archive iteration. They are
  independent dicts keyed by `task_id`, populated by
  `git log --all --grep=... --format=%H %aI %s` — the same shape as
  today.
- The archive iteration over `iter_archived_frontmatter` is still the
  single chunked producer. Each archived file becomes at most one
  `CompletedTask`, with `commit_date` filled by the highest-priority
  available source (code commit > archive commit > mtime).
- All three anchor sources emit ISO-8601 strings (git's `%aI` and
  `datetime.fromtimestamp(..., tz=timezone.utc).isoformat()`), which
  are lexicographically comparable. The existing
  `tasks.sort(key=lambda t: t.commit_date, reverse=True)` already
  produces a globally-consistent ordering across all three anchor
  kinds — no merge-by-source step is needed.
- Progressive `update_index` calls during loading still replace the
  full list with the latest merge; "Load more" pagination still walks
  that same list. Framework-only and code-anchored rows are
  interleaved by date, just like adjacent code-anchored rows are
  today.

## Files to modify

### 1. `.aitask-scripts/codebrowser/history_data.py`

**`CompletedTask` dataclass (line 23)** — add field:

```python
has_code_commits: bool = True
```

(Defaulted so the test-suite fixtures that build `CompletedTask` by
keyword don't need updates.)

**New helper `_build_archive_commit_map(project_root)`** — analogous to
`_build_commit_map`, but greps for `^ait: Archive completed t`:

```python
def _build_archive_commit_map(project_root: Path) -> dict:
    """Build task_id -> (hash, date, message) map from archive commits.

    Archive commits (e.g. `ait: Archive completed t787 task and plan files`)
    are written by aitask_archive.sh and serve as fallback anchors for
    tasks that have no `(tNN)`-tagged source commit.
    """
    archive_map: dict = {}
    try:
        result = subprocess.run(
            ["git", "log", "--all",
             "--grep=^ait: Archive completed t",
             "--format=%H %aI %s"],
            capture_output=True, text=True, cwd=project_root,
        )
        if result.returncode == 0:
            archive_re = re.compile(
                r"^ait:\s+Archive completed t(\d+(?:_\d+)?)\b"
            )
            for line in result.stdout.strip().splitlines():
                if not line:
                    continue
                parts = line.split(" ", 2)
                if len(parts) < 3:
                    continue
                hash_val, date_val, msg = parts
                m = archive_re.match(msg)
                if not m:
                    continue
                tid = m.group(1)
                if tid not in archive_map or date_val > archive_map[tid][1]:
                    archive_map[tid] = (hash_val[:12], date_val, msg)
    except (OSError, subprocess.SubprocessError):
        pass
    return archive_map
```

**`_merge_chunk` (line 100)** — replace `continue` with the fallback
chain. New signature accepts the archive map and archived_dir for mtime
fallback:

```python
def _merge_chunk(
    buffer: list,
    commit_map: dict,
    archive_commit_map: dict,
    archived_dir: Path,
) -> List[CompletedTask]:
    tasks = []
    for tid, metadata, filename in buffer:
        has_code = False
        if tid in commit_map:
            hash_val, date_val, msg = commit_map[tid]
            has_code = True
        elif tid in archive_commit_map:
            hash_val, date_val, msg = archive_commit_map[tid]
        else:
            # Mtime fallback for loose files only
            anchor = _mtime_anchor(archived_dir, tid, filename)
            if anchor is None:
                continue
            hash_val, date_val, msg = anchor

        name = _extract_name_from_filename(filename)
        tasks.append(CompletedTask(
            task_id=tid,
            name=name,
            issue_type=metadata.get("issue_type", ""),
            labels=metadata.get("labels", []),
            priority=metadata.get("priority", ""),
            effort=metadata.get("effort", ""),
            commit_date=date_val,
            commit_hash=hash_val,
            file_source="loose",
            metadata=metadata,
            has_code_commits=has_code,
        ))
    return tasks
```

**New helper `_mtime_anchor(archived_dir, tid, filename)`**:

```python
def _mtime_anchor(
    archived_dir: Path, tid: str, filename: str
) -> Optional[tuple]:
    """Return (hash, iso_date, msg) anchored to the archived file's mtime.

    Returns None if the file is not on disk loose (e.g. tar-bundled
    legacy task with no commit signals).
    """
    if "_" in tid:
        parent = tid.split("_")[0]
        candidate = archived_dir / f"t{parent}" / filename
    else:
        candidate = archived_dir / filename
    try:
        st = candidate.stat()
    except OSError:
        return None
    from datetime import datetime, timezone
    iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
    return ("", iso, f"(mtime fallback for t{tid})")
```

**`load_task_index_progressive` (line 127)** — build the archive map
once and pass both maps + `archived_dir` into every `_merge_chunk` call.

### 2. `.aitask-scripts/codebrowser/history_list.py`

**`HistoryTaskItem.render` (line 108)** — when
`not self.completed_task.has_code_commits`, append a dim `[no-code]`
marker to `line2` (before the labels) and reserve space in the
truncation budget. Concrete change:

```python
no_code_marker = ""
if not t.has_code_commits:
    no_code_marker = " [#FFB86C]\\[no-code][/]"
# ... existing layout ...
line2 = f"      {type_badge}  {date}{no_code_marker}  {labels}"
```

(`#FFB86C` matches the existing `label_filter_status` accent and the
`Plan` view-toggle indicator — consistent with the codebrowser palette.)

The fixed-width `prefix_len`/`children_len` truncation math on line 1
is unaffected because the marker sits on line 2.

### 3. `.aitask-scripts/codebrowser/history_detail.py`

**`_render_task` Commits section (line 734)** — currently the Commits
section is mounted only when `commits` is truthy. For
`has_code_commits=False` tasks, surface an explicit empty-state row
instead of an absent section:

```python
if commits:
    self.mount(_SectionHeader(f"Commits ({len(commits)})"))
    for commit in commits:
        self.mount(CommitLinkField(commit, self._platform_info))
elif not task.has_code_commits:
    self.mount(_SectionHeader("Commits"))
    self.mount(MetadataField(
        "  [dim]No source-code commits — framework activity only "
        "(see aitask-data branch)[/dim]"
    ))
```

This keeps the "Affected Files" section unaffected (it's already gated
on `if commits:` further down — empty for no-code tasks, which is
correct). Task body and plan content still load via
`_get_body_content` exactly as before.

## Tests

Extend `tests/test_history_data.py`:

1. **`TestLoadTaskIndexNoCodeCommit`** — new test class:
   - Add an archived task `t100_verify_only.md` with no `(t100)` commit.
   - Add a commit `ait: Archive completed t100 task and plan files` on
     a separate branch (mimics `aitask-data`).
   - Assert: `t100` appears in `load_task_index`, with
     `has_code_commits is False` and `commit_hash` matching the archive
     commit's short hash.

2. **`TestLoadTaskIndexMtimeFallback`** — new test class:
   - Add `t200_legacy.md` with no commit signals.
   - Assert: appears in index, `has_code_commits is False`,
     `commit_hash == ""`, `commit_date` is a parseable ISO timestamp.

3. **Regression check** — confirm existing tests
   (`test_returns_sorted_by_date_desc`,
   `test_deduplicates_commits`, etc.) still pass: tasks with `(tNN)`
   commits must still anchor on those, with `has_code_commits=True`.

Run: `python3 -m pytest tests/test_history_data.py -v`

## Verification

End-to-end check against the real reproducer:

1. `ait codebrowser` → history list shows **t787** with the `[no-code]`
   marker (previously absent entirely).
2. Open t787 detail → Metadata, task body, and plan content render;
   Commits section shows the "No source-code commits — framework
   activity only" empty-state.
3. Open any normal task (e.g. t604) → unchanged: `[no-code]` marker
   absent, Commits section lists the `(t604)` commits with their
   hashes, Affected Files section populated.

Out of scope (per task): dropping the `(tNN)` requirement, rewriting
manual-verification's commit recipe, migrating existing archived
commits.

## Post-implementation

Follow the standard task-workflow Step 8 → Step 9 flow: commit code +
plan file separately, then archive and push.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Added
  `has_code_commits: bool = True` field to `CompletedTask`. Added
  `_build_archive_commit_map(project_root)` greping
  `^ait: Archive completed t<N>` on `--all` branches. Added
  `_mtime_anchor(archived_dir, tid, filename)` for loose-file mtime
  fallback. Rewrote `_merge_chunk` to walk the three-step anchor
  priority (code > archive > mtime). Wired both maps and `archived_dir`
  through `load_task_index_progressive`. Updated
  `HistoryTaskItem.render` to show a dim `[no-code]` marker (color
  `#FFB86C`, matching the codebrowser palette). Updated
  `_render_task` in `history_detail.py` to mount a "No source-code
  commits — framework activity only" empty-state row in the Commits
  section when `not task.has_code_commits`. Added two new test classes
  (`TestLoadTaskIndexNoCodeCommit`, `TestLoadTaskIndexMtimeFallback`)
  plus a regression assertion that code-anchored tasks still have
  `has_code_commits=True`.
- **Deviations from plan:** None. The minor concrete touch was
  importing `datetime, timezone` at module-level rather than inside
  `_mtime_anchor` — cleaner and the import is otherwise harmless.
- **Issues encountered:** `pytest` is not in the venv; ran the tests
  via `python3 -m unittest tests.test_history_data -v` instead.
  Reference for future runs of this test file.
- **Key decisions:**
  - The archive-commit grep matches `^ait: Archive completed t<N>`
    only (not a broader "any framework commit touching the archived
    file"). This is intentional: that recipe is the canonical archival
    commit written by `aitask_archive.sh`, present for every task
    archived under the current workflow. A broader scan would be
    O(commits × files) more expensive without surfacing additional
    tasks.
  - mtime fallback uses `datetime.fromtimestamp(..., tz=timezone.utc)`
    to produce an ISO-8601 string with the same lexicographic-order
    semantics as git's `%aI` — so the unified
    `tasks.sort(key=lambda t: t.commit_date, reverse=True)` continues
    to work without per-source merge logic.
  - Empty-state Commits row uses `MetadataField`, the existing
    non-focusable dim row widget — no new widget class needed.
- **Upstream defects identified:** None.
- **End-to-end verification:** `load_task_index` on the real repo
  surfaces 37 previously-hidden no-code tasks (including t787 anchored
  at archive commit `5f2b5bd7` on 2026-05-27). t604 unchanged
  (`has_code_commits=True`, anchored at the `(t604)` code commit).
