---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, tui, artifacts, trails]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
implemented_with: claudecode/opus5
created_at: 2026-08-02 10:15
updated_at: 2026-08-02 20:02
---

## Symptom

A newly created implementation trail does not appear in `ait board`'s By-Trail
trail selector (`z` then `s`) while the board is already running. Observed with
`art:trail-shadow-review-loop` (owner t1159): the trail selector listed only the
older `art:trail-gates-framework-landing`.

## Root cause (confirmed)

The on-disk state is entirely correct — this is a **stale in-memory cache** bug
in the running board, not a data or schema problem.

Verified during exploration:

- `.aitask-data/artifacts/manifests/trail-shadow-review-loop.json` exists with a
  resolvable `current` blob.
- `python3 .aitask-scripts/lib/trail_schema.py validate <blob>` → `VALID:trail-shadow-review-loop`.
- `aitasks/t1159_shadow_review_loop_automation.md` frontmatter carries
  `artifacts: [{handle: art:trail-shadow-review-loop, kind: implementation_trail, name: ...}]`,
  and `task_yaml.parse_frontmatter` parses it correctly.
- Running the board's own discovery headlessly against a **fresh** `TaskManager`
  returns BOTH trails:
  `discover_trails` → `_iter_trail_frontmatter_records` yields
  `art:trail-gates-framework-landing` (owner 635) and
  `art:trail-shadow-review-loop` (owner 1159).

The failing ingredient is the *running process*: the board PID observed at
diagnosis started at 06:18, while t1159's `artifacts:` frontmatter was written at
~07:59 by `/aitask-trail`.

`.aitask-scripts/board/aitask_board.py`:

- `_trail_discovery_worker` (:7412-7416) calls `discover_trails(self.manager)`.
- `discover_trails` (:808) / `_iter_trail_frontmatter_records` (:712-717) read
  `manager.task_datas` + `manager.child_task_datas`, which are populated by
  `load_tasks()` / `load_child_tasks()` **at board startup** and never re-read by
  the discovery path.

So discovery re-runs the artifact subprocesses against stale task metadata, and a
trail whose owning task's frontmatter changed after startup is invisible.

## Why no key recovers it

No single By-Trail key both re-reads task files and rescans discovery:

- `action_trail_select` (`s`, :6134-6138) → `_open_trail_select(rescan=True)`:
  rescans discovery (blob loads) but never calls `manager.load_tasks()`.
- `action_trail_refresh_local` (`r`, :6090-6099): calls `manager.load_tasks()`
  but only re-projects the already-cached trail doc — it does not clear
  `self._trail_infos`, so the discovery cache keeps the stale record set.
- `self._trail_infos` is cleared in exactly one place, `_on_trail_reload`
  (:7523), which only runs for the *active* trail's blob reload (`d`).

Additionally, `action_trail_task` (`T`, :7609-7634) launches `/aitask-trail` for
creation with **no `watch_handle`**, unlike `action_trail_refresh_agent` (`R`,
:6129-6132) which passes one and installs the artifact-version watch. So when a
newly created trail lands, nothing in the board notices.

Current workaround: restart the board, or press `r` then `s` (in that order).

## Suggested fix (to be settled at planning time)

Candidate directions, not a locked decision:

1. **Reload task files inside the discovery worker.** Have `_trail_discovery_worker`
   (or `_open_trail_select(rescan=True)`) call `self.manager.load_tasks()` /
   `load_child_tasks()` before `discover_trails`. Note `load_tasks()` is pure file
   I/O and already runs on the UI thread in `action_trail_refresh_local`, but the
   discovery worker is a thread worker — check the threading contract before
   moving the call there (the manager is also read by the UI thread).
2. **Make `r` invalidate the discovery cache** (`self._trail_infos = None`) so the
   documented "re-read task files from disk" key actually restores a
   next-`s` rescan to a correct result.
3. **Arm a watch on trail creation.** Give `T` an equivalent of the `R` path's
   post-launch watch so a newly created trail is picked up automatically. This is
   harder than the refresh case: `T` does not know the handle the skill will mint,
   so the watch would have to key on the owning task's frontmatter rather than an
   artifact version listing.

Options 1 and 2 are cheap and independent; 3 is the quality-of-life fix.

## Acceptance criteria

- With the board running, creating a trail for a task and then opening the
  By-Trail selector (via whatever refresh affordance the fix settles on, without
  restarting the board) lists the new trail.
- A regression test covers the stale-metadata path. Note
  `tests/test_board_bytrail_view.py` currently covers the projection/lane
  building but **not** `_iter_trail_frontmatter_records` / `discover_trails`, so
  this is new coverage: build a `TaskManager` over a temp task dir, run
  discovery, mutate a task file's `artifacts:` frontmatter on disk, and assert
  the chosen refresh path surfaces the new handle while the pre-fix path does not
  (negative control).
- If the docs' description of `r` ("Re-reads task files from disk and redraws the
  trail", `website/content/docs/tuis/board/reference.md`) changes meaning, update
  that table and the By-Trail section in the same commit.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-02T17:02:18Z status=pass attempt=1 type=human
