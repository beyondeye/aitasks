---
Task: t1978_fix_archive_iter_truncated_gz_eoferror.md
Base branch: main
Output branch: main
---

# t1978 — truncated `.tar.gz` must not crash best-effort archive readers

## Context

`lib/archive_iter.py:_iter_single_archive` (gz branch) lets the `EOFError` that
gzip raises on a truncated stream escape whenever the caller did not pass
`errors=` (`archive_iter.py:350-355`, `if errors is None: raise`). gzip's
`EOFError` is neither `tarfile.TarError` nor `OSError`, and tarfile does not
convert it. So a single truncated bundle under `aitasks/archived/_bN/` crashes
every best-effort caller (board, board_task_manager, stats_data, codebrowser
history_data, dep_resolution, roadmap_origin_facts, trail_discovery,
trail_gather). That contradicts the module docstring, which already promises that
a "corrupt or truncated bundle" is skipped on the default path. t1957_3 kept the
raise only to leave the default path untouched in its own change.

Reproduced on Python 3.14.7: both `iter_all_archived_markdown(arch)` and
`find_archived_markdown_by_id("5", arch)` raise
`EOFError: Compressed file ended before the end-of-stream marker was reached`.
No caller catches `EOFError` (grep over `.aitask-scripts/`). The fix only changes
a crash into a skip.

Second bullet (data in other repos): three stored trails are still at
`schema_version 1.0.0` and are rejected by the 1.1.0 schema. I re-checked this
from this host with `ait artifact get`:
- thinking_app: `art:trail-build-test-speed`, `art:trail-localization-programme`
- thinking_backend: `art:trail-new-prod-and-dev-servers`

