---
Task: t1365_fix_bytrail_discovery_misses_new_trail.md
Worktree: (none — current branch)
Branch: (none — current branch)
Base branch: main
Output branch: main
---

# t1365 — By-Trail discovery misses a trail created after the board started

## Context

A trail created while `ait board` is running does not appear in the By-Trail
trail selector (`z` then `s`). Observed with `art:trail-shadow-review-loop`
(owner t1159): the selector listed only the older
`art:trail-gates-framework-landing`.

The on-disk state is correct — this is a **stale in-memory snapshot**. Trail
discovery reads *active* task frontmatter out of `TaskManager.task_datas` /
`child_task_datas`, populated once at board startup by `load_tasks()` and never
re-read by the discovery path; it reads *archived* frontmatter fresh from disk.
So a trail whose owning task's `artifacts:` frontmatter was written after the
board launched is invisible until a restart, and no By-Trail key recovers it
(`s` rescans discovery but not the task files; `r` reloads the task files but
re-projects the cached trail doc without clearing `self._trail_infos`).

Intended outcome: with the board running, a trail created for a task shows up in
the By-Trail selector — and renders with real member cards, not ghosts — without
a restart.

## Approach

Make discovery read **both** halves of its input from disk, so it can never
serve a startup snapshot; report (rather than swallow) files the scan could not
read, so a concurrent non-atomic frontmatter rewrite degrades into a retryable
warning instead of a crash or a false "no trails"; and close the two adjacent
staleness paths the same root cause leaves open — the selector cache on view
re-entry, and the lane projection that still reads the manager.

All work is in `.aitask-scripts/board/aitask_board.py` plus two test modules and
one docs page.

### 1. Discovery reads active task frontmatter from disk

- **New module-level helper `_iter_active_task_frontmatter()`** next to
  `_iter_trail_frontmatter_records` (~line 718). Yields `(filename, metadata)`
  for every live task file using the two glob patterns
  `TaskManager.load_tasks()` / `load_child_tasks()` already use
  (`TASKS_DIR/"*.md"`, `TASKS_DIR/"t*"/"t*_*.md"`), sorted for deterministic
  order, parsed with the existing `parse_frontmatter`.

  **Per-file `try/except Exception: continue` around read+parse, plus an
  `isinstance(meta, dict)` guard — and the skipped filenames are *reported*,
  not swallowed.** The guard is not defensive padding, it is load-bearing.
  `parse_frontmatter` *raises* on malformed YAML (verified: `ParserError` on
  `foo: [unclosed`); both existing sources are immune for different reasons
  (`Task.load` has a bare `except` at `aitask_board.py:244`;
  `iter_archived_frontmatter` wraps `parse_fn` at `archive_iter.py:145-150`),
  and a hand-rolled loop inherits neither. The consumer is
  `@work(thread=True)`, whose Textual default is `exit_on_error=True`, so an
  unhandled parse error **exits the board**. It is reachable in exactly this
  bug's scenario: `frontmatter_patch.py:214,238` rewrites task files with a
  plain `open(path, "w")` (no temp+rename, verified), so patching `artifacts:`
  into a task while the user presses `s` is a torn read.

  The helper takes an `unreadable` list and appends the name of every file it
  skips. Silently dropping the file would trade a crash for a worse failure
  mode — a *persistent* read failure (bad permissions, a helper bug) would
  present forever as "that trail does not exist", with nothing to diagnose.

  **Scope of the diagnostic: active task files only.** The archived half keeps
  `iter_archived_frontmatter`'s existing silent skip, so a malformed or
  unreadable *archived* owner still disappears without a warning. That is a
  deliberate boundary, not an oversight: the torn-read race being defended
  against is a live task file being rewritten by `ait artifact new` while the
  scan runs, and archived files are inert. Widening it would mean threading an
  out-param through three swallow layers in a shared lib
  (`archive_iter.py:122-131` read errors, `:145-151` parse errors, plus tar
  extraction) whose contract is consumed by `codebrowser/history_data.py:226`
  and pinned by `tests/test_archive_iter_consolidated.py:316`. The warning text
  therefore says "active task file(s)" and never implies archive coverage, and
  the limitation is recorded under "Known limitations" below.

- **`_iter_trail_frontmatter_records()`** (line 718) — drop the `manager`
  parameter; source active records from the new helper. The active and archived
  branches currently duplicate a near-identical `TrailInfo` emit block; collapse
  them into one inner helper taking `(filename, meta, archived)`. `owner_id`
  comes from `parse_task_filename(filename)` for both halves — equivalent to the
  current `task_own_id(task)`, which *is*
  `parse_task_filename(task.filename)[0].lstrip("t")`
  (`.aitask-scripts/lib/topic_semantics.py:46`).

- **`discover_trails()`** (line 814) — drop the `manager` parameter and return
  `(infos, unreadable)` instead of a bare list, so the caller can tell "there
  are no trails" apart from "part of the scan could not be read".
  **`_trail_discovery_worker`** (line 7571) — call `discover_trails()` and pass
  both halves to the callback. Nothing else in that worker touches the manager.

Docstrings record *why* discovery reads from disk (t1365) so the invariant is
not quietly undone.

### 1b. An unreadable file must not masquerade as "no trails"

A torn read is a retryable snapshot race, not an answer. In
`_on_trail_discovery` (~7576), after the supersession guard:

- If `unreadable` is non-empty, `self.notify(...)` at `severity="warning"`,
  naming the first few skipped files and telling the user to press `s` to
  retry. This is the observable diagnostic — a persistent failure keeps warning
  on every scan instead of silently shrinking the trail list.
- If `infos` is empty **and** `unreadable` is non-empty, **explicitly assign
  `self._trail_infos = None`** and return. Merely returning without assigning
  would be a bug: `_open_trail_select` does not clear the cache before a
  `rescan=True`, so an earlier successful scan's handles would survive the
  errored one — a retryable read failure would leave stale handles live for
  `_activate_trail`'s doc lookup (:7611). Assigning `None` is what makes the
  result non-authoritative in both directions: `_open_trail_select_from_cache`
  never fires its "No implementation trails found — create one with T…"
  notification, and `_render_bytrail` (:7505) falls back to the neutral "No
  trail selected — press s to choose one" hint instead of the definitive one,
  because that hint is gated on `_trail_infos is not None`. The next open
  re-scans.
  Re-render only when there is no active trail (`if not self.active_trail_handle:
  self._rerender_trail()`), so the hint transition from the definitive message
  to the neutral one is actually drawn. With no active trail the view holds only
  that hint, so there is no card focus or column scroll to lose; when a trail
  *is* active the lanes are left untouched for the same reason the cancel path
  is (see change 3).
- Otherwise cache `infos` and continue as normal. A partial result (some
  handles found, some files skipped) is still shown — the warning says it may
  be incomplete.

### 2. Clear the discovery cache when the By-Trail view is (re-)entered

`_open_trail_select` funnels the *worker*, not the *cache*. `_set_base_filter`
(~6745-6749) auto-opens with `rescan=False`; if the user opened the selector
earlier and pressed Esc, `_trail_infos` is a non-empty stale list and
`active_trail_handle` is still `None`, so leaving and re-entering By-Trail
(`z`, `z`) rebuilds the selector **from the stale cache** — the reported symptom
reached without ever pressing `s`. Set `self._trail_infos = None` in the
`if name == "bytrail":` arm of `_set_base_filter`. One line; it costs a scan
only when the selector actually opens.

### 3. Refresh the manager once discovery lands, so members are not ghosts

Discovery no longer touches the manager, but the lane projection
`_build_active_trail_lanes` (~7542) still builds `tasks_by_id` from
`manager.task_datas` / `child_task_datas`, and neither `_activate_trail` (~7605)
nor `refresh_board`'s bytrail branch reloads tasks. A freshly authored trail
normally references tasks created after board start, so without this the "fixed"
flow ends: new trail listed → activated → **members render as missing ghosts**
until the user presses `r`, and `d` (which reads disk) contradicts the render.

Call `self.manager.load_tasks()` at the top of **`_activate_trail`** (~7605),
immediately before its existing `self.refresh_board()`. This is
convention-compliant (the module's rule is that manager mutation happens on the
UI thread) and measured at 0.169s, inside a user-initiated action that already
does a full board refresh.