Relaxing `SCHEMA_NORMALIZATION_LOCK` is ruled out by its own design comment
(`trail_gather.py:188` — "EXACTLY ONE ENTRY, always … a leftover key would
quietly re-admit documents this design means to reject"). The user chose to
hand the repair to the sibling repos as follow-up tasks. Plan review then
established that ordinary refresh cannot repair these trails, so the tasks
call for regeneration (Step 4).

Current-branch mode (profile `fast`); no worktree.

## Steps

### 1. Red test first — `tests/test_archive_iter_consolidated.py`

In `TestOptInFailureReporting`:
- Add a helper that builds the truncated fixture, so the opt-in and default
  tests share it instead of repeating the inline build from
  `test_truncated_tar_gz_is_reported`:
  ```python
  def _truncated_tar_gz(self, directory: Path, name: str) -> Path:
      path = directory / name
      _make_tar_gz(path, _big_bundle(count=40, size=4000))
      path.write_bytes(path.read_bytes()[: path.stat().st_size // 2])
      return path
  ```
  Then switch `test_truncated_tar_gz_is_reported` to use it. Its assertions stay
  the same.
- New test next to `test_default_path_stays_best_effort`:
  ```python
  def test_truncated_tar_gz_is_skipped_on_the_default_path(self):
      """gzip raises EOFError on a truncated stream and tarfile does not
      convert it; without a list the bundle is skipped like any other
      unreadable one, and the scan goes on to the next bundle."""
      self._truncated_tar_gz(self.bundle_dir, "old0.tar.gz")
      _make_tar_gz(self.archived / "_b1" / "old10.tar.gz",
                   {"t1000_ok.md": "ok"})
      self.assertEqual([n for n, _ in iter_all_archived_markdown(self.archived)],
                       ["t1000_ok.md"])
      self.assertIsNone(find_archived_markdown_by_id("5", self.archived))
  ```
  The healthy `_b1` bundle sorts after `_b0`, so the test proves the scan
  continues past the bad bundle, not just that it returns nothing.
- Run `python3 -m pytest tests/test_archive_iter_consolidated.py -q` **before**
  the fix. The new test must fail with `EOFError` (red proof). The other tests
  must still pass.

### 2. Fix — `.aitask-scripts/lib/archive_iter.py`

- In `_iter_single_archive`, fold `EOFError` into the existing read-failure
  clause and delete the separate `except EOFError` branch (lines 350-355):
  ```python
  except (tarfile.TarError, OSError, subprocess.SubprocessError,
          EOFError) as exc:
      # EOFError: a truncated .tar.gz — gzip raises it and tarfile does not
      # convert it to a TarError.
      _note(errors, archive_path, exc)
      return
  ```
  `_note` is already a no-op when `errors is None`, so the default path skips
  the bundle and the opt-in path still reports it, as before.
- Module docstring: the line "Leaving ``errors`` unset keeps the best-effort
  path exactly as it was." is version-history wording, and after this fix it is
  no longer literally true. Reword it to state the current contract:
  "Leaving ``errors`` unset keeps every reader best-effort."

### 3. Verify

- `python3 -m pytest tests/test_archive_iter_consolidated.py -q` → all green,
  including the new test and the unchanged `test_truncated_tar_gz_is_reported`
  (the opt-in path still reports exactly 1 entry).
- Re-run the scratch repro from planning (truncated bundle, no `errors=`). Both
  calls must return without raising.
- Consumer tests: `tests/test_local_dep_parity.py` plus the trail_links /
  trail_discovery modules (`ls tests | grep -E 'trail_(links|discovery)'`).
- Full Python suite once, in the background:
  `bash tests/run_all_python_tests.sh`. Read only the final `PYTHON SUITE:` line
  and check `${PIPESTATUS[0]}` if piped.

### 4. Cross-repo regeneration tasks (user-approved; revised after review)

**Ordinary `/aitask-trail --refresh` cannot repair these trails.** I verified
this during planning (2026-10-14, read-only):
- `aitask_trail_gather.sh drift --trail <handle>` returns
  `INVALID:$.schema_version|const|expected '1.1.0', got '1.0.0'` then
  `ERROR:invalid_trail:1` for `art:trail-build-test-speed` and
  `art:trail-new-prod-and-dev-servers`. `art:trail-localization-programme`
  returns `ERROR:invalid_trail:44`. On top of the version, it carries
  hand-written freshness keys the schema rejects (`drift_digest`,
  `drift_reason_counts`, `refresh_blocked_by`, string `drift_reasons`).
- The refresh flow runs drift first (SKILL.md.j2 Step 3.2) and stops on any
  `ERROR:`, `invalid_trail` included.
- The create flow refuses an existing handle ("never overwrite an existing trail
  from the create flow").
- The framework ships no trail-schema migration tool.

So each follow-up must name a supported regeneration path and its
prerequisites. The strict lock stays; t1978 implements no migration.

Fresh-snapshot probes of each trail's recorded scope, run now (the digests are
moment-relative):
- `snapshot --scope multi_topic --owner 221 42 221` (thinking_app) → OK.
- `snapshot --scope task --owner 45 45` (thinking_backend) → OK.
- `snapshot --scope topic --owner 110 110` (thinking_app) →
  `ERROR:unknown_task:thinking_app#110`. Topic root t110 is archived, which is
  exactly thinking_app's t267.

Create the tasks with `./.aitask-scripts/aitask_create.sh --batch --project
<name> --type chore --priority low --effort low --desc-file - --commit` (quoted
heredoc). There are **three** tasks, not two. I split thinking_app so that its
blocked trail carries a machine-visible `depends` instead of blocking the trail
that can be fixed now:

1. **thinking_app** — regenerate `art:trail-build-test-speed` (`--labels
   tooling`). Owner thinking_app#221; scope multi_topic [42, 221]; referenced
   from t221's frontmatter. Snapshot works today.
2. **thinking_app** — regenerate `art:trail-localization-programme`
   (`--labels tooling --deps 267`; the flag is `--deps` — the sibling create
   scripts reject `--depends` as an unknown option). After creation, verify the
   new task file carries `depends: [267]`. Owner thinking_app#110 (archived); scope
   topic 110. Blocked by t267 under either path, because neither create nor
   refresh can snapshot an archived root.
3. **thinking_backend** — regenerate `art:trail-new-prod-and-dev-servers` (no
   label fits its labels.txt). Owner t45 (live). The recorded scope is `ad_hoc`:
   t45 widened to t49, t50, t47, t46, t41 and thinking_app#200, and t44, t49,
   t50 and thinking_app#200 are now archived. The gatherer has no `ad_hoc`
   scope, so the create flow starts from `--scope task --owner 45 45` and
   re-approves the expansion (Step 2b).

Every description carries the same core:
- **Origin / why:** `aitasks#1978`. The trail is at schema 1.0.0 and the
  framework schema is 1.1.0 behind a deliberately single-version lock
  (`trail_gather.py` `SCHEMA_NORMALIZATION_LOCK`, which will not be relaxed). It
  renders as an error card and keeps every cross-repo scan from aitasks partial.
- **Evidence:** the drift output above, and why refresh stops on it.
- **Supported path — choose one and record which:**
  - **(A) Regenerate under a new handle**, available today. Run the
    `/aitask-trail` create flow over the recorded scope with a fresh snapshot
    and a new slug. Then retire the old handle (`ait artifact rm <owner> <old
    handle>`) and repoint every reference to it (task frontmatter / bodies,
    listed per task).
  - **(B) Keep the handle.** This needs a framework-side regeneration or
    migration path for an invalid trail, which aitasks does not ship. Request it
    in aitasks first (`ait create --batch --project aitasks`) and add that as a
    dependency.
  - Never bump `schema_version` by hand-editing the stored document. Its
    `generation.input_digest` would then not come from a fresh snapshot.
- **Acceptance — scoped to this task's own trail only:**
  - the regenerated version passes both Step 2e.3 checks —
    `aitask_trail_depth.sh validate <tmpfile> --expect-depth lite|deep` →
    `VALID:<trail_id>`, and `aitask_trail_gather.sh drift --trail <tmpfile>` →
    `CURRENT`;
  - the fresh `snapshot` `DIGEST:` line for this trail's scope is recorded as
    evidence;
  - `drift --trail <final handle>` reports `CURRENT`;
  - on path (A), this trail's old handle is retired and its references are
    repointed.
  No other trail is a condition of done.
- **Aggregate report (informational, not acceptance):** list every stored trail
  in the repo with its `schema_version` (loop over `ait artifact ls` + `get`).
  Attribute any remaining 1.0.0 trail to the task that owns its repair. For
  thinking_app that is the sibling task created here (localization, blocked on
  t267). For thinking_backend, any other 1.0.0 trail found is reported, not
  fixed.

**Creation order:** task 2 (localization) first, then task 1, whose aggregate
report names task 2's id as the owner of the localization trail. Task 2 needs
no back-reference, because it scopes only its own trail. No post-creation edit
is needed. Verify each created file's frontmatter (`depends`, `labels`,
`issue_type`). Record the ids in the plan's Final Implementation Notes and in
the Step 10 `follow_ups`.

### 5. Step 9 (Post-Implementation)

Review → commit `bug: Skip truncated .tar.gz bundles on the best-effort archive
path (t1978)` (code files by name), commit the plan with `aitask_task_commit.sh`,
then the gates run and archival per the task-workflow Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