**Not** in `_on_trail_discovery`, which was the first shape considered: putting
it there replaces every `Task` object *while the selector modal is opening*, and
the Esc-cancel arm of `on_select` is the one branch that does not re-render
afterwards. Patching that with a cancel-path `_rerender_trail(...)` does not
work either — `_focused_card()` is `query("TaskCard:focus").first()`
(`aitask_board.py:6877`), and with the modal on screen no board card is focused,
so the re-render would receive an empty refocus target and a plain
scan-then-cancel would silently drop keyboard focus (and reset column scroll).
`_activate_trail` has exactly one caller (`on_select`'s non-`None` arm), so
reloading there covers every activation — including one made from the cached
path — while the cancel path touches nothing at all and keeps its focus.

This is scope the acceptance criteria do not name explicitly — AC bullet 1 only
requires the trail to be *listed*. It is included because it is the same stale
`TaskManager` snapshot, and shipping a fix whose newly-listed trail renders as
all-ghosts would be a hollow fix.

### 4. Tests

- `tests/test_board_fixture_harness.py:184-185` — `discover_trails(manager)` →
  `discover_trails() == ([], [])`; drop the now-unused local `manager`. The
  assertion changes meaning from "the manager holds no trail frontmatter" to
  "the tree contains none on disk, and none were unreadable" — still true, and
  stronger.
- `tests/test_board_bytrail_view.py:518` — stub `lambda manager: []` →
  `lambda: ([], [])`.
- **New class `TrailDiscoveryFreshnessTests`** in
  `tests/test_board_bytrail_view.py` (the file covers projection/lane building
  today, not discovery). It must go through `tests/lib/board_fixture.py` —
  `bf.enter_fixture_tree(...)` / `FixtureBoardTestBase` — never
  `patch.object(ab, "TASKS_DIR", tmp)`: `TaskManager.__init__` calls
  `load_metadata()` against the **import-time** `METADATA_FILE`, so a bare
  `TASKS_DIR` patch would read and *write* the live repo's
  `aitasks/metadata/board_config.json`. Cases:

  1. **Stale-metadata path (the AC case).** Build `manager = ab.TaskManager()`
     *before* mutating anything — that real object is the pre-fix source. Write
     `artifacts: [{handle: art:trail-x, kind: implementation_trail, …}]` into a
     fixture task with `task_yaml.serialize_frontmatter`. With
     `patch.object(ab, "load_trail_blob", lambda h: (doc, "", []))`, assert
     `discover_trails()` lists `art:trail-x` **and** that its `load_error` is
     `""` — an absent `ARTIFACT_SCRIPT` under the fixture cwd would otherwise
     degrade to a `load_error` record that still carries the handle and fake the
     pass.
  2. **Negative control, real objects only:** at that same moment,
     `list(manager.task_datas.values()) + list(manager.child_task_datas.values())`
     — the exact expression the deleted code consumed — carries no `artifacts`
     mentioning the handle. No replica of the old function.
  3. **Recovery control** (kills the vacuous pass where the frontmatter was
     written wrong and *nobody* could have seen it): `manager.load_tasks()`,
     then the same expression does contain it.
  4. **Malformed YAML skips only its own file.** Write a garbage-frontmatter
     file (`foo: [unclosed`) alongside two valid trail owners; assert discovery
     returns *both* good handles, that `unreadable` names exactly the bad file,
     and that the call did not raise. (The fixture's `t_unparseable.md`,
     `tests/lib/board_fixture.py:264`, is *filename*-unparseable with valid
     YAML — it does not cover this.) A companion case makes the same assertion
     for an unreadable file (`chmod 000` / patched `read_text` raising `OSError`)
     so a permission failure is covered as well as a parse failure.
  4b. **An empty-but-errored scan is not authoritative.** With the *only*
     trail-owning file made unparseable, drive `_on_trail_discovery` and assert:
     `app._trail_infos is None` (so the next open re-scans), a warning
     notification naming the file was raised, and `_render_bytrail` shows the
     neutral "No trail selected" hint rather than "No implementation trails
     found". Control: with no unreadable files and genuinely no trails, the
     authoritative message *is* used and `_trail_infos == []`.
  4c. **Stale handles are dropped, not retained** — the case that distinguishes
     "assign `None`" from "just return". **Pre-populate** `app._trail_infos`
     with a non-empty list from a prior successful scan, then deliver an
     empty-plus-unreadable result and assert `app._trail_infos is None`. This
     test fails against the return-without-assigning variant, which is the whole
     point of it.
  5. A **child** task's handle is discovered (covers the `t*/t*_*.md` glob), and
     an **archived** owner still yields `owner_archived=True` (regression guard
     on the merged emit block).
  6. **Pilot test for the running-board claim** (AC bullet 1 is a running-board
     claim): boot the app, `z`, write the `artifacts:` frontmatter on disk,
     press `s`, wait for `_trail_infos`, assert the handle is listed and a
     `TrailSelectScreen` is on screen. Because the reload now lives in
     `_activate_trail`, the "manager is still stale" control *is* available here
     too: at the moment the selector lists the handle,
     `app.manager.task_datas[<fn>].metadata.get("artifacts")` is still `None`,
     proving the listing came from the disk read.
  7. **Selector-cancel regression (the hazard change 3 avoids):** focus a card,
     press `s`, wait for the selector, press Esc, and assert the same card is
     still focused and the board container was not re-mounted — i.e. cancelling
     a scan disturbs nothing. This pins the reason `load_tasks()` lives in
     `_activate_trail` rather than in the discovery callback.
  8. **Activation refreshes the projection (change 3):** activate a trail whose
     member task file was created after the manager was built, and assert the
     member renders as a real card rather than a ghost.
  9. **View re-entry (change 2):** with a stale non-empty `_trail_infos`, leave
     and re-enter By-Trail and assert the cache was invalidated / the new handle
     is listed.

### 5. Docs — `website/content/docs/tuis/board/reference.md`

- Keybinding table (line 34): `s` — note it re-scans, so a trail created since
  the board started is listed.
- "Keeping the view current" (~lines 195-212): add an `s` row to the
  refresh-cost table (`Re-scans task files for trails, including any created
  since the board started` · `A second or two — one artifact read per trail`)
  and a sentence in the paragraph below: reach for `s` when a *new trail* was
  created since the board started, no restart needed. The section presents four
  refresh keys today and never says which one picks up a newly created trail —
  the shipped workaround was "restart the board, or press `r` then `s`".

`r`'s documented meaning ("re-reads task files from disk and redraws the trail")
is unchanged, so the AC's conditional doc clause does not otherwise trigger.

## Side benefit

Reading active frontmatter from disk also fixes a latent mis-attribution: a task
archived *after* board start stays in `task_datas`, so discovery emits both an
active and an archived record for the same handle; `dedupe_trail_records` prefers
the active one (rank 0) and the §9.2 "owner tN archived" banner is silently
wrong. The disk read makes it correct.

## Known limitations

- **The unreadable-file diagnostic covers active task files only.** A malformed
  or unreadable *archived* task file is still skipped silently by
  `iter_archived_frontmatter` (`archive_iter.py:145-151`) and
  `iter_all_archived_markdown` (`:122-131`), so a trail owned solely by such a
  file disappears with no warning — and, because `unreadable` stays empty, the
  scan would still report the authoritative "No implementation trails found".
  Rationale and the cost of widening it are in change 1 above.

## Deliberately not done

- **Arm an artifact watch on the `T` create path** (the task's option 3) — a
  quality-of-life feature, not part of the acceptance criteria. `T` does not know
  the handle the skill will mint, so the watch would have to key on the owning
  task's frontmatter rather than an artifact-version listing. The residual gap it
  would close: the user must still *press* `s` (or re-enter the view); the board
  does not notice a new trail on its own.
- **Clearing `_trail_infos` from `r`** — redundant once change 2 lands and `s`
  always re-scans from disk.

## Verification

1. The two touched test modules (each sets up its own `sys.path`; run from the
   repo root):
   ```bash
   python3 tests/test_board_bytrail_view.py
   python3 tests/test_board_fixture_harness.py
   ```
2. **Prove the new tests can fail** — temporarily restore the manager-sourced
   active branch in `_iter_trail_frontmatter_records`, re-run
   `TrailDiscoveryFreshnessTests`, confirm the stale-metadata case *and* the
   Pilot case fail, then undo that one edit in place (no `git checkout` — the
   working tree carries a concurrent session's changes).
3. Board regression sweep:
   ```bash
   bash tests/run_all_python_tests.sh --test-dir tests
   ```
   Read only the final `PYTHON SUITE:` line; use `${PIPESTATUS[0]}` if piped.
4. Live acceptance — the reported symptom: start `ait board`, press `z` then `s`
   and note the trail list; in another shell add an `artifacts:` entry with
   `kind: implementation_trail` to a task file; back in the running board press
   `s` and confirm the new handle is listed, then activate it and confirm its
   members render as real cards rather than ghosts.
5. **Staging discipline at commit time:** `.aitask-scripts/board/aitask_board.py`
   and `website/content/docs/tuis/board/reference.md` both carry uncommitted
   hunks from a concurrent in-flight session (t1243_3, board gap-indexing).
   Verify staged *content*, not just paths, before committing.

## Risk

### Code-health risk: medium

- `.aitask-scripts/board/aitask_board.py` currently holds **uncommitted changes
  from a concurrent in-flight session** (t1243_3: hunks in `TaskManager`
  ~1338-1520 and ~8211+), and `reference.md` holds one too. This task's hunks
  are disjoint, but the Step-8 commit must stage only this task's hunks rather
  than whole files · severity: medium · → mitigation: none (declined at planning)
- The change touches four behaviours in one module (discovery source and return
  shape, torn-read reporting, selector cache lifetime, manager reload on trail
  activation) rather than one. Each is small and covered by a test, but the
  combination is wider than the task's "reload task files" framing ·
  severity: medium · → mitigation: none (declined at planning)
- Discovery's active source changes from in-memory `Task` objects to a disk
  scan, so it no longer honours `_is_phantom_stub` filtering and record order
  becomes sorted-by-path. Both are inert (a board-keys-only stub carries no
  `artifacts:`; `_trail_owner_rank` never consults iteration order, and the
  selector has no meaningful order today), but they are behaviour changes ·
  severity: low · → mitigation: none (declined at planning)

### Goal-achievement risk: low

- The root cause is confirmed in the task and the fix removes the stale source
  outright, so the acceptance criterion is directly testable at both the unit
  and running-board level. The residual gap is that the user must still press
  `s` or re-enter the view — the board will not notice a new trail on its own ·
  severity: low · → mitigation: none (declined at planning)
